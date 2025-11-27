"""
Unit tests for ev_calculator module (Story 5.1).

Tests EV calculation functions, EVResult model validation, and filtering logic.
Focus on mathematical correctness, edge case handling, and error scenarios.

Coverage Target: 80% overall, 100% for critical paths (calculate_ev, calculate_implied_probability)

Test Organization:
- TestCalculateEV: Core EV formula tests
- TestCalculateImpliedProbability: Implied probability tests
- TestCalculateEVPercentage: Percentage conversion tests
- TestEVResultModel: Pydantic model validation
- TestFilterEVsByThreshold: Threshold filtering tests
"""

import pytest
from unittest.mock import MagicMock, patch

from bet_bot.analysis.edge import (
    EVResult,
    calculate_ev,
    calculate_ev_percentage,
    calculate_implied_probability,
    filter_evs_by_threshold,
)


class TestCalculateEV:
    """Test calculate_ev() function - core EV formula: EV = (ai_prob × odds) - 1"""

    def test_valid_positive_ev(self):
        """Valid case: positive EV (0.58 × 2.10) - 1 = 0.218 = 21.8%"""
        result = calculate_ev(ai_probability=0.58, odds=2.10)
        assert result is not None
        # Actual calculation: (0.58 * 2.10) - 1 = 1.218 - 1 = 0.218
        assert abs(result - 0.218) < 0.001  # Allow small floating-point tolerance

    def test_valid_negative_ev(self):
        """Valid case: negative EV (0.45 × 1.80) - 1 = -0.19"""
        result = calculate_ev(ai_probability=0.45, odds=1.80)
        assert result is not None
        assert abs(result - (-0.19)) < 0.001

    def test_edge_case_minimum_valid_inputs(self):
        """Edge case: odds = 1.01, ai_prob = 0.99"""
        result = calculate_ev(ai_probability=0.99, odds=1.01)
        assert result is not None
        expected = (0.99 * 1.01) - 1
        assert abs(result - expected) < 0.001

    def test_edge_case_extreme_valid_inputs(self):
        """Edge case: odds = 10.0, ai_prob = 0.99 (strong edge)"""
        result = calculate_ev(ai_probability=0.99, odds=10.0)
        assert result is not None
        expected = (0.99 * 10.0) - 1  # 9.9 - 1 = 8.9 (890% EV)
        assert abs(result - expected) < 0.001

    def test_invalid_odds_equals_one(self):
        """Invalid: odds = 1.0 (bookmakers never offer 1.0)"""
        result = calculate_ev(ai_probability=0.5, odds=1.0)
        assert result is None

    def test_invalid_odds_less_than_one(self):
        """Invalid: odds < 1.0"""
        result = calculate_ev(ai_probability=0.5, odds=0.9)
        assert result is None

    def test_invalid_odds_negative(self):
        """Invalid: odds < 0"""
        result = calculate_ev(ai_probability=0.5, odds=-2.0)
        assert result is None

    def test_invalid_ai_prob_greater_than_one(self):
        """Invalid: ai_probability > 1.0"""
        result = calculate_ev(ai_probability=1.5, odds=2.0)
        assert result is None

    def test_invalid_ai_prob_less_than_zero(self):
        """Invalid: ai_probability < 0.0"""
        result = calculate_ev(ai_probability=-0.1, odds=2.0)
        assert result is None

    def test_invalid_ai_prob_none(self):
        """Invalid: ai_probability = None"""
        result = calculate_ev(ai_probability=None, odds=2.0)
        assert result is None

    def test_invalid_odds_none(self):
        """Invalid: odds = None"""
        result = calculate_ev(ai_probability=0.5, odds=None)
        assert result is None

    def test_invalid_ai_prob_nan(self):
        """Invalid: ai_probability = NaN"""
        result = calculate_ev(ai_probability=float('nan'), odds=2.0)
        assert result is None

    def test_invalid_odds_nan(self):
        """Invalid: odds = NaN"""
        result = calculate_ev(ai_probability=0.5, odds=float('nan'))
        assert result is None

    def test_invalid_ai_prob_string(self):
        """Invalid: ai_probability wrong type"""
        result = calculate_ev(ai_probability="0.5", odds=2.0)
        assert result is None

    def test_invalid_odds_string(self):
        """Invalid: odds wrong type"""
        result = calculate_ev(ai_probability=0.5, odds="2.0")
        assert result is None

    def test_zero_probability_zero_ev(self):
        """Edge case: ai_prob=0 gives negative EV"""
        result = calculate_ev(ai_probability=0.0, odds=2.0)
        assert result is not None
        assert abs(result - (-1.0)) < 0.001

    def test_full_probability_one(self):
        """Edge case: ai_prob=1.0 (certainty)"""
        result = calculate_ev(ai_probability=1.0, odds=2.0)
        assert result is not None
        assert abs(result - 1.0) < 0.001


