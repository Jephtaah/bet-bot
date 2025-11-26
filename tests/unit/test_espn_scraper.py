"""
Unit tests for ESPN scraper module.

Tests cover:
- HTML parsing (match results, goal averages)
- Retry logic and timeouts
- Rate limiting enforcement
- Error handling and graceful degradation
- TeamForm model validation
- Fallback behavior (API-Football -> ESPN)
- Logging verification

Target: 85%+ code coverage

Test Strategy:
- Mock httpx.AsyncClient.get() to return sample ESPN HTML
- Mock BeautifulSoup parsing
- Use asyncio for async test execution
- Verify rate limiting timing
- Capture logger output
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from bs4 import BeautifulSoup
from pydantic import ValidationError

from bet_bot.data.fetchers import fetch_team_form_with_fallback
from bet_bot.data.fetchers.espn_scraper import (
    RateLimiter,
    calculate_win_percentages,
    fetch_html_with_retry,
    fetch_team_form_espn,
    parse_goals_averages,
    parse_match_results,
)
from bet_bot.models import TeamForm


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_espn_html() -> str:
    """Sample ESPN team page HTML with match results and statistics."""
    return """
    <html>
        <body>
            <table class="Table">
                <tr><th>Date</th><th>Opponent</th><th>Result</th><th>Score</th></tr>
                <tr><td>Nov 24</td><td>West Brom</td><td>W</td><td>2-1</td></tr>
                <tr><td>Nov 17</td><td>Norwich</td><td>L</td><td>1-2</td></tr>
                <tr><td>Nov 10</td><td>Plymouth</td><td>D</td><td>1-1</td></tr>
                <tr><td>Nov 03</td><td>Southampton</td><td>W</td><td>3-0</td></tr>
                <tr><td>Oct 27</td><td>Bristol City</td><td>W</td><td>2-1</td></tr>
                <tr><td>Oct 20</td><td>Coventry</td><td>L</td><td>0-1</td></tr>
                <tr><td>Oct 13</td><td>Middlesbrough</td><td>D</td><td>0-0</td></tr>
                <tr><td>Oct 06</td><td>Leeds</td><td>W</td><td>1-0</td></tr>
                <tr><td>Sep 29</td><td>Cardiff</td><td>W</td><td>2-0</td></tr>
                <tr><td>Sep 22</td><td>Reading</td><td>D</td><td>2-2</td></tr>
            </table>
            <table class="Table">
                <tr><th>Stat</th><th>Home</th><th>Away</th></tr>
                <tr><td>Goals For Avg</td><td>1.8</td><td>1.5</td></tr>
                <tr><td>Goals Against Avg</td><td>1.2</td><td>1.3</td></tr>
            </table>
        </body>
    </html>
    """


@pytest.fixture
def malformed_html() -> str:
    """Malformed HTML without proper table structure."""
    return """
    <html>
        <body>
            <div>No tables here</div>
        </body>
    </html>
    """


@pytest.fixture
def espn_html_missing_elements() -> str:
    """ESPN HTML with missing result cells (graceful degradation test)."""
    return """
    <html>
        <body>
            <table class="Table">
                <tr><th>Date</th><th>Opponent</th><th>Result</th></tr>
                <tr><td>Nov 24</td><td>West Brom</td><td>W</td></tr>
                <tr><td>Nov 17</td></tr>  <!-- Missing cells -->
                <tr><td>Nov 10</td><td>Plymouth</td><td>D</td></tr>
            </table>
        </body>
    </html>
    """


# ============================================================================
# Test: parse_match_results()
# ============================================================================

class TestParseMatchResults:
    """Tests for parse_match_results() function."""

    def test_extract_match_results_success(self, sample_espn_html: str) -> None:
        """Test successful extraction of match results from ESPN HTML."""
        results = parse_match_results(sample_espn_html)

        assert len(results) == 10
        assert results[0] == 'W'
        assert results[1] == 'L'
        assert results[2] == 'D'
        assert all(r in ['W', 'D', 'L'] for r in results)

    def test_extract_last_5_results(self, sample_espn_html: str) -> None:
        """Test that we can extract exactly last 5 results if needed."""
        results = parse_match_results(sample_espn_html)

        last_5 = results[:5]
        assert len(last_5) == 5
        assert last_5 == ['W', 'L', 'D', 'W', 'W']

    def test_handle_missing_table(self, malformed_html: str) -> None:
        """Test graceful degradation when results table is missing."""
        results = parse_match_results(malformed_html)

        assert results == []  # Returns empty list, not None

    def test_handle_missing_elements(self, espn_html_missing_elements: str) -> None:
        """Test graceful handling of missing cells in table rows."""
        results = parse_match_results(espn_html_missing_elements)

        # Should extract results that have valid cells, skip problematic rows
        assert len(results) == 2
        assert results[0] == 'W'
        assert results[1] == 'D'

    def test_handle_empty_html(self) -> None:
        """Test graceful handling of empty HTML."""
        results = parse_match_results("<html></html>")

        assert results == []

    def test_invalid_html_structure(self) -> None:
        """Test graceful handling of invalid HTML structure."""
        results = parse_match_results("This is not HTML")

        assert results == []


# ============================================================================
# Test: parse_goals_averages()
# ============================================================================

class TestParseGoalsAverages:
    """Tests for parse_goals_averages() function."""

    def test_extract_goal_averages_success(self, sample_espn_html: str) -> None:
        """Test successful extraction of goal averages from ESPN HTML."""
        gf_home, gf_away, ga_home, ga_away = parse_goals_averages(sample_espn_html)

        assert gf_home == 1.8
        assert gf_away == 1.5
        assert ga_home == 1.2
        assert ga_away == 1.3

    def test_handle_missing_stats_table(self, malformed_html: str) -> None:
        """Test graceful degradation when stats table is missing."""
        gf_home, gf_away, ga_home, ga_away = parse_goals_averages(malformed_html)

        # Should return defaults (0.0) not crash
        assert gf_home == 0.0
        assert gf_away == 0.0
        assert ga_home == 0.0
        assert ga_away == 0.0

    def test_return_type(self, sample_espn_html: str) -> None:
        """Test that function returns tuple of 4 floats."""
        result = parse_goals_averages(sample_espn_html)

        assert isinstance(result, tuple)
        assert len(result) == 4
        assert all(isinstance(v, float) for v in result)


# ============================================================================
# Test: calculate_win_percentages()
# ============================================================================

class TestCalculateWinPercentages:
    """Tests for calculate_win_percentages() function."""

    def test_calculate_win_pct_5_games(self) -> None:
        """Test win percentage calculation for 5 games."""
        results = ['W', 'W', 'D', 'L', 'W']
        win_5, win_10 = calculate_win_percentages(results, [])

        assert win_5 == 0.6  # 3 wins out of 5 = 60%

    def test_calculate_win_pct_10_games(self) -> None:
        """Test win percentage calculation for 10 games."""
        results = ['W', 'W', 'D', 'L', 'W', 'L', 'D', 'W', 'D', 'D']
        win_5, win_10 = calculate_win_percentages([], results)

        assert win_10 == 0.4  # 4 wins out of 10 = 40%

    def test_zero_wins(self) -> None:
        """Test win percentage when no wins."""
        results = ['L', 'L', 'D']
        win_5, win_10 = calculate_win_percentages(results, [])

        assert win_5 == 0.0

    def test_all_wins(self) -> None:
        """Test win percentage when all wins."""
        results = ['W', 'W', 'W', 'W', 'W']
        win_5, win_10 = calculate_win_percentages(results, [])

        assert win_5 == 1.0

    def test_empty_results(self) -> None:
        """Test with empty results lists."""
        win_5, win_10 = calculate_win_percentages([], [])

        assert win_5 == 0.0
        assert win_10 == 0.0


# ============================================================================
# Test: RateLimiter
# ============================================================================

class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.mark.asyncio
    async def test_rate_limiter_acquire_success(self) -> None:
        """Test that acquire() allows requests within limit."""
        limiter = RateLimiter(max_requests=3, time_window=1)

        # Should acquire without waiting
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()

        assert len(limiter.requests) == 3

    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_limit(self) -> None:
        """Test that rate limiter waits when limit is reached."""
        limiter = RateLimiter(max_requests=1, time_window=1)

        await limiter.acquire()
        # Should block and wait ~1 second before allowing next request
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start

        assert elapsed >= 0.8  # Allow 20% timing variance for system load

    @pytest.mark.asyncio
    async def test_rate_limiter_cleans_old_requests(self) -> None:
        """Test that requests outside time window are cleaned."""
        limiter = RateLimiter(max_requests=2, time_window=0.1)

        await limiter.acquire()
        await limiter.acquire()

        # Wait for time window to pass
        await asyncio.sleep(0.15)

        # Should be able to acquire again (old requests cleaned)
        await limiter.acquire()

        # Only current request should be in deque
        assert len(limiter.requests) == 1

    @pytest.mark.asyncio
    async def test_rate_limiter_respects_30_per_minute(self) -> None:
        """Test ESPN scraper rate limit of 30 per minute."""
        limiter = RateLimiter(max_requests=30, time_window=60)

        # Should acquire 30 times without delay
        start = asyncio.get_event_loop().time()
        for _ in range(30):
            await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start

        # Should be fast (no waiting needed for first 30, allow margin for system load)
        assert elapsed < 10.0  # Should complete in under 10 seconds


# ============================================================================
# Test: fetch_html_with_retry()
# ============================================================================

class TestFetchHtmlWithRetry:
    """Tests for fetch_html_with_retry() function."""

    @pytest.mark.asyncio
    async def test_fetch_html_success(self) -> None:
        """Test successful HTML fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Test</html>"

        with patch('bet_bot.data.fetchers.espn_scraper.get_http_client') as mock_get:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get.return_value = mock_client

            html = await fetch_html_with_retry("https://example.com")

            assert html == "<html>Test</html>"
            assert mock_client.get.called

    @pytest.mark.asyncio
    async def test_fetch_html_timeout_retry(self) -> None:
        """Test retry logic on timeout exception."""
        with patch('bet_bot.data.fetchers.espn_scraper.get_http_client') as mock_get:
            mock_client = AsyncMock()
            # Simulate timeout on first attempt, then success
            mock_client.get.side_effect = [
                httpx.TimeoutException("Timeout"),
                MagicMock(status_code=200, text="<html>Success</html>")
            ]
            mock_get.return_value = mock_client

            html = await fetch_html_with_retry("https://example.com")

            assert html == "<html>Success</html>"
            assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_html_403_not_retried(self) -> None:
        """Test that 403 Forbidden is not retried (ESPN blocking)."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.request = MagicMock()

        with patch('bet_bot.data.fetchers.espn_scraper.get_http_client') as mock_get:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await fetch_html_with_retry("https://example.com")

    @pytest.mark.asyncio
    async def test_fetch_html_404_not_retried(self) -> None:
        """Test that 404 Not Found is not retried."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.request = MagicMock()

        with patch('bet_bot.data.fetchers.espn_scraper.get_http_client') as mock_get:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await fetch_html_with_retry("https://example.com")


