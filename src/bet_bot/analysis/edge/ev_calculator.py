"""
Expected Value (EV) Calculator for bet-bot application.

This module calculates expected value for each AI probability + odds pair to identify
picks with positive edge for threshold filtering in Story 5.2.

Features:
- Calculate EV using formula: EV = (AI_prob × odds) - 1
- Calculate implied probability from odds: implied_prob = 1 / odds
- Validate inputs (odds > 1.0, AI prob in [0.0, 1.0])
- Handle edge cases: invalid odds, invalid probabilities, NaN/None values
- Extract EV for all markets: match_result, total_goals, corners, cards
- Batch process multiple fixtures efficiently
- Filter EV results by threshold for Story 5.2 integration

Models:
- EVResult: Pydantic model for single EV calculation output

Functions:
- calculate_ev(ai_probability, odds) -> float | None: Core EV calculation
- calculate_implied_probability(odds) -> float | None: Bookmaker implied probability
- calculate_ev_percentage(ev_decimal) -> float: Convert decimal to percentage
- _extract_market_evs_from_fixture(fixture) -> list[EVResult]: Market-specific extraction
- calculate_all_evs(fixtures) -> list[Fixture]: Batch processing
- filter_evs_by_threshold(ev_results, threshold_pct) -> tuple: Threshold filtering

Architecture:
Input: Fixture with ai_analysis (from Story 4.4) + odds data
Output: Fixture with ev_results field populated with EVResult objects
Consumer: Story 5.2 (Threshold Filter), Story 5.3 (Confidence Scoring)

Integration:
from bet_bot.analysis.edge.ev_calculator import (
    EVResult,
    calculate_ev,
    calculate_implied_probability,
    calculate_all_evs,
    filter_evs_by_threshold
)

Usage Example:
    # Single EV calculation
    ev = calculate_ev(ai_probability=0.58, odds=2.10)
    ev_pct = calculate_ev_percentage(ev)  # 5.8%

    # Batch processing fixtures
    updated_fixtures = await calculate_all_evs(fixtures_with_ai_analysis)

    # Filter for positive EV picks
    recommended, marginal = filter_evs_by_threshold(
        ev_results=fixture.ev_results,
        threshold_pct=5.0
    )
"""

import asyncio
import logging
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from bet_bot.models.fixtures import Fixture

# Module-level logger
logger = logging.getLogger(__name__)


