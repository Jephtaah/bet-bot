"""
Confidence Scoring Logic for bet-bot application.

This module scores confidence in each betting recommendation based on data quality
and freshness. Confidence represents the reliability of each pick, accounting for
how fresh the input data is (form, injuries, odds).

Overview:
---------
- Base confidence: 75% (neutral starting point)
- Adjustments: +/- points based on data freshness and completeness
- Final range: Clamped to [0, 100]%

Adjustments:
- Form freshness (< 24h: +15, 24-48h: +10, > 48h: -5)
- Injury data (< 12h: +5, missing or > 12h: -10)
- Odds freshness (< 30min: +5, 30-60min: -5, > 60min: -10)
- Form sample size (>= 10 games: 0, >= 5 games: 0, < 5 games: -10)

Architecture:
- Receives EVResult and Fixture from Stories 5.1 and 5.2
- Produces ConfidenceScoreBreakdown with detailed breakdown
- Feeds into Stake Sizing (Story 6.1) for bet sizing decisions
- Returns human-readable explanation for user understanding

Models:
- ConfidenceScoreBreakdown: Pydantic model for structured scoring output

Functions:
- calculate_base_score() -> int: Return base confidence (75)
- score_form_freshness(form_timestamp: datetime | None) -> int: Form data age points
- score_injury_freshness(injury_timestamp: datetime | None) -> int: Injury data age points
- score_odds_freshness(odds_timestamp: datetime | None) -> int: Odds data age points
- score_form_sample_size(games_count: int) -> int: Sample size penalty
- score_pick(ev_result: EVResult, fixture: Fixture) -> ConfidenceScoreBreakdown: Single pick
- apply_confidence_scoring(picks: list[EVResult], fixtures: list[Fixture]) -> list[dict]: Batch

Usage:
------
    from bet_bot.analysis.edge.confidence_scorer import (
        ConfidenceScoreBreakdown,
        score_pick,
        apply_confidence_scoring
    )

    # Single pick scoring
    breakdown = await score_pick(ev_result, fixture)
    print(f"Confidence: {breakdown.final_confidence}%")
    print(f"Breakdown: {breakdown.explanation}")

    # Batch scoring
    picks_with_confidence = await apply_confidence_scoring(recommended_picks, fixtures)
    for pick in picks_with_confidence:
        print(f"{pick['market_type']}.{pick['outcome']}: {pick['confidence_breakdown']['final_confidence']}%")
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from bet_bot.models.fixtures import Fixture
from bet_bot.analysis.edge.ev_calculator import EVResult

# Module-level logger
logger = logging.getLogger(__name__)


class ConfidenceScoreBreakdown(BaseModel):
    """
    Structured output for confidence scoring with detailed breakdown.

    Represents the complete confidence scoring result for a single pick,
    including all components and a human-readable explanation.

    Attributes:
        base_score: Always 75 (baseline confidence before adjustments)
        form_adjustment: Points for form data freshness (-10 to +15)
        injury_adjustment: Points for injury data availability (-10 to +5)
        odds_adjustment: Points for odds data freshness (-10 to +5)
        sample_size_adjustment: Penalty for small sample size (-10 to 0)
        total_adjustments: Sum of all adjustments
        final_confidence: Clamped to [0, 100] range
        explanation: Human-readable breakdown (e.g., "Fresh form (+15) but small sample (-10)")

    Example:
        >>> breakdown = ConfidenceScoreBreakdown(
        ...     base_score=75,
        ...     form_adjustment=15,
        ...     injury_adjustment=0,
        ...     odds_adjustment=-5,
        ...     sample_size_adjustment=0,
        ...     total_adjustments=10,
        ...     final_confidence=85,
        ...     explanation="Fresh form (+15) but slightly stale odds (-5)"
        ... )
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        use_enum_values=True
    )

    base_score: int = Field(
        default=75,
        description="Baseline confidence score (always 75)",
        ge=75,
        le=75
    )

    form_adjustment: int = Field(
        ...,
        description="Form data freshness adjustment (-10 to +15)",
        ge=-10,
        le=15
    )

    injury_adjustment: int = Field(
        ...,
        description="Injury data freshness adjustment (-10 to +5)",
        ge=-10,
        le=5
    )

    odds_adjustment: int = Field(
        ...,
        description="Odds data freshness adjustment (-10 to +5)",
        ge=-10,
        le=5
    )

    sample_size_adjustment: int = Field(
        ...,
        description="Form sample size penalty (-10 to 0)",
        ge=-10,
        le=0
    )

    total_adjustments: int = Field(
        ...,
        description="Sum of all adjustments"
    )

    final_confidence: int = Field(
        ...,
        description="Final confidence score clamped to [0, 100]",
        ge=0,
        le=100
    )

    explanation: str = Field(
        ...,
        description="Human-readable explanation of confidence breakdown",
        min_length=1
    )

    @field_validator("base_score")
    @classmethod
    def validate_base_score(cls, v: int) -> int:
        """Base score must always be exactly 75."""
        if v != 75:
            raise ValueError("base_score must be exactly 75")
        return v

    @field_validator("total_adjustments")
    @classmethod
    def validate_total_adjustments(cls, v: int, info) -> int:
        """Total adjustments must be sum of individual adjustments."""
        if "form_adjustment" in info.data and "injury_adjustment" in info.data and \
           "odds_adjustment" in info.data and "sample_size_adjustment" in info.data:
            expected = (
                info.data["form_adjustment"] +
                info.data["injury_adjustment"] +
                info.data["odds_adjustment"] +
                info.data["sample_size_adjustment"]
            )
            if v != expected:
                raise ValueError(f"total_adjustments ({v}) must be sum of components ({expected})")
        return v

    @field_validator("final_confidence")
    @classmethod
    def validate_final_confidence(cls, v: int, info) -> int:
        """Final confidence must equal base_score + total_adjustments, clamped to [0, 100]."""
        if "base_score" in info.data and "total_adjustments" in info.data:
            calculated = info.data["base_score"] + info.data["total_adjustments"]
            expected = max(0, min(100, calculated))
            if v != expected:
                raise ValueError(f"final_confidence ({v}) must be base + adjustments clamped to [0, 100] ({expected})")
        return v


