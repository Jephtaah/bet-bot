"""
bet-bot CLI Entry Point

This module provides the command-line interface for the bet-bot tool using Typer.
It defines the main application structure and commands for analyzing football
betting opportunities with positive expected value.

The analyze command orchestrates the complete pipeline:
1. Fetch fixture data from multiple sources
2. Consolidate and validate data
3. Analyze with OpenAI
4. Detect profitable edges
5. Calculate stakes
6. Display results

Usage:
    python -m bet_bot.cli --help
    python -m bet_bot.cli analyze --bankroll 1000
    python -m bet_bot.cli analyze --bankroll 1000 --threshold 5.0 --league "Premier League"
"""

import asyncio
import logging
import time
from typing import Any

import typer

from bet_bot.analysis.ai.client import analyze_all_fixtures
from bet_bot.analysis.edge.pipeline import detect_edges
from bet_bot.config import config, validate_config
from bet_bot.data.consolidation.consolidator import consolidate_fixtures
from bet_bot.data.fetchers import fetch_all_data
from bet_bot.display.error_handler import display_error
from bet_bot.display.formatter import format_picks_for_display
from bet_bot.display.renderer import render_analysis_results
from bet_bot.exceptions import BetBotError
from bet_bot.models.analysis import Pick
from bet_bot.models.fixtures import Fixture
from bet_bot.utils import get_logger

# Version constant
__version__ = "0.1.0"

# Get logger for CLI module
logger = get_logger(__name__)

# Initialize Typer app with metadata
app = typer.Typer(
    name="bet-bot",
    help="Positive Expected Value Detection Tool for Football Betting",
    add_completion=False  # Disable shell completion for simplicity
)


def version_callback(value: bool) -> None:
    """
    Callback for --version flag.

    Prints the current version and exits immediately.
    """
    if value:
        typer.echo(f"bet-bot version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit"
    )
) -> None:
    """
    bet-bot: Positive Expected Value Detection Tool for Football Betting

    Use 'bet-bot analyze' to find betting opportunities with positive expected value.
    """
    # Validate configuration at startup before any command runs
    try:
        validate_config()
    except ValueError as e:
        typer.echo(f"Configuration Error: {e}", err=True)
        typer.echo("\nPlease ensure you have:", err=True)
        typer.echo("1. Created a .env file in the project root", err=True)
        typer.echo("2. Added your API keys (see .env.template for format)", err=True)
        typer.echo("3. Set OPENAI_API_KEY and API_FOOTBALL_KEY", err=True)
        raise typer.Exit(1)


