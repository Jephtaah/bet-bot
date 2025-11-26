"""
Unit tests for API-Football client module.

Tests cover:
- HTTP client singleton pattern
- Rate limiting (token bucket algorithm)
- Retry logic with exponential backoff
- Error handling (401, 403, 404, 429, 5xx)
- Retry-After header parsing
- Fetch functions (fixtures, form, injuries, odds)
- Pydantic model validation
- Field alias mapping
- Graceful degradation
"""

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import ValidationError

from bet_bot.data.fetchers.api_football import (
    RateLimiter,
    api_football_limiter,
    close_http_client,
    fetch_fixtures,
    fetch_injuries,
    fetch_odds,
    fetch_team_form,
    fetch_with_rate_limit,
    fetch_with_retry,
    get_api_headers,
    get_http_client,
)
from bet_bot.exceptions import (
    APIAuthenticationError,
    APIError,
    APIRateLimitError,
    APIServerError,
)
from bet_bot.models import Fixture, Injury, Odds, TeamForm


class TestHTTPClient:
    """Test HTTP client singleton pattern."""

    @pytest.mark.asyncio
    async def test_get_http_client_singleton(self):
        """Test that get_http_client returns same instance."""
        client1 = await get_http_client()
        client2 = await get_http_client()

        assert client1 is client2

    @pytest.mark.asyncio
    async def test_http_client_configuration(self):
        """Test HTTP client is configured correctly."""
        client = await get_http_client()

        assert client.timeout.read == 30.0
        assert client.timeout.connect == 10.0
        assert client.limits.max_connections == 100
        assert client.limits.max_keepalive_connections == 20
        assert client.follow_redirects is True
        # Clean up after test
        await close_http_client()

    @pytest.mark.asyncio
    async def test_close_http_client(self):
        """Test closing HTTP client."""
        client = await get_http_client()
        await close_http_client()

        # Should create new instance after close
        new_client = await get_http_client()
        assert new_client is not client

        # Cleanup
        await close_http_client()


class TestRateLimiter:
    """Test rate limiter token bucket algorithm."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_under_limit(self):
        """Test rate limiter allows requests under limit."""
        limiter = RateLimiter(max_requests=10, time_window=1)

        start_time = time.time()
        for _ in range(10):
            await limiter.acquire()
        elapsed = time.time() - start_time

        # Should complete quickly (no blocking)
        assert elapsed < 0.5

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_over_limit(self):
        """Test rate limiter blocks when limit exceeded."""
        limiter = RateLimiter(max_requests=5, time_window=1)

        start_time = time.time()

        # Make 5 requests (should be instant)
        for _ in range(5):
            await limiter.acquire()

        # 6th request should block
        await limiter.acquire()
        elapsed = time.time() - start_time

        # Should have waited ~1 second
        assert elapsed >= 0.9  # Allow small timing variance

    @pytest.mark.asyncio
    async def test_rate_limiter_sliding_window(self):
        """Test rate limiter uses sliding window correctly."""
        limiter = RateLimiter(max_requests=3, time_window=1)

        # Make 3 requests
        for _ in range(3):
            await limiter.acquire()

        # Wait half the window
        await asyncio.sleep(0.5)

        # Should still block (window hasn't expired)
        start_time = time.time()
        await limiter.acquire()
        elapsed = time.time() - start_time

        # Should wait remaining time (~0.5s)
        assert 0.4 <= elapsed <= 0.7


class TestAuthHeaders:
    """Test API authentication header generation."""

    def test_get_api_headers_format(self):
        """Test API headers have correct format."""
        headers = get_api_headers()

        assert "x-rapidapi-key" in headers
        assert "x-rapidapi-host" in headers
        assert headers["x-rapidapi-host"] == "api-football-v3.p.rapidapi.com"
        assert "User-Agent" in headers
        assert "Accept" in headers


class TestRetryLogic:
    """Test retry logic with exponential backoff."""

    @pytest.mark.asyncio
    async def test_fetch_with_retry_success(self):
        """Test successful fetch with retry decorator."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": []}

        with patch("bet_bot.data.fetchers.api_football.get_http_client") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            response = await fetch_with_retry("https://test.com")

            assert response.status_code == 200
            mock_instance.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_with_retry_retries_5xx(self):
        """Test retry logic retries 5xx errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="Server Error",
            request=MagicMock(),
            response=mock_response
        )

        with patch("bet_bot.data.fetchers.api_football.get_http_client") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            with pytest.raises(httpx.HTTPStatusError):
                await fetch_with_retry("https://test.com")

            # Should have retried 5 times
            assert mock_instance.get.call_count == 5

    @pytest.mark.asyncio
    async def test_fetch_with_retry_does_not_retry_4xx(self):
        """Test retry logic does NOT retry 4xx errors."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("bet_bot.data.fetchers.api_football.get_http_client") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            response = await fetch_with_retry("https://test.com")

            assert response.status_code == 404
            # Should NOT retry
            mock_instance.get.assert_called_once()


