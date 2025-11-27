"""
Threshold Filter for Edge Detection in bet-bot application.

This module filters expected value (EV) calculations to identify betting picks
that meet or exceed the 5% EV threshold, enforcing disciplined edge detection.

The 5% threshold is non-negotiable and represents the core discipline of the system:
- No picks below 5% EV should ever be recommended to the user
- MARGINAL picks (2-5% EV) are logged but explicitly not recommended
- The system treats "NO PICKS AVAILABLE" as a normal, expected output
- This prevents emotional betting and overconfidence

Features:
- Separate EV results into RECOMMENDED (≥5%), MARGINAL (2-5%), LOW (<2%), and INVALID
- Validate that no picks below 5% threshold exist in main output
- Generate structured "NO PICKS AVAILABLE" message when zero recommended picks found
- Batch process multiple fixtures with graceful error handling
- Log filtering summary with breakdown by category

Models:
- PickCategory: Enum for pick classification (RECOMMENDED, MARGINAL, LOW, INVALID)
- FilteredPick: Pydantic model for categorized pick with reasoning

Functions:
- filter_picks_by_threshold(ev_results, threshold_pct) -> tuple: Separate by threshold
- categorize_picks(ev_results) -> dict: Categorize into 4 buckets
- validate_threshold_enforcement(picks) -> bool: Verify all picks meet 5% minimum
- verify_no_threshold_bypass(recommended_picks, all_picks) -> bool: Detect breaches
- no_picks_available_message(ev_results, threshold_pct) -> str: User-friendly message
- apply_threshold_filter(fixtures, threshold_pct) -> dict: Batch orchestration

Architecture:
Input: Fixture with ev_results from Story 5.1 (EVResult objects)
Output: Filtered picks with categories, summary stats, and no-picks messaging
Consumer: Story 5.3 (Confidence Scoring), Story 5.4 (Edge Detection Pipeline)

Integration:
from bet_bot.analysis.edge.threshold_filter import (
    PickCategory,
    FilteredPick,
    filter_picks_by_threshold,
    categorize_picks,
    validate_threshold_enforcement,
    apply_threshold_filter,
    no_picks_available_message
)

Usage Example:
    # Separate picks by threshold
    recommended, marginal = filter_picks_by_threshold(
        ev_results=fixture.ev_results,
        threshold_pct=5.0
    )

    # Categorize all picks
    categorized = categorize_picks(fixture.ev_results)
    print(f"RECOMMENDED: {len(categorized['RECOMMENDED'])}")
    print(f"MARGINAL: {len(categorized['MARGINAL'])}")

    # Batch process multiple fixtures
    results = await apply_threshold_filter(
        fixtures=fixtures_with_ev_results,
        threshold_pct=5.0
    )
    if not results['has_picks']:
        print(results['no_picks_message'])
"""

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from bet_bot.analysis.edge.ev_calculator import EVResult
from bet_bot.models.fixtures import Fixture

# Module-level logger
logger = logging.getLogger(__name__)


class PickCategory(str, Enum):
    """
    Enum for pick classification based on expected value.

    Values:
    - RECOMMENDED: EV >= 5% (recommended for betting)
    - MARGINAL: 2% <= EV < 5% (borderline, not recommended)
    - LOW: 0% <= EV < 2% (minimal edge)
    - INVALID: is_valid == False (insufficient data)
    """

    RECOMMENDED = "RECOMMENDED"
    MARGINAL = "MARGINAL"
    LOW = "LOW"
    INVALID = "INVALID"