def calculate_base_score() -> int:
    """
    Calculate baseline confidence score.

    The base confidence is a neutral starting point of 75%. This represents
    a "moderate confidence" level before considering data freshness adjustments.
    Adjustments (positive or negative) are then applied based on data quality.

    Returns:
        int: Always 75 (baseline confidence percentage)

    Examples:
        >>> calculate_base_score()
        75

        >>> base = calculate_base_score()
        >>> confidence = base + form_adjustment + injury_adjustment  # Further adjustments
    """
    return 75


def score_form_freshness(form_timestamp: datetime | None) -> int:
    """
    Score form data freshness.

    Form data quality impacts confidence. Fresh form (< 24 hours) suggests
    the form estimate is accurate. Stale form (> 48 hours) reduces confidence
    because recent results may have changed the team's form significantly.

    Scoring:
    - < 24 hours old: +15 points (data very fresh)
    - 24-48 hours old: +10 points (data acceptable)
    - > 48 hours old: -5 points (data stale, confidence reduced)
    - None (missing): 0 points (neutral, no penalty)

    Args:
        form_timestamp: Datetime when form data was last fetched (timezone-aware UTC)
                       None if form data not available

    Returns:
        int: Adjustment points (-5 to +15)

    Examples:
        >>> from datetime import datetime, timezone, timedelta
        >>> now = datetime.now(timezone.utc)

        >>> # Fresh form (20 minutes old)
        >>> form_ts = now - timedelta(minutes=20)
        >>> score_form_freshness(form_ts)
        15

        >>> # Old form (60 hours old)
        >>> form_ts = now - timedelta(hours=60)
        >>> score_form_freshness(form_ts)
        -5

        >>> # No form data
        >>> score_form_freshness(None)
        0
    """
    if form_timestamp is None:
        return 0

    try:
        age = datetime.now(timezone.utc) - form_timestamp
        age_hours = age.total_seconds() / 3600

        if age_hours < 24:
            return 15  # Fresh form
        elif age_hours < 48:
            return 10  # Acceptable age
        else:
            return -5  # Stale form

    except Exception as e:
        logger.warning(f"Error calculating form freshness: {str(e)}")
        return 0


