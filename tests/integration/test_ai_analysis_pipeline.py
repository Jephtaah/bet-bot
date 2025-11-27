"""
Integration tests for AI analysis pipeline (Stories 4.1-4.3).

Tests the complete pipeline from prompt building through OpenAI analysis
to response parsing. Verifies that parsed markets match MarketAnalysis
models and probabilities are normalized correctly.

Test coverage:
- End-to-end: Fixture → Prompt → OpenAI Response → Parsed Markets
- Fixture attachment and error handling
- Realistic OpenAI responses
- Data flow between pipeline stages
"""

import json
import pytest
from datetime import datetime, timezone

from bet_bot.analysis.ai import (
    attach_parsed_analysis_to_fixture,
    parse_all_fixture_responses,
    parse_openai_response,
)
from bet_bot.models import AIAnalysis, Fixture, League, MarketAnalysis, Team


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_league() -> League:
    """Create a sample league."""
    return League(
        league_id="39",
        league_name="Championship",
        league_country="England",
        league_season=2025
    )


@pytest.fixture
def sample_fixture(sample_league) -> Fixture:
    """Create a sample fixture for testing."""
    return Fixture(
        fixture_id="548821",
        kickoff_time=datetime(2025, 11, 27, 15, 0, 0, tzinfo=timezone.utc),
        home_team=Team(
            id="1",
            name="Leeds United",
            form_5_games=["W", "W", "D", "L", "W"],
            avg_goals_for=1.8,
            avg_goals_against=1.2
        ),
        away_team=Team(
            id="2",
            name="Bristol City",
            form_5_games=["W", "D", "L", "L", "D"],
            avg_goals_for=1.4,
            avg_goals_against=1.5
        ),
        league=sample_league,
        odds={
            "match_result": {"home": 2.10, "draw": 3.50, "away": 3.20},
            "total_goals": {"over_2_5": 1.85, "under_2_5": 1.95}
        }
    )


@pytest.fixture
def realistic_openai_response() -> dict:
    """Create a realistic OpenAI response matching Story 4.1 spec."""
    return {
        "markets": [
            {
                "type": "match_result",
                "probabilities": {
                    "home": 0.58,
                    "draw": 0.22,
                    "away": 0.20
                },
                "reasoning": "Leeds playing at home with excellent recent form (60% win rate). "
                "Bristol City's defensive issues against pressing teams mitigated by home advantage. "
                "Team dynamics favor host control.",
                "confidence": 0.82
            },
            {
                "type": "total_goals",
                "probabilities": {
                    "over": 0.65,
                    "under": 0.35
                },
                "reasoning": "Both teams attacking-minded. Leeds average 6.2 corner per game at home. "
                "Bristol's defensive line prone to individual errors. Recent form suggests "
                "2.5+ goals in 70% of matches.",
                "confidence": 0.77
            },
            {
                "type": "corners",
                "probabilities": {
                    "over": 0.72,
                    "under": 0.28
                },
                "reasoning": "Leeds average 6.2 corners per game at home. "
                "Bristol's defensive style (high press, wider formation) leads to more set pieces. "
                "Historical H2H suggests 8+ corners.",
                "confidence": 0.79
            },
            {
                "type": "cards",
                "probabilities": {
                    "over": 0.58,
                    "under": 0.42
                },
                "reasoning": "Leeds vs Bristol has history of competitive, intense matches. "
                "Referee tendencies for Championship matches include lower card thresholds. "
                "Both teams have high card-per-match averages.",
                "confidence": 0.64
            }
        ]
    }


@pytest.fixture
def realistic_openai_response_json(realistic_openai_response) -> str:
    """Create realistic OpenAI response as JSON string."""
    return json.dumps(realistic_openai_response)


# ============================================================================
# Integration Tests
# ============================================================================