class FilteredPick(BaseModel):
    """
    Pydantic model for a categorized pick with reasoning.

    Represents an EV result with its category assignment and explanation.

    Attributes:
        ev_result: The EVResult object from Story 5.1
        category: PickCategory (RECOMMENDED, MARGINAL, LOW, or INVALID)
        category_reason: Human-readable explanation (e.g., "EV 5.8% >= 5.0% threshold")
        recommended: Boolean flag (True if RECOMMENDED, False otherwise)

    Validation:
    - category and recommended must be consistent (RECOMMENDED → recommended=True)

    Example:
        >>> pick = FilteredPick(
        ...     ev_result=EVResult(...),
        ...     category=PickCategory.RECOMMENDED,
        ...     category_reason="EV 5.8% >= 5.0% threshold",
        ...     recommended=True
        ... )
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        use_enum_values=False
    )

    ev_result: EVResult = Field(
        ...,
        description="The EVResult object from Story 5.1"
    )

    category: PickCategory = Field(
        ...,
        description="Pick classification (RECOMMENDED, MARGINAL, LOW, INVALID)"
    )

    category_reason: str = Field(
        ...,
        description="Explanation for category assignment",
        min_length=1
    )

    recommended: bool = Field(
        ...,
        description="True if RECOMMENDED, False otherwise"
    )

    @field_validator("category_reason")
    @classmethod
    def validate_non_empty_reason(cls, v: str) -> str:
        """Validate category_reason is not empty."""
        if not v or not v.strip():
            raise ValueError("Category reason cannot be empty")
        return v.strip()

    @field_validator("recommended")
    @classmethod
    def validate_consistency(cls, v: bool, info: ValidationInfo) -> bool:
        """Validate that category and recommended are consistent."""
        if "category" in info.data:
            category = info.data["category"]
            if category == PickCategory.RECOMMENDED and not v:
                raise ValueError("RECOMMENDED category must have recommended=True")
            if category != PickCategory.RECOMMENDED and v:
                raise ValueError("Non-RECOMMENDED category must have recommended=False")
        return v


def filter_picks_by_threshold(
    ev_results: list[EVResult],
    threshold_pct: float = 5.0
) -> tuple[list[EVResult], list[EVResult]]:
    """
    Filter EV results by threshold, separating recommended from marginal picks.

    Splits EVResult list into two groups:
    - above_threshold: EV >= threshold (recommended picks)
    - below_threshold: EV < threshold (marginal/invalid picks)

    Threshold Validation:
    - threshold_pct must be >= 0.0 (non-negative)
    - threshold_pct must be <= 100.0 (realistic percentage)
    - Raises ValueError if threshold invalid

    Filtering Logic:
    - Invalid results (is_valid=False) → below_threshold
    - ev_percentage >= threshold_pct → above_threshold
    - ev_percentage < threshold_pct → below_threshold

    Args:
        ev_results: List of EVResult objects to filter
        threshold_pct: Threshold in percentage (default 5.0 for +5%). Must be 0.0-100.0.

    Returns:
        Tuple of (above_threshold, below_threshold) EVResult lists

    Raises:
        ValueError: If threshold_pct < 0.0 or > 100.0

    Side Effects:
        Logs at DEBUG level: filter summary with counts and percentage

    Examples:
        >>> recommended, marginal = filter_picks_by_threshold(
        ...     ev_results=[EVResult(...), ...],
        ...     threshold_pct=5.0
        ... )
        >>> print(f"Recommended: {len(recommended)}, Marginal: {len(marginal)}")

        >>> # Empty input
        >>> above, below = filter_picks_by_threshold([], 5.0)
        >>> print(above, below)  # ([], [])

        >>> # Boundary condition: exactly at threshold
        >>> # EV 5.0% with 5.0% threshold → above_threshold (inclusive)
    """
    # Validate threshold
    if threshold_pct < 0.0:
        raise ValueError(f"Threshold cannot be negative: {threshold_pct}")
    if threshold_pct > 100.0:
        raise ValueError(f"Threshold cannot exceed 100%: {threshold_pct}")

    above = []
    below = []

    for ev in ev_results:
        # Invalid results go to "below"
        if not ev.is_valid:
            below.append(ev)
        # Check threshold (inclusive: >= threshold)
        elif ev.ev_percentage >= threshold_pct:
            above.append(ev)
        else:
            below.append(ev)

    # Calculate percentage for logging
    total = len(ev_results) if ev_results else 1
    above_pct = 100.0 * len(above) / total

    logger.debug(
        f"Filtered EV results: {len(above)} above {threshold_pct}% threshold "
        f"({above_pct:.1f}%), {len(below)} below/invalid"
    )

    return above, below


def categorize_picks(ev_results: list[EVResult]) -> dict[str, list[EVResult]]:
    """
    Categorize EV results into RECOMMENDED, MARGINAL, LOW, and INVALID buckets.

    Categorization Rules:
    - RECOMMENDED: ev_percentage >= 5.0 (meets minimum threshold)
    - MARGINAL: 2.0 <= ev_percentage < 5.0 (borderline picks)
    - LOW: 0.0 <= ev_percentage < 2.0 (minimal edge)
    - INVALID: is_valid == False (insufficient data for EV calculation)

    All input picks are categorized (no picks excluded or dropped).

    Args:
        ev_results: List of EVResult objects to categorize

    Returns:
        Dictionary with category keys mapping to EVResult lists:
        {
            "RECOMMENDED": [...],
            "MARGINAL": [...],
            "LOW": [...],
            "INVALID": [...]
        }

    Side Effects:
        Logs at DEBUG level: categorization summary with counts per category

    Examples:
        >>> categorized = categorize_picks(ev_results)
        >>> print(f"RECOMMENDED: {len(categorized['RECOMMENDED'])}")
        >>> print(f"MARGINAL: {len(categorized['MARGINAL'])}")
        >>> print(f"LOW: {len(categorized['LOW'])}")
        >>> print(f"INVALID: {len(categorized['INVALID'])}")

        >>> # Verify all picks accounted for
        >>> total_input = len(ev_results)
        >>> total_output = sum(len(picks) for picks in categorized.values())
        >>> assert total_input == total_output  # Should always be true
    """
    recommended = []
    marginal = []
    low = []
    invalid = []

    for ev in ev_results:
        if not ev.is_valid:
            invalid.append(ev)
        elif ev.ev_percentage >= 5.0:
            recommended.append(ev)
        elif ev.ev_percentage >= 2.0:
            marginal.append(ev)
        else:
            low.append(ev)

    logger.debug(
        f"Categorized {len(ev_results)} EV results: "
        f"{len(recommended)} RECOMMENDED, "
        f"{len(marginal)} MARGINAL, "
        f"{len(low)} LOW, "
        f"{len(invalid)} INVALID"
    )

    return {
        "RECOMMENDED": recommended,
        "MARGINAL": marginal,
        "LOW": low,
        "INVALID": invalid
    }


def validate_threshold_enforcement(picks: list[EVResult]) -> bool:
    """
    Validate that all picks meet the 5% EV threshold (discipline enforcement).

    This is a critical safety check to ensure no picks below 5% EV are ever
    recommended. The 5% threshold is non-negotiable and prevents emotional betting.

    Validation:
    - All picks must have ev_percentage >= 5.0
    - Raises ValueError if any pick violates threshold
    - Returns True if all picks are valid

    Args:
        picks: List of EVResult objects to validate

    Returns:
        True if all picks >= 5% EV threshold

    Raises:
        ValueError: If any pick has ev_percentage < 5.0 (discipline violation)

    Side Effects:
        Logs at WARNING level: any threshold violations

    Examples:
        >>> # All picks valid (>= 5%)
        >>> validate_threshold_enforcement([EVResult(...), EVResult(...)])
        True

        >>> # Discipline violation detected
        >>> validate_threshold_enforcement([EVResult(ev_percentage=4.5), ...])
        ValueError: Pick violates 5% threshold: EV 4.5% < 5.0%

        >>> # Empty list
        >>> validate_threshold_enforcement([])
        True
    """
    for pick in picks:
        if pick.ev_percentage < 5.0:
            error_msg = (
                f"Pick violates 5% threshold: "
                f"{pick.market_type}.{pick.outcome} EV {pick.ev_percentage}% < 5.0%"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    return True


def verify_no_threshold_bypass(
    recommended_picks: list[EVResult],
    all_picks: list[EVResult]
) -> bool:
    """
    Verify that recommended_picks is a valid subset of all_picks with correct thresholds.

    This function detects if:
    1. A pick in recommended_picks was not in all_picks (added incorrectly)
    2. A pick in recommended_picks has EV < 5% (threshold bypass)
    3. A pick below 5% threshold exists in recommended_picks (discipline breach)

    Args:
        recommended_picks: List of picks marked as recommended (EV >= 5%)
        all_picks: Full list of picks before filtering

    Returns:
        True if recommended_picks is valid subset of all_picks

    Side Effects:
        Logs at WARNING level: any discrepancies found

    Examples:
        >>> recommended = [pick1, pick2]  # Both with EV >= 5%
        >>> all_picks = [pick1, pick2, pick3]  # pick3 has EV < 5%
        >>> verify_no_threshold_bypass(recommended, all_picks)
        True

        >>> # Tampered picks (bypassed threshold)
        >>> recommended = [pick_below_5pct]
        >>> verify_no_threshold_bypass(recommended, all_picks)
        # Logs warning and returns False (after checks)
    """
    # Create a set of pick IDs for quick lookup
    all_pick_ids = {
        (p.market_type, p.outcome, p.ev_percentage) for p in all_picks
    }

    for pick in recommended_picks:
        # Check if pick is in original all_picks
        pick_id = (pick.market_type, pick.outcome, pick.ev_percentage)
        if pick_id not in all_pick_ids:
            logger.warning(
                f"Recommended pick not in original all_picks: "
                f"{pick.market_type}.{pick.outcome} EV {pick.ev_percentage}%"
            )
            return False

        # Check threshold (shouldn't happen, but verify)
        if pick.ev_percentage < 5.0:
            logger.warning(
                f"Recommended pick below 5% threshold: "
                f"{pick.market_type}.{pick.outcome} EV {pick.ev_percentage}%"
            )
            return False

    return True


def no_picks_available_message(
    ev_results: list[EVResult],
    threshold_pct: float = 5.0
) -> str:
    """
    Generate a structured "NO PICKS AVAILABLE" message for users.

    Called when zero RECOMMENDED picks exist after filtering. Provides:
    - Summary of what was found (MARGINAL, LOW, INVALID counts)
    - Contextual information for users
    - Suggestions for next steps

    Args:
        ev_results: Full list of EVResult objects (before filtering)
        threshold_pct: Threshold percentage (default 5.0)

    Returns:
        Formatted string suitable for terminal display

    Examples:
        >>> msg = no_picks_available_message(ev_results, 5.0)
        >>> print(msg)
        📋 NO PICKS AVAILABLE
        0 picks meet the 5% EV threshold.
        ...
    """
    # Categorize all picks
    categorized = categorize_picks(ev_results)

    marginal_count = len(categorized["MARGINAL"])
    low_count = len(categorized["LOW"])
    invalid_count = len(categorized["INVALID"])

    message = f"""📋 NO PICKS AVAILABLE