async def _run_analysis_pipeline(
    bankroll: float,
    threshold: float = 5.0,
    league: str | None = None,
) -> tuple[list[Pick] | None, dict[str, Any]]:
    """
    Execute the complete analysis pipeline orchestrating all 6 phases.

    Args:
        bankroll: User's betting bankroll in USD
        threshold: EV threshold percentage (default 5.0, passed to detect_edges for filtering)
        league: Optional league filter (passed to detect_edges to filter by league)

    Returns:
        Tuple of (picks or None, data_quality tracking dict)

    Raises:
        Exception: Any uncaught exceptions bubble up to caller for top-level handling

    Note:
        Both threshold and league parameters are implemented and passed through
        to detect_edges for dynamic threshold filtering and league-based filtering.
    """
    data_quality: dict[str, dict[str, Any]] = {}
    timing: dict[str, float] = {}

    # Phase 1: Data Fetching
    logger.info("=" * 80)
    logger.info("Phase 1: FETCHING DATA")
    logger.info("=" * 80)
    start_phase = time.perf_counter()
    try:
        typer.echo("\n📥 Fetching fixture data...")
        logger.info("Starting Phase 1: Fetch all data sources")

        raw_data_dict = await fetch_all_data()
        if raw_data_dict is None:
            logger.error("fetch_all_data returned None - authentication or critical failure")
            data_quality["fetch"] = {
                "status": "failed",
                "latency_ms": int((time.perf_counter() - start_phase) * 1000),
                "error": "API authentication or critical failure",
            }
            return None, data_quality

        fixtures_raw = raw_data_dict.get("fixtures", [])

        elapsed = time.perf_counter() - start_phase
        timing["fetch"] = elapsed

        logger.info(f"Phase 1 Complete: Fetched {len(fixtures_raw)} raw fixtures in {elapsed:.2f}s")
        data_quality["fetch"] = {
            "status": "success",
            "latency_ms": int(elapsed * 1000),
            "record_count": len(fixtures_raw),
        }

        if not fixtures_raw:
            logger.warning("No fixtures fetched from any source")
            data_quality["fetch"]["status"] = "failed"
            data_quality["fetch"]["error"] = "No fixtures found"
            return None, data_quality

    except Exception as e:
        elapsed = time.perf_counter() - start_phase
        timing["fetch"] = elapsed
        logger.error(f"Phase 1 failed: {str(e)}", exc_info=True)
        data_quality["fetch"] = {
            "status": "failed",
            "latency_ms": int(elapsed * 1000),
            "error": str(e),
        }
        raise

    # Phase 2: Data Consolidation
    logger.info("=" * 80)
    logger.info("Phase 2: CONSOLIDATING DATA")
    logger.info("=" * 80)
    start_phase = time.perf_counter()
    try:
        typer.echo("🔄 Consolidating fixture data...")
        logger.info("Starting Phase 2: Consolidate, normalize, validate")

        consolidated_fixtures = await consolidate_fixtures(raw_data_dict)

        elapsed = time.perf_counter() - start_phase
        timing["consolidate"] = elapsed

        logger.info(
            f"Phase 2 Complete: Consolidated {len(consolidated_fixtures)} fixtures "
            f"in {elapsed:.2f}s"
        )
        data_quality["consolidate"] = {
            "status": "success",
            "latency_ms": int(elapsed * 1000),
            "record_count": len(consolidated_fixtures),
        }

        if not consolidated_fixtures:
            logger.warning("No fixtures survived consolidation")
            return None, data_quality

    except Exception as e:
        elapsed = time.perf_counter() - start_phase
        timing["consolidate"] = elapsed
        logger.error(f"Phase 2 failed: {str(e)}", exc_info=True)
        data_quality["consolidate"] = {
            "status": "failed",
            "latency_ms": int(elapsed * 1000),
            "error": str(e),
        }
        raise

    # Phase 3: AI Analysis
    logger.info("=" * 80)
    logger.info("Phase 3: AI ANALYSIS")
    logger.info("=" * 80)
    start_phase = time.perf_counter()
    try:
        typer.echo(f"🤖 Analyzing {len(consolidated_fixtures)} fixtures with OpenAI...")
        logger.info(f"Starting Phase 3: Analyze {len(consolidated_fixtures)} fixtures with OpenAI")

        analyzed_fixtures = await analyze_all_fixtures(consolidated_fixtures)

        elapsed = time.perf_counter() - start_phase
        timing["analyze"] = elapsed

        # Count successfully analyzed
        analyzed_count = sum(
            1 for f in analyzed_fixtures
            if hasattr(f, "ai_analysis") and f.ai_analysis is not None
        )

        logger.info(
            f"Phase 3 Complete: Analyzed {analyzed_count}/{len(analyzed_fixtures)} fixtures "
            f"in {elapsed:.2f}s"
        )
        data_quality["analyze"] = {
            "status": "success" if analyzed_count > 0 else "degraded",
            "latency_ms": int(elapsed * 1000),
            "record_count": analyzed_count,
        }

        if not analyzed_fixtures:
            logger.warning("No fixtures were analyzed")
            return None, data_quality

    except Exception as e:
        elapsed = time.perf_counter() - start_phase
        timing["analyze"] = elapsed
        logger.error(f"Phase 3 failed: {str(e)}", exc_info=True)
        data_quality["analyze"] = {
            "status": "failed",
            "latency_ms": int(elapsed * 1000),
            "error": str(e),
        }
        raise

    # Phase 4: Edge Detection
    logger.info("=" * 80)
    logger.info("Phase 4: EDGE DETECTION")
    logger.info("=" * 80)
    start_phase = time.perf_counter()
    try:
        typer.echo(f"⚡ Detecting edges (threshold: {threshold}%)...")
        logger.info(
            f"Starting Phase 4: Edge detection (threshold={threshold}%, league_filter={league or 'all'})"
        )

        picks = await detect_edges(
            fixtures=analyzed_fixtures,
            bankroll=bankroll,
            threshold=threshold,
            league_filter=league,
        )

        elapsed = time.perf_counter() - start_phase
        timing["edge_detect"] = elapsed

        # Handle both Pick list and NO_PICKS message string
        if isinstance(picks, str):
            logger.info(f"Phase 4 Complete: No picks above 5% threshold in {elapsed:.2f}s")
            data_quality["edge_detect"] = {
                "status": "success",
                "latency_ms": int(elapsed * 1000),
                "record_count": 0,
            }
            return None, data_quality

        logger.info(
            f"Phase 4 Complete: Found {len(picks)} picks above 5% threshold "
            f"in {elapsed:.2f}s"
        )
        data_quality["edge_detect"] = {
            "status": "success",
            "latency_ms": int(elapsed * 1000),
            "record_count": len(picks),
        }

    except Exception as e:
        elapsed = time.perf_counter() - start_phase
        timing["edge_detect"] = elapsed
        logger.error(f"Phase 4 failed: {str(e)}", exc_info=True)
        data_quality["edge_detect"] = {
            "status": "failed",
            "latency_ms": int(elapsed * 1000),
            "error": str(e),
        }
        raise

    # Phase 5: Stake Sizing (already done in detect_edges, but logging it as separate phase)
    logger.info("=" * 80)
    logger.info("Phase 5: STAKE SIZING")
    logger.info("=" * 80)
    logger.info(f"Stake sizing already calculated during edge detection")
    if picks:
        logger.info(
            f"Phase 5 Complete: Calculated stakes for {len(picks)} picks "
            f"based on bankroll ${bankroll:.2f}"
        )
    data_quality["stake_size"] = {
        "status": "success",
        "record_count": len(picks) if picks else 0,
    }

    # Phase 6: Display & Output
    logger.info("=" * 80)
    logger.info("Phase 6: DISPLAY & OUTPUT")
    logger.info("=" * 80)
    start_phase = time.perf_counter()

    if picks:
        logger.info(f"Rendering {len(picks)} picks for display")
    else:
        logger.info("No picks to render - displaying appropriate state")

    elapsed = time.perf_counter() - start_phase
    timing["render"] = elapsed

    logger.info(f"Phase 6 Complete: Rendered output in {elapsed:.2f}s")
    data_quality["render"] = {
        "status": "success",
        "latency_ms": int(elapsed * 1000),
    }

    # Log phase execution summary
    logger.info("=" * 80)
    logger.info("PIPELINE EXECUTION SUMMARY")
    logger.info("=" * 80)
    total_time = sum(timing.values())
    for phase_name, phase_time in timing.items():
        percentage = (phase_time / total_time * 100) if total_time > 0 else 0
        logger.info(f"  {phase_name:20s}: {phase_time:7.2f}s ({percentage:5.1f}%)")
    logger.info(f"  {'TOTAL':20s}: {total_time:7.2f}s (100.0%)")

    return picks, data_quality