class TestErrorHandling:
    """Test error handling for different HTTP status codes."""

    @pytest.mark.asyncio
    async def test_401_raises_authentication_error(self):
        """Test 401 response raises APIAuthenticationError."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid API key"

        error = httpx.HTTPStatusError(
            message="Auth failed",
            request=MagicMock(),
            response=mock_response
        )

        with patch("bet_bot.data.fetchers.api_football.fetch_with_retry") as mock_fetch:
            mock_fetch.side_effect = error

            with pytest.raises(APIAuthenticationError) as exc_info:
                await fetch_with_rate_limit("https://test.com")

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_403_raises_authentication_error(self):
        """Test 403 response raises APIAuthenticationError."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"

        error = httpx.HTTPStatusError(
            message="Forbidden",
            request=MagicMock(),
            response=mock_response
        )

        with patch("bet_bot.data.fetchers.api_football.fetch_with_retry") as mock_fetch:
            mock_fetch.side_effect = error

            with pytest.raises(APIAuthenticationError) as exc_info:
                await fetch_with_rate_limit("https://test.com")

            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_404_returns_none(self):
        """Test 404 response returns None (graceful degradation)."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        error = httpx.HTTPStatusError(
            message="Not Found",
            request=MagicMock(),
            response=mock_response
        )

        with patch("bet_bot.data.fetchers.api_football.fetch_with_retry") as mock_fetch:
            mock_fetch.side_effect = error

            result = await fetch_with_rate_limit("https://test.com")

            assert result is None

    @pytest.mark.asyncio
    async def test_500_raises_server_error(self):
        """Test 5xx response raises APIServerError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        error = httpx.HTTPStatusError(
            message="Server Error",
            request=MagicMock(),
            response=mock_response
        )

        with patch("bet_bot.data.fetchers.api_football.fetch_with_retry") as mock_fetch:
            mock_fetch.side_effect = error

            with pytest.raises(APIServerError) as exc_info:
                await fetch_with_rate_limit("https://test.com")

            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self):
        """Test timeout returns None (graceful degradation)."""
        with patch("bet_bot.data.fetchers.api_football.fetch_with_retry") as mock_fetch:
            mock_fetch.side_effect = httpx.TimeoutException("Timeout")

            result = await fetch_with_rate_limit("https://test.com")

            assert result is None

    @pytest.mark.asyncio
    async def test_network_error_returns_none(self):
        """Test network error returns None (graceful degradation)."""
        with patch("bet_bot.data.fetchers.api_football.fetch_with_retry") as mock_fetch:
            mock_fetch.side_effect = httpx.NetworkError("Connection failed")

            result = await fetch_with_rate_limit("https://test.com")

            assert result is None


