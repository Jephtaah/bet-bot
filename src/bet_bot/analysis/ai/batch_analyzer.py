"""
Batch orchestrator for OpenAI fixture analysis pipeline.

This module chains Stories 4.1-4.3 to analyze all consolidated fixtures
end-to-end and prepare them for EV calculation (Story 5.1).

Main Entry Points:
    - batch_analyze_all_fixtures(): Orchestrates complete pipeline for fixture batch

Pipeline Flow (per fixture):
    1. Story 4.1: Generate prompt via export_prompt_for_api()
    2. Story 4.2: Analyze with OpenAI via analyze_fixture()
    3. Story 4.3: Parse response via parse_openai_response()
    4. Story 4.3: Attach to fixture via attach_parsed_analysis_to_fixture()

Features:
    - Sequential processing respects Story 4.2's internal rate limiting
    - Graceful error handling at each stage (never raises exceptions)
    - Progress tracking with per-fixture logging
    - Pipeline status summary (counts, error details, token usage)
    - All errors logged with fixture_id context
    - Returns all fixtures (successful + failed) for caller filtering

Integration:
    - Input: List[Fixture] from Story 3.3 (with quality_score)
    - Output: List[Fixture] with ai_analysis populated (or error_message if failed)
    - Called by: Story 5.1 (EV Calculator) - next phase
    - Depends on: Stories 4.1, 4.2, 4.3 public APIs

Design Principles:
    - Never raise exceptions - all errors logged and attached to fixtures
    - No additional rate limiting (Story 4.2 handles transparently)
    - Log per-fixture progress with fixture_id context
    - Return both successful and failed fixtures
    - Provide summary for completion reporting
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from bet_bot.analysis.ai.client import analyze_fixture
from bet_bot.analysis.ai.prompt_builder import export_prompt_for_api
from bet_bot.analysis.ai.response_parser import (
    attach_parsed_analysis_to_fixture,
    parse_openai_response,
)
from bet_bot.models.fixtures import Fixture

logger = logging.getLogger(__name__)


async def batch_analyze_all_fixtures(fixtures: list[Fixture] | None) -> list[Fixture]:
    """
    Orchestrate complete AI analysis pipeline for all fixtures.

    Main entry point that chains Stories 4.1-4.3 for batch fixture analysis.
    Accepts consolidated fixtures and returns them with AI analysis attached
    (or error_message if analysis failed at any stage).

    Pipeline per fixture:
        1. Validate fixture has required fields
        2. Generate prompt (Story 4.1: export_prompt_for_api)
        3. Call OpenAI API (Story 4.2: analyze_fixture)
        4. Parse response (Story 4.3: parse_openai_response)
        5. Attach to fixture (Story 4.3: attach_parsed_analysis_to_fixture)

    Error Handling:
        - Errors at any stage are logged and marked on fixture.error_message
        - One fixture failure does NOT block others
        - All fixtures (successful + failed) are returned
        - Caller can filter failures using error_message field

    Args:
        fixtures: List of consolidated Fixture objects (from Story 3.3)

    Returns:
        List[Fixture]: Same fixtures with ai_analysis field populated
                      (or error_message if analysis failed)

    Example:
        >>> from bet_bot.analysis.ai import batch_analyze_all_fixtures
        >>> fixtures = await get_consolidated_fixtures()  # Story 3.3 output
        >>> analyzed = await batch_analyze_all_fixtures(fixtures)
        >>> successful = [f for f in analyzed if f.ai_analysis]
        >>> failed = [f for f in analyzed if f.error_message]
        >>> print(f"Analyzed {len(successful)}/{len(fixtures)} successfully")
    """
    # Validate input
    if not _validate_fixtures_for_analysis(fixtures):
        logger.error("Invalid fixture list for analysis")
        return []

    if not fixtures:
        logger.info("No fixtures to analyze")
        return []

    batch_size = len(fixtures)
    logger.info(f"Starting batch analysis of {batch_size} fixtures")

    # Initialize progress tracking
    results: list[Fixture] = []
    success_count = 0
    failed_count = 0
    errors: list[dict[str, Any]] = []
    start_time = datetime.now(timezone.utc)

    # Process each fixture through full pipeline
    for idx, fixture in enumerate(fixtures, 1):
        try:
            logger.debug(f"Processing fixture {idx}/{batch_size}: {fixture.fixture_id}")

            # Orchestrate single fixture through pipeline
            result_fixture = await _analyze_single_fixture(fixture)

            # Track result
            if result_fixture:
                results.append(result_fixture)

                # Check if analysis succeeded (no error_message and has ai_analysis)
                if not result_fixture.error_message and result_fixture.ai_analysis:
                    success_count += 1
                    logger.info(
                        f"✓ Fixture {idx}/{batch_size} analyzed successfully: "
                        f"{fixture.fixture_id}"
                    )
                else:
                    failed_count += 1
                    error_msg = result_fixture.error_message or "Unknown error"
                    logger.warning(
                        f"✗ Fixture {idx}/{batch_size} analysis failed: "
                        f"{fixture.fixture_id} - {error_msg}"
                    )
                    errors.append({
                        "fixture_id": fixture.fixture_id,
                        "error": error_msg,
                    })
            else:
                failed_count += 1
                logger.error(f"Fixture {idx}/{batch_size} returned None: {fixture.fixture_id}")
                errors.append({
                    "fixture_id": fixture.fixture_id,
                    "error": "Fixture processing returned None",
                })

        except Exception as e:
            # Should not happen - but catch-all for unexpected errors
            logger.exception(f"Unexpected error processing fixture {fixture.fixture_id}: {str(e)}")
            failed_count += 1
            errors.append({
                "fixture_id": fixture.fixture_id,
                "error": f"Unexpected error: {str(e)}",
            })

    # Create and log summary
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    summary = _create_pipeline_summary(results)

    logger.info(
        f"Batch analysis complete: {success_count}/{batch_size} successful, "
        f"{failed_count}/{batch_size} failed ({summary['success_rate']:.1%} success rate) "
        f"in {duration:.1f}s"
    )

    if errors:
        logger.warning(f"Error summary: {len(errors)} fixtures failed")
        for error_detail in errors[:10]:  # Log first 10 errors
            logger.warning(
                f"  {_format_error_summary_from_dict(error_detail)}"
            )
        if len(errors) > 10:
            logger.warning(f"  ... and {len(errors) - 10} more errors")

    return results


async def _analyze_single_fixture(fixture: Fixture) -> Fixture | None:
    """
    Orchestrate single fixture through complete analysis pipeline.

    Handles the 4.1 → 4.2 → 4.3 pipeline for one fixture with
    error handling at each stage.

    Pipeline:
        1. Validate fixture structure
        2. Call Story 4.1: export_prompt_for_api() → get prompt dict
        3. Call Story 4.2: analyze_fixture() → get fixture with raw ai_analysis
        4. Check for errors from Story 4.2
        5. Call Story 4.3: parse_openai_response() → get MarketAnalysis objects
        6. Call Story 4.3: attach_parsed_analysis_to_fixture() → attach to fixture

    Error Handling:
        - Errors at any stage are caught, logged, and marked on fixture
        - fixture.error_message is set on failure
        - Fixture is returned even on failure (for caller filtering)

    Args:
        fixture: Individual Fixture to analyze

    Returns:
        Fixture: Same fixture with ai_analysis populated or error_message set

    Side Effects:
        - Logs at each stage (DEBUG for processing, INFO for success, WARNING for errors)
        - May wait for Story 4.2 rate limiting
    """
    if not fixture or not fixture.fixture_id:
        logger.error("Cannot analyze fixture without fixture_id")
        return None

    fixture_id = fixture.fixture_id

    try:
        # Step 1: Validate fixture (redundant but safe)
        if not fixture.home_team or not fixture.away_team:
            logger.warning(f"Fixture {fixture_id}: missing team information")
            fixture.error_message = "Missing team information"
            return fixture

        # Step 2: Generate prompt (Story 4.1)
        try:
            logger.debug(f"Fixture {fixture_id}: generating prompt")
            # Call Story 4.1 public API - export_prompt_for_api() per AC #3
            prompt_dict = await export_prompt_for_api(fixture)

            if not prompt_dict or not prompt_dict.get("system_prompt") or not prompt_dict.get("user_message"):
                logger.error(f"Fixture {fixture_id}: empty prompt generated")
                fixture.error_message = "Prompt generation failed: empty prompt"
                return fixture

            logger.debug(
                f"Fixture {fixture_id}: prompt generated "
                f"(system: {len(prompt_dict.get('system_prompt', ''))} chars, "
                f"user: {len(prompt_dict.get('user_message', ''))} chars)"
            )
        except Exception as e:
            logger.error(f"Fixture {fixture_id}: prompt generation failed - {str(e)}")
            fixture.error_message = f"Prompt generation error: {str(e)}"
            return fixture

        # Step 3: Call OpenAI API (Story 4.2)
        try:
            logger.debug(f"Fixture {fixture_id}: calling OpenAI API")
            analyzed_fixture = await analyze_fixture(fixture)

            if not analyzed_fixture:
                logger.error(f"Fixture {fixture_id}: OpenAI analysis returned None")
                fixture.error_message = "OpenAI analysis returned None"
                return fixture

            # Check if Story 4.2 encountered an error
            if analyzed_fixture.error_message:
                logger.warning(f"Fixture {fixture_id}: OpenAI error - {analyzed_fixture.error_message}")
                return analyzed_fixture  # Already has error_message set

            # Check if ai_analysis was populated
            if not analyzed_fixture.ai_analysis:
                logger.error(f"Fixture {fixture_id}: OpenAI returned empty ai_analysis")
                analyzed_fixture.error_message = "Empty OpenAI response"
                return analyzed_fixture

            logger.debug(f"Fixture {fixture_id}: OpenAI response received")

            # Update our working fixture reference
            fixture = analyzed_fixture

        except Exception as e:
            logger.error(f"Fixture {fixture_id}: OpenAI API call failed - {str(e)}")
            fixture.error_message = f"OpenAI API error: {str(e)}"
            return fixture

        # Step 4: Parse response (Story 4.3)
        try:
            logger.debug(f"Fixture {fixture_id}: parsing OpenAI response")

            # ai_analysis should be raw JSON dict/str from Story 4.2
            raw_response = fixture.ai_analysis
            if not raw_response:
                logger.error(f"Fixture {fixture_id}: no raw ai_analysis to parse")
                fixture.error_message = "No raw response to parse"
                return fixture

            # Parse the response (async call)
            parsed_markets = await parse_openai_response(raw_response, fixture_id)

            if not parsed_markets:
                logger.warning(f"Fixture {fixture_id}: response parsing returned None/empty")
                fixture.error_message = "Response parsing failed or returned empty"
                return fixture

            logger.debug(f"Fixture {fixture_id}: parsed {len(parsed_markets)} markets")

        except Exception as e:
            logger.error(f"Fixture {fixture_id}: response parsing failed - {str(e)}")
            fixture.error_message = f"Response parsing error: {str(e)}"
            return fixture

        # Step 5: Attach parsed analysis (Story 4.3)
        try:
            logger.debug(f"Fixture {fixture_id}: attaching parsed analysis")
            fixture = await attach_parsed_analysis_to_fixture(fixture, parsed_markets)

            if not fixture:
                logger.error(f"Fixture {fixture_id}: attach_parsed_analysis returned None")
                fixture.error_message = "Failed to attach parsed analysis"
                return fixture

            if not fixture.ai_analysis:
                logger.error(f"Fixture {fixture_id}: ai_analysis not attached")
                fixture.error_message = "Analysis attachment failed"
                return fixture

            logger.info(f"Fixture {fixture_id}: analysis complete")
            return fixture

        except Exception as e:
            logger.error(f"Fixture {fixture_id}: attachment failed - {str(e)}")
            fixture.error_message = f"Attachment error: {str(e)}"
            return fixture

    except Exception as e:
        # Outer catch-all for safety
        logger.exception(f"Fixture {fixture_id}: unexpected error in orchestration - {str(e)}")
        fixture.error_message = f"Unexpected error: {str(e)}"
        return fixture


def _validate_fixtures_for_analysis(fixtures: list[Fixture] | None) -> bool:
    """
    Validate input fixture list for analysis.

    Checks:
    - fixtures is not None and is a list
    - fixtures is not empty
    - Each fixture has required fields (logs warnings but continues)

    Args:
        fixtures: Fixture list to validate

    Returns:
        True if fixtures are valid enough to process, False for critical failures

    Side Effects:
        Logs warnings for missing fields but continues (graceful degradation)
    """
    if not fixtures:
        logger.warning("fixtures is None or empty")
        return False

    if not isinstance(fixtures, list):
        logger.error(f"fixtures is not a list: {type(fixtures).__name__}")
        return False

    if len(fixtures) == 0:
        logger.info("Empty fixture list provided")
        return False

    # Check sample of fixtures for required fields
    missing_count = 0
    for idx, fixture in enumerate(fixtures[:5]):  # Check first 5
        if not fixture.fixture_id:
            logger.warning(f"Fixture {idx}: missing fixture_id")
            missing_count += 1

        if not fixture.home_team or not fixture.away_team:
            logger.warning(f"Fixture {idx}: missing team information")
            missing_count += 1

        if not fixture.kickoff_time:
            logger.warning(f"Fixture {idx}: missing kickoff_time")
            missing_count += 1

    if missing_count > len(fixtures) * 0.5:  # >50% missing critical fields
        logger.error(f"Too many fixtures with missing fields ({missing_count}/{min(5, len(fixtures))})")
        return False

    return True


def _create_pipeline_summary(results: list[Fixture]) -> dict[str, Any]:
    """
    Generate summary statistics from analysis results.

    Extracts counts, success rate, error details, and token usage
    for completion reporting.

    Args:
        results: List of analyzed fixtures (with ai_analysis or error_message)

    Returns:
        dict: {
            'total': int,
            'successful': int,
            'failed': int,
            'success_rate': float (0.0-1.0),
            'error_list': list[dict],
            'tokens_total': int (if available),
            'cost_total': float (if available)
        }

    Side Effects:
        None (read-only aggregation)
    """
    if not results:
        return {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "success_rate": 0.0,
            "error_list": [],
            "tokens_total": 0,
            "cost_total": 0.0,
        }

    total = len(results)
    successful = 0
    failed = 0
    error_list: list[dict[str, Any]] = []
    tokens_total = 0

    for fixture in results:
        # Defensive null-check: validate fixture before accessing attributes
        if not fixture or not hasattr(fixture, "fixture_id"):
            failed += 1
            error_list.append({
                "fixture_id": "unknown",
                "error": "Invalid fixture object",
            })
            continue

        # Check success (has ai_analysis and no error_message)
        if fixture.ai_analysis and not fixture.error_message:
            successful += 1

            # Aggregate token usage if available
            if hasattr(fixture, "ai_analysis") and hasattr(fixture.ai_analysis, "tokens_used"):
                tokens_total += fixture.ai_analysis.tokens_used or 0
        else:
            failed += 1
            error_list.append({
                "fixture_id": fixture.fixture_id,
                "error": fixture.error_message or "Analysis missing",
            })

    success_rate = successful / total if total > 0 else 0.0

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "success_rate": success_rate,
        "error_list": error_list,
        "tokens_total": tokens_total,
        "cost_total": (tokens_total * 0.000001) if tokens_total > 0 else 0.0,  # Approximate
    }


def _format_error_summary(fixture: Fixture) -> str:
    """
    Format error message for display.

    Args:
        fixture: Fixture with error_message

    Returns:
        str: Formatted error summary like "Fixture {id}: {error}"
    """
    fixture_id = fixture.fixture_id if fixture else "unknown"
    error_msg = fixture.error_message if fixture and hasattr(fixture, "error_message") else "Unknown error"
    return f"Fixture {fixture_id}: {error_msg}"


def _format_error_summary_from_dict(error_detail: dict[str, Any]) -> str:
    """
    Format error detail dict for display.

    Args:
        error_detail: Dict with 'fixture_id' and 'error' keys

    Returns:
        str: Formatted error summary
    """
    return f"Fixture {error_detail.get('fixture_id', 'unknown')}: {error_detail.get('error', 'Unknown error')}"
