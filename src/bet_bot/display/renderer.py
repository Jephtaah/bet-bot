"""
Results renderer for analysis output.

This module transforms analysis results (picks, bankroll, data quality) into
beautifully formatted terminal output using the Rich library. It handles multiple
output states (success, no picks, errors, degraded service) with appropriate
styling and helpful guidance.

Features:
- State-aware rendering: PICKS_FOUND, NO_PICKS_AVAILABLE, NO_MATCHES_TODAY, ERROR, DEGRADED
- Rich-formatted panels with color-coded states
- Summary statistics: total picks, average EV, confidence, ROI calculation
- Data quality tracking with per-source status
- Actionable next steps guidance based on result state
- Graceful error handling and troubleshooting suggestions

Functions:
    render_analysis_results: Main function to render analysis results
    _format_picks_found_state: Render successful picks with statistics
    _format_no_picks_state: Render no profitable picks message
    _format_no_matches_state: Render no fixtures available message
    _format_error_state: Render error with troubleshooting
    _format_degraded_state: Render partial failure with warning
    _format_data_quality_notes: Generate data quality tracking display
    _format_next_steps: Generate actionable next steps section

Usage:
    from bet_bot.display import render_analysis_results

    picks = [pick1, pick2]
    bankroll = 1000.0
    data_quality = {"api_football": {"status": "success"}, "openai": {"status": "success"}}

    output = await render_analysis_results(picks, bankroll, data_quality)
    print(output)
"""

import logging
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.box import ROUNDED

from bet_bot.display.formatter import format_picks_for_display
from bet_bot.models.analysis import Pick

logger = logging.getLogger(__name__)


def _determine_output_state(
    picks: list[Pick] | None,
    data_quality: dict[str, dict[str, Any]] | None
) -> tuple[str, bool]:
    """
    Determine which output state applies based on picks and data quality.

    Args:
        picks: List of Pick objects from edge detection
        data_quality: Dictionary tracking data source status

    Returns:
        Tuple of (state: str, is_error: bool)
        States: 'picks_found', 'no_picks', 'no_matches', 'error', 'degraded'
    """
    if not picks:
        picks = []

    # Check for error state (critical data sources failed)
    if data_quality:
        failed_sources = [
            source for source, info in data_quality.items()
            if isinstance(info, dict) and info.get("status") == "failed"
        ]

        # If critical sources failed AND no picks were generated
        critical_sources = {"api_football", "openai"}
        critical_failures = len(critical_sources & set(failed_sources))

        if critical_failures > 0 and not picks:
            return "error", True

        # If some sources failed but we have picks, it's degraded
        if len(failed_sources) > 0 and picks:
            return "degraded", False

    # If we have picks, success
    if picks:
        return "picks_found", False

    # If no picks and no fixtures (zero analyzed)
    if data_quality and data_quality.get("fixtures_analyzed", 0) == 0:
        return "no_matches", False

    # Otherwise, no picks available at threshold
    return "no_picks", False


def _format_picks_found_state(
    picks: list[Pick],
    bankroll: float,
    data_quality: dict[str, dict[str, Any]] | None = None
) -> str:
    """
    Format successful picks state with statistics.

    Args:
        picks: List of Pick objects to display
        bankroll: User's betting bankroll
        data_quality: Optional data quality tracking

    Returns:
        Rich-formatted string for terminal display
    """
    output_lines = []

    # Header
    output_lines.append("✅ ANALYSIS COMPLETE - PICKS FOUND")
    output_lines.append("")

    # Formatted picks table from formatter
    picks_table = format_picks_for_display(picks)
    output_lines.append(picks_table)
    output_lines.append("")

    # Calculate statistics
    total_picks = len(picks)
    avg_ev = sum(pick.ev_percentage for pick in picks) / total_picks if picks else 0
    avg_confidence = int(sum(pick.confidence for pick in picks) / total_picks) if picks else 0
    total_stake = sum(pick.recommended_stake for pick in picks)
    expected_roi = total_stake * (avg_ev / 100) if avg_ev > 0 else 0
    roi_percentage = (expected_roi / bankroll * 100) if bankroll > 0 else 0

    # Summary statistics
    output_lines.append("📊 Summary Statistics")
    output_lines.append(f"  Total Picks: {total_picks}")
    output_lines.append(f"  Average EV: {avg_ev:+.1f}%")
    output_lines.append(f"  Average Confidence: {avg_confidence}%")
    output_lines.append(f"  Total Stake Required: ${total_stake:,.2f}")
    output_lines.append(f"  Expected ROI: ${expected_roi:,.2f} ({roi_percentage:+.1f}% of bankroll)")
    output_lines.append("")

    # Data quality notes if provided
    if data_quality:
        quality_notes = _format_data_quality_notes(data_quality)
        output_lines.append(quality_notes)
        output_lines.append("")

    # Next steps
    next_steps = _format_next_steps("picks_found", total_picks, {"bankroll": bankroll})
    output_lines.append(next_steps)

    return "\n".join(output_lines)