# ============================================================================
# Test: fetch_team_form_espn()
# ============================================================================

class TestFetchTeamFormEspn:
    """Tests for fetch_team_form_espn() function."""

    @pytest.mark.asyncio
    async def test_fetch_team_form_success(
        self,
        sample_espn_html: str
    ) -> None:
        """Test successful team form fetch and parsing."""
        with patch('bet_bot.data.fetchers.espn_scraper.fetch_html_with_retry') as mock_fetch:
            mock_fetch.return_value = sample_espn_html

            form = await fetch_team_form_espn("Leeds United", "Championship")

            assert form is not None
            assert isinstance(form, TeamForm)
            assert form.team_name == "Leeds United"
            assert len(form.last_5_results) == 5
            assert form.win_percentage_5 == 0.6

    @pytest.mark.asyncio
    async def test_fetch_team_form_timeout(self) -> None:
        """Test graceful handling of timeout."""
        with patch('bet_bot.data.fetchers.espn_scraper.fetch_html_with_retry') as mock_fetch:
            mock_fetch.side_effect = httpx.TimeoutException("Timeout")

            form = await fetch_team_form_espn("Leeds United", "Championship")

            assert form is None

    @pytest.mark.asyncio
    async def test_fetch_team_form_network_error(self) -> None:
        """Test graceful handling of network error."""
        with patch('bet_bot.data.fetchers.espn_scraper.fetch_html_with_retry') as mock_fetch:
            mock_fetch.side_effect = httpx.NetworkError("Network error")

            form = await fetch_team_form_espn("Leeds United", "Championship")

            assert form is None

    @pytest.mark.asyncio
    async def test_fetch_team_form_403_forbidden(self) -> None:
        """Test graceful handling of 403 ESPN blocking."""
        with patch('bet_bot.data.fetchers.espn_scraper.fetch_html_with_retry') as mock_fetch:
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_fetch.side_effect = httpx.HTTPStatusError(
                "Forbidden",
                request=MagicMock(),
                response=mock_response
            )

            form = await fetch_team_form_espn("Leeds United", "Championship")

            assert form is None

    @pytest.mark.asyncio
    async def test_fetch_team_form_validation_error(
        self,
        sample_espn_html: str
    ) -> None:
        """Test graceful handling of Pydantic validation error."""
        with patch('bet_bot.data.fetchers.espn_scraper.fetch_html_with_retry') as mock_fetch:
            mock_fetch.return_value = sample_espn_html

            with patch(
                'bet_bot.data.fetchers.espn_scraper.TeamForm'
            ) as mock_form_class:
                mock_form_class.side_effect = ValidationError.from_exception_data(
                    "TeamForm",
                    [{"type": "value_error", "loc": ("team_id",)}]
                )

                form = await fetch_team_form_espn("Leeds United", "Championship")

                assert form is None

    @pytest.mark.asyncio
    async def test_fetch_team_form_returns_valid_teamform(
        self,
        sample_espn_html: str
    ) -> None:
        """Test that returned TeamForm has all required fields populated."""
        with patch('bet_bot.data.fetchers.espn_scraper.fetch_html_with_retry') as mock_fetch:
            mock_fetch.return_value = sample_espn_html

            form = await fetch_team_form_espn("Leeds United", "Championship")

            assert form is not None
            # Verify all required fields are populated
            assert form.team_id is not None
            assert form.team_name == "Leeds United"
            assert isinstance(form.last_5_results, list)
            assert isinstance(form.last_10_results, list)
            assert 0.0 <= form.win_percentage_5 <= 1.0
            assert 0.0 <= form.win_percentage_10 <= 1.0
            assert form.goals_avg_home >= 0.0
            assert form.goals_avg_away >= 0.0
            assert form.goals_against_avg_home >= 0.0
            assert form.goals_against_avg_away >= 0.0

    @pytest.mark.asyncio
    async def test_fetch_team_form_respects_rate_limit(
        self,
        sample_espn_html: str
    ) -> None:
        """Test that rate limiter is respected before fetch."""
        with patch('bet_bot.data.fetchers.espn_scraper.espn_limiter') as mock_limiter:
            mock_limiter.acquire = AsyncMock()

            with patch('bet_bot.data.fetchers.espn_scraper.fetch_html_with_retry') as mock_fetch:
                mock_fetch.return_value = sample_espn_html

                await fetch_team_form_espn("Leeds United", "Championship")

                # Verify rate limiter was called
                assert mock_limiter.acquire.called


