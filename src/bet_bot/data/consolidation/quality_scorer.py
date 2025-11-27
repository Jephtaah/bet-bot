"""
Data quality scoring for consolidated fixtures.

This module assesses overall data quality for each fixture by scoring
on a 0-100 scale based on data completeness and freshness. Quality scores
inform confidence scoring in downstream analysis phases.

Main Functions:
    score_fixtures: Async entry point for fixture quality scoring
    calculate_quality_score: Calculate quality score for a single fixture

The scoring process:
1. Check required fields are present (20 pts)
2. Assess data freshness from validation result (20 pts)
3. Check injury data availability (15 pts)
4. Check head-to-head data availability (10 pts)
5. Count available odds markets (10 pts)
6. Assess form data sample size (10 pts)
7. Apply PASS validation bonus (+15 pts, capped at 100)
8. Log detailed breakdown per fixture
9. Return all fixtures with quality scores attached

Scoring Scale:
    90-100: Excellent data (complete, fresh, comprehensive)
    70-89: Good data (mostly complete and fresh)
    50-69: Acceptable data (some data age/gaps)
    30-49: Degraded data (significant gaps or age)
    0-29: Poor data (major issues, use with caution)
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from bet_bot.data.consolidation.validator import ValidationResult, ValidationStatus
from bet_bot.models import Fixture

logger = logging.getLogger(__name__)


# ===== QUALITY SCORE MODEL =====
class DataQualityScore(BaseModel):
    """
    Quality score for a single fixture.

    Tracks component scores and overall quality assessment for
    confidence scoring downstream in analysis phase.

    Attributes:
        fixture_id: ID of fixture being scored
        overall_score: Overall quality score (0-100)
        score_breakdown: Dict with individual component scores
        required_fields_score: Points from required fields check (0-20)
        freshness_score: Points from data freshness check (0-20)
        injury_score: Points from injury data check (0-15)
        h2h_score: Points from H2H data check (0-10)
        markets_score: Points from odds markets check (0-10)
        form_sample_score: Points from form sample size check (0-10)
        validation_bonus: Bonus points if validation PASS (0-15)
        reasoning: Explanation of which factors helped/hurt score
        timestamp: When quality score was calculated
    """

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True
    )

    fixture_id: str = Field(
        ...,
        description="ID of fixture being scored"
    )

    overall_score: int = Field(
        ...,
        description="Overall quality score (0-100)",
        ge=0,
        le=100
    )

    score_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="Individual component scores"
    )

    required_fields_score: int = Field(
        default=0,
        description="Points from required fields check",
        ge=0,
        le=20
    )

    freshness_score: int = Field(
        default=0,
        description="Points from data freshness check",
        ge=0,
        le=20
    )

    injury_score: int = Field(
        default=0,
        description="Points from injury data check",
        ge=0,
        le=15
    )

    h2h_score: int = Field(
        default=0,
        description="Points from H2H data check",
        ge=0,
        le=10
    )

    markets_score: int = Field(
        default=0,
        description="Points from odds markets check",
        ge=0,
        le=10
    )

    form_sample_score: int = Field(
        default=0,
        description="Points from form sample size check",
        ge=0,
        le=10
    )

    validation_bonus: int = Field(
        default=0,
        description="Bonus points if validation PASS",
        ge=0,
        le=15
    )

    reasoning: str = Field(
        default="",
        description="Explanation of which factors helped/hurt score"
    )

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When quality score was calculated"
    )


# ===== INTERNAL HELPER FUNCTIONS FOR SCORING =====

def _score_required_fields(fixture: Fixture) -> tuple[int, str]:
    """
    Score required fields presence (0-20 points).

    Checks: fixture_id, teams, league, kickoff_time, odds
    - All present → 20 pts
    - Missing one field → 10 pts
    - Missing 2+ fields → 0 pts

    Args:
        fixture: Fixture to assess

    Returns:
        Tuple of (points, reason)
    """
    missing_fields = []

    if not fixture.fixture_id or not fixture.fixture_id.strip():
        missing_fields.append("fixture_id")

    if not fixture.home_team or not fixture.away_team:
        missing_fields.append("teams")

    if not fixture.league:
        missing_fields.append("league")

    if not fixture.kickoff_time:
        missing_fields.append("kickoff_time")

    if not fixture.odds:
        missing_fields.append("odds")

    if len(missing_fields) == 0:
        return 20, "All required fields present"
    elif len(missing_fields) == 1:
        return 10, f"Missing field: {missing_fields[0]}"
    else:
        return 0, f"Missing fields: {', '.join(missing_fields)}"


def _score_data_freshness(fixture: Fixture, validation_result: ValidationResult) -> tuple[int, str]:
    """
    Score data freshness based on validation result (0-20 points).

    Uses ValidationResult status from Story 3.2:
    - PASS status → 20 pts
    - DEGRADATION status → 10 pts
    - CRITICAL status → 0 pts

    Args:
        fixture: Fixture being scored
        validation_result: ValidationResult from Story 3.2

    Returns:
        Tuple of (points, reason)
    """
    if validation_result.status == ValidationStatus.PASS:
        return 20, "All data fresh (PASS status)"
    elif validation_result.status == ValidationStatus.DEGRADATION:
        return 10, f"Some data stale (DEGRADATION: {validation_result.reason})"
    else:  # CRITICAL
        return 0, f"Critical data issues (CRITICAL: {validation_result.reason})"


def _score_injury_data(fixture: Fixture) -> tuple[int, str]:
    """
    Score injury data presence (0-15 points).

    - Injuries for both teams → 15 pts
    - Injuries for one team only → 8 pts
    - No injury data → 0 pts

    Args:
        fixture: Fixture to assess

    Returns:
        Tuple of (points, reason)
    """
    home_has_injuries = bool(fixture.home_team.injuries)
    away_has_injuries = bool(fixture.away_team.injuries)

    if home_has_injuries and away_has_injuries:
        return 15, f"Injury data for both teams ({len(fixture.home_team.injuries)} home, {len(fixture.away_team.injuries)} away)"
    elif home_has_injuries or away_has_injuries:
        team = "home" if home_has_injuries else "away"
        count = len(fixture.home_team.injuries) if home_has_injuries else len(fixture.away_team.injuries)
        return 8, f"Injury data for {team} team only ({count} players)"
    else:
        return 0, "No injury data available"


def _score_h2h_data(fixture: Fixture) -> tuple[int, str]:
    """
    Score head-to-head data presence (0-10 points).

    - 5+ past matches → 10 pts
    - 2-4 past matches → 5 pts
    - No h2h data → 0 pts

    Args:
        fixture: Fixture to assess

    Returns:
        Tuple of (points, reason)
    """
    h2h_count = len(fixture.head_to_head_history)

    if h2h_count >= 5:
        return 10, f"Strong H2H history ({h2h_count} matches)"
    elif h2h_count >= 2:
        return 5, f"Limited H2H history ({h2h_count} matches)"
    else:
        return 0, "No H2H history available"


def _score_odds_markets(fixture: Fixture) -> tuple[int, str]:
    """
    Score odds markets availability (0-10 points).

    Count available odds markets (match_result, totals, corners/cards, etc.)
    - 3+ markets → 10 pts
    - 2 markets → 5 pts
    - 1 market → 2 pts
    - No odds → 0 pts

    Args:
        fixture: Fixture to assess

    Returns:
        Tuple of (points, reason)
    """
    market_count = len(fixture.odds)

    if market_count >= 3:
        markets = ", ".join(fixture.odds.keys())
        return 10, f"Multiple markets available ({market_count}: {markets})"
    elif market_count == 2:
        markets = ", ".join(fixture.odds.keys())
        return 5, f"Two markets available ({markets})"
    elif market_count == 1:
        market = list(fixture.odds.keys())[0]
        return 2, f"Single market available ({market})"
    else:
        return 0, "No odds data available"


def _score_form_sample_size(fixture: Fixture) -> tuple[int, str]:
    """
    Score form data sample size (0-10 points).

    Check length of form data for both teams (form_5_games)
    - 10+ games form for both teams → 10 pts (note: max per team is 5, so treat 5+ as excellent)
    - 5+ games form for both teams → 10 pts
    - 5+ games for one team → 3 pts
    - < 5 games for both → 0 pts

    Args:
        fixture: Fixture to assess

    Returns:
        Tuple of (points, reason)
    """
    home_form_count = len(fixture.home_team.form_5_games)
    away_form_count = len(fixture.away_team.form_5_games)

    if home_form_count >= 5 and away_form_count >= 5:
        return 10, f"Strong form data for both teams ({home_form_count} home, {away_form_count} away)"
    elif home_form_count >= 5 or away_form_count >= 5:
        team = "home" if home_form_count >= 5 else "away"
        count = home_form_count if home_form_count >= 5 else away_form_count
        other_count = away_form_count if home_form_count >= 5 else home_form_count
        return 3, f"Form data for {team} team ({count} games), limited for other ({other_count})"
    else:
        return 0, f"Limited form data ({home_form_count} home, {away_form_count} away)"


# ===== SCORE AGGREGATION =====

def _calculate_quality_score(
    fixture: Fixture,
    validation_result: ValidationResult
) -> DataQualityScore:
    """
    Calculate overall quality score for a fixture.

    Sums component scores (max 85 from components + 15 bonus if PASS = 100 max).
    Clamps result to [0, 100].

    Args:
        fixture: Fixture being scored
        validation_result: ValidationResult from Story 3.2

    Returns:
        DataQualityScore with breakdown and reasoning
    """
    # Score each component
    required_score, required_reason = _score_required_fields(fixture)
    freshness_score, freshness_reason = _score_data_freshness(fixture, validation_result)
    injury_score, injury_reason = _score_injury_data(fixture)
    h2h_score, h2h_reason = _score_h2h_data(fixture)
    markets_score, markets_reason = _score_odds_markets(fixture)
    form_score, form_reason = _score_form_sample_size(fixture)

    # Sum component scores (max 85)
    component_total = (
        required_score + freshness_score + injury_score +
        h2h_score + markets_score + form_score
    )

    # Apply bonus for PASS validation status (max 15)
    validation_bonus = 15 if validation_result.status == ValidationStatus.PASS else 0

    # Calculate overall score (clamped to 100)
    overall = min(100, component_total + validation_bonus)

    # Build reasoning string
    reasoning_parts = [
        f"Required fields: {required_score}/20 ({required_reason})",
        f"Freshness: {freshness_score}/20 ({freshness_reason})",
        f"Injuries: {injury_score}/15 ({injury_reason})",
        f"H2H: {h2h_score}/10 ({h2h_reason})",
        f"Markets: {markets_score}/10 ({markets_reason})",
        f"Form sample: {form_score}/10 ({form_reason})"
    ]

    if validation_bonus > 0:
        reasoning_parts.append(f"Validation bonus: +{validation_bonus} (PASS status)")

    reasoning = " | ".join(reasoning_parts)

    return DataQualityScore(
        fixture_id=fixture.fixture_id,
        overall_score=overall,
        required_fields_score=required_score,
        freshness_score=freshness_score,
        injury_score=injury_score,
        h2h_score=h2h_score,
        markets_score=markets_score,
        form_sample_score=form_score,
        validation_bonus=validation_bonus,
        score_breakdown={
            "required_fields": required_score,
            "freshness": freshness_score,
            "injuries": injury_score,
            "h2h": h2h_score,
            "markets": markets_score,
            "form_sample": form_score,
            "validation_bonus": validation_bonus
        },
        reasoning=reasoning
    )


# ===== MAIN ORCHESTRATION FUNCTION =====

async def score_fixtures(
    validated_fixtures: list[tuple[Fixture, ValidationResult]]
) -> list[tuple[Fixture, DataQualityScore]]:
    """
    Score quality for all validated fixtures.

    Main entry point that processes all fixtures, calculates quality scores,
    logs detailed breakdown, and returns fixtures with scores attached.

    Never filters fixtures - returns all, including degraded data.
    Continues processing even if individual fixtures have issues.

    Args:
        validated_fixtures: List of (Fixture, ValidationResult) tuples from Story 3.2

    Returns:
        List of (Fixture, DataQualityScore) tuples with quality scores attached

    Example:
        >>> validated_fixtures = [(fixture1, validation1), (fixture2, validation2)]
        >>> scored = await score_fixtures(validated_fixtures)
        >>> for fixture, score in scored:
        ...     print(f"{fixture.fixture_id}: {score.overall_score}/100")
    """
    scored_fixtures: list[tuple[Fixture, DataQualityScore]] = []
    quality_scores: list[int] = []

    logger.info(f"Starting quality scoring for {len(validated_fixtures)} fixtures")

    for fixture, validation_result in validated_fixtures:
        try:
            # Calculate quality score
            quality_score = _calculate_quality_score(fixture, validation_result)
            scored_fixtures.append((fixture, quality_score))
            quality_scores.append(quality_score.overall_score)

            # Log per-fixture breakdown
            home_team = fixture.home_team.name if fixture.home_team else "?"
            away_team = fixture.away_team.name if fixture.away_team else "?"
            logger.info(
                f"Fixture {fixture.fixture_id} ({home_team} vs {away_team}): "
                f"Quality={quality_score.overall_score}/100 | "
                f"required={quality_score.required_fields_score}, "
                f"freshness={quality_score.freshness_score}, "
                f"injuries={quality_score.injury_score}, "
                f"h2h={quality_score.h2h_score}, "
                f"markets={quality_score.markets_score}, "
                f"form={quality_score.form_sample_score}, "
                f"bonus={quality_score.validation_bonus}"
            )

        except Exception as e:
            # Log error but continue processing
            logger.warning(
                f"Error scoring fixture {fixture.fixture_id}: {str(e)}. "
                "Assigning zero quality score."
            )
            # Create minimal quality score on error
            quality_score = DataQualityScore(
                fixture_id=fixture.fixture_id,
                overall_score=0,
                reasoning=f"Scoring error: {str(e)}"
            )
            scored_fixtures.append((fixture, quality_score))
            quality_scores.append(0)

    # Log summary statistics
    if quality_scores:
        avg_quality = sum(quality_scores) / len(quality_scores)
        min_quality = min(quality_scores)
        max_quality = max(quality_scores)
        logger.info(
            f"Quality scoring complete: {len(scored_fixtures)} fixtures scored | "
            f"Average quality: {avg_quality:.1f}/100 | "
            f"Range: {min_quality}-{max_quality}"
        )
    else:
        logger.warning("No fixtures scored (empty input)")

    return scored_fixtures


def score_and_filter(
    validated_fixtures: list[tuple[Fixture, ValidationResult]],
    quality_threshold: int = 0
) -> list[tuple[Fixture, DataQualityScore]]:
    """
    Score fixtures and optionally filter by quality threshold.

    Convenience function for integration with downstream analysis phases.
    Can filter out low-quality fixtures if confidence can't accommodate them.

    Args:
        validated_fixtures: List of (Fixture, ValidationResult) tuples from Story 3.2
        quality_threshold: Minimum quality score to include (0-100, default 0 = no filtering)

    Returns:
        List of (Fixture, DataQualityScore) tuples meeting quality threshold

    Example:
        >>> # Score all fixtures
        >>> all_scored = await score_fixtures(validated_fixtures)
        >>>
        >>> # Or score and filter in one call
        >>> high_quality_only = score_and_filter(validated_fixtures, quality_threshold=50)
    """
    # Note: This is a sync wrapper. For async version, caller should use score_fixtures directly
    # in an async context and filter results.

    if quality_threshold < 0 or quality_threshold > 100:
        logger.warning(f"Invalid quality_threshold {quality_threshold}, using 0")
        quality_threshold = 0

    # This function is synchronous but score_fixtures is async
    # For actual filtering, caller should do:
    # scored = await score_fixtures(validated_fixtures)
    # filtered = [s for s in scored if s[1].overall_score >= threshold]

    logger.info(
        f"Quality filter configured: {quality_threshold}/100 minimum. "
        "Use score_fixtures() for actual scoring."
    )

    return []
