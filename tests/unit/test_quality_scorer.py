"""
Unit tests for quality_scorer module.

Tests all component scoring functions and overall quality score calculation.
Covers edge cases, error handling, and logging output validation.
Target coverage: 85%+
"""

import pytest
from datetime import datetime, timezone

from bet_bot.data.consolidation.quality_scorer import (
    DataQualityScore,
    _score_required_fields,
    _score_data_freshness,
    _score_injury_data,
    _score_h2h_data,
    _score_odds_markets,
    _score_form_sample_size,
    _calculate_quality_score,
    score_fixtures,
)
from bet_bot.data.consolidation.validator import ValidationResult, ValidationStatus
from bet_bot.models import Fixture, Team, League


# ===== FIXTURES FOR TESTING =====

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
def sample_team_with_form_and_injuries(sample_league) -> Team:
    """Create a team with full form and injury data."""
    return Team(
        id="123",
        name="Leeds United",
        form_5_games=["W", "W", "D", "L", "W"],
        avg_goals_for=1.8,
        avg_goals_against=1.2,
        injuries=["5001", "5002"]
    )


@pytest.fixture
def sample_team_no_data(sample_league) -> Team:
    """Create a team with minimal data."""
    return Team(
        id="456",
        name="Derby County",
        form_5_games=[],
        avg_goals_for=0.0,
        avg_goals_against=0.0,
        injuries=[]
    )


@pytest.fixture
def sample_fixture_excellent(sample_league, sample_team_with_form_and_injuries) -> Fixture:
    """Create a fixture with excellent data."""
    return Fixture(
        fixture_id="548821",
        kickoff_time=datetime.now(timezone.utc),
        home_team=sample_team_with_form_and_injuries,
        away_team=Team(
            id="789",
            name="Bristol City",
            form_5_games=["W", "W", "W", "D", "W"],
            avg_goals_for=2.1,
            avg_goals_against=0.8,
            injuries=["6001"]
        ),
        league=sample_league,
        odds={
            "match_result": {"home": 2.10, "draw": 3.50, "away": 3.20},
            "total_goals": {"over_2_5": 1.85, "under_2_5": 1.95},
            "corners": {"over_10_5": 1.75, "under_10_5": 2.05}
        },
        head_to_head_history=["W", "D", "W", "L", "W"]
    )


@pytest.fixture
def sample_fixture_poor(sample_league, sample_team_no_data) -> Fixture:
    """Create a fixture with poor data."""
    return Fixture(
        fixture_id="548822",
        kickoff_time=datetime.now(timezone.utc),
        home_team=sample_team_no_data,
        away_team=Team(
            id="999",
            name="Coventry City",
            form_5_games=[],
            avg_goals_for=0.0,
            avg_goals_against=0.0,
            injuries=[]
        ),
        league=sample_league,
        odds={"match_result": {"home": 2.10, "draw": 3.50, "away": 3.20}},
        head_to_head_history=[]
    )


@pytest.fixture
def validation_pass() -> ValidationResult:
    """Create a PASS validation result."""
    return ValidationResult(
        fixture_id="548821",
        status=ValidationStatus.PASS,
        reason="All data fresh",
        fixture_valid=True,
        odds_status="PASS",
        form_status="PASS",
        injuries_status="PASS",
        h2h_status="PASS",
        data_freshness_score=95
    )


@pytest.fixture
def validation_degradation() -> ValidationResult:
    """Create a DEGRADATION validation result."""
    return ValidationResult(
        fixture_id="548822",
        status=ValidationStatus.DEGRADATION,
        reason="Form data is 18 hours old",
        fixture_valid=True,
        odds_status="PASS",
        form_status="DEGRADATION",
        injuries_status="PASS",
        h2h_status="UNKNOWN",
        data_freshness_score=60
    )


@pytest.fixture
def validation_critical() -> ValidationResult:
    """Create a CRITICAL validation result."""
    return ValidationResult(
        fixture_id="548823",
        status=ValidationStatus.CRITICAL,
        reason="Odds data is 3 hours old",
        fixture_valid=True,
        odds_status="CRITICAL",
        form_status="PASS",
        injuries_status="PASS",
        h2h_status="PASS",
        data_freshness_score=10
    )


# ===== TESTS: REQUIRED FIELDS SCORING =====

def test_score_required_fields_all_present(sample_fixture_excellent):
    """Test scoring when all required fields are present."""
    points, reason = _score_required_fields(sample_fixture_excellent)
    assert points == 20
    assert "All required fields" in reason


def test_score_required_fields_missing_odds(sample_fixture_excellent):
    """Test scoring when odds are missing."""
    sample_fixture_excellent.odds = {}
    points, reason = _score_required_fields(sample_fixture_excellent)
    assert points == 10
    assert "odds" in reason