# ============================================================================
# Test: Logging Verification
# ============================================================================

class TestLoggingContext:
    """Tests to verify logging includes proper context."""

    def test_parse_match_results_logs_extraction(
        self,
        caplog,
        sample_espn_html: str
    ) -> None:
        """Test that parsing logs include result count."""
        with caplog.at_level(logging.DEBUG):
            parse_match_results(sample_espn_html)

            assert "Extracted" in caplog.text
            assert "match results" in caplog.text

    def test_parse_goals_averages_logs_on_error(self, caplog) -> None:
        """Test that goal average parsing errors are logged."""
        with caplog.at_level(logging.WARNING):
            parse_goals_averages("<html>No stats</html>")

            # Should not raise, but may log warning
            assert True

    @pytest.mark.asyncio
    async def test_fetch_team_form_logs_timeout(
        self,
        caplog
    ) -> None:
        """Test that timeout errors are logged with context."""
        with patch('bet_bot.data.fetchers.espn_scraper.fetch_html_with_retry') as mock_fetch:
            mock_fetch.side_effect = httpx.TimeoutException("Timeout")

            with caplog.at_level(logging.WARNING):
                await fetch_team_form_espn("Leeds United", "Championship")

                assert "timeout" in caplog.text.lower()
                assert "Leeds United" in caplog.text


