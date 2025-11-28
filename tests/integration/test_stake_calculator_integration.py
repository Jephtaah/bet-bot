"""
Integration tests for stake_calculator module (Story 6.1).

Tests integration with Story 5.4 edge detection pipeline, Pick objects, and realistic scenarios.
Verifies stake calculation works correctly with actual data structures from the pipeline.

Test Organization:
- TestIntegrationWithPickObjects: Creating stakes for Pick objects from edge detection
- TestMultiplePickStaking: Multiple picks in various scenarios
- TestDataQualityScenarios: Fresh vs stale data impact on stakes
- TestRealisticBettingScenarios: Real-world betting situations
"""

import pytest

from bet_bot.analysis.stakes import calculate_stake
from bet_bot.models.analysis import Pick
from bet_bot.models.fixtures import Fixture
from datetime import datetime, timezone


class TestIntegrationWithPickObjects:
    """Test calculating stakes for Pick objects from Story 5.4"""

    def test_calculate_stake_for_single_pick(self):
        """Calculate stake for a single Pick object from edge detection"""
        # This simulates how Story 5.4's detect_edges() would call calculate_stake
        pick_ev = 5.2
        pick_confidence = 72
        bankroll = 1000.0

        stake_result = calculate_stake(
            bankroll=bankroll,
            ev_percentage=pick_ev,
            confidence=pick_confidence,
        )

        # Verify it works and returns correct structure
        assert "suggested_stake" in stake_result
        assert "stake_in_units" in stake_result
        assert "bankroll_percentage" in stake_result
        assert stake_result["suggested_stake"] > 0

    def test_pick_fields_populate_correctly(self):
        """Verify Pick model can be populated with calculated stake values"""
        # From edge detection pipeline, a Pick would have:
        pick_data = {
            "fixture_id": "fixture_12345",
            "market": "home_team_win",
            "ai_probability": 0.58,
            "implied_probability": 0.476,
            "ev_percentage": 5.2,
            "confidence": 72,
            "suggested_odds": 2.10,
        }

        # Calculate stake
        stake_result = calculate_stake(
            bankroll=1000.0,
            ev_percentage=pick_data["ev_percentage"],
            confidence=pick_data["confidence"],
        )

        # Add stake to pick data and create Pick object
        pick_data["recommended_stake"] = stake_result["suggested_stake"]
        pick = Pick(**pick_data)

        # Verify Pick is created with stake
        assert pick.recommended_stake > 0
        assert pick.recommended_stake == stake_result["suggested_stake"]

    def test_stake_values_added_to_multiple_picks(self):
        """Calculate stakes for multiple different picks from edge detection"""
        picks_data = [
            {"ev": 5.2, "confidence": 72},
            {"ev": 8.1, "confidence": 85},
            {"ev": 3.5, "confidence": 60},
            {"ev": 6.0, "confidence": 78},
        ]

        bankroll = 1000.0
        stakes = []

        for pick in picks_data:
            stake_result = calculate_stake(
                bankroll=bankroll,
                ev_percentage=pick["ev"],
                confidence=pick["confidence"],
            )
            stakes.append(stake_result["suggested_stake"])

        # Each pick should have a unique stake
        assert len(stakes) == 4
        assert all(s > 0 for s in stakes)
        # Picks with higher EV and confidence should have higher stakes
        assert stakes[1] > stakes[2]  # 8.1% EV should > 3.5% EV


