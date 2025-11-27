"""
Unit tests for response_parser.py module.

Tests cover all parser functions including:
- JSON parsing and error handling
- Probability validation
- Probability normalization
- Market extraction and parsing
- Structure validation
- Batch processing
- Edge cases and error conditions
"""

import json
import pytest
from datetime import datetime, timezone

from bet_bot.analysis.ai.response_parser import (
    _extract_market_probabilities,
    _normalize_probabilities,
    _parse_market,
    _validate_market_probabilities,
    _validate_openai_response_structure,
    attach_parsed_analysis_to_fixture,
    get_probability_summary,
    parse_all_fixture_responses,
    parse_openai_response,
)
from bet_bot.models import AIAnalysis, Fixture, League, MarketAnalysis, Team


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_league() -> League:
    """Create a sample league for testing."""
    return League(
        league_id="39",
        league_name="Championship",
        league_country="England",
        league_season=2025
    )


@pytest.fixture
def sample_home_team() -> Team:
    """Create a sample home team."""
    return Team(
        id="1",
        name="Leeds United",
        form_5_games=["W", "W", "D", "L", "W"],
        avg_goals_for=1.8,
        avg_goals_against=1.2,
        injuries=[]
    )


@pytest.fixture
def sample_away_team() -> Team:
    """Create a sample away team."""
    return Team(
        id="2",
        name="Bristol City",
        form_5_games=["W", "D", "L", "L", "D"],
        avg_goals_for=1.4,
        avg_goals_against=1.5,
        injuries=[]
    )


@pytest.fixture
def sample_fixture(sample_league, sample_home_team, sample_away_team) -> Fixture:
    """Create a sample fixture for testing."""
    return Fixture(
        fixture_id="548821",
        kickoff_time=datetime(2025, 11, 27, 15, 0, 0, tzinfo=timezone.utc),
        home_team=sample_home_team,
        away_team=sample_away_team,
        league=sample_league,
        odds={
            "match_result": {"home": 2.10, "draw": 3.50, "away": 3.20}
        }
    )


@pytest.fixture
def valid_openai_response() -> dict:
    """Create a valid OpenAI response."""
    return {
        "markets": [
            {
                "type": "match_result",
                "probabilities": {"home": 0.55, "draw": 0.25, "away": 0.20},
                "reasoning": "Home team in good form, favorable matchups",
                "confidence": 0.85
            },
            {
                "type": "total_goals",
                "probabilities": {"over": 0.60, "under": 0.40},
                "reasoning": "Both teams attacking, but defenses solid",
                "confidence": 0.72
            }
        ]
    }


@pytest.fixture
def valid_openai_response_json(valid_openai_response) -> str:
    """Create a valid OpenAI response as JSON string."""
    return json.dumps(valid_openai_response)


# ============================================================================
# Test _validate_openai_response_structure
# ============================================================================

class TestValidateOpenAIResponseStructure:
    """Tests for _validate_openai_response_structure function."""

    def test_valid_structure(self, valid_openai_response):
        """Test validation passes for valid response structure."""
        assert _validate_openai_response_structure(valid_openai_response) is True

    def test_missing_markets_key(self):
        """Test validation fails when 'markets' key is missing."""
        response = {"data": []}
        assert _validate_openai_response_structure(response) is False

    def test_markets_not_list(self):
        """Test validation fails when 'markets' is not a list."""
        response = {"markets": "not_a_list"}
        assert _validate_openai_response_structure(response) is False

    def test_market_not_dict(self):
        """Test validation fails when market is not a dict."""
        response = {"markets": ["not_a_dict"]}
        assert _validate_openai_response_structure(response) is False

    def test_market_missing_type(self):
        """Test validation fails when market missing 'type' field."""
        response = {
            "markets": [
                {
                    "probabilities": {"home": 0.5},
                    "reasoning": "test",
                    "confidence": 0.8
                }
            ]
        }
        assert _validate_openai_response_structure(response) is False

    def test_market_missing_probabilities(self):
        """Test validation fails when market missing 'probabilities'."""
        response = {
            "markets": [
                {
                    "type": "match_result",
                    "reasoning": "test",
                    "confidence": 0.8
                }
            ]
        }
        assert _validate_openai_response_structure(response) is False

    def test_market_missing_reasoning(self):
        """Test validation fails when market missing 'reasoning'."""
        response = {
            "markets": [
                {
                    "type": "match_result",
                    "probabilities": {"home": 0.5},
                    "confidence": 0.8
                }
            ]
        }
        assert _validate_openai_response_structure(response) is False

    def test_market_missing_confidence(self):
        """Test validation fails when market missing 'confidence'."""
        response = {
            "markets": [
                {
                    "type": "match_result",
                    "probabilities": {"home": 0.5},
                    "reasoning": "test"
                }
            ]
        }
        assert _validate_openai_response_structure(response) is False

    def test_probabilities_not_dict(self):
        """Test validation fails when probabilities is not dict."""
        response = {
            "markets": [
                {
                    "type": "match_result",
                    "probabilities": ["not", "dict"],
                    "reasoning": "test",
                    "confidence": 0.8
                }
            ]
        }
        assert _validate_openai_response_structure(response) is False


