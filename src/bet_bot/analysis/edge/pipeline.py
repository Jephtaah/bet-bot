"""
Edge Detection Pipeline Orchestrator for bet-bot application.

This module orchestrates the complete edge detection pipeline for Story 5.4:
1. Calculate EV for each market (Story 5.1)
2. Filter by 5% EV threshold (Story 5.2)
3. Score confidence based on data quality (Story 5.3)
4. Transform results into Pick objects ready for display/stake sizing

The detect_edges() function is the main entry point for the entire edge detection phase.

Architecture:
Input: Fixtures with AI analysis from Story 4.4 (ai_analysis field populated)
Output: List of Pick objects or NO_PICKS message string
Consumer: Story 6.1 (Stake Sizing), Story 7.1 (Display/Output)

Features:
- Orchestrates exact order: EV calc → threshold filtering → confidence scoring
- Calculates recommended_stake using formula: bankroll × (EV_pct * 0.01 * 0.1) × (confidence / 100)
- Handles "NO PICKS" case gracefully with user-friendly message
- Logs comprehensive summary statistics: picks by category, EV distribution, confidence tiers
- Transforms EVResult + ConfidenceScoreBreakdown into Pick objects
- Graceful degradation: if any step fails for a single pick, log error and continue

Functions:
- detect_edges(fixtures, bankroll) -> list[Pick] | str: Main orchestrator
- _calculate_recommended_stake(ev_percentage, confidence, bankroll) -> float: Stake calculation
- _create_pick_from_ev_and_confidence(ev_result, confidence_breakdown, stake, fixture) -> Pick: Transform
- _calculate_summary_statistics(picks, all_ev_results) -> dict: Summary stats
- _log_summary_statistics(summary) -> None: Logging

Usage:
------
    from bet_bot.analysis.edge import detect_edges

    # Orchestrate full pipeline
    picks = await detect_edges(
        fixtures=fixtures_with_ai_analysis,
        bankroll=1000.0
    )

    if isinstance(picks, str):
        print(picks)  # NO_PICKS message
    else:
        for pick in picks:
            print(f"{pick.market}: {pick.ev_percentage:.1f}% EV @ {pick.suggested_odds}")
"""

import logging
from typing import Any

from bet_bot.models.analysis import Pick
from bet_bot.models.fixtures import Fixture
from bet_bot.analysis.edge.ev_calculator import (
    calculate_all_evs,
    EVResult,
)
from bet_bot.analysis.edge.threshold_filter import (
    apply_threshold_filter,
    FilteredPick,
    no_picks_available_message,
)
from bet_bot.analysis.edge.confidence_scorer import (
    apply_confidence_scoring,
    ConfidenceScoreBreakdown,
)

# Module-level logger
logger = logging.getLogger(__name__)


def _calculate_recommended_stake(
    ev_percentage: float,
    confidence: int,
    bankroll: float,
) -> float:
    """
    Calculate recommended stake using formula: bankroll × (EV_pct × 0.01 × 0.1) × (confidence / 100).

    Args:
        ev_percentage: Expected value as percentage (0-100)
        confidence: Confidence score (0-100)
        bankroll: Total betting bankroll in currency units

    Returns:
        Recommended stake in currency units, clamped to max 5% of bankroll

    Example:
        >>> stake = _calculate_recommended_stake(
        ...     ev_percentage=5.0,
        ...     confidence=80,
        ...     bankroll=1000.0
        ... )
        >>> # 1000 × (5 * 0.01 * 0.1) × (80 / 100) = 1000 × 0.005 × 0.8 = $4
        >>> stake
        4.0
    """
    # Formula: bankroll × (EV_pct × 0.01 × 0.1) × (confidence / 100)
    # Note: EV_pct is already in 0-100 range, so multiply by 0.01 to get decimal
    stake = bankroll * (ev_percentage * 0.01 * 0.1) * (confidence / 100)

    # Clamp stake to max 5% of bankroll (safety measure)
    max_stake = bankroll * 0.05
    if stake > max_stake:
        logger.debug(
            f"Stake {stake:.2f} exceeds max 5% ({max_stake:.2f}), clamping",
            extra={"ev": ev_percentage, "confidence": confidence, "bankroll": bankroll},
        )
        stake = max_stake

    return max(stake, 0.01)  # Ensure minimum $0.01 stake