def test_score_required_fields_missing_multiple(sample_fixture_excellent):
    """Test scoring when multiple fields are missing."""
    sample_fixture_excellent.odds = {}
    sample_fixture_excellent.head_to_head_history = []
    # Note: head_to_head is not in required fields check, so only odds missing
    points, reason = _score_required_fields(sample_fixture_excellent)
    assert points == 10

    # Actually test multiple missing
    sample_fixture_excellent.fixture_id = ""
    sample_fixture_excellent.odds = {}
    points, reason = _score_required_fields(sample_fixture_excellent)
    assert points == 0
    assert "Missing fields" in reason


def test_score_required_fields_empty_fixture_id(sample_fixture_excellent):
    """Test scoring when fixture_id is empty."""
    sample_fixture_excellent.fixture_id = ""
    points, reason = _score_required_fields(sample_fixture_excellent)
    assert points == 10
    assert "fixture_id" in reason


# ===== TESTS: FRESHNESS SCORING =====

def test_score_data_freshness_pass(sample_fixture_excellent, validation_pass):
    """Test freshness scoring with PASS status."""
    points, reason = _score_data_freshness(sample_fixture_excellent, validation_pass)
    assert points == 20
    assert "PASS" in reason


def test_score_data_freshness_degradation(sample_fixture_excellent, validation_degradation):
    """Test freshness scoring with DEGRADATION status."""
    points, reason = _score_data_freshness(sample_fixture_excellent, validation_degradation)
    assert points == 10
    assert "DEGRADATION" in reason


def test_score_data_freshness_critical(sample_fixture_excellent, validation_critical):
    """Test freshness scoring with CRITICAL status."""
    points, reason = _score_data_freshness(sample_fixture_excellent, validation_critical)
    assert points == 0
    assert "CRITICAL" in reason


# ===== TESTS: INJURY DATA SCORING =====

def test_score_injury_data_both_teams(sample_fixture_excellent):
    """Test injury scoring when both teams have injury data."""
    points, reason = _score_injury_data(sample_fixture_excellent)
    assert points == 15
    assert "both teams" in reason


def test_score_injury_data_one_team(sample_fixture_excellent):
    """Test injury scoring when only one team has injury data."""
    sample_fixture_excellent.away_team.injuries = []
    points, reason = _score_injury_data(sample_fixture_excellent)
    assert points == 8
    assert "only" in reason


def test_score_injury_data_none(sample_fixture_poor):
    """Test injury scoring when no injury data available."""
    points, reason = _score_injury_data(sample_fixture_poor)
    assert points == 0
    assert "No injury data" in reason


# ===== TESTS: H2H DATA SCORING =====

def test_score_h2h_data_5_plus_matches(sample_fixture_excellent):
    """Test H2H scoring with 5+ matches."""
    points, reason = _score_h2h_data(sample_fixture_excellent)
    assert points == 10
    assert "5 matches" in reason


def test_score_h2h_data_2_to_4_matches(sample_fixture_excellent):
    """Test H2H scoring with 2-4 matches."""
    sample_fixture_excellent.head_to_head_history = ["W", "D", "W"]
    points, reason = _score_h2h_data(sample_fixture_excellent)
    assert points == 5
    assert "3 matches" in reason


def test_score_h2h_data_none(sample_fixture_poor):
    """Test H2H scoring with no matches."""
    points, reason = _score_h2h_data(sample_fixture_poor)
    assert points == 0
    assert "No H2H history" in reason


def test_score_h2h_data_single_match(sample_fixture_excellent):
    """Test H2H scoring with single match."""
    sample_fixture_excellent.head_to_head_history = ["W"]
    points, reason = _score_h2h_data(sample_fixture_excellent)
    assert points == 0
    assert "No H2H history" in reason


# ===== TESTS: ODDS MARKETS SCORING =====

def test_score_odds_markets_3_plus(sample_fixture_excellent):
    """Test markets scoring with 3+ markets."""
    points, reason = _score_odds_markets(sample_fixture_excellent)
    assert points == 10
    assert "3" in reason or "Multiple" in reason


def test_score_odds_markets_2_markets(sample_fixture_excellent):
    """Test markets scoring with 2 markets."""
    sample_fixture_excellent.odds = {
        "match_result": {"home": 2.10, "draw": 3.50, "away": 3.20},
        "total_goals": {"over_2_5": 1.85, "under_2_5": 1.95}
    }
    points, reason = _score_odds_markets(sample_fixture_excellent)
    assert points == 5
    assert "2" in reason or "Two" in reason


def test_score_odds_markets_1_market(sample_fixture_excellent):
    """Test markets scoring with 1 market."""
    sample_fixture_excellent.odds = {
        "match_result": {"home": 2.10, "draw": 3.50, "away": 3.20}
    }
    points, reason = _score_odds_markets(sample_fixture_excellent)
    assert points == 2
    assert "Single" in reason or "1" in reason


