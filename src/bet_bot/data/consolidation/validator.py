"""
Data freshness validation for consolidated fixtures.

This module validates that all data (odds, form, injuries, fixtures) meets
freshness requirements before downstream analysis. Fixtures are flagged with
validation status (PASS, DEGRADATION, or CRITICAL) to inform confidence scoring.

Main Functions:
    validate_fixtures: Async entry point for fixture validation
    validate_and_filter: Validation with optional filtering

The validation process:
1. Check fixture date is today (±24h)
2. Check odds are < 1 hour old
3. Check form data is < 24 hours old
4. Check injuries are < 12 hours old
5. Check head-to-head data exists
6. Aggregate results into ValidationResult
7. Attach metadata to fixture and return
8. Log all validation outcomes with reason

Validation Status:
    PASS: All data fresh, full confidence
    DEGRADATION: Some data stale, accept but lower confidence
    CRITICAL: Required data missing/stale, reject fixture
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from bet_bot.models import Fixture

logger = logging.getLogger(__name__)


# ===== VALIDATION STATUS ENUM =====
class ValidationStatus(str, Enum):
    """Validation result status codes."""

    PASS = "PASS"
    DEGRADATION = "DEGRADATION"
    CRITICAL = "CRITICAL"


# ===== VALIDATION RESULT MODEL =====
class ValidationResult(BaseModel):
    """
    Validation result for a single fixture.

    Tracks which data types passed/failed validation and provides
    reason for downstream confidence scoring.

    Attributes:
        fixture_id: ID of fixture being validated
        status: Overall validation status (PASS, DEGRADATION, CRITICAL)
        reason: Explanation of why fixture has this status
        fixture_valid: Fixture date is within ±24h (always checked)
        odds_status: Odds freshness status (PASS, DEGRADATION, CRITICAL)
        form_status: Form data freshness status
        injuries_status: Injury data freshness status
        h2h_status: Head-to-head data presence status
        data_freshness_score: Overall freshness score (0-100)
        timestamp: When validation occurred
        odds_age_minutes: Age of odds data in minutes (if stale)
        form_age_hours: Age of form data in hours (if stale)
        injuries_age_hours: Age of injuries data in hours (if stale)
    """

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True
    )

    fixture_id: str = Field(
        ...,
        description="ID of fixture being validated"
    )

    status: ValidationStatus = Field(
        ...,
        description="Overall validation status"
    )

    reason: str = Field(
        ...,
        description="Explanation of validation status"
    )

    fixture_valid: bool = Field(
        ...,
        description="Fixture date within ±24h"
    )

    odds_status: str = Field(
        default="UNKNOWN",
        description="Odds freshness status"
    )

    form_status: str = Field(
        default="UNKNOWN",
        description="Form data freshness status"
    )

    injuries_status: str = Field(
        default="UNKNOWN",
        description="Injury data freshness status"
    )

    h2h_status: str = Field(
        default="UNKNOWN",
        description="Head-to-head data presence status"
    )

    data_freshness_score: int = Field(
        default=100,
        description="Overall freshness score (0-100)",
        ge=0,
        le=100
    )

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When validation occurred"
    )

    odds_age_minutes: Optional[int] = Field(
        default=None,
        description="Age of odds data in minutes (if stale)"
    )

    form_age_hours: Optional[int] = Field(
        default=None,
        description="Age of form data in hours (if stale)"
    )

    injuries_age_hours: Optional[int] = Field(
        default=None,
        description="Age of injuries data in hours (if stale)"
    )


# ===== INTERNAL HELPER FUNCTIONS FOR VALIDATION =====

def _validate_fixture_date(fixture_date: Optional[datetime]) -> tuple[ValidationStatus, str]:
    """
    Validate fixture date is today (±24h).

    Args:
        fixture_date: Fixture kickoff time

    Returns:
        Tuple of (status, reason)
    """
    if fixture_date is None:
        return ValidationStatus.CRITICAL, "Fixture date is missing"

    # Ensure we're comparing timezone-aware datetimes
    if fixture_date.tzinfo is None:
        fixture_date = fixture_date.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    age = now - fixture_date

    # Fixture must be today (±24h)
    # Within 24h in the past or 24h in the future
    if age < timedelta(hours=-24):
        # Too far in future (> 24h)
        return ValidationStatus.CRITICAL, f"Fixture scheduled too far in future ({abs(age.days)} days)"

    if age > timedelta(hours=24):
        # Too old (> 24h past)
        return ValidationStatus.CRITICAL, f"Fixture date is {age.days}d in the past"

    return ValidationStatus.PASS, "Fixture date is today"


def _validate_odds_freshness(odds_timestamp: Optional[datetime]) -> tuple[ValidationStatus, str, Optional[int]]:
    """
    Validate odds freshness (< 1 hour old).

    Args:
        odds_timestamp: When odds data was fetched

    Returns:
        Tuple of (status, reason, age_minutes)
    """
    if odds_timestamp is None:
        return ValidationStatus.CRITICAL, "Odds timestamp is missing", None

    # Ensure timezone-aware
    if odds_timestamp.tzinfo is None:
        odds_timestamp = odds_timestamp.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    age = now - odds_timestamp

    # Check for future timestamps
    if age < timedelta(0):
        return ValidationStatus.CRITICAL, "Odds timestamp is in the future", None

    age_minutes = int(age.total_seconds() / 60)

    if age > timedelta(hours=1):
        return ValidationStatus.DEGRADATION, f"Odds are {age_minutes} minutes old", age_minutes

    return ValidationStatus.PASS, f"Odds are {age_minutes} minutes old", age_minutes


def _validate_form_freshness(form_timestamp: Optional[datetime]) -> tuple[ValidationStatus, str, Optional[int]]:
    """
    Validate form data freshness (< 24 hours old).

    Args:
        form_timestamp: When form data was fetched

    Returns:
        Tuple of (status, reason, age_hours)
    """
    if form_timestamp is None:
        return ValidationStatus.DEGRADATION, "Form timestamp is missing", None

    # Ensure timezone-aware
    if form_timestamp.tzinfo is None:
        form_timestamp = form_timestamp.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    age = now - form_timestamp

    # Check for future timestamps
    if age < timedelta(0):
        return ValidationStatus.CRITICAL, "Form timestamp is in the future", None

    age_hours = int(age.total_seconds() / 3600)

    if age > timedelta(hours=24):
        return ValidationStatus.DEGRADATION, f"Form data is {age_hours} hours old", age_hours

    return ValidationStatus.PASS, f"Form data is {age_hours} hours old", age_hours


def _validate_injuries_freshness(injuries_timestamp: Optional[datetime]) -> tuple[ValidationStatus, str, Optional[int]]:
    """
    Validate injuries freshness (< 12 hours old).

    Args:
        injuries_timestamp: When injuries data was fetched

    Returns:
        Tuple of (status, reason, age_hours)
    """
    if injuries_timestamp is None:
        return ValidationStatus.DEGRADATION, "Injuries timestamp is missing", None

    # Ensure timezone-aware
    if injuries_timestamp.tzinfo is None:
        injuries_timestamp = injuries_timestamp.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    age = now - injuries_timestamp

    # Check for future timestamps
    if age < timedelta(0):
        return ValidationStatus.CRITICAL, "Injuries timestamp is in the future", None

    age_hours = int(age.total_seconds() / 3600)

    if age > timedelta(hours=12):
        return ValidationStatus.DEGRADATION, f"Injury data is {age_hours} hours old", age_hours

    return ValidationStatus.PASS, f"Injury data is {age_hours} hours old", age_hours


def _validate_h2h(h2h_data: Optional[list[str]]) -> tuple[ValidationStatus, str]:
    """
    Validate head-to-head data (static data, just check presence).

    Args:
        h2h_data: Head-to-head history list

    Returns:
        Tuple of (status, reason)
    """
    if not h2h_data or len(h2h_data) == 0:
        return ValidationStatus.DEGRADATION, "Head-to-head history is missing or empty"

    return ValidationStatus.PASS, f"Head-to-head history exists ({len(h2h_data)} matches)"


def _aggregate_validation_status(
    statuses: list[ValidationStatus],
) -> ValidationStatus:
    """
    Aggregate individual validation statuses into overall status.

    Rules:
        - CRITICAL from any component → overall CRITICAL (reject)
        - DEGRADATION from 1+ → overall DEGRADATION (accept, lower confidence)
        - PASS from all → overall PASS

    Args:
        statuses: List of individual validation statuses

    Returns:
        Overall validation status
    """
    if not statuses:
        return ValidationStatus.PASS

    # Critical overrides everything
    if ValidationStatus.CRITICAL in statuses:
        return ValidationStatus.CRITICAL

    # Degradation is next priority
    if ValidationStatus.DEGRADATION in statuses:
        return ValidationStatus.DEGRADATION

    # All must be PASS
    return ValidationStatus.PASS


def _calculate_freshness_score(
    fixture_valid: bool,
    odds_status: ValidationStatus,
    form_status: ValidationStatus,
    injuries_status: ValidationStatus,
    odds_age_minutes: Optional[int] = None,
    form_age_hours: Optional[int] = None,
    injuries_age_hours: Optional[int] = None,
) -> int:
    """
    Calculate overall data freshness score (0-100).

    Score impacts confidence in analysis later (Story 5.3).

    Args:
        fixture_valid: Fixture date is valid
        odds_status: Odds freshness status
        form_status: Form freshness status
        injuries_status: Injuries freshness status
        odds_age_minutes: Age of odds in minutes
        form_age_hours: Age of form in hours
        injuries_age_hours: Age of injuries in hours

    Returns:
        Freshness score (0-100)
    """
    score = 100

    # Fixture date is mandatory
    if not fixture_valid:
        return 0

    # Odds degradation
    if odds_status == ValidationStatus.DEGRADATION and odds_age_minutes:
        # Penalty based on age (every 10 min over 1h = -5 points)
        penalty = min(30, (odds_age_minutes - 60) // 10 * 5)
        score -= penalty

    # Form degradation
    if form_status == ValidationStatus.DEGRADATION and form_age_hours:
        # Penalty based on age (every 6h over 24h = -10 points)
        penalty = min(40, (form_age_hours - 24) // 6 * 10)
        score -= penalty

    # Injuries degradation
    if injuries_status == ValidationStatus.DEGRADATION and injuries_age_hours:
        # Penalty based on age (every 3h over 12h = -5 points)
        penalty = min(25, (injuries_age_hours - 12) // 3 * 5)
        score -= penalty

    return max(0, score)


# ===== MAIN VALIDATION FUNCTIONS =====

async def validate_fixtures(
    consolidated_fixtures: list[Fixture],
) -> list[tuple[Fixture, ValidationResult]]:
    """
    Validate all consolidated fixtures for data freshness.

    This is the main entry point for fixture validation. Accepts consolidated
    fixtures from Story 3.1, validates all timestamp fields, and returns
    same fixtures with ValidationResult attached.

    Args:
        consolidated_fixtures: List of consolidated Fixture objects with
                              timestamps and source lineage from Story 3.1

    Returns:
        List of tuples (Fixture, ValidationResult) with validation results
        attached. All fixtures returned (both passing and flagged).

    Notes:
        - Never halts on individual fixture failure
        - All fixtures processed regardless of issues
        - Validation outcomes logged at appropriate levels
        - Results can be used to filter fixtures or adjust confidence downstream
    """
    logger.info(f"Starting validation of {len(consolidated_fixtures)} consolidated fixtures")

    if not consolidated_fixtures:
        logger.warning("No fixtures provided for validation")
        return []

    results = []

    for fixture in consolidated_fixtures:
        try:
            # Extract timestamps from fixture
            # Fixture uses kickoff_time (the match time)
            fixture_date = fixture.kickoff_time

            # Extract timestamps from fixture attributes using __dict__
            # This handles both Pydantic field access and dynamic attributes set by consolidator
            fixture_dict = fixture.__dict__ if hasattr(fixture, '__dict__') else {}

            odds_timestamp = fixture_dict.get('odds_timestamp')
            form_timestamp = fixture_dict.get('form_data_timestamp')
            injuries_timestamp = fixture_dict.get('injuries_timestamp')
            h2h_data = fixture.head_to_head_history

            # Validate each component
            fixture_status, fixture_reason = _validate_fixture_date(fixture_date)

            odds_status, odds_reason, odds_age_minutes = _validate_odds_freshness(odds_timestamp)

            form_status, form_reason, form_age_hours = _validate_form_freshness(form_timestamp)

            injuries_status, injuries_reason, injuries_age_hours = _validate_injuries_freshness(
                injuries_timestamp
            )

            h2h_status, h2h_reason = _validate_h2h(h2h_data)

            # Aggregate results
            overall_status = _aggregate_validation_status(
                [fixture_status, odds_status, form_status, injuries_status, h2h_status]
            )

            # Fixture date is always checked (critical for analysis)
            fixture_valid = fixture_status == ValidationStatus.PASS

            # Build reason string
            reasons = []
            if fixture_status != ValidationStatus.PASS:
                reasons.append(f"fixture: {fixture_reason}")
            if odds_status != ValidationStatus.PASS:
                reasons.append(f"odds: {odds_reason}")
            if form_status != ValidationStatus.PASS:
                reasons.append(f"form: {form_reason}")
            if injuries_status != ValidationStatus.PASS:
                reasons.append(f"injuries: {injuries_reason}")
            if h2h_status != ValidationStatus.PASS:
                reasons.append(f"h2h: {h2h_reason}")

            overall_reason = " | ".join(reasons) if reasons else "All data fresh and valid"

            # Calculate freshness score
            freshness_score = _calculate_freshness_score(
                fixture_valid,
                odds_status,
                form_status,
                injuries_status,
                odds_age_minutes,
                form_age_hours,
                injuries_age_hours,
            )

            # Create validation result
            validation_result = ValidationResult(
                fixture_id=fixture.fixture_id,
                status=overall_status,
                reason=overall_reason,
                fixture_valid=fixture_valid,
                odds_status=str(odds_status),
                form_status=str(form_status),
                injuries_status=str(injuries_status),
                h2h_status=str(h2h_status),
                data_freshness_score=freshness_score,
                odds_age_minutes=odds_age_minutes,
                form_age_hours=form_age_hours,
                injuries_age_hours=injuries_age_hours,
            )

            results.append((fixture, validation_result))

            # Log at appropriate level
            if overall_status == ValidationStatus.PASS:
                logger.info(
                    f"Fixture {fixture.fixture_id} validation PASSED: "
                    f"{fixture.home_team.name} vs {fixture.away_team.name}"
                )
            elif overall_status == ValidationStatus.DEGRADATION:
                logger.warning(
                    f"Fixture {fixture.fixture_id} validation DEGRADATION: "
                    f"{fixture.home_team.name} vs {fixture.away_team.name} | "
                    f"{overall_reason}"
                )
            else:  # CRITICAL
                logger.error(
                    f"Fixture {fixture.fixture_id} validation CRITICAL: "
                    f"{fixture.home_team.name} vs {fixture.away_team.name} | "
                    f"{overall_reason}"
                )

        except Exception as e:
            logger.exception(
                f"Unexpected error validating fixture {fixture.fixture_id}: {str(e)}"
            )
            # Create error result for this fixture
            error_result = ValidationResult(
                fixture_id=fixture.fixture_id,
                status=ValidationStatus.CRITICAL,
                reason=f"Validation error: {str(e)}",
                fixture_valid=False,
            )
            results.append((fixture, error_result))

    # Log summary
    pass_count = sum(1 for _, result in results if result.status == ValidationStatus.PASS)
    degrad_count = sum(1 for _, result in results if result.status == ValidationStatus.DEGRADATION)
    crit_count = sum(1 for _, result in results if result.status == ValidationStatus.CRITICAL)

    logger.info(
        f"Validation complete: {len(results)} fixtures validated - "
        f"{pass_count} PASS, {degrad_count} DEGRADATION, {crit_count} CRITICAL"
    )

    return results


async def validate_and_filter(
    consolidated_fixtures: list[Fixture],
    include_degradation: bool = True,
) -> list[Fixture]:
    """
    Validate fixtures and optionally filter based on validation status.

    Wrapper around validate_fixtures() that optionally filters out CRITICAL
    fixtures, used by downstream stages (quality scoring, analysis) to decide
    which fixtures to process.

    Args:
        consolidated_fixtures: List of consolidated Fixture objects
        include_degradation: If True, include DEGRADATION fixtures. If False,
                           only return PASS fixtures.

    Returns:
        Filtered list of Fixture objects based on validation status.
        If include_degradation=True, returns PASS + DEGRADATION.
        If include_degradation=False, returns only PASS.
        Always excludes CRITICAL fixtures.

    Notes:
        - CRITICAL fixtures are always filtered out
        - DEGRADATION fixtures can be included or excluded based on parameter
        - Validation results are NOT attached (only used for filtering)
        - Downstream stages can attach results if needed
    """
    validation_results = await validate_fixtures(consolidated_fixtures)

    filtered = []
    for fixture, result in validation_results:
        # Always exclude CRITICAL
        if result.status == ValidationStatus.CRITICAL:
            continue

        # Check DEGRADATION inclusion
        if result.status == ValidationStatus.DEGRADATION and not include_degradation:
            continue

        # Include this fixture
        filtered.append(fixture)

    logger.info(
        f"Filtered results: {len(filtered)}/{len(consolidated_fixtures)} fixtures "
        f"passed validation{'(excluding DEGRADATION)' if not include_degradation else ''}"
    )

    return filtered