# ============================================================================
# Test _validate_market_probabilities
# ============================================================================

class TestValidateMarketProbabilities:
    """Tests for _validate_market_probabilities function."""

    def test_valid_probabilities(self):
        """Test validation passes for valid probabilities."""
        probs = {"home": 0.55, "draw": 0.25, "away": 0.20}
        assert _validate_market_probabilities("match_result", probs) is True

    def test_probabilities_with_tolerance(self):
        """Test validation passes for sum within tolerance."""
        probs = {"home": 0.56, "draw": 0.25, "away": 0.20}  # sum = 1.01
        assert _validate_market_probabilities("match_result", probs) is True

    def test_probabilities_sum_too_low(self):
        """Test validation fails when sum is too low."""
        probs = {"home": 0.40, "draw": 0.25, "away": 0.20}  # sum = 0.85
        assert _validate_market_probabilities("match_result", probs) is False

    def test_probabilities_sum_too_high(self):
        """Test validation fails when sum is too high."""
        probs = {"home": 0.60, "draw": 0.50, "away": 0.20}  # sum = 1.30
        assert _validate_market_probabilities("match_result", probs) is False

    def test_empty_probabilities(self):
        """Test validation fails for empty probabilities dict."""
        assert _validate_market_probabilities("match_result", {}) is False

    def test_non_numeric_probability(self):
        """Test validation fails when probability is not numeric."""
        probs = {"home": "0.5", "draw": 0.25, "away": 0.25}
        assert _validate_market_probabilities("match_result", probs) is False

    def test_probability_below_range(self):
        """Test validation fails when probability below 0.0."""
        probs = {"home": -0.1, "draw": 0.5, "away": 0.6}
        assert _validate_market_probabilities("match_result", probs) is False

    def test_probability_above_range(self):
        """Test validation fails when probability above 1.0."""
        probs = {"home": 0.6, "draw": 0.3, "away": 1.2}
        assert _validate_market_probabilities("match_result", probs) is False

    def test_binary_market_valid(self):
        """Test validation for binary market (2 outcomes)."""
        probs = {"over": 0.60, "under": 0.40}
        assert _validate_market_probabilities("total_goals", probs) is True

    def test_binary_market_sum_deviation(self):
        """Test binary market with sum slightly off."""
        probs = {"over": 0.62, "under": 0.39}  # sum = 1.01
        assert _validate_market_probabilities("total_goals", probs) is True


# ============================================================================
# Test _normalize_probabilities
# ============================================================================