def score_injury_freshness(injury_timestamp: datetime | None) -> int:
    """
    Score injury data freshness.

    Injury information directly impacts match prediction. Fresh injury data
    (< 12 hours) ensures we know the current squad. Missing or stale injury
    data is risky - key players may be newly injured, causing our prediction
    to be based on incorrect information.

    Scoring:
    - < 12 hours old: +5 points (current injury status known)
    - >= 12 hours old or None: -10 points (stale or missing, high risk)

    Args:
        injury_timestamp: Datetime when injury data was last fetched (timezone-aware UTC)
                         None if injury data not available

    Returns:
        int: Adjustment points (-10 or +5)

    Examples:
        >>> from datetime import datetime, timezone, timedelta
        >>> now = datetime.now(timezone.utc)

        >>> # Fresh injuries (5 hours old)
        >>> inj_ts = now - timedelta(hours=5)
        >>> score_injury_freshness(inj_ts)
        5

        >>> # Stale injuries (24 hours old)
        >>> inj_ts = now - timedelta(hours=24)
        >>> score_injury_freshness(inj_ts)
        -10

        >>> # No injury data
        >>> score_injury_freshness(None)
        -10
    """
    if injury_timestamp is None:
        return -10  # Missing injury data is penalized

    try:
        age = datetime.now(timezone.utc) - injury_timestamp
        age_hours = age.total_seconds() / 3600

        if age_hours < 12:
            return 5  # Fresh injury data
        else:
            return -10  # Stale injury data

    except Exception as e:
        logger.warning(f"Error calculating injury freshness: {str(e)}")
        return -10


def score_odds_freshness(odds_timestamp: datetime | None) -> int:
    """
    Score odds data freshness.

    Odds change frequently as money comes in. Fresh odds (< 30 minutes)
    reflect the current market consensus. Stale odds (> 60 minutes) may
    misrepresent current market sentiment, reducing edge reliability.

    Scoring:
    - < 30 minutes old: +5 points (very fresh, high confidence)
    - 30-60 minutes old: -5 points (slightly stale, some concern)
    - > 60 minutes old: -10 points (stale, significant concern)
    - None (missing): 0 points (neutral, we'll use available odds)

    Args:
        odds_timestamp: Datetime when odds were last fetched (timezone-aware UTC)
                       None if odds not available

    Returns:
        int: Adjustment points (-10 to +5)

    Examples:
        >>> from datetime import datetime, timezone, timedelta
        >>> now = datetime.now(timezone.utc)

        >>> # Fresh odds (10 minutes old)
        >>> odds_ts = now - timedelta(minutes=10)
        >>> score_odds_freshness(odds_ts)
        5

        >>> # Medium-aged odds (45 minutes old)
        >>> odds_ts = now - timedelta(minutes=45)
        >>> score_odds_freshness(odds_ts)
        -5

        >>> # Very stale odds (2 hours old)
        >>> odds_ts = now - timedelta(hours=2)
        >>> score_odds_freshness(odds_ts)
        -10

        >>> # No odds data
        >>> score_odds_freshness(None)
        0
    """
    if odds_timestamp is None:
        return 0

    try:
        age = datetime.now(timezone.utc) - odds_timestamp
        age_minutes = age.total_seconds() / 60

        if age_minutes < 30:
            return 5  # Very fresh odds
        elif age_minutes < 60:
            return -5  # Moderately stale
        else:
            return -10  # Very stale

    except Exception as e:
        logger.warning(f"Error calculating odds freshness: {str(e)}")
        return 0