class TestAIAnalysisPipeline:
    """Tests for complete AI analysis pipeline."""

    @pytest.mark.asyncio
    async def test_parse_realistic_response(self, realistic_openai_response_json):
        """Test parsing realistic OpenAI response."""
        result = await parse_openai_response(
            realistic_openai_response_json,
            "fixture_548821"
        )

        # Verify result structure
        assert isinstance(result, list)
        assert len(result) == 4  # All 4 markets parsed

        # Verify all are MarketAnalysis objects
        assert all(isinstance(m, MarketAnalysis) for m in result)

        # Verify market types
        market_types = {m.market_type for m in result}
        assert market_types == {"match_result", "total_goals", "corners", "cards"}

    @pytest.mark.asyncio
    async def test_probability_normalization_in_pipeline(self, realistic_openai_response_json):
        """Test that probabilities are normalized through pipeline."""
        result = await parse_openai_response(
            realistic_openai_response_json,
            "fixture_548821"
        )

        # All parsed markets should have valid probabilities
        for market in result:
            assert 0.0 <= market.ai_probability <= 1.0

    @pytest.mark.asyncio
    async def test_confidence_conversion(self, realistic_openai_response):
        """Test confidence is converted from float to int percentage."""
        result = await parse_openai_response(
            realistic_openai_response,
            "fixture_548821"
        )

        for market in result:
            # Confidence should be int in [0, 100]
            assert isinstance(market.confidence, int)
            assert 0 <= market.confidence <= 100

    @pytest.mark.asyncio
    async def test_attach_to_fixture(self, sample_fixture, realistic_openai_response):
        """Test attaching parsed analysis to fixture."""
        # Parse response
        parsed_markets = await parse_openai_response(
            realistic_openai_response,
            sample_fixture.fixture_id
        )

        # Attach to fixture
        result = await attach_parsed_analysis_to_fixture(
            sample_fixture,
            parsed_markets
        )

        # Verify attachment
        assert result.ai_analysis is not None
        assert isinstance(result.ai_analysis, AIAnalysis)
        assert len(result.ai_analysis.markets) == 4
        assert result.ai_analysis.fixture_id == sample_fixture.fixture_id

    @pytest.mark.asyncio
    async def test_full_pipeline_end_to_end(self, sample_fixture, realistic_openai_response_json):
        """Test complete pipeline: parse response + attach to fixture."""
        # Add raw response to fixture (as Story 4.2 would)
        sample_fixture.ai_analysis = realistic_openai_response_json

        # Parse and attach
        parsed_markets = await parse_openai_response(
            sample_fixture.ai_analysis,
            sample_fixture.fixture_id
        )
        result = await attach_parsed_analysis_to_fixture(
            sample_fixture,
            parsed_markets
        )

        # Verify complete pipeline result
        assert result.ai_analysis is not None
        assert len(result.ai_analysis.markets) == 4

        # Verify each market has expected fields
        for market in result.ai_analysis.markets:
            assert market.market_type in {"match_result", "total_goals", "corners", "cards"}
            assert isinstance(market.ai_probability, float)
            assert 0.0 <= market.ai_probability <= 1.0
            assert isinstance(market.confidence, int)
            assert 0 <= market.confidence <= 100
            assert isinstance(market.reasoning, str)
            assert len(market.reasoning) > 0

    @pytest.mark.asyncio
    async def test_batch_parsing_multiple_fixtures(self, sample_league):
        """Test batch parsing of multiple fixtures."""
        # Create multiple fixtures with responses
        fixtures = []
        for i in range(3):
            fixture = Fixture(
                fixture_id=f"fixture_{i}",
                kickoff_time=datetime(2025, 11, 27, 15, 0, 0, tzinfo=timezone.utc),
                home_team=Team(id=f"h{i}", name=f"Home {i}"),
                away_team=Team(id=f"a{i}", name=f"Away {i}"),
                league=sample_league,
                ai_analysis={
                    "markets": [
                        {
                            "type": "match_result",
                            "probabilities": {"home": 0.55, "draw": 0.25, "away": 0.20},
                            "reasoning": f"Analysis for fixture {i}",
                            "confidence": 0.80 + (i * 0.05)
                        }
                    ]
                }
            )
            fixtures.append(fixture)

        # Batch parse
        result = await parse_all_fixture_responses(fixtures)

        # Verify all processed
        assert len(result) == 3
        for fixture in result:
            assert fixture.ai_analysis is not None
            assert len(fixture.ai_analysis.markets) == 1

    @pytest.mark.asyncio
    async def test_malformed_response_handling(self, sample_fixture):
        """Test graceful handling of malformed responses."""
        malformed_response = {
            "markets": [
                {
                    "type": "match_result",
                    "probabilities": {"home": 1.5, "draw": -0.2, "away": -0.3},  # Invalid
                    "reasoning": "Invalid probabilities",
                    "confidence": 0.8
                },
                {
                    "type": "total_goals",
                    "probabilities": {"over": 0.60, "under": 0.40},  # Valid
                    "reasoning": "Valid probabilities",
                    "confidence": 0.75
                }
            ]
        }

        # Should still parse and normalize
        result = await parse_openai_response(malformed_response, sample_fixture.fixture_id)

        # Should get at least the valid market
        assert len(result) >= 1

        # All results should have valid probabilities
        for market in result:
            assert 0.0 <= market.ai_probability <= 1.0

    @pytest.mark.asyncio
    async def test_empty_response_handling(self):
        """Test handling of empty response."""
        empty_response = {"markets": []}
        result = await parse_openai_response(empty_response, "fixture_123")
        assert result == []

    @pytest.mark.asyncio
    async def test_invalid_json_handling(self):
        """Test handling of invalid JSON."""
        invalid_json = "{ not valid json }"
        result = await parse_openai_response(invalid_json, "fixture_123")
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_markets_key(self):
        """Test handling of response missing 'markets' key."""
        response = {"analysis": "some data"}
        result = await parse_openai_response(response, "fixture_123")
        assert result is None

    @pytest.mark.asyncio
    async def test_market_analysis_model_compliance(self, realistic_openai_response):
        """Test that parsed markets comply with MarketAnalysis model requirements."""
        result = await parse_openai_response(
            realistic_openai_response,
            "fixture_123"
        )

        for market in result:
            # MarketAnalysis model requirements
            assert market.market_type and len(market.market_type) > 0
            assert isinstance(market.ai_probability, float)
            assert 0.0 <= market.ai_probability <= 1.0
            assert market.reasoning and len(market.reasoning) > 0
            assert isinstance(market.confidence, int)
            assert 0 <= market.confidence <= 100

            # Should be creatable as Pydantic model
            try:
                test_market = MarketAnalysis(
                    market_type=market.market_type,
                    ai_probability=market.ai_probability,
                    reasoning=market.reasoning,
                    confidence=market.confidence
                )
                assert test_market is not None
            except Exception as e:
                pytest.fail(f"Failed to validate MarketAnalysis: {str(e)}")

    @pytest.mark.asyncio
    async def test_aianalysis_model_compliance(self, sample_fixture, realistic_openai_response):
        """Test that attached AIAnalysis complies with model requirements."""
        parsed_markets = await parse_openai_response(
            realistic_openai_response,
            sample_fixture.fixture_id
        )

        result = await attach_parsed_analysis_to_fixture(
            sample_fixture,
            parsed_markets
        )

        # AIAnalysis model requirements
        assert result.ai_analysis.fixture_id == sample_fixture.fixture_id
        assert isinstance(result.ai_analysis.markets, list)
        assert len(result.ai_analysis.markets) == len(parsed_markets)
        assert isinstance(result.ai_analysis.analysis_timestamp, datetime)

    @pytest.mark.asyncio
    async def test_data_flow_preserves_information(self, realistic_openai_response):
        """Test that data flow through parsing preserves critical information."""
        # Original response
        original_match_result = realistic_openai_response["markets"][0]

        # Parse
        parsed = await parse_openai_response(
            realistic_openai_response,
            "fixture_123"
        )

        # Find match_result in parsed
        parsed_match_result = [m for m in parsed if m.market_type == "match_result"][0]

        # Verify information preservation
        assert parsed_match_result.market_type == original_match_result["type"]
        assert parsed_match_result.ai_probability > 0  # Should have probability
        assert len(parsed_match_result.reasoning) > 0  # Should preserve reasoning
        # Confidence was 0.82, should convert to 82
        assert parsed_match_result.confidence == 82

    @pytest.mark.asyncio
    async def test_realistic_fixture_attachment_flow(self, sample_fixture):
        """Test realistic flow: fixture receives raw response, gets parsed and attached."""
        # Simulate Story 4.2 behavior: raw response attached as ai_analysis
        raw_response = {
            "markets": [
                {
                    "type": "match_result",
                    "probabilities": {"home": 0.58, "draw": 0.22, "away": 0.20},
                    "reasoning": "Home team advantage with good form",
                    "confidence": 0.82
                },
                {
                    "type": "total_goals",
                    "probabilities": {"over": 0.65, "under": 0.35},
                    "reasoning": "Attacking teams, defensive weaknesses",
                    "confidence": 0.77
                }
            ]
        }

        # Simulate Story 4.3 flow
        sample_fixture.ai_analysis = raw_response

        # Parse
        parsed_markets = await parse_openai_response(
            sample_fixture.ai_analysis,
            sample_fixture.fixture_id
        )

        # Attach
        result = await attach_parsed_analysis_to_fixture(
            sample_fixture,
            parsed_markets
        )

        # Verify result ready for Story 4.4 (edge detection)
        assert result.ai_analysis is not None
        assert isinstance(result.ai_analysis, AIAnalysis)
        assert len(result.ai_analysis.markets) == 2
        assert all(hasattr(m, "ai_probability") for m in result.ai_analysis.markets)
        assert all(hasattr(m, "market_type") for m in result.ai_analysis.markets)