class TestNormalizeProbabilities:
    """Tests for _normalize_probabilities function."""

    def test_already_normalized(self):
        """Test normalization when already at 1.0."""
        probs = {"home": 0.55, "draw": 0.25, "away": 0.20}
        result = _normalize_probabilities("match_result", probs)
        assert abs(sum(result.values()) - 1.0) < 0.001

    def test_normalize_sum_less_than_1(self):
        """Test normalization when sum < 1.0."""
        probs = {"home": 0.5, "draw": 0.25, "away": 0.15}  # sum = 0.9
        result = _normalize_probabilities("match_result", probs)
        assert abs(sum(result.values()) - 1.0) < 0.001
        assert result["home"] > 0.5  # Should increase

    def test_normalize_sum_greater_than_1(self):
        """Test normalization when sum > 1.0."""
        probs = {"home": 0.6, "draw": 0.25, "away": 0.25}  # sum = 1.1
        result = _normalize_probabilities("match_result", probs)
        assert abs(sum(result.values()) - 1.0) < 0.001
        assert result["home"] < 0.6  # Should decrease

    def test_normalize_zero_sum(self):
        """Test normalization with all zeros (division by zero)."""
        probs = {"home": 0.0, "draw": 0.0, "away": 0.0}
        result = _normalize_probabilities("match_result", probs)
        assert result == probs  # Should return original

    def test_clips_out_of_range(self):
        """Test normalization clips values to [0.0, 1.0]."""
        # If one probability is already 1.0, normalization should clip
        probs = {"home": 1.0, "draw": 0.5, "away": 0.5}  # sum = 2.0
        result = _normalize_probabilities("match_result", probs)
        # All values should be in [0.0, 1.0]
        for val in result.values():
            assert 0.0 <= val <= 1.0

    def test_preserve_relative_ratios(self):
        """Test normalization preserves probability ratios."""
        probs = {"home": 0.4, "draw": 0.3, "away": 0.2}  # sum = 0.9
        result = _normalize_probabilities("match_result", probs)
        # Ratios should be preserved
        assert abs((result["home"] / result["draw"]) - (0.4 / 0.3)) < 0.01


# ============================================================================
# Test _extract_market_probabilities
# ============================================================================

class TestExtractMarketProbabilities:
    """Tests for _extract_market_probabilities function."""

    def test_extract_match_result(self):
        """Test extraction of match_result probabilities."""
        probs = {"home": 0.55, "draw": 0.25, "away": 0.20}
        result = _extract_market_probabilities("match_result", probs)
        assert result["home"] == 0.55
        assert result["draw"] == 0.25
        assert result["away"] == 0.20

    def test_extract_total_goals(self):
        """Test extraction of total_goals probabilities."""
        probs = {"over": 0.60, "under": 0.40}
        result = _extract_market_probabilities("total_goals", probs)
        assert result["over"] == 0.60
        assert result["under"] == 0.40

    def test_missing_outcome_keys(self):
        """Test that missing outcome keys get default values."""
        probs = {"home": 0.5}
        result = _extract_market_probabilities("match_result", probs)
        assert "draw" in result  # Should be added with default
        assert "away" in result  # Should be added with default

    def test_default_value_binary_market(self):
        """Test default value for binary market (0.5)."""
        probs = {"over": 0.6}
        result = _extract_market_probabilities("total_goals", probs)
        assert result["under"] == 0.5  # Default for binary

    def test_default_value_multi_outcome_market(self):
        """Test default value for multi-outcome market."""
        probs = {"home": 0.5}
        result = _extract_market_probabilities("match_result", probs)
        # Should use 1/3 for missing outcomes
        assert 0.3 < result["draw"] < 0.4
        assert 0.3 < result["away"] < 0.4


# ============================================================================
# Test _parse_market
# ============================================================================