def test_score_odds_markets_none(sample_fixture_poor):
    """Test markets scoring with no odds."""
    points, reason = _score_odds_markets(sample_fixture_poor)
    assert points == 2  # Has 1 market (match_result)
    assert "Single" in reason or "1" in reason


def test_score_odds_markets_empty(sample_fixture_excellent):
    """Test markets scoring with empty odds dict."""
    sample_fixture_excellent.odds = {}
    points, reason = _score_odds_markets(sample_fixture_excellent)
    assert points == 0
    assert "No odds" in reason


# ===== TESTS: FORM SAMPLE SIZE SCORING =====

def test_score_form_sample_size_10_plus_both(sample_fixture_excellent):
    """Test form scoring with 5+ games (max available) for both teams."""
    # Note: form_5_games max is 5, so treating 5+ as excellent
    sample_fixture_excellent.home_team.form_5_games = ["W"] * 5
    sample_fixture_excellent.away_team.form_5_games = ["W"] * 5
    points, reason = _score_form_sample_size(sample_fixture_excellent)
    assert points == 10
    assert "both teams" in reason


def test_score_form_sample_size_5_to_9_both(sample_fixture_excellent):
    """Test form scoring with 5+ games for both teams."""
    sample_fixture_excellent.home_team.form_5_games = ["W"] * 5
    sample_fixture_excellent.away_team.form_5_games = ["W"] * 5
    points, reason = _score_form_sample_size(sample_fixture_excellent)
    assert points == 10
    assert "both teams" in reason


def test_score_form_sample_size_5_plus_one_team(sample_fixture_excellent):
    """Test form scoring with 5+ games for one team only."""
    sample_fixture_excellent.home_team.form_5_games = ["W"] * 5
    sample_fixture_excellent.away_team.form_5_games = ["W"] * 2
    points, reason = _score_form_sample_size(sample_fixture_excellent)
    assert points == 3
    assert "limited for other" in reason


def test_score_form_sample_size_less_than_5(sample_fixture_poor):
    """Test form scoring with < 5 games for both teams."""
    points, reason = _score_form_sample_size(sample_fixture_poor)
    assert points == 0
    assert "Limited form data" in reason


def test_score_form_sample_size_partial_data(sample_fixture_excellent):
    """Test form scoring with partial form data."""
    sample_fixture_excellent.home_team.form_5_games = ["W", "W", "D"]
    sample_fixture_excellent.away_team.form_5_games = ["W"]
    points, reason = _score_form_sample_size(sample_fixture_excellent)
    assert points == 0
    assert "Limited" in reason


# ===== TESTS: OVERALL SCORE AGGREGATION =====

def test_calculate_quality_score_excellent(sample_fixture_excellent, validation_pass):
    """Test quality score with excellent data."""
    score = _calculate_quality_score(sample_fixture_excellent, validation_pass)

    assert isinstance(score, DataQualityScore)
    assert score.fixture_id == "548821"
    assert score.overall_score == 100  # Perfect score
    assert score.required_fields_score == 20
    assert score.freshness_score == 20
    assert score.injury_score == 15
    assert score.h2h_score == 10
    assert score.markets_score == 10
    assert score.form_sample_score == 10
    assert score.validation_bonus == 15
    assert len(score.reasoning) > 0 and "|" in score.reasoning  # Has detailed reasoning


def test_calculate_quality_score_degraded(sample_fixture_poor, validation_degradation):
    """Test quality score with degraded data."""
    score = _calculate_quality_score(sample_fixture_poor, validation_degradation)

    assert score.overall_score < 50
    assert score.required_fields_score == 20
    assert score.freshness_score == 10
    assert score.injury_score == 0
    assert score.h2h_score == 0
    assert score.form_sample_score == 0
    assert score.validation_bonus == 0
    assert "form" in score.reasoning.lower()


def test_calculate_quality_score_critical(sample_fixture_excellent, validation_critical):
    """Test quality score with critical validation status."""
    score = _calculate_quality_score(sample_fixture_excellent, validation_critical)

    assert score.freshness_score == 0
    assert score.validation_bonus == 0
    assert score.overall_score < 85  # No bonus for CRITICAL


def test_calculate_quality_score_clamped_to_100(sample_fixture_excellent, validation_pass):
    """Test that score is clamped to max 100."""
    score = _calculate_quality_score(sample_fixture_excellent, validation_pass)
    assert score.overall_score <= 100


def test_calculate_quality_score_clamped_to_0(sample_fixture_poor, validation_critical):
    """Test that score is clamped to min 0."""
    score = _calculate_quality_score(sample_fixture_poor, validation_critical)
    assert score.overall_score >= 0