@app.command()
def analyze(
    bankroll: float = typer.Option(
        ...,
        "--bankroll",
        "-b",
        help="Your betting bankroll in USD (required, must be positive)",
        min=0.01,
    ),
    threshold: float = typer.Option(
        5.0,
        "--threshold",
        "-t",
        help="EV threshold percentage (default 5.0%, range 0-100)",
        min=0.0,
        max=100.0,
    ),
    league: str | None = typer.Option(
        None,
        "--league",
        "-l",
        help="Optional league filter (e.g., 'Premier League')",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging (DEBUG level)",
    ),
) -> None:
    """
    Analyze today's fixtures and find positive EV betting opportunities.

    This command orchestrates the complete analysis pipeline:
    1. Fetch fixture data from API-Football, ESPN, and other sources
    2. Consolidate and validate data quality
    3. Analyze with OpenAI GPT-4 for probability estimates
    4. Calculate expected value and detect profitable edges
    5. Size bets based on bankroll and confidence
    6. Display formatted results or helpful guidance

    Examples:
        # Basic analysis with $1000 bankroll
        bet-bot analyze --bankroll 1000

        # Custom threshold (higher = fewer picks)
        bet-bot analyze --bankroll 1000 --threshold 7.5

        # Filter to specific league
        bet-bot analyze --bankroll 1000 --league "Premier League"

        # Enable verbose logging
        bet-bot analyze --bankroll 1000 --verbose

    Args:
        bankroll: Your available betting bankroll in USD (required, must be > $0)
        threshold: Minimum EV percentage threshold (default 5%, range 0-100%)
        league: Optional league filter to analyze only specific league
        verbose: Enable verbose DEBUG level logging
    """
    # Log CLI startup
    logger.info("=" * 80)
    logger.info(f"Starting bet-bot {__version__}")
    logger.info("=" * 80)
    logger.debug(
        f"Command: analyze | Bankroll: ${bankroll:.2f} | Threshold: {threshold}% | "
        f"League: {league or 'all'} | Verbose: {verbose}"
    )

    # Validate bankroll
    if bankroll <= 0:
        logger.error("Bankroll validation failed: value must be positive")
        typer.echo("❌ Error: Bankroll must be positive", err=True)
        raise typer.Exit(1)

    if threshold < 0 or threshold > 100:
        logger.error(f"Threshold validation failed: {threshold} not in [0, 100]")
        typer.echo("❌ Error: Threshold must be between 0 and 100", err=True)
        raise typer.Exit(1)

    # Configure logging if verbose mode
    if verbose:
        logger.setLevel(logging.DEBUG)
        logger.info("Verbose logging enabled (DEBUG level)")

    # Print welcome message
    typer.echo("")
    typer.echo("🎯 bet-bot - Positive Expected Value Detection Tool")
    typer.echo(f"📊 Bankroll: ${bankroll:,.2f}")
    typer.echo(f"⚡ EV Threshold: {threshold:.1f}%")
    if league:
        typer.echo(f"🏆 League Filter: {league}")
    typer.echo("")

    # Run the analysis pipeline
    try:
        picks, data_quality = asyncio.run(
            _run_analysis_pipeline(
                bankroll=bankroll,
                threshold=threshold,
                league=league,
            )
        )

        # Render results using Story 7.2 renderer
        output = asyncio.run(
            render_analysis_results(
                picks=picks,
                bankroll=bankroll,
                data_quality=data_quality,
            )
        )

        typer.echo(output)

        logger.info("Analysis completed successfully - exit code 0")
        return  # Exit code 0 by default for successful execution

    except KeyboardInterrupt:
        logger.warning("Analysis cancelled by user (Ctrl+C)")
        typer.echo("\n\n❌ Analysis cancelled by user", err=True)
        raise typer.Exit(130)

    except BetBotError as e:
        logger.error(f"BetBot error: {str(e)}", exc_info=True)
        error_msg = display_error(e, context={"phase": "pipeline"})
        typer.echo("")
        typer.echo(error_msg, err=True)
        logger.info("Analysis failed - exit code 1")
        raise typer.Exit(1)

    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        error_msg = display_error(e, context={"phase": "pipeline"})
        typer.echo("")
        typer.echo(error_msg, err=True)
        logger.info("Analysis failed with unexpected error - exit code 1")
        raise typer.Exit(1)


# Entry point for module execution
if __name__ == "__main__":
    app()
