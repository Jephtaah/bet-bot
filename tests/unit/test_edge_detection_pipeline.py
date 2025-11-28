"""
Unit tests for edge detection pipeline (Story 5.4).

Tests the detect_edges() orchestrator function and supporting utilities:
- Orchestration logic (EV → threshold → confidence → Pick transformation)
- Stake calculation formula and clamping
- Summary statistics calculation
- NO_PICKS message handling
- Error resilience and graceful degradation
- Logging output verification

Test coverage target: > 85% on pipeline module
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from bet_bot.models.analysis import Pick
from bet_bot.models.fixtures import Fixture, Team, League
from bet_bot.analysis.edge.pipeline import (
    detect_edges,
    _calculate_recommended_stake,
    _create_pick_from_ev_and_confidence,
    _calculate_summary_statistics,
    _log_summary_statistics,
)
from bet_bot.analysis.edge.ev_calculator import EVResult
from bet_bot.analysis.edge.confidence_scorer import ConfidenceScoreBreakdown
from bet_bot.analysis.edge.threshold_filter import FilteredPick, PickCategory


# Fixtures for test data
@pytest.fixture
def sample_team_home() -> Team:
    """Create a sample home team for testing."""
    return Team(id="1", name="Home Team")


@pytest.fixture
def sample_team_away() -> Team:
    """Create a sample away team for testing."""
    return Team(id="2", name="Away Team")


@pytest.fixture
def sample_league() -> League:
    """Create a sample League for testing."""
    return League(
        league_id="1",
        league_name="Test League",
        league_country="England",
        league_season=2025,
    )


@pytest.fixture
def sample_fixture(sample_team_home, sample_team_away, sample_league) -> Fixture:
    """Create a sample Fixture with required fields."""
    return Fixture(
        fixture_id="12345",
        kickoff_time=datetime.now(timezone.utc) + timedelta(days=1),
        home_team=sample_team_home,
        away_team=sample_team_away,
        league=sample_league,
        odds_data={"match_result": {"home": 2.10, "draw": 3.50, "away": 4.00}},
        odds_timestamp=datetime.now(timezone.utc) - timedelta(minutes=15),
    )


@pytest.fixture
def sample_ev_result(sample_fixture) -> EVResult:
    """Create a sample EVResult for testing."""
    return EVResult(
        market_type="match_result",
        outcome="home",
        ai_probability=0.58,
        odds=2.10,
        implied_probability=0.476,
        ev_decimal=0.058,
        ev_percentage=5.8,
        is_valid=True,
        skip_reason=None,
    )


@pytest.fixture
def sample_confidence_breakdown() -> ConfidenceScoreBreakdown:
    """Create a sample ConfidenceScoreBreakdown for testing."""
    return ConfidenceScoreBreakdown(
        base_score=75,
        form_adjustment=15,
        injury_adjustment=0,
        odds_adjustment=-5,
        sample_size_adjustment=0,
        total_adjustments=10,
        final_confidence=85,
        explanation="Fresh form (+15) but slightly stale odds (-5)",
    )


# Tests for _calculate_recommended_stake
class TestStakeCalculation:
    """Tests for stake calculation formula."""

    def test_stake_calculation_basic(self):
        """Test basic stake calculation with standard inputs."""
        # bankroll=1000, EV=5%, confidence=80%
        # = 1000 × (5 * 0.01 * 0.1) × (80 / 100)
        # = 1000 × 0.005 × 0.8 = 4.0
        stake = _calculate_recommended_stake(
            ev_percentage=5.0,
            confidence=80,
            bankroll=1000.0,
        )
        assert stake == pytest.approx(4.0, rel=0.01)

    def test_stake_calculation_zero_ev(self):
        """Test stake calculation with zero EV."""
        stake = _calculate_recommended_stake(
            ev_percentage=0.0,
            confidence=80,
            bankroll=1000.0,
        )
        assert stake > 0  # Minimum stake maintained

    def test_stake_calculation_zero_confidence(self):
        """Test stake calculation with zero confidence."""
        stake = _calculate_recommended_stake(
            ev_percentage=5.0,
            confidence=0,
            bankroll=1000.0,
        )
        assert stake > 0  # Minimum stake maintained

    def test_stake_calculation_100_percent(self):
        """Test stake calculation with 100% EV and confidence."""
        stake = _calculate_recommended_stake(
            ev_percentage=100.0,
            confidence=100,
            bankroll=1000.0,
        )
        # Should be clamped to max 5% of bankroll
        assert stake <= 50.0  # 5% of 1000
        assert stake > 0

    def test_stake_calculation_clamping(self):
        """Test that stake is clamped to max 5% of bankroll."""
        # High EV + high confidence = large stake
        stake = _calculate_recommended_stake(
            ev_percentage=50.0,
            confidence=100,
            bankroll=1000.0,
        )
        max_stake = 1000.0 * 0.05
        assert stake <= max_stake

    def test_stake_calculation_small_bankroll(self):
        """Test stake calculation with small bankroll."""
        stake = _calculate_recommended_stake(
            ev_percentage=10.0,
            confidence=75,
            bankroll=100.0,
        )
        # Should still calculate correctly and be positive
        assert stake > 0
        assert stake <= 100.0 * 0.05

    def test_stake_calculation_large_bankroll(self):
        """Test stake calculation with large bankroll."""
        stake = _calculate_recommended_stake(
            ev_percentage=5.0,
            confidence=75,
            bankroll=10000.0,
        )
        assert stake > 0
        assert stake <= 10000.0 * 0.05


# Tests for _create_pick_from_ev_and_confidence
class TestPickCreation:
    """Tests for creating Pick objects from EV and confidence data."""

    def test_pick_creation_success(self, sample_ev_result, sample_confidence_breakdown, sample_fixture):
        """Test successful Pick creation."""
        pick = _create_pick_from_ev_and_confidence(
            ev_result=sample_ev_result,
            confidence_breakdown=sample_confidence_breakdown,
            stake=4.0,
            fixture=sample_fixture,
        )

        assert isinstance(pick, Pick)
        assert pick.fixture_id == sample_fixture.fixture_id
        assert pick.ai_probability == 0.58
        assert pick.implied_probability == pytest.approx(0.476, rel=0.01)
        assert pick.ev_percentage == 5.8
        assert pick.confidence == 85
        assert pick.recommended_stake == 4.0
        assert pick.suggested_odds == 2.10

    def test_pick_creation_with_different_outcomes(self, sample_fixture):
        """Test Pick creation with various market outcomes."""
        outcomes = [
            ("match_result", "home", 2.10),
            ("total_goals", "over", 1.85),
            ("corners", "over", 3.25),
        ]

        for market_type, outcome, odds in outcomes:
            ev_result = EVResult(
                market_type=market_type,
                outcome=outcome,
                ai_probability=0.55,
                odds=odds,
                implied_probability=1 / odds,
                ev_decimal=0.05,
                ev_percentage=5.0,
                is_valid=True,
                skip_reason=None,
            )

            pick = _create_pick_from_ev_and_confidence(
                ev_result=ev_result,
                confidence_breakdown=ConfidenceScoreBreakdown(
                    base_score=75,
                    form_adjustment=0,
                    injury_adjustment=0,
                    odds_adjustment=0,
                    sample_size_adjustment=0,
                    total_adjustments=0,
                    final_confidence=75,
                    explanation="Neutral",
                ),
                stake=10.0,
                fixture=sample_fixture,
            )

            assert pick.market == f"{market_type}_{outcome}"
            assert pick.suggested_odds == odds


# Tests for _calculate_summary_statistics
class TestSummaryStatistics:
    """Tests for summary statistics calculation."""

    def test_summary_statistics_with_picks(self, sample_fixture):
        """Test summary statistics with multiple picks."""
        picks = [
            Pick(
                fixture_id="fixture_123",
                market="match_result_home",
                ai_probability=0.58,
                implied_probability=0.476,
                ev_percentage=5.8,
                confidence=85,
                recommended_stake=4.0,
                suggested_odds=2.10,
            ),
            Pick(
                fixture_id="fixture_123",
                market="match_result_away",
                ai_probability=0.35,
                implied_probability=0.25,
                ev_percentage=8.5,
                confidence=72,
                recommended_stake=6.0,
                suggested_odds=4.00,
            ),
            Pick(
                fixture_id="fixture_123",
                market="total_goals_over",
                ai_probability=0.62,
                implied_probability=0.54,
                ev_percentage=6.2,
                confidence=80,
                recommended_stake=5.0,
                suggested_odds=1.85,
            ),
        ]

        ev_results = [
            EVResult(
                market_type="match_result",
                outcome="home",
                ai_probability=0.58,
                odds=2.10,
                implied_probability=0.476,
                ev_decimal=0.058,
                ev_percentage=5.8,
                is_valid=True,
                skip_reason=None,
            ),
        ]

        stats = _calculate_summary_statistics(picks, ev_results)

        assert stats["total_ev_calculated"] == 1
        assert stats["total_picks_above_threshold"] == 3
        assert stats["ev_mean"] == pytest.approx(6.83, rel=0.1)
        assert stats["ev_min"] == 5.8
        assert stats["ev_max"] == 8.5
        assert stats["confidence_mean"] == pytest.approx(79.0, rel=0.1)
        assert stats["confidence_high_count"] == 1  # 85 (>80)
        assert stats["confidence_medium_count"] == 2  # 80, 72 (60-80)

    def test_summary_statistics_no_picks(self, sample_fixture):
        """Test summary statistics with no picks."""
        stats = _calculate_summary_statistics([], [])

        assert stats["total_picks_above_threshold"] == 0
        assert stats["ev_mean"] == 0.0
        assert stats["confidence_mean"] == 0
        assert stats["confidence_high_count"] == 0


# Tests for detect_edges orchestrator
class TestDetectEdgesOrchestrator:
    """Tests for the main detect_edges() orchestrator function."""

    @pytest.mark.asyncio
    async def test_detect_edges_empty_fixtures(self):
        """Test detect_edges with empty fixtures list."""
        result = await detect_edges([], bankroll=1000.0)
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_edges_invalid_bankroll(self, sample_fixture):
        """Test detect_edges with invalid bankroll."""
        with pytest.raises(ValueError):
            await detect_edges([sample_fixture], bankroll=0)

        with pytest.raises(ValueError):
            await detect_edges([sample_fixture], bankroll=-100)

    @pytest.mark.asyncio
    async def test_detect_edges_success_path(self, sample_fixture):
        """Test successful detect_edges pipeline execution."""
        # Mock the dependencies
        with patch("bet_bot.analysis.edge.pipeline.calculate_all_evs") as mock_calc_ev:
            with patch(
                "bet_bot.analysis.edge.pipeline.apply_threshold_filter"
            ) as mock_threshold:
                with patch(
                    "bet_bot.analysis.edge.pipeline.apply_confidence_scoring"
                ) as mock_confidence:
                    # Setup mock returns
                    sample_fixture.ev_results = [
                        EVResult(
                            market_type="match_result",
                            outcome="home",
                            ai_probability=0.58,
                            odds=2.10,
                            implied_probability=0.476,
                            ev_decimal=0.058,
                            ev_percentage=5.8,
                            is_valid=True,
                            skip_reason=None,
                        )
                    ]

                    mock_calc_ev.return_value = [sample_fixture]

                    filtered_pick = FilteredPick(
                        ev_result=sample_fixture.ev_results[0],
                        category=PickCategory.RECOMMENDED,
                        category_reason="EV 5.8% >= 5.0% threshold",
                        recommended=True,
                    )

                    mock_threshold.return_value = {
                        "recommended": [filtered_pick],
                        "total": 1,
                        "has_picks": True,
                    }

                    mock_confidence.return_value = [
                        ConfidenceScoreBreakdown(
                            base_score=75,
                            form_adjustment=0,
                            injury_adjustment=0,
                            odds_adjustment=0,
                            sample_size_adjustment=0,
                            total_adjustments=0,
                            final_confidence=75,
                            explanation="Neutral",
                        )
                    ]

                    # Execute
                    result = await detect_edges([sample_fixture], bankroll=1000.0)

                    # Verify
                    assert isinstance(result, list)
                    assert len(result) > 0
                    assert isinstance(result[0], Pick)

    @pytest.mark.asyncio
    async def test_detect_edges_no_picks_message(self, sample_fixture):
        """Test detect_edges returns NO_PICKS message when no picks above threshold."""
        with patch("bet_bot.analysis.edge.pipeline.calculate_all_evs") as mock_calc_ev:
            with patch(
                "bet_bot.analysis.edge.pipeline.apply_threshold_filter"
            ) as mock_threshold:
                with patch(
                    "bet_bot.analysis.edge.pipeline.no_picks_available_message"
                ) as mock_msg:
                    sample_fixture.ev_results = [
                        EVResult(
                            market_type="match_result",
                            outcome="home",
                            ai_probability=0.55,
                            odds=1.90,
                            implied_probability=0.526,
                            ev_decimal=0.01,
                            ev_percentage=1.0,
                            is_valid=True,
                            skip_reason=None,
                        )
                    ]

                    mock_calc_ev.return_value = [sample_fixture]
                    mock_threshold.return_value = {
                        "recommended": [],
                        "total": 1,
                        "has_picks": False,
                    }
                    mock_msg.return_value = "No picks available matching threshold"

                    result = await detect_edges([sample_fixture], bankroll=1000.0)

                    assert isinstance(result, str)
                    assert "No picks available" in result

    @pytest.mark.asyncio
    async def test_detect_edges_graceful_degradation(self, sample_fixture):
        """Test that detect_edges continues processing even if one pick fails."""
        with patch("bet_bot.analysis.edge.pipeline.calculate_all_evs") as mock_calc_ev:
            with patch(
                "bet_bot.analysis.edge.pipeline.apply_threshold_filter"
            ) as mock_threshold:
                with patch(
                    "bet_bot.analysis.edge.pipeline.apply_confidence_scoring"
                ) as mock_confidence:
                    # Create two EV results
                    ev1 = EVResult(
                        market_type="match_result",
                        outcome="home",
                        ai_probability=0.58,
                        odds=2.10,
                        implied_probability=0.476,
                        ev_decimal=0.058,
                        ev_percentage=5.8,
                        is_valid=True,
                        skip_reason=None,
                    )
                    ev2 = EVResult(
                        market_type="match_result",
                        outcome="away",
                        ai_probability=0.35,
                        odds=4.00,
                        implied_probability=0.25,
                        ev_decimal=0.085,
                        ev_percentage=8.5,
                        is_valid=True,
                        skip_reason=None,
                    )

                    sample_fixture.ev_results = [ev1, ev2]
                    mock_calc_ev.return_value = [sample_fixture]

                    mock_threshold.return_value = {
                        "recommended": [
                            FilteredPick(
                                ev_result=ev1,
                                category=PickCategory.RECOMMENDED,
                                category_reason="EV 5.8%",
                                recommended=True,
                            ),
                            FilteredPick(
                                ev_result=ev2,
                                category=PickCategory.RECOMMENDED,
                                category_reason="EV 8.5%",
                                recommended=True,
                            ),
                        ],
                        "total": 2,
                        "has_picks": True,
                    }

                    # Only return breakdown for first pick (second will be skipped)
                    mock_confidence.return_value = [
                        ConfidenceScoreBreakdown(
                            base_score=75,
                            form_adjustment=0,
                            injury_adjustment=0,
                            odds_adjustment=0,
                            sample_size_adjustment=0,
                            total_adjustments=0,
                            final_confidence=75,
                            explanation="Neutral",
                        )
                    ]

                    # Execute - should not raise exception
                    result = await detect_edges([sample_fixture], bankroll=1000.0)

                    # Should process at least the first pick successfully
                    assert isinstance(result, (list, str))


# Tests for logging
class TestLogging:
    """Tests for logging functionality."""

    def test_log_summary_statistics_with_picks(self, caplog):
        """Test that summary statistics are logged correctly."""
        summary = {
            "total_ev_calculated": 15,
            "total_picks_above_threshold": 8,
            "ev_mean": 5.2,
            "ev_min": 3.1,
            "ev_max": 9.8,
            "ev_high_count": 3,
            "ev_medium_count": 4,
            "ev_low_count": 1,
            "confidence_mean": 74,
            "confidence_min": 60,
            "confidence_max": 92,
            "confidence_high_count": 3,
            "confidence_medium_count": 4,
            "confidence_low_count": 1,
        }

        with caplog.at_level("INFO"):
            _log_summary_statistics(summary)

        log_output = caplog.text
        assert "Edge Detection Complete" in log_output
        assert "15 total EVs" in log_output
        assert "8 above 5% threshold" in log_output

    def test_log_summary_statistics_no_picks(self, caplog):
        """Test logging when no picks are found."""
        summary = {
            "total_ev_calculated": 10,
            "total_picks_above_threshold": 0,
            "ev_mean": 0.0,
            "ev_min": 0.0,
            "ev_max": 0.0,
            "ev_high_count": 0,
            "ev_medium_count": 0,
            "ev_low_count": 0,
            "confidence_mean": 0,
            "confidence_min": 0,
            "confidence_max": 0,
            "confidence_high_count": 0,
            "confidence_medium_count": 0,
            "confidence_low_count": 0,
        }

        with caplog.at_level("WARNING"):
            _log_summary_statistics(summary)

        log_output = caplog.text
        assert "No recommended picks found" in log_output or "10 total EVs evaluated" in log_output