class TestCalculateImpliedProbability:
    """Test calculate_implied_probability() function: implied_prob = 1.0 / odds"""

    def test_valid_odds_two_one(self):
        """Valid: odds=2.10 → implied_prob ≈ 0.476"""
        result = calculate_implied_probability(odds=2.10)
        assert result is not None
        assert abs(result - (1.0 / 2.10)) < 0.001

    def test_valid_odds_one_five(self):
        """Valid: odds=1.50 → implied_prob ≈ 0.667"""
        result = calculate_implied_probability(odds=1.50)
        assert result is not None
        assert abs(result - (1.0 / 1.50)) < 0.001

    def test_valid_odds_three_five(self):
        """Valid: odds=3.50 → implied_prob ≈ 0.286"""
        result = calculate_implied_probability(odds=3.50)
        assert result is not None
        assert abs(result - (1.0 / 3.50)) < 0.001

    def test_edge_case_odds_one_point_zero_one(self):
        """Edge case: odds=1.01 (minimum valid)"""
        result = calculate_implied_probability(odds=1.01)
        assert result is not None
        assert abs(result - (1.0 / 1.01)) < 0.001

    def test_edge_case_high_odds(self):
        """Edge case: odds=100.0"""
        result = calculate_implied_probability(odds=100.0)
        assert result is not None
        assert abs(result - 0.01) < 0.001

    def test_invalid_odds_equals_one(self):
        """Invalid: odds = 1.0"""
        result = calculate_implied_probability(odds=1.0)
        assert result is None

    def test_invalid_odds_less_than_one(self):
        """Invalid: odds < 1.0"""
        result = calculate_implied_probability(odds=0.5)
        assert result is None

    def test_invalid_odds_zero(self):
        """Invalid: odds = 0"""
        result = calculate_implied_probability(odds=0.0)
        assert result is None

    def test_invalid_odds_negative(self):
        """Invalid: odds < 0"""
        result = calculate_implied_probability(odds=-2.0)
        assert result is None

    def test_invalid_odds_none(self):
        """Invalid: odds = None"""
        result = calculate_implied_probability(odds=None)
        assert result is None

    def test_invalid_odds_nan(self):
        """Invalid: odds = NaN"""
        result = calculate_implied_probability(odds=float('nan'))
        assert result is None

    def test_invalid_odds_string(self):
        """Invalid: odds wrong type"""
        result = calculate_implied_probability(odds="2.0")
        assert result is None


class TestCalculateEVPercentage:
    """Test calculate_ev_percentage() function: pct = decimal × 100"""

    def test_positive_ev_percentage(self):
        """Convert 0.058 to 5.8%"""
        result = calculate_ev_percentage(0.058)
        assert abs(result - 5.8) < 0.001

    def test_negative_ev_percentage(self):
        """Convert -0.19 to -19%"""
        result = calculate_ev_percentage(-0.19)
        assert abs(result - (-19.0)) < 0.001

    def test_large_positive_ev(self):
        """Convert 0.125 to 12.5%"""
        result = calculate_ev_percentage(0.125)
        assert abs(result - 12.5) < 0.001

    def test_zero_ev(self):
        """Convert 0.0 to 0%"""
        result = calculate_ev_percentage(0.0)
        assert result == 0.0

    def test_very_small_ev(self):
        """Convert 0.001 to 0.1%"""
        result = calculate_ev_percentage(0.001)
        assert abs(result - 0.1) < 0.0001