class EVResult(BaseModel):
    """
    Structured output for single EV calculation.

    Represents the expected value calculation result for a specific market outcome.
    Used in list[EVResult] attached to Fixture.ev_results field.

    Attributes:
        market_type: Betting market type (e.g., "match_result", "total_goals")
        outcome: Specific outcome within market (e.g., "home", "over", "draw")
        ai_probability: AI-estimated probability (0.0-1.0)
        odds: Bookmaker decimal odds (>= 1.0)
        implied_probability: Probability implied by odds (1/odds)
        ev_decimal: Expected value in decimal format (e.g., 0.058 for +5.8%)
        ev_percentage: Expected value as percentage (e.g., 5.8)
        is_valid: True if calculation succeeded, False if inputs invalid
        skip_reason: Explanation if is_valid=False (e.g., "odds <= 1.0")

    Example:
        >>> ev = EVResult(
        ...     market_type="match_result",
        ...     outcome="home",
        ...     ai_probability=0.58,
        ...     odds=2.10,
        ...     implied_probability=0.476,
        ...     ev_decimal=0.058,
        ...     ev_percentage=5.8,
        ...     is_valid=True
        ... )
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        use_enum_values=True
    )

    market_type: str = Field(
        ...,
        description="Betting market type (e.g., match_result, total_goals, corners, cards)",
        min_length=1
    )

    outcome: str = Field(
        ...,
        description="Specific outcome within market (e.g., home, over, under, draw)",
        min_length=1
    )

    ai_probability: float = Field(
        ...,
        description="AI-estimated probability (0.0-1.0)",
        ge=0.0,
        le=1.0
    )

    odds: float = Field(
        ...,
        description="Bookmaker decimal odds (>= 1.0)",
        ge=1.0
    )

    implied_probability: float = Field(
        ...,
        description="Probability implied by odds (1/odds) (0.0-1.0)",
        ge=0.0,
        le=1.0
    )

    ev_decimal: float = Field(
        ...,
        description="Expected value in decimal format (e.g., 0.058 for +5.8%)"
    )

    ev_percentage: float = Field(
        ...,
        description="Expected value as percentage (e.g., 5.8 for +5.8%)"
    )

    is_valid: bool = Field(
        default=True,
        description="True if calculation succeeded, False if inputs invalid"
    )

    skip_reason: str | None = Field(
        default=None,
        description="Explanation if is_valid=False (e.g., 'odds <= 1.0')"
    )

    @field_validator("market_type", "outcome")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate string fields are not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


def calculate_ev(ai_probability: float, odds: float) -> float | None:
    """
    Calculate expected value (EV) for a single probability + odds pair.

    Formula: EV = (ai_probability × odds) - 1

    A positive EV indicates an edge (positive expected return). For example:
    - EV = 0.058 means +5.8% expected return
    - EV = -0.19 means -19% expected return (avoid)

    Input Validation:
    - odds: Must be > 1.0 (valid bookmaker odds always > 1.0)
    - ai_probability: Must be in [0.0, 1.0]
    - Handles NaN, None, and type errors gracefully

    Args:
        ai_probability: AI-estimated probability (0.0-1.0)
        odds: Bookmaker decimal odds (> 1.0)

    Returns:
        EV decimal (e.g., 0.058) if successful, None if inputs invalid

    Side Effects:
        Logs warnings for invalid inputs at WARNING level

    Examples:
        >>> calculate_ev(0.58, 2.10)  # (0.58 * 2.10) - 1 = 0.058 (+5.8%)
        0.058

        >>> calculate_ev(0.45, 1.80)  # (0.45 * 1.80) - 1 = -0.19 (-19%)
        -0.19

        >>> calculate_ev(0.50, 1.01)  # (0.50 * 1.01) - 1 = -0.495 (-49.5%)
        -0.495

        >>> calculate_ev(0.99, 1.50)  # Valid edge case
        0.485

        >>> calculate_ev(1.5, 2.0)  # Invalid: probability > 1.0
        None

        >>> calculate_ev(0.5, 0.9)  # Invalid: odds <= 1.0
        None
    """
    try:
        # Validate odds
        if odds is None or (isinstance(odds, float) and math.isnan(odds)):
            logger.warning(f"Invalid odds: None or NaN")
            return None

        if not isinstance(odds, (int, float)):
            logger.warning(f"Invalid odds type: {type(odds).__name__}, value: {odds}")
            return None

        if odds <= 1.0:
            logger.warning(f"Invalid odds: {odds} (must be > 1.0)")
            return None

        # Validate ai_probability
        if ai_probability is None or (isinstance(ai_probability, float) and math.isnan(ai_probability)):
            logger.warning(f"Invalid ai_probability: None or NaN")
            return None

        if not isinstance(ai_probability, (int, float)):
            logger.warning(f"Invalid ai_probability type: {type(ai_probability).__name__}, value: {ai_probability}")
            return None

        if ai_probability < 0.0 or ai_probability > 1.0:
            logger.warning(f"Invalid ai_probability: {ai_probability} (must be in [0.0, 1.0])")
            return None

        # Calculate EV: EV = (ai_prob × odds) - 1
        ev = (ai_probability * odds) - 1

        return ev

    except Exception as e:
        logger.warning(f"Unexpected error calculating EV: {str(e)}")
        return None


def calculate_implied_probability(odds: float) -> float | None:
    """
    Calculate bookmaker implied probability from decimal odds.

    Formula: implied_probability = 1.0 / odds

    The implied probability represents what probability the bookmaker is
    pricing into the odds. Comparing against AI probability reveals edge.

    Input Validation:
    - odds: Must be > 1.0
    - Handles NaN, None, and type errors gracefully

    Args:
        odds: Bookmaker decimal odds (> 1.0)

    Returns:
        Implied probability (0.0-1.0) if successful, None if invalid

    Side Effects:
        Logs warnings for invalid inputs at WARNING level

    Examples:
        >>> calculate_implied_probability(2.10)  # 1/2.10
        0.476...

        >>> calculate_implied_probability(1.50)  # 1/1.50
        0.667...

        >>> calculate_implied_probability(3.50)  # 1/3.50
        0.286...

        >>> calculate_implied_probability(1.0)  # Invalid
        None

        >>> calculate_implied_probability(0.5)  # Invalid
        None
    """
    try:
        # Validate odds
        if odds is None or (isinstance(odds, float) and math.isnan(odds)):
            logger.warning(f"Invalid odds in calculate_implied_probability: None or NaN")
            return None

        if not isinstance(odds, (int, float)):
            logger.warning(f"Invalid odds type in calculate_implied_probability: {type(odds).__name__}")
            return None

        if odds <= 1.0:
            logger.warning(f"Invalid odds in calculate_implied_probability: {odds} (must be > 1.0)")
            return None

        # Calculate: 1.0 / odds
        implied_prob = 1.0 / odds

        return implied_prob

    except Exception as e:
        logger.warning(f"Unexpected error calculating implied probability: {str(e)}")
        return None


def calculate_ev_percentage(ev_decimal: float) -> float:
    """
    Convert decimal EV to percentage format.

    Simple multiplication: ev_percentage = ev_decimal × 100

    Args:
        ev_decimal: EV in decimal format (e.g., 0.058)

    Returns:
        EV as percentage (e.g., 5.8 for +5.8%)

    Examples:
        >>> calculate_ev_percentage(0.058)  # +5.8%
        5.8

        >>> calculate_ev_percentage(-0.19)  # -19%
        -19.0

        >>> calculate_ev_percentage(0.125)  # +12.5%
        12.5
    """
    return ev_decimal * 100


def _extract_market_evs_from_fixture(fixture: Fixture) -> list[EVResult]:
    """
    Extract EVResult objects for all markets in a fixture.

    Market-specific EV extraction. For each market in fixture.ai_analysis,
    calculates EV for all available outcomes using odds from fixture.odds.

    Supported Markets:
    - match_result: 3-way (home, draw, away)
    - total_goals: 2-way (over, under at multiple thresholds)
    - corners: 2-way (over_9_5, under_9_5)
    - cards: 2-way (over, under at multiple thresholds)

    Error Handling:
    - Skips market if ai_analysis missing: logs warning, continues
    - Skips outcome if odds missing: logs warning, creates EVResult with is_valid=False
    - Invalid calculation creates EVResult with is_valid=False and skip_reason

    Args:
        fixture: Fixture with ai_analysis and odds populated

    Returns:
        List of EVResult objects (may include some with is_valid=False)

    Side Effects:
        Logs at DEBUG/WARNING levels:
        - DEBUG: Processing market, outcomes extracted
        - WARNING: Missing ai_analysis, missing odds for outcomes, validation failures
    """
    ev_results: list[EVResult] = []

    # Validate fixture and ai_analysis
    if not fixture:
        logger.warning("_extract_market_evs_from_fixture: fixture is None")
        return []

    if not fixture.ai_analysis:
        logger.warning(f"Fixture {fixture.fixture_id}: No ai_analysis to extract EV from")
        return []

    # Get markets from ai_analysis
    markets = fixture.ai_analysis.markets if hasattr(fixture.ai_analysis, 'markets') else []
    if not markets:
        logger.debug(f"Fixture {fixture.fixture_id}: No markets in ai_analysis")
        return []

    # Get odds from fixture
    odds_data = fixture.odds or {}

    # Process each market
    for market in markets:
        market_type = market.market_type
        ai_prob = market.ai_probability

        logger.debug(f"Fixture {fixture.fixture_id}: Processing market '{market_type}'")

        if market_type == "match_result":
            # 3-way market: home, draw, away
            outcomes = ["home", "draw", "away"]
            odds_keys = {
                "home": ["match_result.home", "match_result_home_win"],
                "draw": ["match_result.draw", "match_result_draw"],
                "away": ["match_result.away", "match_result_away_win"]
            }

            match_result_odds = odds_data.get("match_result", {})
            for outcome in outcomes:
                # Try different odds key formats
                odds_value = None
                for key_variant in odds_keys[outcome]:
                    if "." in key_variant:
                        # Nested format not used, skip
                        continue
                    elif key_variant in match_result_odds:
                        odds_value = match_result_odds[key_variant]
                        break

                # Try simpler key format
                if odds_value is None:
                    simple_key = outcome if outcome != "draw" else "draw"
                    odds_value = match_result_odds.get(simple_key)

                if odds_value is None:
                    logger.warning(
                        f"Fixture {fixture.fixture_id}: Missing odds for "
                        f"match_result.{outcome}"
                    )
                    ev_results.append(EVResult(
                        market_type=market_type,
                        outcome=outcome,
                        ai_probability=ai_prob,
                        odds=1.0,
                        implied_probability=1.0,
                        ev_decimal=0.0,
                        ev_percentage=0.0,
                        is_valid=False,
                        skip_reason=f"Missing odds for {outcome}"
                    ))
                    continue

                # Calculate EV for this outcome
                ev = calculate_ev(ai_prob, odds_value)
                implied_prob = calculate_implied_probability(odds_value)

                if ev is not None and implied_prob is not None:
                    ev_pct = calculate_ev_percentage(ev)
                    ev_results.append(EVResult(
                        market_type=market_type,
                        outcome=outcome,
                        ai_probability=ai_prob,
                        odds=odds_value,
                        implied_probability=implied_prob,
                        ev_decimal=ev,
                        ev_percentage=ev_pct,
                        is_valid=True
                    ))
                else:
                    logger.warning(
                        f"Fixture {fixture.fixture_id}: EV calculation failed for "
                        f"match_result.{outcome} (odds={odds_value})"
                    )
                    ev_results.append(EVResult(
                        market_type=market_type,
                        outcome=outcome,
                        ai_probability=ai_prob,
                        odds=odds_value if odds_value else 1.0,
                        implied_probability=implied_prob or 1.0,
                        ev_decimal=ev or 0.0,
                        ev_percentage=calculate_ev_percentage(ev) if ev is not None else 0.0,
                        is_valid=False,
                        skip_reason="Invalid odds or probability"
                    ))

        elif market_type == "total_goals":
            # 2-way market: over, under
            outcomes = ["over", "under"]
            total_goals_odds = odds_data.get("total_goals", {})

            for outcome in outcomes:
                odds_value = total_goals_odds.get(outcome)
                if odds_value is None:
                    logger.warning(
                        f"Fixture {fixture.fixture_id}: Missing odds for "
                        f"total_goals.{outcome}"
                    )
                    ev_results.append(EVResult(
                        market_type=market_type,
                        outcome=outcome,
                        ai_probability=ai_prob,
                        odds=1.0,
                        implied_probability=1.0,
                        ev_decimal=0.0,
                        ev_percentage=0.0,
                        is_valid=False,
                        skip_reason=f"Missing odds for {outcome}"
                    ))
                    continue

                ev = calculate_ev(ai_prob, odds_value)
                implied_prob = calculate_implied_probability(odds_value)

                if ev is not None and implied_prob is not None:
                    ev_pct = calculate_ev_percentage(ev)
                    ev_results.append(EVResult(
                        market_type=market_type,
                        outcome=outcome,
                        ai_probability=ai_prob,
                        odds=odds_value,
                        implied_probability=implied_prob,
                        ev_decimal=ev,
                        ev_percentage=ev_pct,
                        is_valid=True
                    ))
                else:
                    logger.warning(
                        f"Fixture {fixture.fixture_id}: EV calculation failed for "
                        f"total_goals.{outcome}"
                    )
                    ev_results.append(EVResult(
                        market_type=market_type,
                        outcome=outcome,
                        ai_probability=ai_prob,
                        odds=odds_value if odds_value else 1.0,
                        implied_probability=implied_prob or 1.0,
                        ev_decimal=ev or 0.0,
                        ev_percentage=calculate_ev_percentage(ev) if ev is not None else 0.0,
                        is_valid=False,
                        skip_reason="Invalid odds or probability"
                    ))

        elif market_type == "corners":
            # 2-way market: over, under
            outcomes = ["over", "under"]
            corners_odds = odds_data.get("corners", {})

            for outcome in outcomes:
                odds_value = corners_odds.get(outcome)
                if odds_value is None:
                    logger.warning(
                        f"Fixture {fixture.fixture_id}: Missing odds for "
                        f"corners.{outcome}"
                    )
                    ev_results.append(EVResult(
                        market_type=market_type,
                        outcome=outcome,
                        ai_probability=ai_prob,
                        odds=1.0,
                        implied_probability=1.0,
                        ev_decimal=0.0,
                        ev_percentage=0.0,
                        is_valid=False,
                        skip_reason=f"Missing odds for {outcome}"
                    ))
                    continue

                ev = calculate_ev(ai_prob, odds_value)
                implied_prob = calculate_implied_probability(odds_value)

                if ev is not None and implied_prob is not None:
                    ev_pct = calculate_ev_percentage(ev)
                    ev_results.append(EVResult(
                        market_type=market_type,
                        outcome=outcome,
                        ai_probability=ai_prob,
                        odds=odds_value,
                        implied_probability=implied_prob,
                        ev_decimal=ev,
                        ev_percentage=ev_pct,
                        is_valid=True
                    ))
                else:
                    logger.warning(
                        f"Fixture {fixture.fixture_id}: EV calculation failed for "
                        f"corners.{outcome}"
                    )
                    ev_results.append(EVResult(
                        market_type=market_type,
                        outcome=outcome,
                        ai_probability=ai_prob,
                        odds=odds_value if odds_value else 1.0,
                        implied_probability=implied_prob or 1.0,
                        ev_decimal=ev or 0.0,
                        ev_percentage=calculate_ev_percentage(ev) if ev is not None else 0.0,
                        is_valid=False,
                        skip_reason="Invalid odds or probability"
                    ))

        elif market_type == "cards":
            # 2-way market: over, under
            outcomes = ["over", "under"]
            cards_odds = odds_data.get("cards", {})

            for outcome in outcomes:
                odds_value = cards_odds.get(outcome)
                if odds_value is None:
                    logger.warning(
                        f"Fixture {fixture.fixture_id}: Missing odds for "
                        f"cards.{outcome}"
                    )
                    ev_results.append(EVResult(
                        market_type=market_type,
                        outcome=outcome,
                        ai_probability=ai_prob,
                        odds=1.0,
                        implied_probability=1.0,
                        ev_decimal=0.0,
                        ev_percentage=0.0,
                        is_valid=False,
                        skip_reason=f"Missing odds for {outcome}"
                    ))
                    continue

                ev = calculate_ev(ai_prob, odds_value)
                implied_prob = calculate_implied_probability(odds_value)

                if ev is not None and implied_prob is not None:
                    ev_pct = calculate_ev_percentage(ev)
                    ev_results.append(EVResult(
                        market_type=market_type,
                        outcome=outcome,
                        ai_probability=ai_prob,
                        odds=odds_value,
                        implied_probability=implied_prob,
                        ev_decimal=ev,
                        ev_percentage=ev_pct,
                        is_valid=True
                    ))
                else:
                    logger.warning(
                        f"Fixture {fixture.fixture_id}: EV calculation failed for "
                        f"cards.{outcome}"
                    )
                    ev_results.append(EVResult(
                        market_type=market_type,
                        outcome=outcome,
                        ai_probability=ai_prob,
                        odds=odds_value if odds_value else 1.0,
                        implied_probability=implied_prob or 1.0,
                        ev_decimal=ev or 0.0,
                        ev_percentage=calculate_ev_percentage(ev) if ev is not None else 0.0,
                        is_valid=False,
                        skip_reason="Invalid odds or probability"
                    ))

    logger.debug(f"Fixture {fixture.fixture_id}: Extracted {len(ev_results)} EV results")
    return ev_results


async def calculate_all_evs(fixtures: list[Fixture]) -> list[Fixture]:
    """
    Batch process fixtures to calculate EV for all available markets.

    Iterates through fixtures, calculates EV for all markets, attaches
    ev_results to each fixture. Handles failures gracefully (one fixture
    failure doesn't block others).

    Error Handling:
    - Skips fixture if no ai_analysis: logs warning, continues with next
    - Sets fixture.error_message on failure (never raises exception)
    - Logs progress: "Processing X of Y (fixture_id)"
    - Logs summary: "Calculated EV for N fixtures, M markets"

    Args:
        fixtures: List of fixtures with ai_analysis populated (from Story 4.4)

    Returns:
        List of fixtures with ev_results field populated
        (some may have error_message if calculation failed)

    Side Effects:
        Logs at INFO/DEBUG/WARNING levels:
        - INFO: Progress "Processing X of Y", summary at end
        - DEBUG: EV extraction details
        - WARNING: Missing ai_analysis, calculation failures

    Examples:
        >>> updated = await calculate_all_evs(fixtures_with_ai_analysis)
        >>> for fixture in updated:
        ...     print(f"{fixture.fixture_id}: {len(fixture.ev_results)} EV results")
    """
    if not fixtures:
        logger.info("calculate_all_evs: No fixtures to process")
        return []

    logger.info(f"Starting EV calculation for {len(fixtures)} fixtures")

    results = []
    total_ev_count = 0
    failures = 0

    for idx, fixture in enumerate(fixtures, 1):
        try:
            fixture_key = (
                f"{fixture.home_team.name} vs {fixture.away_team.name}"
                if fixture.home_team and fixture.away_team
                else fixture.fixture_id
            )
            logger.info(f"Calculating EV for fixture {idx}/{len(fixtures)}: {fixture_key}")

            # Extract EV results for this fixture
            ev_results = _extract_market_evs_from_fixture(fixture)

            # Attach to fixture
            fixture.ev_results = ev_results

            total_ev_count += len(ev_results)
            results.append(fixture)

            logger.debug(
                f"Fixture {fixture.fixture_id}: Calculated {len(ev_results)} EV results"
            )

        except Exception as e:
            logger.error(f"Error calculating EV for fixture {idx}: {str(e)}")
            if fixture:
                fixture.error_message = f"EV calculation failed: {str(e)}"
                results.append(fixture)
            failures += 1

    # Log summary
    successes = len(results) - failures
    logger.info(
        f"EV calculation complete: {successes}/{len(fixtures)} successful, "
        f"{failures} failures, {total_ev_count} total EV results calculated"
    )

    return results


def filter_evs_by_threshold(
    ev_results: list[EVResult],
    threshold_pct: float = 5.0
) -> tuple[list[EVResult], list[EVResult]]:
    """
    Filter EV results by threshold (for Story 5.2 integration).

    Splits EVResult list into two groups: above threshold (recommended picks)
    and below threshold (marginal picks).

    Threshold Behavior:
    - Positive EV > threshold: included in "above" group
    - EV <= threshold: included in "below" group
    - Invalid results (is_valid=False): included in "below" group

    Args:
        ev_results: List of EVResult objects to filter
        threshold_pct: Threshold in percentage (default 5.0 for +5%)

    Returns:
        Tuple of (above_threshold, below_threshold) lists

    Side Effects:
        Logs at DEBUG level: filter summary (counts and percentage)

    Examples:
        >>> recommended, marginal = filter_evs_by_threshold(
        ...     ev_results=fixture.ev_results,
        ...     threshold_pct=5.0
        ... )
        >>> print(f"Recommended: {len(recommended)}, Marginal: {len(marginal)}")

        >>> # Custom threshold
        >>> aggressive, conservative = filter_evs_by_threshold(
        ...     ev_results=fixture.ev_results,
        ...     threshold_pct=2.0  # More aggressive
        ... )
    """
    above = []
    below = []

    for ev in ev_results:
        # Invalid results go to "below"
        if not ev.is_valid:
            below.append(ev)
        # Check threshold
        elif ev.ev_percentage >= threshold_pct:
            above.append(ev)
        else:
            below.append(ev)

    logger.debug(
        f"Filtered EV results: {len(above)} above {threshold_pct}% "
        f"({100*len(above)/max(len(ev_results),1):.1f}%), "
        f"{len(below)} below/invalid"
    )

    return above, below