def _format_no_picks_state(
    data_quality: dict[str, dict[str, Any]] | None = None
) -> str:
    """
    Format no profitable picks state.

    Args:
        data_quality: Optional data quality tracking

    Returns:
        Rich-formatted string for terminal display
    """
    output_lines = []

    # Header
    output_lines.append("ℹ️ NO PROFITABLE PICKS FOUND")
    output_lines.append("")

    # Explanation
    output_lines.append("All analyzed fixtures had EV below 5% threshold or insufficient data quality.")
    output_lines.append("")
    output_lines.append("💡 Suggestions:")
    output_lines.append("  • Consider lowering EV threshold temporarily for testing")
    output_lines.append("  • Or expand to additional leagues for more opportunities")
    output_lines.append("  • Check back tomorrow for new fixtures")
    output_lines.append("")

    # Data quality notes if provided
    if data_quality:
        quality_notes = _format_data_quality_notes(data_quality)
        output_lines.append(quality_notes)
        output_lines.append("")

    # Next steps
    next_steps = _format_next_steps("no_picks", 0, {})
    output_lines.append(next_steps)

    return "\n".join(output_lines)


def _format_no_matches_state(
    data_quality: dict[str, dict[str, Any]] | None = None
) -> str:
    """
    Format no matches today state.

    Args:
        data_quality: Optional data quality tracking

    Returns:
        Rich-formatted string for terminal display
    """
    output_lines = []

    # Header
    output_lines.append("🔍 NO MATCHES TODAY")
    output_lines.append("")

    # Explanation
    output_lines.append("No fixtures found for your target leagues on this date.")
    output_lines.append("")
    output_lines.append("💡 Next steps:")
    output_lines.append("  • Check back tomorrow for new fixtures")
    output_lines.append("  • Expand target leagues with: bet-bot config set-leagues")
    output_lines.append("")

    # Data quality notes if provided
    if data_quality:
        quality_notes = _format_data_quality_notes(data_quality)
        output_lines.append(quality_notes)
        output_lines.append("")

    # Next steps
    next_steps = _format_next_steps("no_matches", 0, {})
    output_lines.append(next_steps)

    return "\n".join(output_lines)


def _format_error_state(
    error_type: str = "unknown",
    error_message: str = "",
    data_quality: dict[str, dict[str, Any]] | None = None
) -> str:
    """
    Format error state with troubleshooting guidance.

    Args:
        error_type: Type of error (api_failure, rate_limit, network_error, etc.)
        error_message: Human-readable error message
        data_quality: Optional data quality tracking showing which sources failed

    Returns:
        Rich-formatted string for terminal display
    """
    output_lines = []

    # Header
    output_lines.append("❌ ANALYSIS FAILED")
    output_lines.append("")

    # Error details
    output_lines.append(f"Error Type: {error_type}")
    if error_message:
        output_lines.append(f"Details: {error_message}")
    output_lines.append("")

    # Troubleshooting guidance
    output_lines.append("Troubleshooting:")
    if "rate_limit" in error_type.lower():
        output_lines.append("  • API rate limit exceeded")
        output_lines.append("  • Wait 60 seconds before retrying")
        output_lines.append("  • Check your API rate plan")
    elif "authentication" in error_type.lower() or "401" in error_message or "403" in error_message:
        output_lines.append("  • Check API key is valid in .env file")
        output_lines.append("  • Verify API credentials are not expired")
        output_lines.append("  • Contact API provider if issues persist")
    elif "network" in error_type.lower() or "connection" in error_type.lower():
        output_lines.append("  • Check internet connection")
        output_lines.append("  • Verify firewall/proxy settings")
        output_lines.append("  • Retry in a few moments")
    elif "timeout" in error_type.lower():
        output_lines.append("  • Request timeout - server may be slow")
        output_lines.append("  • Try again in 5 minutes")
        output_lines.append("  • Check your internet connection")
    else:
        output_lines.append("  • Retry the analysis")
        output_lines.append("  • Check logs for details: ~/.bet-bot/logs/")
        output_lines.append("  • Verify all API keys are configured")
    output_lines.append("")

    # Data quality notes if provided
    if data_quality:
        quality_notes = _format_data_quality_notes(data_quality)
        output_lines.append(quality_notes)
        output_lines.append("")

    # Next steps
    next_steps = _format_next_steps("error", 0, {})
    output_lines.append(next_steps)

    return "\n".join(output_lines)