class TestParseMarket:
    """Tests for _parse_market function."""

    def test_parse_valid_market(self):
        """Test parsing a valid market object."""
        market_obj = {
            "type": "match_result",
            "probabilities": {"home": 0.55, "draw": 0.25, "away": 0.20},
            "reasoning": "Home team in good form",
            "confidence": 0.85
        }
        result = _parse_market(market_obj, "fixture_123")
        assert isinstance(result, MarketAnalysis)
        assert result.market_type == "match_result"
        assert result.ai_probability == 0.55
        assert result.confidence == 85

    def test_parse_market_confidence_conversion(self):
        """Test confidence is converted from [0.0, 1.0] to [0, 100]."""
        market_obj = {
            "type": "match_result",
            "probabilities": {"home": 0.6, "draw": 0.25, "away": 0.15},
            "reasoning": "test",
            "confidence": 0.72
        }
        result = _parse_market(market_obj, "fixture_123")
        assert result.confidence == 72

    def test_parse_market_missing_type(self):
        """Test parsing handles missing type gracefully with default."""
        market_obj = {
            "probabilities": {"home": 0.5, "draw": 0.3, "away": 0.2},
            "reasoning": "test",
            "confidence": 0.8
        }
        result = _parse_market(market_obj, "fixture_123")
        # Should use "unknown" as default type
        assert result is not None
        assert result.market_type == "unknown"

    def test_parse_market_missing_probabilities(self):
        """Test parsing fails when probabilities missing."""
        market_obj = {
            "type": "match_result",
            "reasoning": "test",
            "confidence": 0.8
        }
        result = _parse_market(market_obj, "fixture_123")
        assert result is None

    def test_parse_market_reasoning_truncation(self):
        """Test reasoning is truncated to 500 chars."""
        long_reasoning = "x" * 1000
        market_obj = {
            "type": "match_result",
            "probabilities": {"home": 0.55, "draw": 0.25, "away": 0.20},
            "reasoning": long_reasoning,
            "confidence": 0.8
        }
        result = _parse_market(market_obj, "fixture_123")
        assert len(result.reasoning) == 500

    def test_parse_market_invalid_confidence_type(self):
        """Test confidence defaults to 50 if not numeric."""
        market_obj = {
            "type": "match_result",
            "probabilities": {"home": 0.55, "draw": 0.25, "away": 0.20},
            "reasoning": "test",
            "confidence": "high"
        }
        result = _parse_market(market_obj, "fixture_123")
        assert result is not None  # Should continue with default

    def test_parse_market_calculates_ai_probability(self):
        """Test ai_probability is set to max probability."""
        market_obj = {
            "type": "match_result",
            "probabilities": {"home": 0.60, "draw": 0.25, "away": 0.15},
            "reasoning": "test",
            "confidence": 0.8
        }
        result = _parse_market(market_obj, "fixture_123")
        assert result.ai_probability == 0.60


# ============================================================================
# Test parse_openai_response (async)
# ============================================================================

class TestParseOpenAIResponse:
    """Tests for parse_openai_response async function."""

    @pytest.mark.asyncio
    async def test_parse_valid_response_dict(self, valid_openai_response):
        """Test parsing valid response as dict."""
        result = await parse_openai_response(valid_openai_response, "fixture_123")
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(m, MarketAnalysis) for m in result)

    @pytest.mark.asyncio
    async def test_parse_valid_response_json(self, valid_openai_response_json):
        """Test parsing valid response as JSON string."""
        result = await parse_openai_response(valid_openai_response_json, "fixture_123")
        assert isinstance(result, list)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self):
        """Test parsing invalid JSON returns None."""
        invalid_json = "{ invalid json }"
        result = await parse_openai_response(invalid_json, "fixture_123")
        assert result is None

    @pytest.mark.asyncio
    async def test_parse_missing_markets_key(self):
        """Test parsing response without 'markets' key returns None."""
        response = {"data": []}
        result = await parse_openai_response(response, "fixture_123")
        assert result is None

    @pytest.mark.asyncio
    async def test_parse_empty_markets_array(self):
        """Test parsing response with empty markets array returns empty list."""
        response = {"markets": []}
        result = await parse_openai_response(response, "fixture_123")
        assert result == []

    @pytest.mark.asyncio
    async def test_parse_partial_failure(self):
        """Test partial response parsing (some markets valid, some invalid)."""
        response = {
            "markets": [
                {
                    "type": "match_result",
                    "probabilities": {"home": 0.55, "draw": 0.25, "away": 0.20},
                    "reasoning": "valid",
                    "confidence": 0.85
                },
                {
                    "type": "invalid_market",
                    "probabilities": {},  # Invalid
                    "reasoning": "invalid",
                    "confidence": 0.8
                },
                {
                    "type": "total_goals",
                    "probabilities": {"over": 0.60, "under": 0.40},
                    "reasoning": "valid",
                    "confidence": 0.72
                }
            ]
        }
        result = await parse_openai_response(response, "fixture_123")
        # Should have 2 valid markets (1st and 3rd)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_parse_markets_not_list(self):
        """Test parsing when 'markets' is not a list."""
        response = {"markets": "not_a_list"}
        result = await parse_openai_response(response, "fixture_123")
        assert result is None

    @pytest.mark.asyncio
    async def test_parse_invalid_probability_range(self):
        """Test parsing market with out-of-range probabilities."""
        response = {
            "markets": [
                {
                    "type": "match_result",
                    "probabilities": {"home": 1.5, "draw": -0.2, "away": -0.3},
                    "reasoning": "invalid",
                    "confidence": 0.8
                }
            ]
        }
        result = await parse_openai_response(response, "fixture_123")
        # Should still parse but normalize
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_parse_string_probabilities(self):
        """Test parsing when probabilities are strings (JSON serialization)."""
        response = {
            "markets": [
                {
                    "type": "match_result",
                    "probabilities": {"home": "0.5", "draw": "0.3", "away": "0.2"},
                    "reasoning": "test",
                    "confidence": 0.8
                }
            ]
        }
        result = await parse_openai_response(response, "fixture_123")
        # Should fail or normalize due to type error
        assert result is not None