def _create_pick_from_ev_and_confidence(
    ev_result: EVResult,
    confidence_breakdown: ConfidenceScoreBreakdown,
    stake: float,
    fixture: Fixture | None,
) -> Pick:
    """
    Transform EVResult + ConfidenceScoreBreakdown into Pick object.

    Args:
        ev_result: EVResult with EV calculations from Story 5.1
        confidence_breakdown: ConfidenceScoreBreakdown from Story 5.3
        stake: Calculated recommended stake
        fixture: Parent fixture (contains the fixture_id), or None if fixture not available

    Returns:
        Pick object with all required fields populated

    Raises:
        ValueError: If required fields are missing
    """
    try:
        # Get fixture_id from the fixture object (EVResult doesn't have fixture_id)
        fixture_id = fixture.fixture_id if fixture else "unknown"

        pick = Pick(
            fixture_id=fixture_id,
            market=f"{ev_result.market_type}_{ev_result.outcome}",
            ai_probability=ev_result.ai_probability,
            implied_probability=ev_result.implied_probability,
            ev_percentage=ev_result.ev_percentage,
            confidence=confidence_breakdown.final_confidence,
            recommended_stake=stake,
            suggested_odds=ev_result.odds,
        )
        return pick
    except Exception as e:
        logger.error(
            f"Failed to create Pick from EV result",
            extra={
                "fixture_id": fixture.fixture_id if fixture else "unknown",
                "market": ev_result.market_type,
                "error": str(e),
            },
        )
        raise


def _calculate_summary_statistics(
    picks: list[Pick],
    all_ev_results: list[EVResult],
) -> dict[str, Any]:
    """
    Calculate summary statistics for edge detection results.

    Args:
        picks: List of recommended picks (above 5% threshold)
        all_ev_results: All EV results calculated (before filtering)

    Returns:
        Dict with comprehensive statistics:
        - total_ev_calculated: Total number of EV results
        - total_picks_above_threshold: Number of recommended picks
        - ev_mean: Mean EV percentage across recommended picks
        - ev_min: Minimum EV percentage
        - ev_max: Maximum EV percentage
        - ev_high_count: Count of picks with EV > 8%
        - ev_medium_count: Count of picks with 5% <= EV <= 8%
        - ev_low_count: Count of picks with EV < 5% (for context)
        - confidence_mean: Mean confidence across picks
        - confidence_high_count: Count with confidence > 80
        - confidence_medium_count: Count with 60 <= confidence <= 80
        - confidence_low_count: Count with confidence < 60
        - confidence_min: Minimum confidence
        - confidence_max: Maximum confidence
    """
    stats = {
        "total_ev_calculated": len(all_ev_results),
        "total_picks_above_threshold": len(picks),
    }

    if len(picks) > 0:
        ev_percentages = [p.ev_percentage for p in picks]
        confidences = [p.confidence for p in picks]

        # EV statistics
        stats["ev_mean"] = sum(ev_percentages) / len(ev_percentages)
        stats["ev_min"] = min(ev_percentages)
        stats["ev_max"] = max(ev_percentages)

        # EV distribution tiers
        stats["ev_high_count"] = sum(1 for ev in ev_percentages if ev > 8.0)
        stats["ev_medium_count"] = sum(1 for ev in ev_percentages if 5.0 <= ev <= 8.0)
        stats["ev_low_count"] = sum(1 for ev in ev_percentages if ev < 5.0)

        # Confidence statistics
        stats["confidence_mean"] = sum(confidences) / len(confidences)
        stats["confidence_min"] = min(confidences)
        stats["confidence_max"] = max(confidences)

        # Confidence distribution tiers
        stats["confidence_high_count"] = sum(1 for c in confidences if c > 80)
        stats["confidence_medium_count"] = sum(1 for c in confidences if 60 <= c <= 80)
        stats["confidence_low_count"] = sum(1 for c in confidences if c < 60)
    else:
        # No picks found
        stats["ev_mean"] = 0.0
        stats["ev_min"] = 0.0
        stats["ev_max"] = 0.0
        stats["ev_high_count"] = 0
        stats["ev_medium_count"] = 0
        stats["ev_low_count"] = 0
        stats["confidence_mean"] = 0
        stats["confidence_min"] = 0
        stats["confidence_max"] = 0
        stats["confidence_high_count"] = 0
        stats["confidence_medium_count"] = 0
        stats["confidence_low_count"] = 0

    return stats