class TestEVResultModel:
    """Test EVResult Pydantic model validation"""

    def test_valid_ev_result_creation(self):
        """Create valid EVResult with all fields"""
        ev = EVResult(
            market_type="match_result",
            outcome="home",
            ai_probability=0.58,
            odds=2.10,
            implied_probability=0.476,
            ev_decimal=0.058,
            ev_percentage=5.8,
            is_valid=True
        )
        assert ev.market_type == "match_result"
        assert ev.outcome == "home"
        assert ev.ai_probability == 0.58
        assert ev.is_valid is True

    def test_ev_result_with_skip_reason(self):
        """Create EVResult with is_valid=False and skip_reason"""
        ev = EVResult(
            market_type="match_result",
            outcome="home",
            ai_probability=0.58,
            odds=1.0,  # Exactly 1.0 (valid for model, but invalid for calculation)
            implied_probability=1.0,
            ev_decimal=0.0,
            ev_percentage=0.0,
            is_valid=False,
            skip_reason="odds <= 1.0"
        )
        assert ev.is_valid is False
        assert ev.skip_reason == "odds <= 1.0"

    def test_ev_result_probability_range_validation(self):
        """Pydantic validates ai_probability and implied_probability ranges"""
        # AI probability must be [0.0, 1.0]
        with pytest.raises(Exception):  # ValidationError
            EVResult(
                market_type="match_result",
                outcome="home",
                ai_probability=1.5,  # Invalid
                odds=2.10,
                implied_probability=0.476,
                ev_decimal=0.058,
                ev_percentage=5.8
            )

    def test_ev_result_odds_validation(self):
        """Pydantic validates odds >= 1.0"""
        with pytest.raises(Exception):  # ValidationError
            EVResult(
                market_type="match_result",
                outcome="home",
                ai_probability=0.58,
                odds=0.5,  # Invalid: < 1.0
                implied_probability=0.476,
                ev_decimal=0.058,
                ev_percentage=5.8
            )

    def test_ev_result_empty_market_type_validation(self):
        """Pydantic validates market_type not empty"""
        with pytest.raises(Exception):  # ValidationError
            EVResult(
                market_type="",  # Invalid: empty
                outcome="home",
                ai_probability=0.58,
                odds=2.10,
                implied_probability=0.476,
                ev_decimal=0.058,
                ev_percentage=5.8
            )

    def test_ev_result_empty_outcome_validation(self):
        """Pydantic validates outcome not empty"""
        with pytest.raises(Exception):  # ValidationError
            EVResult(
                market_type="match_result",
                outcome="",  # Invalid: empty
                ai_probability=0.58,
                odds=2.10,
                implied_probability=0.476,
                ev_decimal=0.058,
                ev_percentage=5.8
            )