def score_form_sample_size(games_count: int) -> int:
    """
    Score form data sample size.

    Form is calculated from recent games. A small sample (< 5 games) may not
    reflect true team form - one or two outliers can skew the statistics.
    Larger samples (>= 5 games) are more reliable.

    Scoring:
    - >= 10 games: 0 points (excellent sample, already in base)
    - 5-9 games: 0 points (acceptable sample size)
    - < 5 games: -10 points (small sample, high variance risk)

    Args:
        games_count: Number of recent games in form data (0+)

    Returns:
        int: Adjustment points (0 or -10)

    Examples:
        >>> # Large sample (15 games)
        >>> score_form_sample_size(15)
        0

        >>> # Acceptable sample (7 games)
        >>> score_form_sample_size(7)
        0

        >>> # Small sample (3 games)
        >>> score_form_sample_size(3)
        -10

        >>> # Empty form (0 games)
        >>> score_form_sample_size(0)
        -10
    """
    if games_count < 5:
        return -10  # Small sample penalty
    else:
        return 0  # Acceptable or large sample


async def score_pick(
    ev_result: EVResult,
    fixture: Fixture
) -> ConfidenceScoreBreakdown:
    """
    Score confidence for a single pick.

    Orchestrates all scoring functions to produce a comprehensive confidence
    assessment. Extracts timestamps from fixture and ev_result, calls individual
    scoring functions, and returns structured ConfidenceScoreBreakdown with
    all components and human-readable explanation.

    Process:
    1. Extract timestamps from fixture and ev_result
    2. Count form games from fixture.home_team or fixture.away_team
    3. Call all individual scoring functions
    4. Calculate total adjustments (sum of all scores)
    5. Calculate final confidence = 75 + total_adjustments
    6. Clamp final_confidence to [0, 100]
    7. Generate human-readable explanation
    8. Return ConfidenceScoreBreakdown

    Args:
        ev_result: EVResult from Story 5.1 with market, outcome, odds
        fixture: Fixture with teams, timestamps, and ai_analysis

    Returns:
        ConfidenceScoreBreakdown: Complete breakdown with final confidence (0-100)

    Raises:
        ValueError: If fixture or ev_result is invalid
        AttributeError: If required fields missing (caught and logged)

    Examples:
        >>> from datetime import datetime, timezone
        >>> fixture = Fixture(
        ...     fixture_id="123",
        ...     kickoff_time=datetime.now(timezone.utc),
        ...     home_team=home_team,
        ...     away_team=away_team,
        ...     league=league,
        ...     odds={"match_result": {"home": 2.10}},
        ... )
        >>> ev_result = EVResult(
        ...     market_type="match_result",
        ...     outcome="home",
        ...     ai_probability=0.58,
        ...     odds=2.10,
        ...     implied_probability=0.476,
        ...     ev_decimal=0.058,
        ...     ev_percentage=5.8,
        ...     is_valid=True
        ... )
        >>> breakdown = await score_pick(ev_result, fixture)
        >>> print(f"Confidence: {breakdown.final_confidence}%")
        >>> print(f"Breakdown: {breakdown.explanation}")
    """
    try:
        # Extract timestamps (all timezone-aware UTC)
        form_timestamp = getattr(fixture, "form_last_updated", None)
        injury_timestamp = getattr(fixture, "injuries_last_checked", None)
        odds_timestamp = getattr(fixture, "odds_timestamp", None)

        # Count form games (from home or away team, whichever relevant to pick)
        games_count = 0
        if hasattr(fixture, "home_team") and fixture.home_team:
            games_count = len(fixture.home_team.form_5_games) if fixture.home_team.form_5_games else 0
        if hasattr(fixture, "away_team") and fixture.away_team:
            away_games = len(fixture.away_team.form_5_games) if fixture.away_team.form_5_games else 0
            games_count = max(games_count, away_games)

        # Call individual scoring functions
        form_score = score_form_freshness(form_timestamp)
        injury_score = score_injury_freshness(injury_timestamp)
        odds_score = score_odds_freshness(odds_timestamp)
        sample_size_score = score_form_sample_size(games_count)

        # Calculate totals
        base_score = calculate_base_score()
        total_adjustments = form_score + injury_score + odds_score + sample_size_score
        final_confidence = max(0, min(100, base_score + total_adjustments))

        # Generate explanation
        explanation_parts = []

        if form_score > 0:
            explanation_parts.append(f"Fresh form (+{form_score})")
        elif form_score < 0:
            explanation_parts.append(f"Stale form ({form_score})")

        if injury_score > 0:
            explanation_parts.append(f"Current injuries (+{injury_score})")
        elif injury_score < 0:
            explanation_parts.append(f"Missing/stale injuries ({injury_score})")

        if odds_score > 0:
            explanation_parts.append(f"Fresh odds (+{odds_score})")
        elif odds_score < 0:
            explanation_parts.append(f"Stale odds ({odds_score})")

        if sample_size_score < 0:
            explanation_parts.append(f"Small sample ({sample_size_score})")

        explanation = " | ".join(explanation_parts) if explanation_parts else "Baseline confidence with no strong adjustments"

        logger.debug(
            f"Scored pick {ev_result.market_type}.{ev_result.outcome}: "
            f"confidence={final_confidence}% "
            f"(form={form_score}, injuries={injury_score}, odds={odds_score}, sample={sample_size_score})"
        )

        return ConfidenceScoreBreakdown(
            base_score=base_score,
            form_adjustment=form_score,
            injury_adjustment=injury_score,
            odds_adjustment=odds_score,
            sample_size_adjustment=sample_size_score,
            total_adjustments=total_adjustments,
            final_confidence=final_confidence,
            explanation=explanation
        )

    except Exception as e:
        logger.exception(f"Error scoring pick for {ev_result.market_type}.{ev_result.outcome}: {str(e)}")
        # Return neutral confidence on error (base score only)
        return ConfidenceScoreBreakdown(
            base_score=75,
            form_adjustment=0,
            injury_adjustment=0,
            odds_adjustment=0,
            sample_size_adjustment=0,
            total_adjustments=0,
            final_confidence=75,
            explanation="Unable to calculate adjustments due to error"
        )