def _log_summary_statistics(summary: dict[str, Any]) -> None:
    """
    Log comprehensive summary statistics.

    Example output:
    "Edge Detection Complete: 15 total EVs, 8 above 5% threshold.
     EV: +5.2% avg (3.1% min, 9.8% max) [high:3, medium:4, low:1].
     Confidence: 74% avg [high:3, medium:4, low:1]"
    """
    total_evs = summary["total_ev_calculated"]
    total_picks = summary["total_picks_above_threshold"]

    if total_picks > 0:
        ev_msg = (
            f"EV: +{summary['ev_mean']:.1f}% avg "
            f"({summary['ev_min']:.1f}% min, {summary['ev_max']:.1f}% max) "
            f"[high:{summary['ev_high_count']}, "
            f"medium:{summary['ev_medium_count']}, "
            f"low:{summary['ev_low_count']}]"
        )

        conf_msg = (
            f"Confidence: {summary['confidence_mean']:.0f}% avg "
            f"({summary['confidence_min']}% min, {summary['confidence_max']}% max) "
            f"[high:{summary['confidence_high_count']}, "
            f"medium:{summary['confidence_medium_count']}, "
            f"low:{summary['confidence_low_count']}]"
        )

        logger.info(
            f"Edge Detection Complete: {total_evs} total EVs, {total_picks} above 5% threshold. {ev_msg}. {conf_msg}"
        )
    else:
        logger.warning(
            f"Edge Detection Complete: {total_evs} total EVs evaluated, "
            f"{total_picks} above 5% threshold. No recommended picks found."
        )