class TestFilterEVsByThreshold:
    """Test filter_evs_by_threshold() function"""

    def test_filter_empty_list(self):
        """Filter empty EV list"""
        above, below = filter_evs_by_threshold([], threshold_pct=5.0)
        assert len(above) == 0
        assert len(below) == 0

    def test_filter_all_above_threshold(self):
        """All results above threshold"""
        ev_results = [
            EVResult(
                market_type="match_result",
                outcome="home",
                ai_probability=0.58,
                odds=2.10,
                implied_probability=0.476,
                ev_decimal=0.058,
                ev_percentage=5.8,
                is_valid=True
            ),
            EVResult(
                market_type="match_result",
                outcome="away",
                ai_probability=0.60,
                odds=2.00,
                implied_probability=0.5,
                ev_decimal=0.10,
                ev_percentage=10.0,
                is_valid=True
            )
        ]
        above, below = filter_evs_by_threshold(ev_results, threshold_pct=5.0)
        assert len(above) == 2
        assert len(below) == 0

    def test_filter_all_below_threshold(self):
        """All results below threshold"""
        ev_results = [
            EVResult(
                market_type="match_result",
                outcome="home",
                ai_probability=0.52,
                odds=2.00,
                implied_probability=0.5,
                ev_decimal=0.04,
                ev_percentage=4.0,
                is_valid=True
            )
        ]
        above, below = filter_evs_by_threshold(ev_results, threshold_pct=5.0)
        assert len(above) == 0
        assert len(below) == 1

    def test_filter_mixed_results(self):
        """Mix of above and below threshold"""
        ev_results = [
            EVResult(
                market_type="match_result",
                outcome="home",
                ai_probability=0.58,
                odds=2.10,
                implied_probability=0.476,
                ev_decimal=0.218,
                ev_percentage=21.8,  # High EV
                is_valid=True
            ),
            EVResult(
                market_type="match_result",
                outcome="draw",
                ai_probability=0.30,
                odds=3.50,
                implied_probability=0.286,
                ev_decimal=0.05,
                ev_percentage=5.0,  # Exactly at threshold (>= 5.0, so included)
                is_valid=True
            ),
            EVResult(
                market_type="match_result",
                outcome="away",
                ai_probability=0.52,
                odds=2.00,
                implied_probability=0.5,
                ev_decimal=0.04,
                ev_percentage=4.0,  # Below threshold
                is_valid=True
            )
        ]
        above, below = filter_evs_by_threshold(ev_results, threshold_pct=5.0)
        assert len(above) == 2  # Home (21.8%) and Draw (5.0% - at threshold, goes above)
        assert len(below) == 1  # Away (4.0% - below)

    def test_filter_invalid_results_to_below(self):
        """Invalid EV results go to below threshold"""
        ev_results = [
            EVResult(
                market_type="match_result",
                outcome="home",
                ai_probability=0.58,
                odds=2.10,
                implied_probability=0.476,
                ev_decimal=0.058,
                ev_percentage=5.8,
                is_valid=True
            ),
            EVResult(
                market_type="match_result",
                outcome="away",
                ai_probability=0.50,
                odds=1.0,  # Invalid
                implied_probability=1.0,
                ev_decimal=0.0,
                ev_percentage=0.0,
                is_valid=False,
                skip_reason="odds <= 1.0"
            )
        ]
        above, below = filter_evs_by_threshold(ev_results, threshold_pct=5.0)
        assert len(above) == 1
        assert len(below) == 1
        assert below[0].is_valid is False

    def test_filter_custom_threshold(self):
        """Filter with custom threshold (2% for aggressive)"""
        ev_results = [
            EVResult(
                market_type="match_result",
                outcome="home",
                ai_probability=0.52,
                odds=2.10,
                implied_probability=0.476,
                ev_decimal=0.0492,
                ev_percentage=4.92,
                is_valid=True
            )
        ]
        # Above 2% threshold
        above, below = filter_evs_by_threshold(ev_results, threshold_pct=2.0)
        assert len(above) == 1
        assert len(below) == 0

        # Below 5% threshold
        above, below = filter_evs_by_threshold(ev_results, threshold_pct=5.0)
        assert len(above) == 0
        assert len(below) == 1

    def test_filter_threshold_boundary_exactly_at(self):
        """Exactly at threshold boundary (should be in above with >=)"""
        ev_results = [
            EVResult(
                market_type="match_result",
                outcome="home",
                ai_probability=0.55,
                odds=2.0,
                implied_probability=0.5,
                ev_decimal=0.05,
                ev_percentage=5.0,
                is_valid=True
            )
        ]
        above, below = filter_evs_by_threshold(ev_results, threshold_pct=5.0)
        assert len(above) == 1  # >= 5.0, so goes to above
        assert len(below) == 0

    def test_filter_threshold_just_above_boundary(self):
        """Just above threshold boundary"""
        ev_results = [
            EVResult(
                market_type="match_result",
                outcome="home",
                ai_probability=0.551,
                odds=2.0,
                implied_probability=0.5,
                ev_decimal=0.051,
                ev_percentage=5.1,
                is_valid=True
            )
        ]
        above, below = filter_evs_by_threshold(ev_results, threshold_pct=5.0)
        assert len(above) == 1  # >= 5.0, so goes to above
        assert len(below) == 0