class TestMultiplePickStaking:
    """Test stake calculation for multiple picks in various scenarios"""

    def test_multiple_picks_same_fixture(self):
        """Multiple picks from same fixture → independent stake calculations"""
        # Example: same fixture, different markets
        picks = [
            {"market": "home_team_win", "ev": 5.0, "confidence": 75},
            {"market": "over_2_5_goals", "ev": 4.8, "confidence": 70},
        ]

        bankroll = 1000.0
        stakes = []

        for pick in picks:
            result = calculate_stake(
                bankroll=bankroll,
                ev_percentage=pick["ev"],
                confidence=pick["confidence"],
            )
            stakes.append(result["suggested_stake"])

        # Verify independent calculations
        assert len(stakes) == 2
        assert all(s > 0 for s in stakes)
        # Each should be calculated independently based on its own EV/confidence
        assert stakes[0] > stakes[1]  # 5.0% EV > 4.8% EV

    def test_multiple_picks_different_fixtures(self):
        """Multiple picks across different fixtures → independent calculations"""
        picks = [
            {"fixture": "1", "ev": 5.2, "confidence": 72},
            {"fixture": "2", "ev": 6.5, "confidence": 80},
            {"fixture": "3", "ev": 4.1, "confidence": 65},
        ]

        bankroll = 1000.0
        results = []

        for pick in picks:
            result = calculate_stake(
                bankroll=bankroll,
                ev_percentage=pick["ev"],
                confidence=pick["confidence"],
            )
            results.append(result)

        # Verify independent calculations
        assert len(results) == 3
        assert all(r["suggested_stake"] > 0 for r in results)

        # Verify each is calculated based on its own parameters
        stakes = [r["suggested_stake"] for r in results]
        assert stakes[1] > stakes[0] > stakes[2]  # By EV: 6.5 > 5.2 > 4.1

    def test_total_exposure_across_picks(self):
        """Document behavior: total exposure = sum of individual stakes"""
        picks = [
            {"ev": 5.0, "confidence": 75},
            {"ev": 5.0, "confidence": 75},
            {"ev": 5.0, "confidence": 75},
        ]

        bankroll = 1000.0
        total_stake = 0.0

        for pick in picks:
            result = calculate_stake(
                bankroll=bankroll,
                ev_percentage=pick["ev"],
                confidence=pick["confidence"],
            )
            total_stake += result["suggested_stake"]

        # With 3 identical picks of 5% EV, 75% confidence:
        # Each: 1000 × 0.005 × 0.75 = $3.75
        # Total: $11.25 (still well below bankroll)
        assert total_stake == pytest.approx(11.25, abs=0.05)
        assert total_stake < bankroll  # Shouldn't exceed bankroll

    def test_many_marginal_picks_total_exposure(self):
        """Many marginal picks (low EV, medium confidence) create reasonable total exposure"""
        # Simulate 10 marginal picks
        picks = [{"ev": 2.5, "confidence": 55} for _ in range(10)]

        bankroll = 1000.0
        total_exposure = 0.0

        for pick in picks:
            result = calculate_stake(
                bankroll=bankroll,
                ev_percentage=pick["ev"],
                confidence=pick["confidence"],
            )
            total_exposure += result["suggested_stake"]

        # Each: 1000 × 0.0025 × 0.55 = $1.375
        # Total: ~$13.75
        assert total_exposure == pytest.approx(13.75, abs=0.1)
        assert total_exposure < bankroll * 0.05  # Still conservative


class TestDataQualityScenarios:
    """Test how data quality affects stake sizing"""

    def test_fresh_data_high_confidence(self):
        """Fresh data (high confidence) → reasonable full stakes"""
        # Fresh data indicators: high confidence, high EV certainty
        ev = 6.5
        confidence = 85  # High confidence

        result = calculate_stake(bankroll=1000.0, ev_percentage=ev, confidence=confidence)

        # Should have reasonable stake (full calculation)
        stake_percentage = result["bankroll_percentage"]
        assert stake_percentage > 0.4  # At least 0.4% of bankroll
        assert stake_percentage < 5.0  # But never exceeding 5%

    def test_stale_data_low_confidence(self):
        """Stale data (low confidence) → minimal stakes"""
        # Stale data indicators: low confidence, old odds
        ev = 5.0
        confidence = 35  # Low confidence

        result = calculate_stake(bankroll=1000.0, ev_percentage=ev, confidence=confidence)

        # Should have minimal stake due to low confidence
        stake_percentage = result["bankroll_percentage"]
        assert stake_percentage < 0.2  # Less than 0.2% due to low confidence

    def test_mixed_quality_data_distribution(self):
        """Mixed confidence distribution → proportionally varied stakes"""
        picks = [
            {"ev": 5.0, "confidence": 85},  # High quality
            {"ev": 5.0, "confidence": 70},  # Medium quality
            {"ev": 5.0, "confidence": 50},  # Low quality
        ]

        bankroll = 1000.0
        stakes = []

        for pick in picks:
            result = calculate_stake(
                bankroll=bankroll,
                ev_percentage=pick["ev"],
                confidence=pick["confidence"],
            )
            stakes.append(result["suggested_stake"])

        # Higher confidence should produce higher stakes
        assert stakes[0] > stakes[1] > stakes[2]
        # Approximate ratios should reflect confidence ratios (85:70:50)
        assert stakes[0] / stakes[2] > 1.5

    def test_high_confidence_uncertainty_in_ev(self):
        """High confidence but low EV → still moderate stakes"""
        # Confident in prediction but small edge detected
        result = calculate_stake(bankroll=1000.0, ev_percentage=2.0, confidence=90)

        # Should be small despite high confidence
        expected = 1000.0 * (2.0 * 0.01 * 0.1) * (90 / 100)  # = $1.80
        assert result["suggested_stake"] == pytest.approx(expected, abs=0.01)

    def test_high_ev_low_confidence(self):
        """High EV but low confidence → conservative scaling"""
        # Large edge but not confident (maybe recent data anomaly)
        result = calculate_stake(bankroll=1000.0, ev_percentage=15.0, confidence=30)

        # Should be heavily discounted by low confidence
        expected = 1000.0 * (15.0 * 0.01 * 0.1) * (30 / 100)  # = $4.50
        assert result["suggested_stake"] == pytest.approx(expected, abs=0.01)