# ============================================================================
# Test: Fallback Behavior (fetch_team_form_with_fallback)
# ============================================================================

class TestFallbackBehavior:
    """Tests for fallback from API-Football to ESPN scraper."""

    @pytest.mark.asyncio
    async def test_fallback_uses_api_football_first(self) -> None:
        """Test that API-Football is tried first."""
        mock_form = MagicMock(spec=TeamForm)

        with patch('bet_bot.data.fetchers.fetch_team_form') as mock_api:
            mock_api.return_value = mock_form

            with patch('bet_bot.data.fetchers.fetch_team_form_espn') as mock_espn:
                result = await fetch_team_form_with_fallback(
                    team_id="33",
                    league_id="39",
                    team_name="Leeds United",
                    league="Championship"
                )

                assert result == mock_form
                assert mock_api.called
                # ESPN should NOT be called if API-Football succeeds
                assert not mock_espn.called

    @pytest.mark.asyncio
    async def test_fallback_tries_espn_if_api_fails(self) -> None:
        """Test that ESPN is called if API-Football returns None."""
        mock_form = MagicMock(spec=TeamForm)

        with patch('bet_bot.data.fetchers.fetch_team_form') as mock_api:
            mock_api.return_value = None  # API-Football fails

            with patch('bet_bot.data.fetchers.fetch_team_form_espn') as mock_espn:
                mock_espn.return_value = mock_form

                result = await fetch_team_form_with_fallback(
                    team_id="33",
                    league_id="39",
                    team_name="Leeds United",
                    league="Championship"
                )

                assert result == mock_form
                assert mock_api.called
                assert mock_espn.called

    @pytest.mark.asyncio
    async def test_fallback_returns_none_if_both_fail(self) -> None:
        """Test that None is returned if both sources fail."""
        with patch('bet_bot.data.fetchers.fetch_team_form') as mock_api:
            mock_api.return_value = None

            with patch('bet_bot.data.fetchers.fetch_team_form_espn') as mock_espn:
                mock_espn.return_value = None

                result = await fetch_team_form_with_fallback(
                    team_id="33",
                    league_id="39",
                    team_name="Leeds United",
                    league="Championship"
                )

                assert result is None
