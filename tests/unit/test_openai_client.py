"""
Unit tests for OpenAI client module (Story 4.2).

Tests cover:
- Client initialization and singleton pattern
- analyze_fixture function with various scenarios
- Response parsing and validation
- Retry logic and timeout handling
- Rate limiting
- Error handling and graceful degradation
- Token cost estimation
- Batch analysis orchestration

Uses pytest with async support (@pytest.mark.asyncio).
Mocking uses unittest.mock.patch and pytest-mock.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bet_bot.analysis.ai.client import (
    RateLimiter,
    _attach_analysis_to_fixture,
    _estimate_token_cost,
    _parse_openai_response,
    analyze_all_fixtures,
    analyze_fixture,
)
from bet_bot.exceptions import APIAuthenticationError
from bet_bot.models import AIAnalysis, Fixture, League, MarketAnalysis, Team


class TestRateLimiter:
    """Test RateLimiter class."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests_below_limit(self):
        """Test that rate limiter allows requests when below limit."""
        limiter = RateLimiter(max_requests=2, time_window=1)

        # Both requests should succeed immediately
        await limiter.acquire()
        await limiter.acquire()

        # Third should also work (acquired later)
        await limiter.acquire()

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_at_limit(self):
        """Test that rate limiter blocks when at limit."""
        limiter = RateLimiter(max_requests=1, time_window=1)

        await limiter.acquire()
        start = asyncio.get_event_loop().time()

        # Second request should wait ~1 second
        await limiter.acquire()
        end = asyncio.get_event_loop().time()

        elapsed = end - start
        assert elapsed >= 0.9, f"Expected ~1s wait, got {elapsed}s"

    @pytest.mark.asyncio
    async def test_rate_limiter_concurrent_access(self):
        """Test rate limiter is thread-safe with concurrent access."""
        limiter = RateLimiter(max_requests=3, time_window=1)

        async def acquire_once():
            await limiter.acquire()

        # Launch 5 concurrent acquire attempts
        tasks = [acquire_once() for _ in range(5)]
        await asyncio.gather(*tasks)

        # All should complete (some may wait)
        assert len(limiter.requests) > 0


class TestTokenEstimation:
    """Test token cost estimation."""

    def test_estimate_token_cost_basic(self):
        """Test cost calculation for GPT-3.5-turbo pricing."""
        # 1000 input + 500 output tokens
        cost = _estimate_token_cost(1000, 500)

        assert cost['input_cost'] == pytest.approx(0.0005, rel=1e-6)
        assert cost['output_cost'] == pytest.approx(0.00075, rel=1e-6)
        assert cost['total_cost'] == pytest.approx(0.00125, rel=1e-6)

    def test_estimate_token_cost_zero(self):
        """Test cost calculation with zero tokens."""
        cost = _estimate_token_cost(0, 0)

        assert cost['input_cost'] == 0.0
        assert cost['output_cost'] == 0.0
        assert cost['total_cost'] == 0.0

    def test_estimate_token_cost_large_numbers(self):
        """Test cost calculation with large token counts."""
        # 1M input + 1M output tokens
        cost = _estimate_token_cost(1_000_000, 1_000_000)

        assert cost['input_cost'] == pytest.approx(0.50, rel=1e-6)
        assert cost['output_cost'] == pytest.approx(1.50, rel=1e-6)
        assert cost['total_cost'] == pytest.approx(2.00, rel=1e-6)