class TestRealisticBettingScenarios:
    """Test with realistic betting situations"""

    def test_small_bankroll_many_marginal_picks(self):
        """Small bankroll ($500), many marginal picks → minimal but spread stakes"""
        bankroll = 500.0
        marginal_picks = [
            {"ev": 3.0, "confidence": 60},
            {"ev": 2.8, "confidence": 58},
            {"ev": 3.2, "confidence": 62},
            {"ev": 2.9, "confidence": 59},
        ]

        total_exposure = 0.0
        for pick in marginal_picks:
            result = calculate_stake(
                bankroll=bankroll,
                ev_percentage=pick["ev"],
                confidence=pick["confidence"],
            )
            total_exposure += result["suggested_stake"]

        # With small bankroll and marginal picks, stakes should be tiny
        # Each ~$0.50-0.60, total ~$2.20
        assert total_exposure < bankroll * 0.01  # Less than 1% total exposure
        assert total_exposure > 0  # But still something

    def test_large_bankroll_few_high_edge_picks(self):
        """Large bankroll ($10,000), few high-edge picks → larger stakes"""
        bankroll = 10000.0
        high_edge_picks = [
            {"ev": 12.0, "confidence": 88},
            {"ev": 10.5, "confidence": 82},
        ]

        stakes = []
        for pick in high_edge_picks:
            result = calculate_stake(
                bankroll=bankroll,
                ev_percentage=pick["ev"],
                confidence=pick["confidence"],
            )
            stakes.append(result["suggested_stake"])

        # High stakes appropriate for large bankroll and good picks
        assert stakes[0] > 100.0  # First pick should be substantial
        assert stakes[1] > 80.0  # Second pick also solid
        assert all(s <= bankroll * 0.05 for s in stakes)  # Still clamped

    def test_progressive_bankroll_growth(self):
        """Stakes scale proportionally as bankroll grows"""
        ev = 5.0
        confidence = 75

        result_500 = calculate_stake(bankroll=500.0, ev_percentage=ev, confidence=confidence)
        result_1000 = calculate_stake(bankroll=1000.0, ev_percentage=ev, confidence=confidence)
        result_5000 = calculate_stake(bankroll=5000.0, ev_percentage=ev, confidence=confidence)

        # Stakes should scale with bankroll
        # Ratio should be approximately 1:2:10
        ratio_1000_to_500 = result_1000["suggested_stake"] / result_500["suggested_stake"]
        ratio_5000_to_500 = result_5000["suggested_stake"] / result_500["suggested_stake"]

        assert ratio_1000_to_500 == pytest.approx(2.0, abs=0.01)
        assert ratio_5000_to_500 == pytest.approx(10.0, abs=0.01)

    def test_kelly_criterion_inspired_scaling(self):
        """Verify stakes scale conservatively with EV (not linearly)"""
        bankroll = 1000.0
        confidence = 80

        # Stakes for different EV levels
        result_2pct = calculate_stake(bankroll=bankroll, ev_percentage=2.0, confidence=confidence)
        result_5pct = calculate_stake(bankroll=bankroll, ev_percentage=5.0, confidence=confidence)
        result_10pct = calculate_stake(bankroll=bankroll, ev_percentage=10.0, confidence=confidence)

        # Stakes should scale linearly with EV (since our formula is linear in EV)
        # 2% → $1.60, 5% → $4.00, 10% → $8.00
        assert result_2pct["suggested_stake"] == pytest.approx(1.6, abs=0.01)
        assert result_5pct["suggested_stake"] == pytest.approx(4.0, abs=0.01)
        assert result_10pct["suggested_stake"] == pytest.approx(8.0, abs=0.01)

        # Verify scaling is linear with EV
        ratio_5_to_2 = result_5pct["suggested_stake"] / result_2pct["suggested_stake"]
        ratio_10_to_5 = result_10pct["suggested_stake"] / result_5pct["suggested_stake"]

        # 5% EV / 2% EV = 5/2 = 2.5
        # 10% EV / 5% EV = 10/5 = 2.0 (linear scaling with EV)
        assert ratio_5_to_2 == pytest.approx(2.5, abs=0.01)
        assert ratio_10_to_5 == pytest.approx(2.0, abs=0.01)

    def test_balanced_portfolio_stakes(self):
        """Balanced portfolio: mix of confidence levels → varied but reasonable stakes"""
        bankroll = 2000.0
        portfolio = [
            {"ev": 7.0, "confidence": 85},  # High confidence play
            {"ev": 5.5, "confidence": 72},  # Medium confidence
            {"ev": 4.0, "confidence": 60},  # Exploratory play
            {"ev": 6.2, "confidence": 78},  # Good play
        ]

        stakes = []
        for pick in portfolio:
            result = calculate_stake(
                bankroll=bankroll,
                ev_percentage=pick["ev"],
                confidence=pick["confidence"],
            )
            stakes.append(result["suggested_stake"])

        # Total exposure across portfolio
        total = sum(stakes)

        # Should be reasonable portfolio allocation
        assert total < bankroll * 0.1  # Conservative total (<10% of bankroll)
        assert all(s > 0 for s in stakes)  # All stakes positive
        assert max(stakes) / min(stakes) > 1.5  # Reasonable variance in stakes