class TestRetryAfterHeader:
    """Test Retry-After header parsing and handling."""

    @pytest.mark.asyncio
    async def test_retry_after_seconds_format(self):
        """Test Retry-After header with seconds format."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "5"}

        call_count = 0

        async def mock_fetch_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                return mock_response
            else:
                # Return success on retry
                success_response = MagicMock()
                success_response.status_code = 200
                success_response.json.return_value = {"response": []}
                return success_response

        with patch("bet_bot.data.fetchers.api_football.fetch_with_retry") as mock_fetch:
            with patch("asyncio.sleep") as mock_sleep:
                mock_fetch.side_effect = mock_fetch_side_effect

                result = await fetch_with_rate_limit("https://test.com")

                # Should have waited 5 seconds
                mock_sleep.assert_called_once_with(5)
                assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_after_http_date_format(self):
        """Test Retry-After header with HTTP date format."""
        # Future date (5 seconds from now)
        future_date = datetime.now(timezone.utc).replace(tzinfo=None)
        retry_date_str = future_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": retry_date_str}

        call_count = 0

        async def mock_fetch_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                return mock_response
            else:
                success_response = MagicMock()
                success_response.status_code = 200
                success_response.json.return_value = {"response": []}
                return success_response

        with patch("bet_bot.data.fetchers.api_football.fetch_with_retry") as mock_fetch:
            with patch("asyncio.sleep") as mock_sleep:
                mock_fetch.side_effect = mock_fetch_side_effect

                result = await fetch_with_rate_limit("https://test.com")

                # Should have called sleep
                assert mock_sleep.called
                assert call_count == 2


class TestFetchFixtures:
    """Test fetch_fixtures function."""

    @pytest.mark.asyncio
    async def test_fetch_fixtures_success(self):
        """Test successful fixture fetching."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": [
                {
                    "fixture": {
                        "id": 1423864,
                        "date": "2025-11-25T15:00:00+00:00"
                    },
                    "league": {
                        "id": 39,
                        "name": "Premier League",
                        "country": "England",
                        "season": 2025
                    },
                    "teams": {
                        "home": {"id": 33, "name": "Manchester United"},
                        "away": {"id": 34, "name": "Newcastle"}
                    }
                }
            ]
        }

        with patch("bet_bot.data.fetchers.api_football.fetch_with_rate_limit") as mock_fetch:
            mock_fetch.return_value = mock_response

            fixtures = await fetch_fixtures(date="2025-11-25")

            assert len(fixtures) == 1
            assert fixtures[0].fixture_id == "1423864"
            assert fixtures[0].home_team.name == "Manchester United"
            assert fixtures[0].away_team.name == "Newcastle"
            assert fixtures[0].league.league_name == "Premier League"

    @pytest.mark.asyncio
    async def test_fetch_fixtures_no_data(self):
        """Test fetch_fixtures returns empty list for 404."""
        with patch("bet_bot.data.fetchers.api_football.fetch_with_rate_limit") as mock_fetch:
            mock_fetch.return_value = None

            fixtures = await fetch_fixtures(date="2025-11-25")

            assert fixtures == []

    @pytest.mark.asyncio
    async def test_fetch_fixtures_empty_response(self):
        """Test fetch_fixtures handles empty response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": []}

        with patch("bet_bot.data.fetchers.api_football.fetch_with_rate_limit") as mock_fetch:
            mock_fetch.return_value = mock_response

            fixtures = await fetch_fixtures(date="2025-11-25")

            assert fixtures == []


class TestFetchTeamForm:
    """Test fetch_team_form function."""

    @pytest.mark.asyncio
    async def test_fetch_team_form_success(self):
        """Test successful team form fetching."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": {
                "form": "WWDLW",
                "fixtures": {"played": {"total": 10}},
                "goals": {
                    "for": {"average": {"total": 2.5}},
                    "against": {"average": {"total": 1.2}}
                }
            }
        }

        with patch("bet_bot.data.fetchers.api_football.fetch_with_rate_limit") as mock_fetch:
            mock_fetch.return_value = mock_response

            form = await fetch_team_form(
                team_id="33",
                league_id="39",
                team_name="Manchester United",
                season=2025
            )

            assert form is not None
            assert form.team_id == "33"
            assert form.team_name == "Manchester United"
            assert form.last_5_results == ["W", "W", "D", "L", "W"]  # Last 5 of "WWDLW" (full string)
            assert form.win_percentage_5 == 0.6  # 3/5 wins
            assert form.goals_avg_home == 2.5
            assert form.goals_avg_away == 2.5
            assert form.goals_against_avg_home == 1.2
            assert form.goals_against_avg_away == 1.2

    @pytest.mark.asyncio
    async def test_fetch_team_form_no_data(self):
        """Test fetch_team_form returns TeamForm with zeros for no data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": {}}

        with patch("bet_bot.data.fetchers.api_football.fetch_with_rate_limit") as mock_fetch:
            mock_fetch.return_value = mock_response

            form = await fetch_team_form(
                team_id="33",
                league_id="39",
                team_name="Manchester United"
            )

            assert form is not None
            assert form.team_id == "33"
            assert form.team_name == "Manchester United"
            assert form.last_5_results == []
            assert form.win_percentage_5 == 0.0
            assert form.goals_avg_home == 0.0
            assert form.goals_avg_away == 0.0

    @pytest.mark.asyncio
    async def test_fetch_team_form_network_error(self):
        """Test fetch_team_form returns None on network error."""
        with patch("bet_bot.data.fetchers.api_football.fetch_with_rate_limit") as mock_fetch:
            mock_fetch.return_value = None

            form = await fetch_team_form(
                team_id="33",
                league_id="39",
                team_name="Manchester United"
            )

            assert form is None


class TestFetchInjuries:
    """Test fetch_injuries function."""

    @pytest.mark.asyncio
    async def test_fetch_injuries_success(self):
        """Test successful injury fetching."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": [
                {
                    "player": {
                        "id": 123,
                        "name": "John Doe",
                        "position": "Forward",
                        "type": "injury",
                        "reason": "Injured - Knee"
                    }
                },
                {
                    "player": {
                        "id": 124,
                        "name": "Jane Smith",
                        "position": "Midfielder",
                        "type": "suspension",
                        "reason": "Suspended - Red Card"
                    }
                }
            ]
        }

        with patch("bet_bot.data.fetchers.api_football.fetch_with_rate_limit") as mock_fetch:
            mock_fetch.return_value = mock_response

            injuries = await fetch_injuries(team_id="33")

            assert injuries is not None
            assert injuries.team_id == "33"
            assert len(injuries.injured_players) == 2
            assert injuries.missing_key_players_count == 2.0
            assert "John Doe" in injuries.missing_key_players_list

    @pytest.mark.asyncio
    async def test_fetch_injuries_no_data(self):
        """Test fetch_injuries returns empty Injury for no data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": []}

        with patch("bet_bot.data.fetchers.api_football.fetch_with_rate_limit") as mock_fetch:
            mock_fetch.return_value = mock_response

            injuries = await fetch_injuries(team_id="33")

            assert injuries is not None
            assert injuries.team_id == "33"
            assert len(injuries.injured_players) == 0
            assert injuries.missing_key_players_count == 0


class TestFetchOdds:
    """Test fetch_odds function."""

    @pytest.mark.asyncio
    async def test_fetch_odds_success(self):
        """Test successful odds fetching with multiple markets."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": [
                {
                    "fixture": {"id": 1423864},
                    "update": "2025-11-24T14:30:00+00:00",
                    "bookmakers": [
                        {"id": 4, "name": "Pinnacle"}
                    ],
                    "bets": [
                        {
                            "id": 1,
                            "name": "Match Result",
                            "values": [
                                {"value": "Home", "odd": "2.10"},
                                {"value": "Draw", "odd": "3.40"},
                                {"value": "Away", "odd": "3.75"}
                            ]
                        },
                        {
                            "id": 3,
                            "name": "Goals Over/Under 2.5",
                            "values": [
                                {"value": "Over 2.5", "odd": "1.85"},
                                {"value": "Under 2.5", "odd": "1.95"}
                            ]
                        }
                    ]
                }
            ]
        }

        with patch("bet_bot.data.fetchers.api_football.fetch_with_rate_limit") as mock_fetch:
            mock_fetch.return_value = mock_response

            odds = await fetch_odds(fixture_id="1423864")

            assert odds is not None
            assert odds.fixture_id == "1423864"
            assert odds.bookmaker_name == "Pinnacle"
            assert len(odds.markets) == 2

            # Check Match Result market
            match_result = [m for m in odds.markets if m.market_type == "Match Result"][0]
            assert match_result.odds["Home"] == 2.10
            assert match_result.odds["Draw"] == 3.40
            assert match_result.odds["Away"] == 3.75

            # Check Over/Under market
            ou_market = [m for m in odds.markets if "Over/Under" in m.market_type][0]
            assert ou_market.odds["Over 2.5"] == 1.85
            assert ou_market.odds["Under 2.5"] == 1.95

            # Verify timestamp was extracted
            assert odds.odds_updated_at is not None
            assert odds.odds_updated_at.year == 2025
            assert odds.odds_updated_at.month == 11
            assert odds.odds_updated_at.day == 24

    @pytest.mark.asyncio
    async def test_fetch_odds_missing_markets(self):
        """Test fetch_odds handles missing markets gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": [
                {
                    "fixture": {"id": 1423864},
                    "update": "2025-11-24T14:30:00+00:00",
                    "bookmakers": [
                        {"id": 4, "name": "Bet365"}
                    ],
                    "bets": [
                        {
                            "id": 1,
                            "name": "Match Result",
                            "values": [
                                {"value": "Home", "odd": "2.10"},
                                {"value": "Draw", "odd": "3.40"},
                                {"value": "Away", "odd": "3.75"}
                            ]
                        },
                        {
                            "id": 999,
                            "name": "Unavailable Market",
                            "values": []  # No values - market not available
                        }
                    ]
                }
            ]
        }

        with patch("bet_bot.data.fetchers.api_football.fetch_with_rate_limit") as mock_fetch:
            mock_fetch.return_value = mock_response

            odds = await fetch_odds(fixture_id="1423864")

            # Should return Odds with only available market
            assert odds is not None
            assert len(odds.markets) == 1
            assert odds.markets[0].market_type == "Match Result"

    @pytest.mark.asyncio
    async def test_fetch_odds_invalid_odds_values(self):
        """Test fetch_odds skips invalid odds values."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": [
                {
                    "fixture": {"id": 1423864},
                    "update": "2025-11-24T14:30:00+00:00",
                    "bookmakers": [
                        {"id": 4, "name": "TestBook"}
                    ],
                    "bets": [
                        {
                            "id": 1,
                            "name": "Match Result",
                            "values": [
                                {"value": "Home", "odd": "2.10"},
                                {"value": "Invalid", "odd": "0.50"},  # Invalid: < 1.0
                                {"value": "Draw", "odd": "3.40"}
                            ]
                        }
                    ]
                }
            ]
        }

        with patch("bet_bot.data.fetchers.api_football.fetch_with_rate_limit") as mock_fetch:
            mock_fetch.return_value = mock_response

            odds = await fetch_odds(fixture_id="1423864")

            # Should skip invalid odds and return market with valid outcomes only
            assert odds is not None
            assert len(odds.markets) == 1
            assert "Invalid" not in odds.markets[0].odds
            assert odds.markets[0].odds["Home"] == 2.10
            assert odds.markets[0].odds["Draw"] == 3.40

    @pytest.mark.asyncio
    async def test_fetch_odds_stale_odds(self):
        """Test fetch_odds logs warning for stale odds but still returns them."""
        from datetime import timedelta

        # Create timestamp > 1 hour old
        stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
        stale_timestamp = stale_time.isoformat() + "+00:00"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": [
                {
                    "fixture": {"id": 1423864},
                    "update": stale_timestamp,
                    "bookmakers": [
                        {"id": 4, "name": "TestBook"}
                    ],
                    "bets": [
                        {
                            "id": 1,
                            "name": "Match Result",
                            "values": [
                                {"value": "Home", "odd": "2.10"},
                                {"value": "Draw", "odd": "3.40"},
                                {"value": "Away", "odd": "3.75"}
                            ]
                        }
                    ]
                }
            ]
        }

        with patch("bet_bot.data.fetchers.api_football.fetch_with_rate_limit") as mock_fetch:
            mock_fetch.return_value = mock_response

            odds = await fetch_odds(fixture_id="1423864")

            # Should still return Odds despite being stale
            assert odds is not None
            assert len(odds.markets) == 1

    @pytest.mark.asyncio
    async def test_fetch_odds_no_data(self):
        """Test fetch_odds returns None for empty response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": []}

        with patch("bet_bot.data.fetchers.api_football.fetch_with_rate_limit") as mock_fetch:
            mock_fetch.return_value = mock_response

            odds = await fetch_odds(fixture_id="1423864")

            assert odds is None

    @pytest.mark.asyncio
    async def test_fetch_odds_network_error(self):
        """Test fetch_odds returns None on network error."""
        with patch("bet_bot.data.fetchers.api_football.fetch_with_rate_limit") as mock_fetch:
            mock_fetch.return_value = None

            odds = await fetch_odds(fixture_id="1423864")

            assert odds is None