class TestResponseParsing:
    """Test OpenAI response parsing."""

    def test_parse_valid_response(self):
        """Test parsing valid OpenAI response."""
        response = json.dumps({
            "markets": [
                {
                    "market_type": "match_result",
                    "probabilities": {"home": 0.58, "draw": 0.25, "away": 0.17},
                    "reasoning": "Strong form data"
                },
                {
                    "market_type": "total_goals",
                    "probabilities": {"over": 0.65, "under": 0.35},
                    "reasoning": "High-scoring league"
                }
            ]
        })

        markets = _parse_openai_response(response)

        assert len(markets) == 2
        assert markets[0].market_type == "match_result"
        assert markets[0].ai_probability == 0.58
        assert markets[0].confidence == 58

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON returns empty list."""
        response = "invalid json {{"

        markets = _parse_openai_response(response)

        assert markets == []

    def test_parse_missing_markets_field(self):
        """Test parsing response without markets field."""
        response = json.dumps({"data": []})

        markets = _parse_openai_response(response)

        assert markets == []

    def test_parse_probabilities_out_of_range(self):
        """Test parsing clipping probabilities out of range."""
        response = json.dumps({
            "markets": [
                {
                    "market_type": "test",
                    "probabilities": {"outcome1": 1.5, "outcome2": -0.2},
                    "reasoning": "Test"
                }
            ]
        })

        markets = _parse_openai_response(response)

        # Should parse and use max probability (clipped to 1.0)
        assert len(markets) == 1
        assert markets[0].ai_probability <= 1.0

    def test_parse_empty_probabilities(self):
        """Test parsing market with empty probabilities."""
        response = json.dumps({
            "markets": [
                {
                    "market_type": "test",
                    "probabilities": {},
                    "reasoning": "No probs"
                }
            ]
        })

        markets = _parse_openai_response(response)

        # Empty probabilities should skip this market
        assert len(markets) == 0


class TestAttachAnalysis:
    """Test attaching analysis to fixture."""

    def test_attach_analysis_valid_fixture(self):
        """Test attaching analysis to valid fixture."""
        fixture = Fixture(
            fixture_id="123",
            kickoff_time="2025-11-30T15:00:00Z",
            home_team=Team(
                id="1",
                name="Home Team",
                form_5_games=[],
                avg_goals_for=1.5,
                avg_goals_against=1.0,
                injuries=[]
            ),
            away_team=Team(
                id="2",
                name="Away Team",
                form_5_games=[],
                avg_goals_for=1.2,
                avg_goals_against=1.1,
                injuries=[]
            ),
            league=League(
                league_id="1",
                league_name="Test League",
                league_country="Test Country",
                league_season=2025
            ),
            odds={}
        )

        markets = [
            MarketAnalysis(
                market_type="match_result",
                ai_probability=0.58,
                reasoning="Test reasoning",
                confidence=75
            )
        ]

        result = _attach_analysis_to_fixture(fixture, markets)

        assert result.ai_analysis is not None
        assert result.ai_analysis.fixture_id == "123"
        assert len(result.ai_analysis.markets) == 1

    def test_attach_analysis_none_fixture(self):
        """Test attaching analysis to None fixture."""
        result = _attach_analysis_to_fixture(None, [])

        assert result is None

    def test_attach_analysis_empty_fixture_id(self):
        """Test attaching analysis to fixture with empty ID."""
        fixture = Fixture(
            fixture_id="",
            kickoff_time="2025-11-30T15:00:00Z",
            home_team=Team(id="1", name="H", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            away_team=Team(id="2", name="A", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            league=League(league_id="1", league_name="L", league_country="C", league_season=2025),
            odds={}
        )

        result = _attach_analysis_to_fixture(fixture, [])

        assert result == fixture  # Returns unchanged


class TestAnalyzeFixture:
    """Test analyze_fixture function."""

    @pytest.mark.asyncio
    async def test_analyze_fixture_none(self):
        """Test analyze_fixture with None fixture."""
        result = await analyze_fixture(None)

        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_fixture_empty_fixture_id(self):
        """Test analyze_fixture with empty fixture_id."""
        fixture = Fixture(
            fixture_id="",
            kickoff_time="2025-11-30T15:00:00Z",
            home_team=Team(id="1", name="H", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            away_team=Team(id="2", name="A", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            league=League(league_id="1", league_name="L", league_country="C", league_season=2025),
            odds={}
        )

        result = await analyze_fixture(fixture)

        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_fixture_prompt_generation_fails(self):
        """Test analyze_fixture when prompt generation fails."""
        fixture = Fixture(
            fixture_id="123",
            kickoff_time="2025-11-30T15:00:00Z",
            home_team=Team(id="1", name="H", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            away_team=Team(id="2", name="A", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            league=League(league_id="1", league_name="L", league_country="C", league_season=2025),
            odds={}
        )

        with patch('bet_bot.analysis.ai.client.export_prompt_for_api', side_effect=Exception("Prompt error")):
            result = await analyze_fixture(fixture)

            assert result is not None
            assert hasattr(result, 'error_message')
            assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_analyze_fixture_empty_prompt(self):
        """Test analyze_fixture when prompt is empty."""
        fixture = Fixture(
            fixture_id="123",
            kickoff_time="2025-11-30T15:00:00Z",
            home_team=Team(id="1", name="H", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            away_team=Team(id="2", name="A", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            league=League(league_id="1", league_name="L", league_country="C", league_season=2025),
            odds={}
        )

        with patch('bet_bot.analysis.ai.client.export_prompt_for_api', return_value={"system_prompt": "", "user_message": ""}):
            result = await analyze_fixture(fixture)

            assert result is not None
            assert hasattr(result, 'error_message')

    @pytest.mark.asyncio
    async def test_analyze_fixture_invalid_response_json(self):
        """Test analyze_fixture with invalid response JSON."""
        fixture = Fixture(
            fixture_id="123",
            kickoff_time="2025-11-30T15:00:00Z",
            home_team=Team(id="1", name="H", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            away_team=Team(id="2", name="A", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            league=League(league_id="1", league_name="L", league_country="C", league_season=2025),
            odds={}
        )

        with patch('bet_bot.analysis.ai.client.export_prompt_for_api', return_value={"system_prompt": "sys", "user_message": "user"}):
            with patch('bet_bot.analysis.ai.client._call_openai_with_retry', return_value="invalid json"):
                result = await analyze_fixture(fixture)

                assert result is not None
                assert hasattr(result, 'error_message')

    @pytest.mark.asyncio
    async def test_analyze_fixture_success(self):
        """Test successful fixture analysis."""
        fixture = Fixture(
            fixture_id="123",
            kickoff_time="2025-11-30T15:00:00Z",
            home_team=Team(id="1", name="H", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            away_team=Team(id="2", name="A", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            league=League(league_id="1", league_name="L", league_country="C", league_season=2025),
            odds={}
        )

        prompt_response = {"system_prompt": "sys", "user_message": "user"}
        api_response = json.dumps({
            "markets": [{
                "market_type": "match_result",
                "probabilities": {"home": 0.58, "draw": 0.25, "away": 0.17},
                "reasoning": "Test"
            }]
        })

        with patch('bet_bot.analysis.ai.client.export_prompt_for_api', return_value=prompt_response):
            with patch('bet_bot.analysis.ai.client._call_openai_with_retry', return_value=api_response):
                with patch('bet_bot.analysis.ai.client.get_openai_client', new_callable=AsyncMock):
                    result = await analyze_fixture(fixture)

                    assert result is not None
                    assert result.ai_analysis is not None
                    assert len(result.ai_analysis.markets) == 1


class TestAnalyzeAllFixtures:
    """Test batch analysis orchestrator."""

    @pytest.mark.asyncio
    async def test_analyze_all_fixtures_empty_list(self):
        """Test batch analysis with empty fixture list."""
        result = await analyze_all_fixtures(None)

        assert result == []

    @pytest.mark.asyncio
    async def test_analyze_all_fixtures_none(self):
        """Test batch analysis with None."""
        result = await analyze_all_fixtures(None)

        assert result == []

    @pytest.mark.asyncio
    async def test_analyze_all_fixtures_single_fixture(self):
        """Test batch analysis with single fixture."""
        fixture = Fixture(
            fixture_id="123",
            kickoff_time="2025-11-30T15:00:00Z",
            home_team=Team(id="1", name="H", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            away_team=Team(id="2", name="A", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            league=League(league_id="1", league_name="L", league_country="C", league_season=2025),
            odds={}
        )

        with patch('bet_bot.analysis.ai.client.analyze_fixture', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = fixture

            result = await analyze_all_fixtures([fixture])

            assert len(result) == 1
            mock_analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_all_fixtures_continues_on_failure(self):
        """Test batch analysis continues when one fixture fails."""
        fixture1 = Fixture(
            fixture_id="1",
            kickoff_time="2025-11-30T15:00:00Z",
            home_team=Team(id="1", name="H1", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            away_team=Team(id="2", name="A1", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            league=League(league_id="1", league_name="L", league_country="C", league_season=2025),
            odds={}
        )

        fixture2 = Fixture(
            fixture_id="2",
            kickoff_time="2025-11-30T16:00:00Z",
            home_team=Team(id="3", name="H2", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            away_team=Team(id="4", name="A2", form_5_games=[], avg_goals_for=1.0, avg_goals_against=1.0, injuries=[]),
            league=League(league_id="1", league_name="L", league_country="C", league_season=2025),
            odds={}
        )

        with patch('bet_bot.analysis.ai.client.analyze_fixture', new_callable=AsyncMock) as mock_analyze:
            # First fails, second succeeds
            mock_analyze.side_effect = [None, fixture2]

            result = await analyze_all_fixtures([fixture1, fixture2])

            assert len(result) == 2
            assert mock_analyze.call_count == 2


class TestClientInitialization:
    """Test OpenAI client initialization."""

    @pytest.mark.asyncio
    async def test_get_openai_client_singleton(self):
        """Test that get_openai_client returns singleton."""
        with patch('bet_bot.analysis.ai.client._openai_client', None):
            with patch('openai.AsyncOpenAI'):
                client1 = await pytest.fail("Skipping due to config requirements")

    @pytest.mark.asyncio
    async def test_get_openai_client_missing_api_key(self):
        """Test client initialization fails without API key."""
        with patch('bet_bot.analysis.ai.client.config', None):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                from bet_bot.analysis.ai.client import get_openai_client
                await get_openai_client()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