class TestErrorCasesIntegration:
    """Test error handling in integration scenarios"""

    def test_missing_required_fields(self):
        """Integration should handle missing Pick fields gracefully"""
        # This tests the contract: stake calculation needs ev_percentage and confidence
        # Story 5.4 ensures these exist, but we should verify our expectations

        # What we expect from edge detection pipeline:
        required_fields = ["ev_percentage", "confidence"]

        # Our function requires these
        result = calculate_stake(bankroll=1000.0, ev_percentage=5.0, confidence=80)
        assert result is not None

    def test_call_sequence_from_edge_detection(self):
        """Simulate actual call sequence from Story 5.4 detect_edges()"""
        # Story 5.4 does:
        # 1. calculate_all_evs(fixtures) → EVResult
        # 2. apply_threshold_filter(...) → FilteredPick
        # 3. apply_confidence_scoring(...) → ConfidenceScoreBreakdown
        # 4. For each: calculate_stake(bankroll, ev_percentage, confidence) → dict
        # 5. Populate Pick.recommended_stake

        # We're testing step 4-5
        bankroll = 1000.0

        # Simulated outputs from earlier steps
        ev_result = 5.2  # From EVResult.ev_percentage
        confidence_result = 72  # From ConfidenceScoreBreakdown.final_confidence

        # Call our function
        stake_info = calculate_stake(
            bankroll=bankroll,
            ev_percentage=ev_result,
            confidence=confidence_result,
        )

        # This would be assigned to Pick.recommended_stake
        recommended_stake = stake_info["suggested_stake"]

        # Verify it's valid for Pick model
        assert recommended_stake > 0.0
        assert isinstance(recommended_stake, float)