# ============================================================================
# Test attach_parsed_analysis_to_fixture (async)
# ============================================================================

class TestAttachParsedAnalysisToFixture:
    """Tests for attach_parsed_analysis_to_fixture async function."""

    @pytest.mark.asyncio
    async def test_attach_valid_analysis(self, sample_fixture):
        """Test attaching valid parsed analysis."""
        markets = [
            MarketAnalysis(
                market_type="match_result",
                ai_probability=0.55,
                reasoning="test",
                confidence=75
            )
        ]
        result = await attach_parsed_analysis_to_fixture(sample_fixture, markets)
        assert result.ai_analysis is not None
        assert isinstance(result.ai_analysis, AIAnalysis)
        assert len(result.ai_analysis.markets) == 1

    @pytest.mark.asyncio
    async def test_attach_empty_markets(self, sample_fixture):
        """Test attaching empty markets list."""
        result = await attach_parsed_analysis_to_fixture(sample_fixture, [])
        assert result.ai_analysis is not None
        assert len(result.ai_analysis.markets) == 0

    @pytest.mark.asyncio
    async def test_attach_sets_timestamp(self, sample_fixture):
        """Test that attachment sets analysis_timestamp."""
        markets = [
            MarketAnalysis(
                market_type="match_result",
                ai_probability=0.55,
                reasoning="test",
                confidence=75
            )
        ]
        result = await attach_parsed_analysis_to_fixture(sample_fixture, markets)
        assert result.ai_analysis.analysis_timestamp is not None
        assert isinstance(result.ai_analysis.analysis_timestamp, datetime)

    @pytest.mark.asyncio
    async def test_attach_to_invalid_fixture(self):
        """Test attachment with invalid fixture."""
        markets = [
            MarketAnalysis(
                market_type="match_result",
                ai_probability=0.55,
                reasoning="test",
                confidence=75
            )
        ]
        result = await attach_parsed_analysis_to_fixture(None, markets)
        assert result is None


# ============================================================================
# Test parse_all_fixture_responses (async)
# ============================================================================

class TestParseAllFixtureResponses:
    """Tests for parse_all_fixture_responses async function."""

    @pytest.mark.asyncio
    async def test_parse_multiple_fixtures(self, sample_fixture, valid_openai_response):
        """Test parsing responses for multiple fixtures."""
        # Add ai_analysis to fixture
        sample_fixture.ai_analysis = valid_openai_response

        fixtures = [sample_fixture]
        result = await parse_all_fixture_responses(fixtures)
        assert len(result) == 1
        assert result[0].ai_analysis is not None

    @pytest.mark.asyncio
    async def test_parse_empty_list(self):
        """Test parsing empty fixture list."""
        result = await parse_all_fixture_responses([])
        assert result == []

    @pytest.mark.asyncio
    async def test_parse_with_failures(self, sample_league, sample_home_team, sample_away_team):
        """Test parsing continues even if some fixtures fail."""
        fixture1 = Fixture(
            fixture_id="f1",
            kickoff_time=datetime(2025, 11, 27, 15, 0, 0, tzinfo=timezone.utc),
            home_team=sample_home_team,
            away_team=sample_away_team,
            league=sample_league,
            ai_analysis={"markets": []}  # Empty response
        )

        fixture2 = Fixture(
            fixture_id="f2",
            kickoff_time=datetime(2025, 11, 27, 17, 0, 0, tzinfo=timezone.utc),
            home_team=sample_home_team,
            away_team=sample_away_team,
            league=sample_league,
            ai_analysis=None  # No response
        )

        result = await parse_all_fixture_responses([fixture1, fixture2])
        assert len(result) == 2
        # Both should be present even if failed
        assert all(f.fixture_id for f in result)