async def apply_confidence_scoring(
    picks: list[EVResult],
    fixtures: list[Fixture]
) -> list[dict[str, Any]]:
    """
    Batch confidence scoring for multiple picks.

    Accepts filtered picks from Story 5.2 (threshold filter) and fixtures,
    scores confidence for each pick, and returns enhanced picks with confidence
    breakdowns. Implements graceful degradation - one pick's scoring failure
    doesn't block others.

    Process:
    1. Validate inputs (non-empty lists)
    2. Create fixture lookup dict for fast access
    3. For each pick: find corresponding fixture by fixture_id
    4. Call score_pick() for each pick
    5. Build result dict with all pick fields + confidence breakdown
    6. Log progress: "Processing X of Y (fixture_id)"
    7. Log summary: average confidence, min/max, tier distribution (high/medium/low)
    8. Continue on error (log error, skip pick, graceful degradation)

    Args:
        picks: List of EVResult objects from Story 5.2 (filtered by threshold)
        fixtures: List of Fixture objects with required timestamp fields

    Returns:
        list[dict[str, Any]]: List of dicts with pick data + confidence breakdown
                             Each dict contains:
                             - market_type, outcome, ai_probability, odds, ev_percentage
                             - confidence_breakdown: ConfidenceScoreBreakdown as dict
                             - timestamp: scoring timestamp

    Side Effects:
        Logs at INFO/DEBUG/WARNING levels:
        - INFO: "Processing X of Y" for each pick
        - INFO: Summary with average confidence, min/max, tier counts
        - DEBUG: Per-pick scoring details
        - WARNING: Missing fixtures, scoring failures

    Examples:
        >>> picks = [ev_result1, ev_result2, ev_result3]  # From Story 5.2
        >>> fixtures = [fixture1, fixture2, fixture3]  # With timestamps
        >>>
        >>> scored_picks = await apply_confidence_scoring(picks, fixtures)
        >>> for pick in scored_picks:
        ...     print(f"{pick['market_type']}.{pick['outcome']}: "
        ...           f"{pick['confidence_breakdown']['final_confidence']}%")
        >>>
        >>> # Check summary statistics
        >>> confidences = [p['confidence_breakdown']['final_confidence'] for p in scored_picks]
        >>> avg = sum(confidences) / len(confidences)
        >>> print(f"Average confidence: {avg:.1f}%")
    """
    # Validate inputs
    if not picks:
        logger.info("apply_confidence_scoring: No picks to score")
        return []

    if not fixtures:
        logger.warning("apply_confidence_scoring: No fixtures provided")
        return []

    logger.info(f"Starting confidence scoring for {len(picks)} picks")

    # Create fixture lookup for fast access
    fixture_by_id = {f.fixture_id: f for f in fixtures}

    # Score all picks
    results = []
    confidences = []
    failures = 0

    for idx, pick in enumerate(picks, 1):
        try:
            # Find corresponding fixture
            # Picks don't directly store fixture_id, so we need to infer it
            # For now, assume fixture is parent of EVResult (if available)
            fixture = None

            # Try to find fixture by matching with available fixtures
            # Most likely: fixture passed in matches one by market/outcome
            if hasattr(pick, "_fixture"):
                fixture = pick._fixture
            else:
                # Search for fixture with matching ai_analysis
                for f in fixtures:
                    if f.ai_analysis and hasattr(f.ai_analysis, "markets"):
                        for market in f.ai_analysis.markets:
                            if market.market_type == pick.market_type:
                                fixture = f
                                break
                    if fixture:
                        break

            if fixture is None:
                logger.warning(
                    f"Pick {idx}/{len(picks)}: No matching fixture found for "
                    f"{pick.market_type}.{pick.outcome}"
                )
                failures += 1
                continue

            logger.info(
                f"Scoring confidence for pick {idx}/{len(picks)}: "
                f"{pick.market_type}.{pick.outcome} ({fixture.fixture_id})"
            )

            # Score the pick
            breakdown = await score_pick(pick, fixture)

            # Build result dict
            result = {
                "market_type": pick.market_type,
                "outcome": pick.outcome,
                "ai_probability": pick.ai_probability,
                "odds": pick.odds,
                "implied_probability": pick.implied_probability,
                "ev_decimal": pick.ev_decimal,
                "ev_percentage": pick.ev_percentage,
                "is_valid": pick.is_valid,
                "confidence_breakdown": breakdown.model_dump(),
                "fixture_id": fixture.fixture_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            results.append(result)
            confidences.append(breakdown.final_confidence)

            logger.debug(
                f"Pick {idx}: Confidence {breakdown.final_confidence}% "
                f"({breakdown.explanation})"
            )

        except Exception as e:
            logger.exception(
                f"Error scoring pick {idx}/{len(picks)} "
                f"({pick.market_type}.{pick.outcome}): {str(e)}"
            )
            failures += 1
            continue

    # Log summary statistics
    if confidences:
        avg_confidence = sum(confidences) / len(confidences)
        min_confidence = min(confidences)
        max_confidence = max(confidences)

        # Count by tier
        high_count = sum(1 for c in confidences if c > 80)
        medium_count = sum(1 for c in confidences if 60 <= c <= 80)
        low_count = sum(1 for c in confidences if c < 60)

        logger.info(
            f"Confidence scoring summary: "
            f"{len(results)} scored, {failures} failures | "
            f"Avg: {avg_confidence:.1f}%, Min: {min_confidence}%, Max: {max_confidence}% | "
            f"Tiers: High(>80)={high_count}, Medium(60-80)={medium_count}, Low(<60)={low_count}"
        )
    else:
        logger.warning(f"Confidence scoring failed for all {len(picks)} picks")

    return results