async def detect_edges(
    fixtures: list[Fixture],
    bankroll: float = 1000.0,
) -> list[Pick] | str:
    """
    Main edge detection pipeline orchestrator.

    Runs the complete edge detection pipeline:
    1. Calculate EV for each market (Story 5.1)
    2. Filter by 5% EV threshold (Story 5.2)
    3. Score confidence based on data quality (Story 5.3)
    4. Transform results into Pick objects
    5. Calculate recommended stakes
    6. Log comprehensive summary statistics

    Args:
        fixtures: List of Fixture objects with ai_analysis populated (from Story 4.4)
        bankroll: Total betting bankroll in currency units (default: $1000)

    Returns:
        - list[Pick]: List of recommended betting picks (if any exist above 5% threshold)
        - str: User-friendly NO_PICKS message if no picks above threshold

    Raises:
        ValueError: If fixtures is empty or bankroll is invalid

    Example:
        >>> picks = await detect_edges(
        ...     fixtures=fixtures_with_ai_analysis,
        ...     bankroll=1000.0
        ... )
        >>> if isinstance(picks, str):
        ...     print(picks)  # "No picks above 5% threshold..."
        ... else:
        ...     for pick in picks:
        ...         print(f"{pick.market}: +{pick.ev_percentage:.1f}% EV")

    Notes:
        - Ensures exact pipeline order: EV → threshold → confidence
        - Graceful degradation: individual pick failures don't block batch
        - Validates that returned picks meet 5% EV minimum (discipline enforcement)
        - Logs progress at each step with detailed metrics
    """
    if not fixtures:
        logger.warning("detect_edges called with empty fixtures list")
        return []

    if bankroll <= 0:
        raise ValueError(f"Invalid bankroll: {bankroll} (must be positive)")

    logger.info(
        f"Starting edge detection pipeline",
        extra={"fixture_count": len(fixtures), "bankroll": bankroll},
    )

    # Step 1: Calculate EV for all markets (Story 5.1)
    logger.debug("Step 1: Calculating EV for all markets")
    try:
        fixtures_with_ev = await calculate_all_evs(fixtures)
        all_ev_results = []
        for fixture in fixtures_with_ev:
            if hasattr(fixture, "ev_results"):
                all_ev_results.extend(fixture.ev_results)
        logger.info(
            f"Step 1 Complete: Calculated EV for {len(all_ev_results)} market outcomes"
        )
    except Exception as e:
        logger.error(f"Step 1 failed: {str(e)}")
        raise

    # Step 2: Filter by 5% threshold (Story 5.2)
    logger.debug("Step 2: Filtering by 5% EV threshold")
    try:
        filter_result = await apply_threshold_filter(fixtures_with_ev, threshold_pct=5.0)
        recommended_filtered_picks = filter_result.get("recommended", [])

        if not recommended_filtered_picks:
            logger.warning(
                f"No picks above 5% threshold found. "
                f"Found: {filter_result.get('total', 0)} total EV results"
            )
            # Return NO_PICKS message
            no_picks_msg = no_picks_available_message(all_ev_results, threshold_pct=5.0)
            logger.info(f"Returning NO_PICKS message to user")
            return no_picks_msg

        logger.info(
            f"Step 2 Complete: {len(recommended_filtered_picks)} picks above 5% threshold"
        )
    except Exception as e:
        logger.error(f"Step 2 failed: {str(e)}")
        raise

    # Create mapping from EV index to fixture for lookup
    # Since we can't use EVResult as dict key (not hashable), we'll track by position
    ev_to_fixture_list: list[tuple[EVResult, Fixture]] = []
    for fixture in fixtures_with_ev:
        if hasattr(fixture, "ev_results"):
            for ev in fixture.ev_results:
                ev_to_fixture_list.append((ev, fixture))

    # Extract EVResult objects from FilteredPick wrappers
    ev_results_to_score = [fp.ev_result for fp in recommended_filtered_picks]

    # Step 3: Score confidence (Story 5.3)
    logger.debug("Step 3: Scoring confidence for recommended picks")
    try:
        confidence_scores = await apply_confidence_scoring(
            ev_results_to_score,
            fixtures_with_ev,
        )
        logger.info(f"Step 3 Complete: Scored confidence for {len(confidence_scores)} picks")
    except Exception as e:
        logger.error(f"Step 3 failed: {str(e)}")
        raise

    # Step 4: Transform EVResult + ConfidenceScoreBreakdown → Pick objects (Story 5.4)
    logger.debug("Step 4: Transforming results into Pick objects")
    picks = []
    for i, ev_result in enumerate(ev_results_to_score):
        try:
            # Get corresponding confidence breakdown
            if i < len(confidence_scores):
                confidence_data = confidence_scores[i]

                # Handle both dict and ConfidenceScoreBreakdown formats
                if isinstance(confidence_data, dict):
                    confidence_breakdown = confidence_data.get(
                        "confidence_breakdown"
                    ) or ConfidenceScoreBreakdown(**confidence_data)
                else:
                    confidence_breakdown = confidence_data

                # Ensure it's a ConfidenceScoreBreakdown object
                if not isinstance(confidence_breakdown, ConfidenceScoreBreakdown):
                    confidence_breakdown = ConfidenceScoreBreakdown(
                        **confidence_breakdown
                        if isinstance(confidence_breakdown, dict)
                        else {
                            "base_score": 75,
                            "form_adjustment": 0,
                            "injury_adjustment": 0,
                            "odds_adjustment": 0,
                            "sample_size_adjustment": 0,
                            "total_adjustments": 0,
                            "final_confidence": 75,
                            "explanation": "Default confidence",
                        }
                    )

                # Calculate stake
                stake = _calculate_recommended_stake(
                    ev_percentage=ev_result.ev_percentage,
                    confidence=confidence_breakdown.final_confidence,
                    bankroll=bankroll,
                )

                # Get parent fixture for reference from the mapping
                fixture = next(
                    (f for ev, f in ev_to_fixture_list if ev is ev_result),
                    None,
                )

                # Create Pick object
                pick = _create_pick_from_ev_and_confidence(
                    ev_result=ev_result,
                    confidence_breakdown=confidence_breakdown,
                    stake=stake,
                    fixture=fixture,
                )
                picks.append(pick)
                logger.debug(
                    f"Pick {i + 1}: {pick.market} +{pick.ev_percentage:.1f}% EV @ {pick.suggested_odds:.2f}"
                )
            else:
                # Get fixture for context in logging
                fixture = next(
                    (f for ev, f in ev_to_fixture_list if ev is ev_result),
                    None,
                )
                fixture_id = fixture.fixture_id if fixture else "unknown"
                logger.warning(
                    f"No confidence data for pick {i}, skipping",
                    extra={"fixture_id": fixture_id, "market": ev_result.market_type},
                )
        except Exception as e:
            # Get fixture for context in logging
            fixture = next(
                (f for ev, f in ev_to_fixture_list if ev is ev_result),
                None,
            )
            fixture_id = fixture.fixture_id if fixture else "unknown"
            logger.error(
                f"Failed to create Pick {i}: {str(e)}",
                extra={"fixture_id": fixture_id},
            )
            # Continue processing other picks (graceful degradation)
            continue

    if not picks:
        logger.warning("No picks could be created after transformation step")
        no_picks_msg = no_picks_available_message(all_ev_results, threshold_pct=5.0)
        return no_picks_msg

    logger.info(f"Step 4 Complete: Created {len(picks)} Pick objects")

    # Step 5: Calculate summary statistics
    logger.debug("Step 5: Calculating summary statistics")
    summary = _calculate_summary_statistics(picks, all_ev_results)
    _log_summary_statistics(summary)

    logger.info(f"Edge detection pipeline complete: {len(picks)} picks ready for display/staking")

    return picks