0 picks meet the {threshold_pct}% EV threshold.

Summary:
"""

    if marginal_count > 0:
        message += f"- {marginal_count} pick{'s' if marginal_count != 1 else ''} with MARGINAL EV (2%-{threshold_pct}%): Review these for potential opportunity\n"

    if low_count > 0:
        message += f"- {low_count} pick{'s' if low_count != 1 else ''} with LOW EV (<2%): No edge, skip\n"

    if invalid_count > 0:
        message += f"- {invalid_count} pick{'s' if invalid_count != 1 else ''} with INVALID data: Insufficient odds/probability data\n"

    message += """
💡 Next Steps:
1. Review MARGINAL picks if you have custom risk tolerance
2. Check data quality (odds freshness, injury updates)
3. Try again with different leagues or timeframe"""

    return message


async def apply_threshold_filter(
    fixtures: list[Fixture],
    threshold_pct: float = 5.0
) -> dict[str, Any]:
    """
    Batch process fixtures to filter and categorize picks by EV threshold.

    Orchestrates threshold filtering across multiple fixtures:
    1. Extracts ev_results from all fixtures
    2. Categorizes picks into RECOMMENDED, MARGINAL, LOW, INVALID
    3. Validates recommended picks meet 5% threshold (discipline)
    4. Logs filtering summary with breakdowns
    5. Generates "NO PICKS AVAILABLE" message if needed

    Error Handling (Graceful Degradation):
    - One fixture failure doesn't block others
    - Failed fixtures logged, processing continues
    - Returns error message in result if entire batch fails

    Args:
        fixtures: List of Fixture objects with ev_results populated
        threshold_pct: EV threshold percentage (default 5.0, non-negotiable)

    Returns:
        Dictionary with structure:
        {
            "recommended": list[EVResult],  # EV >= 5%
            "marginal": list[EVResult],     # 2% <= EV < 5%
            "low": list[EVResult],          # 0% <= EV < 2%
            "invalid": list[EVResult],      # is_valid == False
            "total_evaluated": int,         # Total picks processed
            "total_recommended": int,       # Count of RECOMMENDED picks
            "threshold_pct": float,         # Threshold used
            "has_picks": bool,              # True if >=1 RECOMMENDED pick
            "no_picks_message": str | None  # Only populated if has_picks=False
        }

    Side Effects:
        Logs at INFO/DEBUG/WARNING levels:
        - INFO: Progress (processing fixture X of Y)
        - INFO: Summary (total evaluated, category breakdown, threshold)
        - WARNING: Any processing failures per fixture
        - DEBUG: Per-fixture details

    Examples:
        >>> results = await apply_threshold_filter(
        ...     fixtures=fixtures_with_ev_results,
        ...     threshold_pct=5.0
        ... )
        >>> if results['has_picks']:
        ...     print(f"Found {results['total_recommended']} recommended picks")
        ... else:
        ...     print(results['no_picks_message'])
    """
    # Validate inputs
    if not fixtures:
        logger.warning("apply_threshold_filter: No fixtures to process")
        return {
            "recommended": [],
            "marginal": [],
            "low": [],
            "invalid": [],
            "total_evaluated": 0,
            "total_recommended": 0,
            "threshold_pct": threshold_pct,
            "has_picks": False,
            "no_picks_message": "No fixtures to evaluate. Try running data fetching again."
        }

    logger.info(f"Starting threshold filtering for {len(fixtures)} fixtures")

    # Collect all EV results
    all_ev_results: list[EVResult] = []
    processing_errors = []

    for idx, fixture in enumerate(fixtures, 1):
        try:
            fixture_key = (
                f"{fixture.home_team.name} vs {fixture.away_team.name}"
                if fixture.home_team and fixture.away_team
                else fixture.fixture_id
            )
            logger.info(
                f"Filtering picks for fixture {idx}/{len(fixtures)}: {fixture_key}"
            )

            # Get EV results from fixture
            ev_results = fixture.ev_results if hasattr(fixture, 'ev_results') else []
            if not ev_results:
                logger.warning(
                    f"Fixture {fixture.fixture_id}: No EV results to filter"
                )
                continue

            all_ev_results.extend(ev_results)
            logger.debug(
                f"Fixture {fixture.fixture_id}: Added {len(ev_results)} EV results"
            )

        except Exception as e:
            error_msg = f"Error processing fixture {idx}: {str(e)}"
            logger.warning(error_msg)
            processing_errors.append(error_msg)
            continue

    # Categorize all picks
    categorized = categorize_picks(all_ev_results)

    recommended = categorized["RECOMMENDED"]
    marginal = categorized["MARGINAL"]
    low = categorized["LOW"]
    invalid = categorized["INVALID"]

    # Validate threshold enforcement on recommended picks
    try:
        if recommended:
            validate_threshold_enforcement(recommended)
    except ValueError as e:
        logger.error(f"Threshold enforcement validation failed: {str(e)}")
        # Don't raise, just log and continue

    # Generate "NO PICKS" message if needed
    no_picks_msg = None
    if not recommended:
        no_picks_msg = no_picks_available_message(all_ev_results, threshold_pct)

    # Log summary
    logger.info(
        f"Threshold filtering complete: {len(all_ev_results)} total evaluated, "
        f"{len(recommended)} RECOMMENDED (>={threshold_pct}%), "
        f"{len(marginal)} MARGINAL, "
        f"{len(low)} LOW, "
        f"{len(invalid)} INVALID"
    )

    if processing_errors:
        logger.warning(f"Processing errors: {len(processing_errors)} fixtures failed")

    return {
        "recommended": recommended,
        "marginal": marginal,
        "low": low,
        "invalid": invalid,
        "total_evaluated": len(all_ev_results),
        "total_recommended": len(recommended),
        "threshold_pct": threshold_pct,
        "has_picks": len(recommended) > 0,
        "no_picks_message": no_picks_msg
    }