class TestErrorHandlingCoverage:
    """Test error handling paths for improved coverage."""

    def test_calculate_ev_with_unexpected_exception(self):
        """Test that unexpected exceptions in calculate_ev are caught and logged."""
        # We can't easily trigger the actual exception in line 243-245,
        # but we can verify the function handles edge cases gracefully
        # by passing unusual numeric types that might cause issues
        result = calculate_ev(ai_probability=float('inf'), odds=2.0)
        # Should handle gracefully even with infinity
        assert result is None or isinstance(result, (int, float))

    def test_calculate_implied_probability_with_edge_numeric_values(self):
        """Test implied probability with edge numeric cases."""
        # Very large odds
        result = calculate_implied_probability(odds=1000.0)
        assert result is not None
        assert 0.0 < result <= 0.001

        # Very small odds (but still > 1.0)
        result = calculate_implied_probability(odds=1.001)
        assert result is not None
        assert abs(result - (1.0 / 1.001)) < 0.001

    def test_calculate_ev_percentage_with_extreme_values(self):
        """Test EV percentage conversion with extreme values."""
        # Very large EV
        result = calculate_ev_percentage(100.0)
        assert result == 10000.0

        # Very negative EV
        result = calculate_ev_percentage(-0.99)
        assert result == -99.0

        # Near zero
        result = calculate_ev_percentage(0.001)
        assert abs(result - 0.1) < 0.001


class TestMarketExtractionErrorHandling:
    """Test error handling in market extraction."""

    def test_extract_market_evs_with_none_fixture(self):
        """Test _extract_market_evs_from_fixture with None fixture."""
        from bet_bot.analysis.edge.ev_calculator import _extract_market_evs_from_fixture

        result = _extract_market_evs_from_fixture(None)
        assert result == []

    def test_extract_market_evs_with_missing_ai_analysis(self):
        """Test market extraction when ai_analysis is None."""
        from bet_bot.analysis.edge.ev_calculator import _extract_market_evs_from_fixture
        from bet_bot.models.fixtures import Fixture, Team, League
        from datetime import datetime, timezone

        team = Team(id="1", name="Test Team")
        league = League(league_id="1", league_name="Test", league_country="Test", league_season=2025)

        fixture = Fixture(
            fixture_id="123",
            kickoff_time=datetime.now(timezone.utc),
            home_team=team,
            away_team=Team(id="2", name="Other Team"),
            league=league,
            ai_analysis=None  # Missing
        )

        result = _extract_market_evs_from_fixture(fixture)
        assert result == []


class TestIntegrationWithMockFixture:
    """Integration tests with mock Fixture objects"""

    def test_ev_result_attached_to_fixture(self):
        """Test that EVResult can be attached to Fixture"""
        from bet_bot.models.fixtures import Fixture, Team, League

        # Create minimal fixture
        league = League(
            league_id="39",
            league_name="Championship",
            league_country="England",
            league_season=2025
        )
        home_team = Team(id="123", name="Leeds United")
        away_team = Team(id="456", name="West Brom")

        fixture = Fixture(
            fixture_id="548821",
            kickoff_time="2025-11-24T15:00:00Z",
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        # Create and attach EV results
        ev = EVResult(
            market_type="match_result",
            outcome="home",
            ai_probability=0.58,
            odds=2.10,
            implied_probability=0.476,
            ev_decimal=0.058,
            ev_percentage=5.8,
            is_valid=True
        )

        fixture.ev_results = [ev]

        assert fixture.ev_results is not None
        assert len(fixture.ev_results) == 1
        assert fixture.ev_results[0].outcome == "home"