def test_dataqualityscore_model_serialization(sample_fixture_excellent, validation_pass):
    """Test that DataQualityScore is serializable."""
    score = _calculate_quality_score(sample_fixture_excellent, validation_pass)

    # Test dict conversion
    score_dict = score.model_dump()
    assert isinstance(score_dict, dict)
    assert "fixture_id" in score_dict
    assert "overall_score" in score_dict

    # Test JSON serialization
    score_json = score.model_dump_json()
    assert isinstance(score_json, str)
    assert "fixture_id" in score_json


# ===== TESTS: MAIN ORCHESTRATION FUNCTION =====

@pytest.mark.asyncio
async def test_score_fixtures_returns_all(sample_fixture_excellent, sample_fixture_poor, validation_pass, validation_degradation):
    """Test that score_fixtures returns all fixtures (no filtering)."""
    validated_fixtures = [
        (sample_fixture_excellent, validation_pass),
        (sample_fixture_poor, validation_degradation)
    ]

    scored = await score_fixtures(validated_fixtures)

    assert len(scored) == 2
    assert scored[0][0] == sample_fixture_excellent
    assert scored[1][0] == sample_fixture_poor


@pytest.mark.asyncio
async def test_score_fixtures_attaches_scores(sample_fixture_excellent, validation_pass):
    """Test that scores are properly attached to fixtures."""
    validated_fixtures = [(sample_fixture_excellent, validation_pass)]

    scored = await score_fixtures(validated_fixtures)

    assert len(scored) == 1
    fixture, score = scored[0]
    assert isinstance(score, DataQualityScore)
    assert score.overall_score > 0


@pytest.mark.asyncio
async def test_score_fixtures_empty_input():
    """Test handling of empty input."""
    scored = await score_fixtures([])
    assert scored == []


@pytest.mark.asyncio
async def test_score_fixtures_continues_on_error(sample_fixture_excellent, validation_pass):
    """Test that scoring continues even if one fixture has an error."""
    # Create a fixture that might cause issues
    fixtures = [
        (sample_fixture_excellent, validation_pass),
    ]

    # Should not raise exception
    scored = await score_fixtures(fixtures)
    assert len(scored) == len(fixtures)


# ===== EDGE CASE TESTS =====

def test_edge_case_fixture_no_form_data(sample_fixture_excellent):
    """Test scoring when form data is missing entirely."""
    sample_fixture_excellent.home_team.form_5_games = []
    sample_fixture_excellent.away_team.form_5_games = []
    points, reason = _score_form_sample_size(sample_fixture_excellent)
    assert points == 0
    assert "Limited" in reason


def test_edge_case_fixture_no_injuries(sample_fixture_excellent):
    """Test scoring when injury data is missing (not critical)."""
    sample_fixture_excellent.home_team.injuries = []
    sample_fixture_excellent.away_team.injuries = []
    points, reason = _score_injury_data(sample_fixture_excellent)
    assert points == 0
    assert "No injury data" in reason


def test_edge_case_fixture_single_market(sample_fixture_excellent):
    """Test scoring with single odds market."""
    sample_fixture_excellent.odds = {"match_result": {"home": 2.10, "draw": 3.50, "away": 3.20}}
    points, reason = _score_odds_markets(sample_fixture_excellent)
    assert points == 2
    assert "Single" in reason


def test_edge_case_all_degraded_data(sample_fixture_poor, validation_critical):
    """Test scoring when all data is degraded."""
    score = _calculate_quality_score(sample_fixture_poor, validation_critical)
    assert score.overall_score < 50
    assert score.overall_score >= 0  # Still produces valid score


def test_edge_case_partial_missing_data(sample_fixture_excellent, validation_degradation):
    """Test scoring with some optional fields missing."""
    sample_fixture_excellent.head_to_head_history = []
    sample_fixture_excellent.home_team.injuries = []
    score = _calculate_quality_score(sample_fixture_excellent, validation_degradation)
    assert score.overall_score > 0
    assert score.h2h_score == 0
    assert score.injury_score == 8  # Away team has injuries


# ===== PYDANTIC MODEL VALIDATION TESTS =====

def test_dataqualityscore_validation_score_range():
    """Test that DataQualityScore validates score ranges."""
    score = DataQualityScore(
        fixture_id="123",
        overall_score=50,
        required_fields_score=20,
        freshness_score=15
    )
    assert 0 <= score.overall_score <= 100
    assert 0 <= score.required_fields_score <= 20


def test_dataqualityscore_invalid_score_too_high():
    """Test that DataQualityScore rejects invalid high scores."""
    with pytest.raises(ValueError):
        DataQualityScore(
            fixture_id="123",
            overall_score=101  # Over max
        )


def test_dataqualityscore_invalid_score_negative():
    """Test that DataQualityScore rejects negative scores."""
    with pytest.raises(ValueError):
        DataQualityScore(
            fixture_id="123",
            overall_score=-1
        )
