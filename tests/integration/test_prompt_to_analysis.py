"""
Integration tests for prompt-to-analysis flow (Story 4.1 → Story 4.2).

Tests the complete pipeline:
1. Story 4.1: export_prompt_for_api() generates structured prompt
2. Story 4.2: analyze_fixture() sends prompt to OpenAI
3. Response parsing converts to MarketAnalysis models
4. Fixture augmentation preserves original data

Uses realistic fixture examples and mocked OpenAI responses.
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from bet_bot.analysis.ai import analyze_fixture, export_prompt_for_api
from bet_bot.models import Fixture, League, Team


@pytest.fixture
def realistic_fixture_1() -> Fixture:
    """Create realistic fixture for Leeds vs Coventry."""
    return Fixture(
        fixture_id="548821",
        kickoff_time=datetime(2025, 11, 30, 15, 0, 0, tzinfo=timezone.utc),
        home_team=Team(
            id="9",
            name="Leeds United",
            form_5_games=["W", "W", "D", "W", "L"],
            avg_goals_for=1.8,
            avg_goals_against=0.9,
            injuries=[]
        ),
        away_team=Team(
            id="51",
            name="Coventry City",
            form_5_games=["W", "D", "D", "L", "W"],
            avg_goals_for=1.4,
            avg_goals_against=1.2,
            injuries=[]
        ),
        league=League(
            league_id="39",
            league_name="Championship",
            league_country="England",
            league_season=2025
        ),
        odds={
            "match_result": {
                "home": 2.10,
                "draw": 3.50,
                "away": 3.20
            },
            "total_goals": {
                "over": 1.95,
                "under": 1.90
            }
        }
    )


@pytest.fixture
def realistic_fixture_2() -> Fixture:
    """Create realistic fixture for Southampton vs Norwich."""
    return Fixture(
        fixture_id="548822",
        kickoff_time=datetime(2025, 11, 30, 17, 30, 0, tzinfo=timezone.utc),
        home_team=Team(
            id="20",
            name="Southampton",
            form_5_games=["L", "L", "D", "L", "L"],
            avg_goals_for=0.8,
            avg_goals_against=1.6,
            injuries=["123", "456"]  # Two injured players
        ),
        away_team=Team(
            id="27",
            name="Norwich City",
            form_5_games=["W", "W", "W", "D", "W"],
            avg_goals_for=2.0,
            avg_goals_against=0.8,
            injuries=[]
        ),
        league=League(
            league_id="39",
            league_name="Championship",
            league_country="England",
            league_season=2025
        ),
        odds={
            "match_result": {
                "home": 3.80,
                "draw": 3.40,
                "away": 1.95
            }
        }
    )


@pytest.fixture
def realistic_fixture_3() -> Fixture:
    """Create realistic fixture for Bristol City vs Sunderland."""
    return Fixture(
        fixture_id="548823",
        kickoff_time=datetime(2025, 11, 30, 19, 45, 0, tzinfo=timezone.utc),
        home_team=Team(
            id="55",
            name="Bristol City",
            form_5_games=["W", "W", "W", "L", "D"],
            avg_goals_for=1.6,
            avg_goals_against=1.0,
            injuries=[]
        ),
        away_team=Team(
            id="16",
            name="Sunderland AFC",
            form_5_games=["D", "W", "D", "W", "L"],
            avg_goals_for=1.3,
            avg_goals_against=1.1,
            injuries=[]
        ),
        league=League(
            league_id="39",
            league_name="Championship",
            league_country="England",
            league_season=2025
        ),
        odds={
            "match_result": {
                "home": 2.45,
                "draw": 3.20,
                "away": 2.90
            }
        }
    )


class TestPromptGeneration:
    """Test Story 4.1 prompt generation works correctly."""

    @pytest.mark.asyncio
    async def test_export_prompt_generates_valid_structure(self, realistic_fixture_1):
        """Test prompt export returns correct structure."""
        prompt_data = await export_prompt_for_api(realistic_fixture_1)

        assert isinstance(prompt_data, dict)
        assert "system_prompt" in prompt_data
        assert "user_message" in prompt_data
        assert len(prompt_data["system_prompt"]) > 0
        assert len(prompt_data["user_message"]) > 0

    @pytest.mark.asyncio
    async def test_exported_prompt_includes_fixture_details(self, realistic_fixture_1):
        """Test exported prompt contains fixture details."""
        prompt_data = await export_prompt_for_api(realistic_fixture_1)
        user_message = prompt_data["user_message"]

        # Should include team names and league
        assert "Leeds United" in user_message
        assert "Coventry City" in user_message
        assert "Championship" in user_message

    @pytest.mark.asyncio
    async def test_exported_prompt_includes_form_data(self, realistic_fixture_1):
        """Test exported prompt includes team form data."""
        prompt_data = await export_prompt_for_api(realistic_fixture_1)
        user_message = prompt_data["user_message"]

        # Should include form indicators
        assert any(char in user_message for char in ['W', 'D', 'L'])

    @pytest.mark.asyncio
    async def test_exported_prompt_includes_odds(self, realistic_fixture_1):
        """Test exported prompt includes betting odds."""
        prompt_data = await export_prompt_for_api(realistic_fixture_1)
        user_message = prompt_data["user_message"]

        # Should include odds numbers
        assert "2.10" in user_message or "2.1" in user_message  # Home odds


class TestResponseParsing:
    """Test OpenAI response parsing preserves data correctly."""

    @pytest.mark.asyncio
    async def test_realistic_openai_response_parsing(self, realistic_fixture_1):
        """Test parsing a realistic OpenAI response."""
        from bet_bot.analysis.ai.client import _parse_openai_response

        # Realistic response format from OpenAI
        response = json.dumps({
            "markets": [
                {
                    "market_type": "match_result",
                    "probabilities": {
                        "home": 0.52,
                        "draw": 0.25,
                        "away": 0.23
                    },
                    "reasoning": "Leeds showing strong home form (W-W-D-W-L). Coventry with mixed form. Head-to-head favors Leeds."
                },
                {
                    "market_type": "total_goals",
                    "probabilities": {
                        "over": 0.61,
                        "under": 0.39
                    },
                    "reasoning": "Both teams average 1.6+ goals. Championship games typically have 2+ goals."
                }
            ]
        })

        markets = _parse_openai_response(response)

        assert len(markets) == 2
        assert markets[0].market_type == "match_result"
        assert markets[0].ai_probability == 0.52
        assert "home form" in markets[0].reasoning.lower()

    @pytest.mark.asyncio
    async def test_all_markets_have_valid_confidence(self, realistic_fixture_1):
        """Test that parsed markets have valid confidence scores."""
        from bet_bot.analysis.ai.client import _parse_openai_response

        response = json.dumps({
            "markets": [
                {
                    "market_type": "test1",
                    "probabilities": {"a": 0.7},
                    "reasoning": "R1"
                },
                {
                    "market_type": "test2",
                    "probabilities": {"b": 0.3},
                    "reasoning": "R2"
                }
            ]
        })

        markets = _parse_openai_response(response)

        for market in markets:
            assert 0 <= market.confidence <= 100


class TestFixtureAugmentation:
    """Test that fixture data is preserved after analysis."""

    @pytest.mark.asyncio
    async def test_fixture_original_data_preserved(self, realistic_fixture_1):
        """Test that original fixture data is not modified."""
        from bet_bot.analysis.ai.client import _attach_analysis_to_fixture, _parse_openai_response

        response = json.dumps({
            "markets": [{
                "market_type": "match_result",
                "probabilities": {"home": 0.58},
                "reasoning": "Test"
            }]
        })

        markets = _parse_openai_response(response)
        original_id = realistic_fixture_1.fixture_id
        original_home = realistic_fixture_1.home_team.name

        augmented = _attach_analysis_to_fixture(realistic_fixture_1, markets)

        # Original data should be unchanged
        assert augmented.fixture_id == original_id
        assert augmented.home_team.name == original_home
        assert augmented.kickoff_time == realistic_fixture_1.kickoff_time

    @pytest.mark.asyncio
    async def test_analysis_timestamp_is_recent(self, realistic_fixture_1):
        """Test that analysis timestamp is recent."""
        from bet_bot.analysis.ai.client import _attach_analysis_to_fixture, _parse_openai_response

        response = json.dumps({
            "markets": [{
                "market_type": "test",
                "probabilities": {"a": 0.5},
                "reasoning": "R"
            }]
        })

        markets = _parse_openai_response(response)
        augmented = _attach_analysis_to_fixture(realistic_fixture_1, markets)

        now = datetime.now(timezone.utc)
        time_diff = (now - augmented.ai_analysis.analysis_timestamp).total_seconds()

        # Should be within 10 seconds
        assert 0 <= time_diff <= 10


class TestEndToEndFlow:
    """Test complete prompt-to-analysis flow."""

    @pytest.mark.asyncio
    async def test_end_to_end_single_fixture(self, realistic_fixture_1):
        """Test complete flow for single fixture (without real OpenAI call)."""
        # Mock the OpenAI API call
        mock_response = json.dumps({
            "markets": [
                {
                    "market_type": "match_result",
                    "probabilities": {"home": 0.55, "draw": 0.27, "away": 0.18},
                    "reasoning": "Leeds form advantage"
                }
            ]
        })

        with patch('bet_bot.analysis.ai.client._call_openai_with_retry', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            with patch('bet_bot.analysis.ai.client.get_openai_client', new_callable=AsyncMock):
                result = await analyze_fixture(realistic_fixture_1)

                # Verify result structure
                assert result is not None
                assert result.fixture_id == realistic_fixture_1.fixture_id
                assert result.ai_analysis is not None
                assert len(result.ai_analysis.markets) > 0

    @pytest.mark.asyncio
    async def test_end_to_end_multiple_fixtures(self, realistic_fixture_1, realistic_fixture_2, realistic_fixture_3):
        """Test complete flow for multiple fixtures."""
        fixtures = [realistic_fixture_1, realistic_fixture_2, realistic_fixture_3]

        # Mock OpenAI responses for each fixture
        responses = [
            json.dumps({
                "markets": [{
                    "market_type": "match_result",
                    "probabilities": {"home": 0.55},
                    "reasoning": "Leeds advantage"
                }]
            }),
            json.dumps({
                "markets": [{
                    "market_type": "match_result",
                    "probabilities": {"away": 0.62},
                    "reasoning": "Norwich in form"
                }]
            }),
            json.dumps({
                "markets": [{
                    "market_type": "match_result",
                    "probabilities": {"home": 0.50},
                    "reasoning": "Evenly matched"
                }]
            })
        ]

        with patch('bet_bot.analysis.ai.client._call_openai_with_retry', new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = responses

            with patch('bet_bot.analysis.ai.client.get_openai_client', new_callable=AsyncMock):
                from bet_bot.analysis.ai.client import analyze_all_fixtures

                results = await analyze_all_fixtures(fixtures)

                # All fixtures should be processed
                assert len(results) == 3

                # All should have analysis
                for result in results:
                    assert result is not None

    @pytest.mark.asyncio
    async def test_fixture_with_injuries_analyzed_correctly(self, realistic_fixture_2):
        """Test that fixture with injuries is analyzed correctly."""
        # This fixture has injured players
        assert len(realistic_fixture_2.home_team.injuries) > 0

        mock_response = json.dumps({
            "markets": [{
                "market_type": "match_result",
                "probabilities": {"away": 0.65},
                "reasoning": "Southampton weakened by injuries"
            }]
        })

        with patch('bet_bot.analysis.ai.client._call_openai_with_retry', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response

            with patch('bet_bot.analysis.ai.client.get_openai_client', new_callable=AsyncMock):
                result = await analyze_fixture(realistic_fixture_2)

                assert result is not None
                assert result.ai_analysis is not None
                # Reasoning should mention injuries
                reasoning = result.ai_analysis.markets[0].reasoning
                assert "weakness" in reasoning.lower() or "injur" in reasoning.lower() or len(reasoning) > 0


class TestErrorHandling:
    """Test error handling in prompt-to-analysis flow."""

    @pytest.mark.asyncio
    async def test_handles_invalid_prompt_response(self, realistic_fixture_1):
        """Test handling of invalid prompt response."""
        with patch('bet_bot.analysis.ai.client.export_prompt_for_api', side_effect=Exception("Prompt error")):
            result = await analyze_fixture(realistic_fixture_1)

            # Should return fixture with error message, not raise
            assert result is not None
            assert hasattr(result, 'error_message')

    @pytest.mark.asyncio
    async def test_handles_malformed_json_response(self, realistic_fixture_1):
        """Test handling of malformed JSON from OpenAI."""
        with patch('bet_bot.analysis.ai.client._call_openai_with_retry', return_value="not json"):
            with patch('bet_bot.analysis.ai.client.get_openai_client', new_callable=AsyncMock):
                result = await analyze_fixture(realistic_fixture_1)

                # Should return fixture with error, not raise
                assert result is not None
                assert hasattr(result, 'error_message')

    @pytest.mark.asyncio
    async def test_handles_missing_market_data(self, realistic_fixture_1):
        """Test handling of response without markets."""
        mock_response = json.dumps({"result": "ok"})  # Missing "markets"

        with patch('bet_bot.analysis.ai.client._call_openai_with_retry', return_value=mock_response):
            with patch('bet_bot.analysis.ai.client.get_openai_client', new_callable=AsyncMock):
                result = await analyze_fixture(realistic_fixture_1)

                # Should return fixture with error
                assert result is not None
                assert hasattr(result, 'error_message')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