# ============================================================================
# Test get_probability_summary
# ============================================================================

class TestGetProbabilitySummary:
    """Tests for get_probability_summary function."""

    def test_summary_single_market(self):
        """Test probability summary for single market."""
        markets = [
            MarketAnalysis(
                market_type="match_result",
                ai_probability=0.55,
                reasoning="test",
                confidence=75
            )
        ]
        result = get_probability_summary(markets)
        assert "match_result" in result
        assert result["match_result"]["ai_probability"] == 0.55
        assert result["match_result"]["confidence"] == 75

    def test_summary_multiple_markets(self):
        """Test probability summary for multiple markets."""
        markets = [
            MarketAnalysis(
                market_type="match_result",
                ai_probability=0.55,
                reasoning="test",
                confidence=75
            ),
            MarketAnalysis(
                market_type="total_goals",
                ai_probability=0.60,
                reasoning="test",
                confidence=70
            )
        ]
        result = get_probability_summary(markets)
        assert len(result) == 2
        assert result["match_result"]["ai_probability"] == 0.55
        assert result["total_goals"]["ai_probability"] == 0.60

    def test_summary_empty_markets(self):
        """Test probability summary for empty markets list."""
        result = get_probability_summary([])
        assert result == {}

    def test_summary_duplicate_market_types(self):
        """Test summary with duplicate market types (last one wins)."""
        markets = [
            MarketAnalysis(
                market_type="match_result",
                ai_probability=0.55,
                reasoning="test1",
                confidence=75
            ),
            MarketAnalysis(
                market_type="match_result",
                ai_probability=0.60,
                reasoning="test2",
                confidence=80
            )
        ]
        result = get_probability_summary(markets)
        # Last one should win
        assert result["match_result"]["ai_probability"] == 0.60
        assert result["match_result"]["confidence"] == 80


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for end-to-end parsing flow."""

    @pytest.mark.asyncio
    async def test_full_parsing_pipeline(self, sample_fixture, valid_openai_response_json):
        """Test complete pipeline: parse response + attach to fixture."""
        fixture = sample_fixture
        fixture.ai_analysis = valid_openai_response_json

        # Parse response
        parsed_markets = await parse_openai_response(
            fixture.ai_analysis,
            fixture.fixture_id
        )

        # Attach to fixture
        result = await attach_parsed_analysis_to_fixture(fixture, parsed_markets)

        # Verify result
        assert result.ai_analysis is not None
        assert len(result.ai_analysis.markets) == 2
        assert isinstance(result.ai_analysis, AIAnalysis)

    @pytest.mark.asyncio
    async def test_realistic_openai_response(self, sample_fixture):
        """Test parsing realistic OpenAI response."""
        realistic_response = {
            "markets": [
                {
                    "type": "match_result",
                    "probabilities": {
                        "home": 0.58,
                        "draw": 0.22,
                        "away": 0.20
                    },
                    "reasoning": "Leeds playing at home with excellent form. "
                    "Defensive issues against Bristol City's pressing style "
                    "mitigated by home advantage.",
                    "confidence": 0.82
                },
                {
                    "type": "total_goals",
                    "probabilities": {
                        "over": 0.65,
                        "under": 0.35
                    },
                    "reasoning": "Both teams attacking-minded, recent form "
                    "suggests high-scoring matches. Bristol defence weak.",
                    "confidence": 0.77
                },
                {
                    "type": "corners",
                    "probabilities": {
                        "over": 0.72,
                        "under": 0.28
                    },
                    "reasoning": "Leeds average 6.2 corners per game at home. "
                    "Bristol defensive style leads to more set pieces.",
                    "confidence": 0.79
                }
            ]
        }

        result = await parse_openai_response(realistic_response, sample_fixture.fixture_id)
        assert len(result) == 3
        assert all(isinstance(m, MarketAnalysis) for m in result)

        # Verify market types
        market_types = {m.market_type for m in result}
        assert "match_result" in market_types
        assert "total_goals" in market_types
        assert "corners" in market_types