def _format_degraded_state(
    picks: list[Pick],
    bankroll: float,
    data_quality: dict[str, dict[str, Any]] | None = None
) -> str:
    """
    Format degraded service state with partial results.

    Args:
        picks: List of Pick objects (partial results despite some data source failures)
        bankroll: User's betting bankroll
        data_quality: Data quality tracking showing which sources failed

    Returns:
        Rich-formatted string for terminal display
    """
    output_lines = []

    # Header
    output_lines.append("⚠️ DEGRADED SERVICE")
    output_lines.append("")

    # Count failed sources
    failed_count = 0
    total_count = 0
    if data_quality:
        for source, info in data_quality.items():
            if isinstance(info, dict) and "status" in info:
                total_count += 1
                if info["status"] == "failed":
                    failed_count += 1

    # Warning message
    output_lines.append(f"{failed_count}/{total_count} data sources failed, analyzing with available data")
    output_lines.append("")
    output_lines.append("⚠️  Warning: Results confidence reduced due to missing data. Use caution with bets.")
    output_lines.append("")

    # Display picks if any
    if picks:
        picks_table = format_picks_for_display(picks)
        output_lines.append(picks_table)
        output_lines.append("")

        # Calculate statistics
        total_picks = len(picks)
        avg_ev = sum(pick.ev_percentage for pick in picks) / total_picks
        avg_confidence = int(sum(pick.confidence for pick in picks) / total_picks)
        total_stake = sum(pick.recommended_stake for pick in picks)

        output_lines.append("📊 Summary (Partial)")
        output_lines.append(f"  Total Picks: {total_picks}")
        output_lines.append(f"  Average EV: {avg_ev:+.1f}%")
        output_lines.append(f"  Average Confidence: {avg_confidence}% (reduced due to data loss)")
        output_lines.append(f"  Total Stake Required: ${total_stake:,.2f}")
        output_lines.append("")
    else:
        output_lines.append("No picks available even with partial data")
        output_lines.append("")

    # Data quality notes
    if data_quality:
        quality_notes = _format_data_quality_notes(data_quality)
        output_lines.append(quality_notes)
        output_lines.append("")

    # Next steps
    next_steps = _format_next_steps("degraded", len(picks) if picks else 0, {"bankroll": bankroll})
    output_lines.append(next_steps)

    return "\n".join(output_lines)


def _format_data_quality_notes(
    data_quality: dict[str, dict[str, Any]]
) -> str:
    """
    Format data quality tracking notes.

    Args:
        data_quality: Dictionary with source status and metadata

    Returns:
        Rich-formatted string showing data source status
    """
    console = Console()

    if not data_quality:
        return ""

    # Build quality table
    table = Table(title="Data Quality Report", box=ROUNDED, padding=(0, 1))
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Latency", justify="right", style="dim")
    table.add_column("Records", justify="right", style="dim")

    overall_success_count = 0
    overall_total_count = 0

    for source, info in data_quality.items():
        if source in ("fixtures_analyzed", "timestamp"):
            continue

        if not isinstance(info, dict):
            continue

        overall_total_count += 1
        status = info.get("status", "unknown")

        if status == "success":
            overall_success_count += 1
            status_display = "[green]✅ Success[/green]"
        elif status == "failed":
            status_display = "[red]❌ Failed[/red]"
        else:
            status_display = "[yellow]⚠️ Unknown[/yellow]"

        latency = info.get("latency_ms")
        latency_display = f"{latency}ms" if latency is not None else "-"

        record_count = info.get("record_count")
        record_display = str(record_count) if record_count is not None else "-"

        table.add_row(source.replace("_", " ").title(), status_display, latency_display, record_display)

    # Calculate overall quality percentage
    if overall_total_count > 0:
        quality_percentage = int(overall_success_count / overall_total_count * 100)
    else:
        quality_percentage = 0

    # Add overall summary
    quality_text = f"\n[cyan]Overall Data Quality: {quality_percentage}% ({overall_success_count}/{overall_total_count} sources)[/cyan]"

    panel_content = str(table) + quality_text
    return panel_content


