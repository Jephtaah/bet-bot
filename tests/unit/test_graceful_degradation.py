"""
Unit tests for graceful degradation and fetch_all_data orchestration.

Tests cover:
- fetch_all_data() orchestration with all sources succeeding
- Fallback logic: API-Football primary, ESPN backup
- Error handling: authentication errors halt pipeline
- Graceful degradation: individual source failures don't block others
- Logging: source tracking and transparency
- Concurrency: parallel async fetching for independent sources
- Edge cases: empty fixture list, partial data missing
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from bet_bot.data.fetchers import (
    fetch_all_data,
    fetch_team_form_with_fallback,
)
from bet_bot.exceptions import (
    APIAuthenticationError,
    APIRateLimitError,
    APIServerError,
    ScraperError,
)
from bet_bot.models import Fixture, Injury, Odds, TeamForm


class TestFetchAllDataSuccessful:
    """Test fetch_all_data with all sources succeeding."""

    @pytest.mark.asyncio
    async def test_fetch_all_data_all_sources_succeed(self):
        """Test fetch_all_data with all sources returning valid data."""
        # Create test fixtures
        fixture = MagicMock(spec=Fixture)
        fixture.fixture_id = "123"
        fixture.home_team_id = "1"
        fixture.home_team_name = "Leeds United"
        fixture.away_team_id = "2"
        fixture.away_team_name = "West Brom"
        fixture.league_id = "39"
        fixture.league_name = "Championship"

        # Create test models
        form_data = MagicMock(spec=TeamForm)
        form_data.team_id = "1"
        form_data.win_percentage_5 = 0.6

        injuries_data = MagicMock(spec=Injury)
        injuries_data.team_id = "1"

        odds_data = MagicMock(spec=Odds)
        odds_data.fixture_id = "123"

        # Mock all fetcher functions
        with patch("bet_bot.data.fetchers.fetch_fixtures", new_callable=AsyncMock) as mock_fixtures, \
             patch("bet_bot.data.fetchers.fetch_team_form", new_callable=AsyncMock) as mock_form, \
             patch("bet_bot.data.fetchers.fetch_team_form_espn", new_callable=AsyncMock) as mock_espn, \
             patch("bet_bot.data.fetchers.fetch_injuries", new_callable=AsyncMock) as mock_injuries, \
             patch("bet_bot.data.fetchers.fetch_odds", new_callable=AsyncMock) as mock_odds:

            # Setup mock returns
            mock_fixtures.return_value = [fixture]
            mock_form.return_value = form_data
            mock_injuries.return_value = [injuries_data]
            mock_odds.return_value = odds_data

            # Call fetch_all_data
            result = await fetch_all_data()

            # Verify result structure
            assert result is not None
            assert isinstance(result, dict)
            assert "fixtures" in result
            assert "form_data" in result
            assert "injuries" in result
            assert "odds" in result
            assert "h2h" in result

            # Verify data was collected
            assert len(result["fixtures"]) == 1
            assert len(result["form_data"]) > 0
            assert len(result["injuries"]) > 0
            assert len(result["odds"]) > 0

            # Verify fetchers were called
            mock_fixtures.assert_called_once()
            assert mock_form.called
            assert mock_injuries.called
            assert mock_odds.called

    @pytest.mark.asyncio
    async def test_fetch_all_data_with_fixture_date(self):
        """Test fetch_all_data respects fixture_date parameter."""
        fixture = MagicMock(spec=Fixture)
        fixture.fixture_id = "123"
        fixture.home_team_id = "1"
        fixture.home_team_name = "Leeds United"
        fixture.away_team_id = "2"
        fixture.away_team_name = "West Brom"
        fixture.league_id = "39"
        fixture.league_name = "Championship"

        with patch("bet_bot.data.fetchers.fetch_fixtures", new_callable=AsyncMock) as mock_fixtures, \
             patch("bet_bot.data.fetchers.fetch_team_form", new_callable=AsyncMock) as mock_form, \
             patch("bet_bot.data.fetchers.fetch_team_form_espn", new_callable=AsyncMock) as mock_espn, \
             patch("bet_bot.data.fetchers.fetch_injuries", new_callable=AsyncMock) as mock_injuries, \
             patch("bet_bot.data.fetchers.fetch_odds", new_callable=AsyncMock) as mock_odds:

            mock_fixtures.return_value = [fixture]
            mock_form.return_value = None
            mock_injuries.return_value = []
            mock_odds.return_value = None

            # Call with fixture_date
            await fetch_all_data(fixture_date="2025-11-25")

            # Verify fetch_fixtures was called with date
            mock_fixtures.assert_called_once()
            call_args = mock_fixtures.call_args
            assert call_args[1]["date"] == "2025-11-25"


class TestFetchAllDataFallback:
    """Test fetch_all_data fallback logic."""

    @pytest.mark.asyncio
    async def test_fetch_all_data_form_fallback_to_espn(self):
        """Test form data falls back to ESPN when API-Football fails."""
        fixture = MagicMock(spec=Fixture)
        fixture.fixture_id = "123"
        fixture.home_team_id = "1"
        fixture.home_team_name = "Leeds United"
        fixture.away_team_id = "2"
        fixture.away_team_name = "West Brom"
        fixture.league_id = "39"
        fixture.league_name = "Championship"

        espn_form = MagicMock(spec=TeamForm)
        espn_form.team_id = "1"

        with patch("bet_bot.data.fetchers.fetch_fixtures", new_callable=AsyncMock) as mock_fixtures, \
             patch("bet_bot.data.fetchers.fetch_team_form", new_callable=AsyncMock) as mock_form, \
             patch("bet_bot.data.fetchers.fetch_team_form_espn", new_callable=AsyncMock) as mock_espn, \
             patch("bet_bot.data.fetchers.fetch_injuries", new_callable=AsyncMock) as mock_injuries, \
             patch("bet_bot.data.fetchers.fetch_odds", new_callable=AsyncMock) as mock_odds:

            mock_fixtures.return_value = [fixture]
            # API-Football form fails, ESPN succeeds
            mock_form.return_value = None
            mock_espn.return_value = espn_form
            mock_injuries.return_value = []
            mock_odds.return_value = None

            result = await fetch_all_data()

            # Verify ESPN was called (fallback)
            assert mock_espn.called
            # Verify form data was included (from ESPN)
            assert "1" in result["form_data"]
            assert result["form_data"]["1"] == espn_form

    @pytest.mark.asyncio
    async def test_fetch_all_data_both_form_sources_fail(self):
        """Test graceful degradation when both form sources fail."""
        fixture = MagicMock(spec=Fixture)
        fixture.fixture_id = "123"
        fixture.home_team_id = "1"
        fixture.home_team_name = "Leeds United"
        fixture.away_team_id = "2"
        fixture.away_team_name = "West Brom"
        fixture.league_id = "39"
        fixture.league_name = "Championship"

        with patch("bet_bot.data.fetchers.fetch_fixtures", new_callable=AsyncMock) as mock_fixtures, \
             patch("bet_bot.data.fetchers.fetch_team_form", new_callable=AsyncMock) as mock_form, \
             patch("bet_bot.data.fetchers.fetch_team_form_espn", new_callable=AsyncMock) as mock_espn, \
             patch("bet_bot.data.fetchers.fetch_injuries", new_callable=AsyncMock) as mock_injuries, \
             patch("bet_bot.data.fetchers.fetch_odds", new_callable=AsyncMock) as mock_odds:

            mock_fixtures.return_value = [fixture]
            # Both form sources fail
            mock_form.return_value = None
            mock_espn.return_value = None
            mock_injuries.return_value = []
            mock_odds.return_value = None

            result = await fetch_all_data()

            # Verify pipeline continues with empty form_data
            assert result is not None
            assert result["form_data"] == {}
            assert len(result["fixtures"]) == 1  # Fixtures still loaded


class TestFetchAllDataErrors:
    """Test fetch_all_data error handling."""

    @pytest.mark.asyncio
    async def test_fetch_all_data_authentication_error_halts(self):
        """Test authentication error halts entire pipeline."""
        with patch("bet_bot.data.fetchers.fetch_fixtures", new_callable=AsyncMock) as mock_fixtures:
            # API-Football auth fails
            mock_fixtures.side_effect = APIAuthenticationError(
                "Invalid API key",
                url="https://api.example.com",
                status_code=401
            )

            result = await fetch_all_data()

            # Verify pipeline halts (returns None)
            assert result is None

            # Verify fixtures were attempted
            mock_fixtures.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_all_data_rate_limit_error_halts(self):
        """Test rate limit error halts pipeline."""
        with patch("bet_bot.data.fetchers.fetch_fixtures", new_callable=AsyncMock) as mock_fixtures:
            # API-Football rate limit error
            mock_fixtures.side_effect = APIRateLimitError(
                "Rate limit exceeded",
                url="https://api.example.com",
                status_code=429
            )

            result = await fetch_all_data()

            # Verify pipeline halts
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_all_data_server_error_continues(self):
        """Test server error allows graceful degradation."""
        fixture = MagicMock(spec=Fixture)
        fixture.fixture_id = "123"
        fixture.home_team_id = "1"
        fixture.home_team_name = "Leeds United"
        fixture.away_team_id = "2"
        fixture.away_team_name = "West Brom"
        fixture.league_id = "39"
        fixture.league_name = "Championship"

        with patch("bet_bot.data.fetchers.fetch_fixtures", new_callable=AsyncMock) as mock_fixtures, \
             patch("bet_bot.data.fetchers.fetch_team_form", new_callable=AsyncMock) as mock_form, \
             patch("bet_bot.data.fetchers.fetch_team_form_espn", new_callable=AsyncMock) as mock_espn, \
             patch("bet_bot.data.fetchers.fetch_injuries", new_callable=AsyncMock) as mock_injuries, \
             patch("bet_bot.data.fetchers.fetch_odds", new_callable=AsyncMock) as mock_odds:

            # Server error but recoverable
            mock_fixtures.side_effect = APIServerError(
                "Internal server error",
                url="https://api.example.com",
                status_code=500
            )
            mock_form.return_value = None
            mock_injuries.return_value = []
            mock_odds.return_value = None

            result = await fetch_all_data()

            # Verify pipeline continues (returns dict with empty data)
            assert result is not None
            assert isinstance(result, dict)
            assert result["fixtures"] == []

    @pytest.mark.asyncio
    async def test_fetch_all_data_timeout_continues(self):
        """Test timeout allows graceful degradation."""
        with patch("bet_bot.data.fetchers.fetch_fixtures", new_callable=AsyncMock) as mock_fixtures, \
             patch("bet_bot.data.fetchers.fetch_team_form", new_callable=AsyncMock) as mock_form, \
             patch("bet_bot.data.fetchers.fetch_team_form_espn", new_callable=AsyncMock) as mock_espn, \
             patch("bet_bot.data.fetchers.fetch_injuries", new_callable=AsyncMock) as mock_injuries, \
             patch("bet_bot.data.fetchers.fetch_odds", new_callable=AsyncMock) as mock_odds:

            # Timeout error
            mock_fixtures.side_effect = asyncio.TimeoutError("Request timed out")
            mock_form.return_value = None
            mock_injuries.return_value = []
            mock_odds.return_value = None

            result = await fetch_all_data()

            # Verify pipeline continues with empty data
            assert result is not None
            assert result["fixtures"] == []


class TestFetchAllDataEdgeCases:
    """Test fetch_all_data edge cases."""

    @pytest.mark.asyncio
    async def test_fetch_all_data_no_fixtures_skips_detailed_fetch(self):
        """Test that no detailed data is fetched if fixtures list is empty."""
        with patch("bet_bot.data.fetchers.fetch_fixtures", new_callable=AsyncMock) as mock_fixtures, \
             patch("bet_bot.data.fetchers.fetch_team_form", new_callable=AsyncMock) as mock_form, \
             patch("bet_bot.data.fetchers.fetch_team_form_espn", new_callable=AsyncMock) as mock_espn, \
             patch("bet_bot.data.fetchers.fetch_injuries", new_callable=AsyncMock) as mock_injuries, \
             patch("bet_bot.data.fetchers.fetch_odds", new_callable=AsyncMock) as mock_odds:

            # Empty fixture list
            mock_fixtures.return_value = []

            result = await fetch_all_data()

            # Verify detailed fetches were not called
            mock_form.assert_not_called()
            mock_injuries.assert_not_called()
            mock_odds.assert_not_called()

            # Verify result has empty data
            assert result is not None
            assert result["fixtures"] == []
            assert result["form_data"] == {}
            assert result["injuries"] == {}
            assert result["odds"] == {}

    @pytest.mark.asyncio
    async def test_fetch_all_data_partial_injuries(self):
        """Test graceful degradation with some teams missing injury data."""
        fixtures = []
        for i in range(2):
            fixture = MagicMock(spec=Fixture)
            fixture.fixture_id = str(i)
            fixture.home_team_id = str(i * 2)
            fixture.home_team_name = f"Team {i * 2}"
            fixture.away_team_id = str(i * 2 + 1)
            fixture.away_team_name = f"Team {i * 2 + 1}"
            fixture.league_id = "39"
            fixture.league_name = "Championship"
            fixtures.append(fixture)

        with patch("bet_bot.data.fetchers.fetch_fixtures", new_callable=AsyncMock) as mock_fixtures, \
             patch("bet_bot.data.fetchers.fetch_team_form", new_callable=AsyncMock) as mock_form, \
             patch("bet_bot.data.fetchers.fetch_team_form_espn", new_callable=AsyncMock) as mock_espn, \
             patch("bet_bot.data.fetchers.fetch_injuries", new_callable=AsyncMock) as mock_injuries, \
             patch("bet_bot.data.fetchers.fetch_odds", new_callable=AsyncMock) as mock_odds:

            mock_fixtures.return_value = fixtures
            mock_form.return_value = None
            mock_espn.return_value = None
            # Only some teams have injuries
            async def injuries_side_effect(team_id):
                return [MagicMock()] if team_id == "0" else []

            mock_injuries.side_effect = injuries_side_effect
            mock_odds.return_value = None

            result = await fetch_all_data()

            # Verify pipeline continues with partial injury data
            assert result is not None
            assert len(result["fixtures"]) == 2
            assert len(result["injuries"]) == 1  # Only team 0 has injuries
            assert "0" in result["injuries"]

    @pytest.mark.asyncio
    async def test_fetch_all_data_returns_none_on_critical_error(self):
        """Test that fetch_all_data returns None only on critical errors."""
        with patch("bet_bot.data.fetchers.fetch_fixtures", new_callable=AsyncMock) as mock_fixtures:
            mock_fixtures.side_effect = APIAuthenticationError(
                "Invalid credentials",
                url="https://api.example.com",
                status_code=401
            )

            result = await fetch_all_data()

            # Only critical errors return None
            assert result is None


class TestFetchAllDataSourceTracking:
    """Test source tracking and logging in fetch_all_data."""

    @pytest.mark.asyncio
    async def test_fetch_all_data_tracks_sources(self):
        """Test that fetch_all_data tracks which sources succeeded."""
        fixture = MagicMock(spec=Fixture)
        fixture.fixture_id = "123"
        fixture.home_team_id = "1"
        fixture.home_team_name = "Leeds United"
        fixture.away_team_id = "2"
        fixture.away_team_name = "West Brom"
        fixture.league_id = "39"
        fixture.league_name = "Championship"

        form_data = MagicMock(spec=TeamForm)
        form_data.team_id = "1"

        injuries_data = [MagicMock(spec=Injury)]
        odds_data = MagicMock(spec=Odds)
        odds_data.fixture_id = "123"

        with patch("bet_bot.data.fetchers.fetch_fixtures", new_callable=AsyncMock) as mock_fixtures, \
             patch("bet_bot.data.fetchers.fetch_team_form", new_callable=AsyncMock) as mock_form, \
             patch("bet_bot.data.fetchers.fetch_team_form_espn", new_callable=AsyncMock) as mock_espn, \
             patch("bet_bot.data.fetchers.fetch_injuries", new_callable=AsyncMock) as mock_injuries, \
             patch("bet_bot.data.fetchers.fetch_odds", new_callable=AsyncMock) as mock_odds, \
             patch("bet_bot.data.fetchers.logger") as mock_logger:

            mock_fixtures.return_value = [fixture]
            mock_form.return_value = form_data
            mock_injuries.return_value = injuries_data
            mock_odds.return_value = odds_data

            result = await fetch_all_data()

            # Verify source tracking logged
            assert any("Sources used:" in str(call) for call in mock_logger.info.call_args_list)


class TestFetchTeamFormWithFallback:
    """Test fetch_team_form_with_fallback fallback logic."""

    @pytest.mark.asyncio
    async def test_fetch_team_form_with_fallback_primary_success(self):
        """Test form fetch returns API-Football result when successful."""
        form_data = MagicMock(spec=TeamForm)
        form_data.team_id = "123"

        with patch("bet_bot.data.fetchers.fetch_team_form", new_callable=AsyncMock) as mock_api, \
             patch("bet_bot.data.fetchers.fetch_team_form_espn", new_callable=AsyncMock) as mock_espn:

            mock_api.return_value = form_data
            mock_espn.return_value = None

            result = await fetch_team_form_with_fallback(
                team_id="123",
                league_id="39",
                team_name="Leeds United",
                league="Championship"
            )

            assert result == form_data
            assert not mock_espn.called

    @pytest.mark.asyncio
    async def test_fetch_team_form_with_fallback_uses_espn(self):
        """Test form fetch falls back to ESPN when API-Football fails."""
        espn_form = MagicMock(spec=TeamForm)
        espn_form.team_id = "123"

        with patch("bet_bot.data.fetchers.fetch_team_form", new_callable=AsyncMock) as mock_api, \
             patch("bet_bot.data.fetchers.fetch_team_form_espn", new_callable=AsyncMock) as mock_espn:

            mock_api.return_value = None
            mock_espn.return_value = espn_form

            result = await fetch_team_form_with_fallback(
                team_id="123",
                league_id="39",
                team_name="Leeds United",
                league="Championship"
            )

            assert result == espn_form
            assert mock_espn.called

    @pytest.mark.asyncio
    async def test_fetch_team_form_with_fallback_both_fail(self):
        """Test form fetch returns None when both sources fail."""
        with patch("bet_bot.data.fetchers.fetch_team_form", new_callable=AsyncMock) as mock_api, \
             patch("bet_bot.data.fetchers.fetch_team_form_espn", new_callable=AsyncMock) as mock_espn:

            mock_api.return_value = None
            mock_espn.return_value = None

            result = await fetch_team_form_with_fallback(
                team_id="123",
                league_id="39",
                team_name="Leeds United",
                league="Championship"
            )

            assert result is None
            assert mock_api.called
            assert mock_espn.called
