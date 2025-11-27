"""
Unit tests for data freshness validation module.

Tests cover:
- Fixture date validation (fresh, old, future, missing)
- Odds freshness validation (within threshold, stale, missing)
- Form data freshness validation
- Injuries freshness validation
- Head-to-head data presence
- Overall validation aggregation
- Logging at appropriate levels
- Edge case handling (timezone, missing timestamps)
- Validation result serialization

Target coverage: 85%+
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from bet_bot.data.consolidation.validator import (
    ValidationResult,
    ValidationStatus,
    validate_and_filter,
    validate_fixtures,
)
from bet_bot.models import Fixture, League, Team


# ===== FIXTURES FOR TESTS =====

@pytest.fixture
def league():
    """Provide a test League object."""
    return League(
        league_id="39",
        league_name="Championship",
        league_country="England",
        league_season=2025
    )


@pytest.fixture
def home_team():
    """Provide a test home team."""
    return Team(
        id="123",
        name="Leeds United",
        form_5_games=["W", "W", "D", "L", "W"],
        avg_goals_for=1.8,
        avg_goals_against=1.2,
        injuries=[]
    )


@pytest.fixture
def away_team():
    """Provide a test away team."""
    return Team(
        id="456",
        name="Derby County",
        form_5_games=["W", "D", "L", "W", "D"],
        avg_goals_for=1.5,
        avg_goals_against=1.3,
        injuries=["5001"]
    )


def create_fixture(
    fixture_id: str = "548821",
    kickoff_time: datetime = None,
    odds_timestamp: datetime = None,
    form_timestamp: datetime = None,
    injuries_timestamp: datetime = None,
    h2h_history: list[str] = None,
    home_team: Team = None,
    away_team: Team = None,
    league: League = None,
) -> Fixture:
    """Helper function to create test Fixture with optional timestamp overrides."""
    if kickoff_time is None:
        kickoff_time = datetime.now(timezone.utc)
    if h2h_history is None:
        h2h_history = ["W", "D", "W", "L", "W"]
    if home_team is None:
        home_team = Team(id="123", name="Leeds United")
    if away_team is None:
        away_team = Team(id="456", name="Derby County")
    if league is None:
        league = League(league_id="39", league_name="Championship", league_country="England", league_season=2025)

    fixture = Fixture(
        fixture_id=fixture_id,
        kickoff_time=kickoff_time,
        home_team=home_team,
        away_team=away_team,
        league=league,
        odds={},
        head_to_head_history=h2h_history,
    )

    # Attach timestamps as attributes using object.__setattr__ to bypass Pydantic v2 restrictions
    # This simulates Story 3.1 consolidation adding metadata to fixture
    if odds_timestamp is not None:
        object.__setattr__(fixture, 'odds_timestamp', odds_timestamp)
    if form_timestamp is not None:
        object.__setattr__(fixture, 'form_data_timestamp', form_timestamp)
    if injuries_timestamp is not None:
        object.__setattr__(fixture, 'injuries_timestamp', injuries_timestamp)

    return fixture


# ===== TEST: FIXTURE DATE VALIDATION =====

class TestFixtureDateValidation:
    """Test fixture date validation (±24h)."""

    @pytest.mark.asyncio
    async def test_fresh_fixture_today(self, home_team, away_team, league):
        """Fresh fixture (today) should PASS."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now,
            form_timestamp=now,
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.fixture_valid is True
        assert validation.status == ValidationStatus.PASS

    @pytest.mark.asyncio
    async def test_fixture_1_day_old(self, home_team, away_team, league):
        """Fixture 1 day old should be CRITICAL (> 24h in past)."""
        now = datetime.now(timezone.utc)
        # Fixture from exactly 1 day ago = 24+ hours old
        one_day_ago = now - timedelta(days=1, seconds=1)  # 24h + 1 second
        fixture = create_fixture(
            kickoff_time=one_day_ago,
            odds_timestamp=now,
            form_timestamp=now,
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        # 1 day old is beyond the ±24h window
        assert validation.fixture_valid is False
        assert validation.status == ValidationStatus.CRITICAL

    @pytest.mark.asyncio
    async def test_fixture_2_days_old_critical(self, home_team, away_team, league):
        """Fixture 2 days old should be CRITICAL."""
        now = datetime.now(timezone.utc)
        two_days_ago = now - timedelta(days=2)
        fixture = create_fixture(
            kickoff_time=two_days_ago,
            odds_timestamp=now,
            form_timestamp=now,
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.fixture_valid is False
        assert validation.status == ValidationStatus.CRITICAL

    @pytest.mark.asyncio
    async def test_fixture_1_day_future(self, home_team, away_team, league):
        """Fixture 1 day in future should PASS (within ±24h)."""
        now = datetime.now(timezone.utc)
        one_day_future = now + timedelta(days=1)
        fixture = create_fixture(
            kickoff_time=one_day_future,
            odds_timestamp=now,
            form_timestamp=now,
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.fixture_valid is True

    @pytest.mark.asyncio
    async def test_fixture_2_days_future_critical(self, home_team, away_team, league):
        """Fixture 2 days in future should be CRITICAL."""
        now = datetime.now(timezone.utc)
        two_days_future = now + timedelta(days=2)
        fixture = create_fixture(
            kickoff_time=two_days_future,
            odds_timestamp=now,
            form_timestamp=now,
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.fixture_valid is False
        assert validation.status == ValidationStatus.CRITICAL

    @pytest.mark.asyncio
    async def test_future_timestamp_far_future(self, home_team, away_team, league):
        """Fixture far in future (> 24h) should be CRITICAL."""
        now = datetime.now(timezone.utc)
        # Test edge case: fixture exactly 24.5h in future
        far_future = now + timedelta(hours=24, minutes=30)
        fixture = create_fixture(
            kickoff_time=far_future,
            odds_timestamp=now,
            form_timestamp=now,
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.fixture_valid is False
        assert validation.status == ValidationStatus.CRITICAL


# ===== TEST: ODDS FRESHNESS VALIDATION =====

class TestOddsFreshnessValidation:
    """Test odds freshness validation (< 1 hour)."""

    @pytest.mark.asyncio
    async def test_fresh_odds_10_minutes(self, home_team, away_team, league):
        """Odds 10 min old should PASS."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now - timedelta(minutes=10),
            form_timestamp=now,
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.odds_status == str(ValidationStatus.PASS)

    @pytest.mark.asyncio
    async def test_stale_odds_90_minutes(self, home_team, away_team, league):
        """Odds 90 min old should be DEGRADATION."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now - timedelta(minutes=90),
            form_timestamp=now,
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.odds_status == str(ValidationStatus.DEGRADATION)
        assert validation.odds_age_minutes == 90

    @pytest.mark.asyncio
    async def test_very_stale_odds_5_hours(self, home_team, away_team, league):
        """Odds 5 hours old should be DEGRADATION."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now - timedelta(hours=5),
            form_timestamp=now,
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.odds_status == str(ValidationStatus.DEGRADATION)

    @pytest.mark.asyncio
    async def test_missing_odds_critical(self, home_team, away_team, league):
        """Missing odds timestamp should be CRITICAL."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=None,
            form_timestamp=now,
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.odds_status == str(ValidationStatus.CRITICAL)
        assert validation.status == ValidationStatus.CRITICAL


# ===== TEST: FORM FRESHNESS VALIDATION =====

class TestFormFreshnessValidation:
    """Test form data freshness validation (< 24 hours)."""

    @pytest.mark.asyncio
    async def test_fresh_form_1_hour(self, home_team, away_team, league):
        """Form data 1 hour old should PASS."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now,
            form_timestamp=now - timedelta(hours=1),
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.form_status == str(ValidationStatus.PASS)

    @pytest.mark.asyncio
    async def test_old_form_20_hours(self, home_team, away_team, league):
        """Form data 20 hours old should PASS (within 24h)."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now,
            form_timestamp=now - timedelta(hours=20),
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.form_status == str(ValidationStatus.PASS)

    @pytest.mark.asyncio
    async def test_very_old_form_48_hours(self, home_team, away_team, league):
        """Form data 48 hours old should be DEGRADATION."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now,
            form_timestamp=now - timedelta(hours=48),
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.form_status == str(ValidationStatus.DEGRADATION)
        assert validation.form_age_hours == 48

    @pytest.mark.asyncio
    async def test_missing_form_degradation(self, home_team, away_team, league):
        """Missing form timestamp should be DEGRADATION (not critical)."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now,
            form_timestamp=None,
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.form_status == str(ValidationStatus.DEGRADATION)
        # Overall should not be CRITICAL since only form is missing
        # (odds and injuries are fresh)


# ===== TEST: INJURIES FRESHNESS VALIDATION =====

class TestInjuriesFreshnessValidation:
    """Test injuries freshness validation (< 12 hours)."""

    @pytest.mark.asyncio
    async def test_fresh_injuries_1_hour(self, home_team, away_team, league):
        """Injuries data 1 hour old should PASS."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now,
            form_timestamp=now,
            injuries_timestamp=now - timedelta(hours=1),
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.injuries_status == str(ValidationStatus.PASS)

    @pytest.mark.asyncio
    async def test_old_injuries_8_hours(self, home_team, away_team, league):
        """Injuries data 8 hours old should PASS (within 12h)."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now,
            form_timestamp=now,
            injuries_timestamp=now - timedelta(hours=8),
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.injuries_status == str(ValidationStatus.PASS)

    @pytest.mark.asyncio
    async def test_very_old_injuries_18_hours(self, home_team, away_team, league):
        """Injuries data 18 hours old should be DEGRADATION."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now,
            form_timestamp=now,
            injuries_timestamp=now - timedelta(hours=18),
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.injuries_status == str(ValidationStatus.DEGRADATION)
        assert validation.injuries_age_hours == 18

    @pytest.mark.asyncio
    async def test_missing_injuries_degradation(self, home_team, away_team, league):
        """Missing injuries timestamp should be DEGRADATION."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now,
            form_timestamp=now,
            injuries_timestamp=None,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.injuries_status == str(ValidationStatus.DEGRADATION)


# ===== TEST: OVERALL AGGREGATION =====

class TestOverallAggregation:
    """Test validation status aggregation."""

    @pytest.mark.asyncio
    async def test_all_data_fresh_pass(self, home_team, away_team, league):
        """All data fresh should be PASS."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now - timedelta(minutes=10),
            form_timestamp=now - timedelta(hours=1),
            injuries_timestamp=now - timedelta(hours=1),
            h2h_history=["W", "D", "W"],
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.status == ValidationStatus.PASS

    @pytest.mark.asyncio
    async def test_odds_stale_form_fresh_degradation(self, home_team, away_team, league):
        """Odds stale + form fresh should be DEGRADATION."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now - timedelta(minutes=90),
            form_timestamp=now - timedelta(hours=1),
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.status == ValidationStatus.DEGRADATION

    @pytest.mark.asyncio
    async def test_fixture_date_in_future_critical(self, home_team, away_team, league):
        """Fixture date in future (> 24h) should be CRITICAL."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now + timedelta(days=2),
            odds_timestamp=now,
            form_timestamp=now,
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.status == ValidationStatus.CRITICAL

    @pytest.mark.asyncio
    async def test_missing_odds_multiple_degradations(self, home_team, away_team, league):
        """Missing odds (CRITICAL) overrides degradations."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=None,  # CRITICAL
            form_timestamp=now - timedelta(hours=30),  # DEGRADATION
            injuries_timestamp=now - timedelta(hours=15),  # DEGRADATION
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        # CRITICAL (missing odds) overrides other DEGRADATION
        assert validation.status == ValidationStatus.CRITICAL


# ===== TEST: LOGGING =====

class TestValidationLogging:
    """Test logging at appropriate levels."""

    @pytest.mark.asyncio
    async def test_pass_logs_at_info_level(self, home_team, away_team, league, caplog):
        """PASS validation should log at INFO level."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now,
            form_timestamp=now,
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        with caplog.at_level(logging.INFO):
            results = await validate_fixtures([fixture])

        assert "validation PASSED" in caplog.text

    @pytest.mark.asyncio
    async def test_degradation_logs_at_warning_level(self, home_team, away_team, league, caplog):
        """DEGRADATION should log at WARNING level."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now - timedelta(minutes=90),
            form_timestamp=now,
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        with caplog.at_level(logging.WARNING):
            results = await validate_fixtures([fixture])

        assert "DEGRADATION" in caplog.text

    @pytest.mark.asyncio
    async def test_critical_logs_at_error_level(self, home_team, away_team, league, caplog):
        """CRITICAL should log at ERROR level."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=None,
            form_timestamp=now,
            injuries_timestamp=now,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        with caplog.at_level(logging.ERROR):
            results = await validate_fixtures([fixture])

        assert "CRITICAL" in caplog.text


# ===== TEST: EDGE CASES =====

class TestEdgeCases:
    """Test edge case handling."""

    @pytest.mark.asyncio
    async def test_naive_datetime_handling(self, home_team, away_team, league):
        """Naive (non-timezone-aware) datetimes should be handled safely."""
        now_naive = datetime.now()
        fixture = create_fixture(
            kickoff_time=now_naive,
            odds_timestamp=now_naive,
            form_timestamp=now_naive,
            injuries_timestamp=now_naive,
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        # Should not crash, should handle gracefully
        results = await validate_fixtures([fixture])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_empty_h2h_degradation(self, home_team, away_team, league):
        """Empty head-to-head should be DEGRADATION."""
        now = datetime.now(timezone.utc)
        fixture = create_fixture(
            kickoff_time=now,
            odds_timestamp=now,
            form_timestamp=now,
            injuries_timestamp=now,
            h2h_history=[],  # Empty
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        results = await validate_fixtures([fixture])
        assert len(results) == 1
        fixture_result, validation = results[0]
        assert validation.h2h_status == str(ValidationStatus.DEGRADATION)

    @pytest.mark.asyncio
    async def test_multiple_fixtures(self, home_team, away_team, league):
        """Should process multiple fixtures without errors."""
        now = datetime.now(timezone.utc)
        fixtures = [
            create_fixture(
                fixture_id=f"fix_{i}",
                kickoff_time=now,
                odds_timestamp=now,
                form_timestamp=now,
                injuries_timestamp=now,
                home_team=home_team,
                away_team=away_team,
                league=league
            )
            for i in range(5)
        ]

        results = await validate_fixtures(fixtures)
        assert len(results) == 5


# ===== TEST: VALIDATE_AND_FILTER =====

class TestValidateAndFilter:
    """Test filtering function."""

    @pytest.mark.asyncio
    async def test_include_degradation_true(self, home_team, away_team, league):
        """With include_degradation=True, should include DEGRADATION fixtures."""
        now = datetime.now(timezone.utc)

        # Mix of PASS and DEGRADATION
        fixtures = [
            create_fixture(
                fixture_id="pass",
                kickoff_time=now,
                odds_timestamp=now,
                form_timestamp=now,
                injuries_timestamp=now,
                home_team=home_team,
                away_team=away_team,
                league=league
            ),
            create_fixture(
                fixture_id="degrad",
                kickoff_time=now,
                odds_timestamp=now - timedelta(minutes=90),
                form_timestamp=now,
                injuries_timestamp=now,
                home_team=home_team,
                away_team=away_team,
                league=league
            ),
        ]

        filtered = await validate_and_filter(fixtures, include_degradation=True)
        assert len(filtered) == 2  # Both included

    @pytest.mark.asyncio
    async def test_include_degradation_false(self, home_team, away_team, league):
        """With include_degradation=False, should exclude DEGRADATION."""
        now = datetime.now(timezone.utc)

        fixtures = [
            create_fixture(
                fixture_id="pass",
                kickoff_time=now,
                odds_timestamp=now,
                form_timestamp=now,
                injuries_timestamp=now,
                home_team=home_team,
                away_team=away_team,
                league=league
            ),
            create_fixture(
                fixture_id="degrad",
                kickoff_time=now,
                odds_timestamp=now - timedelta(minutes=90),
                form_timestamp=now,
                injuries_timestamp=now,
                home_team=home_team,
                away_team=away_team,
                league=league
            ),
        ]

        filtered = await validate_and_filter(fixtures, include_degradation=False)
        assert len(filtered) == 1  # Only PASS
        assert filtered[0].fixture_id == "pass"

    @pytest.mark.asyncio
    async def test_always_exclude_critical(self, home_team, away_team, league):
        """Should always exclude CRITICAL fixtures."""
        now = datetime.now(timezone.utc)

        fixtures = [
            create_fixture(
                fixture_id="pass",
                kickoff_time=now,
                odds_timestamp=now,
                form_timestamp=now,
                injuries_timestamp=now,
                home_team=home_team,
                away_team=away_team,
                league=league
            ),
            create_fixture(
                fixture_id="critical",
                kickoff_time=now,
                odds_timestamp=None,  # CRITICAL
                form_timestamp=now,
                injuries_timestamp=now,
                home_team=home_team,
                away_team=away_team,
                league=league
            ),
        ]

        filtered = await validate_and_filter(fixtures, include_degradation=True)
        assert len(filtered) == 1
        assert filtered[0].fixture_id == "pass"


# ===== TEST: VALIDATION RESULT MODEL =====

class TestValidationResultModel:
    """Test ValidationResult model serialization."""

    def test_validation_result_serializable(self):
        """ValidationResult should be serializable to JSON."""
        result = ValidationResult(
            fixture_id="548821",
            status=ValidationStatus.PASS,
            reason="All data fresh",
            fixture_valid=True,
            odds_status="PASS",
            form_status="PASS",
            injuries_status="PASS",
            h2h_status="PASS",
            data_freshness_score=100,
        )

        # Should serialize without error
        serialized = result.model_dump()
        assert serialized["fixture_id"] == "548821"
        assert serialized["status"] == "PASS"
        assert serialized["data_freshness_score"] == 100

    def test_validation_result_with_age_data(self):
        """ValidationResult should store age information."""
        result = ValidationResult(
            fixture_id="548821",
            status=ValidationStatus.DEGRADATION,
            reason="Odds stale",
            fixture_valid=True,
            odds_status="DEGRADATION",
            odds_age_minutes=90,
            form_age_hours=5,
            injuries_age_hours=8,
            data_freshness_score=70,
        )

        assert result.odds_age_minutes == 90
        assert result.form_age_hours == 5
        assert result.injuries_age_hours == 8