def _format_next_steps(
    state: str,
    picks_count: int,
    context: dict[str, Any] | None = None
) -> str:
    """
    Format actionable next steps based on result state.

    Args:
        state: Output state (picks_found, no_picks, no_matches, error, degraded)
        picks_count: Number of picks in result
        context: Additional context (bankroll, etc.)

    Returns:
        Plain text next steps section
    """
    output_lines = ["🎯 Next Steps:"]

    if state == "picks_found":
        output_lines.append("  1. Review each pick's details and reasoning")
        output_lines.append("  2. Verify odds on your betting exchange")
        output_lines.append("  3. Place recommended bets at specified stakes")
        output_lines.append("  4. Track results for validation")
        output_lines.append("  5. Review profit/loss regularly")
    elif state == "no_picks":
        output_lines.append("  • Review your EV threshold and confidence settings")
        output_lines.append("  • Check back tomorrow for new opportunities")
        output_lines.append("  • Consider expanding to additional leagues")
        output_lines.append("  • Or lower your EV threshold temporarily for testing")
    elif state == "no_matches":
        output_lines.append("  • Check back tomorrow for new fixtures")
        output_lines.append("  • Or configure additional leagues")
        output_lines.append("  • Verify your league settings are correct")
    elif state == "error":
        output_lines.append("  1. Review troubleshooting steps above")
        output_lines.append("  2. Verify API keys in .env file")
        output_lines.append("  3. Check logs: ~/.bet-bot/logs/")
        output_lines.append("  4. Retry the analysis")
        output_lines.append("  5. Contact support if issues persist")
    elif state == "degraded":
        output_lines.append("  1. Review results with caution due to incomplete data")
        output_lines.append("  2. Check which data sources failed (see Data Quality Report)")
        output_lines.append("  3. Consider waiting for all sources to recover")
        output_lines.append("  4. Or place bets with reduced confidence")
        output_lines.append("  5. Monitor results closely")

    return "\n".join(output_lines)


async def render_analysis_results(
    picks: list[Pick] | None = None,
    bankroll: float = 0.0,
    data_quality: dict[str, dict[str, Any]] | None = None
) -> str:
    """
    Render analysis results with state-aware formatting.

    Main entry point for rendering final analysis results. Determines appropriate
    output state based on picks list and data quality, then formats output with
    relevant statistics, data quality notes, and next steps guidance.

    Args:
        picks: List of Pick objects from edge detection pipeline (None = empty list)
        bankroll: User's betting bankroll for context and ROI calculation
        data_quality: Dictionary tracking status of each data source:
            {
                "api_football": {"status": "success", "latency_ms": 42, "record_count": 25},
                "espn": {"status": "failed", "error": "timeout"},
                "openai": {"status": "success", "latency_ms": 1200},
                ...
            }

    Returns:
        Rich-formatted string for terminal display

    Raises:
        ValueError: If picks or bankroll are invalid types

    Example:
        >>> picks = [pick1, pick2]
        >>> data_quality = {
        ...     "api_football": {"status": "success"},
        ...     "openai": {"status": "success"}
        ... }
        >>> output = await render_analysis_results(picks, 1000.0, data_quality)
        >>> print(output)
    """
    # Validate inputs
    if picks is None:
        picks = []
    elif not isinstance(picks, list):
        raise ValueError(f"picks must be list, got {type(picks)}")

    if not isinstance(bankroll, (int, float)):
        raise ValueError(f"bankroll must be numeric, got {type(bankroll)}")

    if data_quality is None:
        data_quality = {}
    elif not isinstance(data_quality, dict):
        raise ValueError(f"data_quality must be dict, got {type(data_quality)}")

    # Determine output state
    state, is_error = _determine_output_state(picks, data_quality)

    # Render appropriate state
    if state == "picks_found":
        return _format_picks_found_state(picks, bankroll, data_quality)
    elif state == "no_picks":
        return _format_no_picks_state(data_quality)
    elif state == "no_matches":
        return _format_no_matches_state(data_quality)
    elif state == "error":
        # Extract error details from data_quality if available
        error_type = "unknown"
        error_message = ""
        if data_quality:
            for source, info in data_quality.items():
                if isinstance(info, dict) and info.get("status") == "failed":
                    error_type = source
                    error_message = info.get("error", "")
                    break
        return _format_error_state(error_type, error_message, data_quality)
    elif state == "degraded":
        return _format_degraded_state(picks, bankroll, data_quality)
    else:
        # Fallback to no picks
        return _format_no_picks_state(data_quality)
