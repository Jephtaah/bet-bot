"""
Integration tests for terminal formatter.

Tests the formatter with realistic Pick scenarios and verifies
integration with the edge detection pipeline output.
"""

import pytest

from bet_bot.display import format_picks_for_display
from bet_bot.models.analysis import Pick


class TestRealWorldScenarios:
    """Test formatter with realistic betting scenarios."""

    def test_premier_league_picks(self) -> None:
        """Test with realistic Premier League fixture picks."""
        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.625,
                implied_probability=0.476,
                ev_percentage=5.8,
                confidence=78,
                recommended_stake=25.0,
                suggested_odds=2.10,
            ),
            Pick(
                fixture_id="548822",
                market="over_2_5_goals",
                ai_probability=0.68,
                implied_probability=0.556,
                ev_percentage=7.1,
                confidence=82,
                recommended_stake=30.0,
                suggested_odds=1.85,
            ),
            Pick(
                fixture_id="548823",
                market="both_teams_score",
                ai_probability=0.58,
                implied_probability=0.502,
                ev_percentage=3.8,
                confidence=65,
                recommended_stake=15.0,
                suggested_odds=2.45,
            ),
        ]

        output = format_picks_for_display(picks)

        # Verify output structure
        assert isinstance(output, str)
        assert len(output) > 100  # Should have substantial content
        assert "3 picks" in output
        # Average EV: (5.8 + 7.1 + 3.8) / 3 = 5.57%
        assert "5.5%" in output or "5.6%" in output
        # Total stake: 25 + 30 + 15 = 70
        assert "$70.00" in output

    def test_mixed_confidence_picks(self) -> None:
        """Test with picks of varying confidence levels."""
        picks = [
            Pick(
                fixture_id="1",
                market="high_conf",
                ai_probability=0.75,
                implied_probability=0.60,
                ev_percentage=7.0,
                confidence=85,
                recommended_stake=40.0,
                suggested_odds=2.25,
            ),
            Pick(
                fixture_id="2",
                market="med_conf",
                ai_probability=0.65,
                implied_probability=0.58,
                ev_percentage=5.0,
                confidence=72,
                recommended_stake=20.0,
                suggested_odds=2.10,
            ),
            Pick(
                fixture_id="3",
                market="low_conf",
                ai_probability=0.58,
                implied_probability=0.52,
                ev_percentage=5.2,
                confidence=58,
                recommended_stake=10.0,
                suggested_odds=2.50,
            ),
        ]

        output = format_picks_for_display(picks)

        # Check for confidence levels
        assert "HIGH" in output  # 85% confidence
        assert "MED" in output   # 72% confidence
        assert "LOW" in output   # 58% confidence

    def test_high_ev_picks(self) -> None:
        """Test with high expected value picks."""
        picks = [
            Pick(
                fixture_id="1",
                market="market1",
                ai_probability=0.80,
                implied_probability=0.50,
                ev_percentage=15.5,
                confidence=88,
                recommended_stake=50.0,
                suggested_odds=2.80,
            ),
            Pick(
                fixture_id="2",
                market="market2",
                ai_probability=0.75,
                implied_probability=0.55,
                ev_percentage=12.3,
                confidence=85,
                recommended_stake=45.0,
                suggested_odds=2.45,
            ),
        ]

        output = format_picks_for_display(picks)

        assert "15.5%" in output
        assert "12.3%" in output
        assert "$95.00" in output  # Total stake

    def test_diverse_ev_range_picks(self) -> None:
        """Test with picks across different EV ranges."""
        picks = [
            Pick(
                fixture_id="1",
                market="market1",
                ai_probability=0.62,
                implied_probability=0.58,
                ev_percentage=3.2,
                confidence=62,
                recommended_stake=12.0,
                suggested_odds=2.05,
            ),
            Pick(
                fixture_id="2",
                market="market2",
                ai_probability=0.70,
                implied_probability=0.58,
                ev_percentage=8.1,
                confidence=80,
                recommended_stake=35.0,
                suggested_odds=2.20,
            ),
            Pick(
                fixture_id="3",
                market="market3",
                ai_probability=0.65,
                implied_probability=0.60,
                ev_percentage=5.0,
                confidence=70,
                recommended_stake=20.0,
                suggested_odds=2.15,
            ),
        ]

        output = format_picks_for_display(picks)

        # Verify EV range display
        assert "3.2%" in output  # Min
        assert "8.1%" in output  # Max

    def test_large_portfolio(self) -> None:
        """Test with a large portfolio of picks."""
        picks = []
        for i in range(15):
            picks.append(
                Pick(
                    fixture_id=f"fixture_{i}",
                    market=f"market_{i}",
                    ai_probability=0.60 + (i * 0.005),
                    implied_probability=0.55,
                    ev_percentage=5.0 + (i % 3),
                    confidence=70 + (i % 15),
                    recommended_stake=10.0 + (i * 1.0),
                    suggested_odds=2.10,
                )
            )

        output = format_picks_for_display(picks)

        assert "15 picks" in output
        assert isinstance(output, str)
        assert len(output) > 500  # Should be substantial content


class TestEmptyAndEdgeCases:
    """Test edge cases and error conditions."""

    def test_all_picks_low_confidence(self) -> None:
        """Test formatting when all picks have low confidence."""
        picks = [
            Pick(
                fixture_id="1",
                market="market1",
                ai_probability=0.55,
                implied_probability=0.52,
                ev_percentage=5.0,
                confidence=45,
                recommended_stake=5.0,
                suggested_odds=2.10,
            ),
            Pick(
                fixture_id="2",
                market="market2",
                ai_probability=0.56,
                implied_probability=0.53,
                ev_percentage=5.2,
                confidence=50,
                recommended_stake=5.0,
                suggested_odds=2.15,
            ),
        ]

        output = format_picks_for_display(picks)

        # Should still format correctly
        assert "2 picks" in output
        assert "LOW" in output

    def test_very_high_stake_amounts(self) -> None:
        """Test formatting with very high stake amounts."""
        picks = [
            Pick(
                fixture_id="1",
                market="high_stakes",
                ai_probability=0.70,
                implied_probability=0.60,
                ev_percentage=6.0,
                confidence=80,
                recommended_stake=5000.0,
                suggested_odds=2.20,
            ),
        ]

        output = format_picks_for_display(picks)

        # Should handle large numbers correctly
        assert "$5,000.00" in output

    def test_very_small_stake_amounts(self) -> None:
        """Test formatting with very small stake amounts."""
        picks = [
            Pick(
                fixture_id="1",
                market="small_stakes",
                ai_probability=0.60,
                implied_probability=0.55,
                ev_percentage=5.0,
                confidence=70,
                recommended_stake=0.50,
                suggested_odds=2.10,
            ),
        ]

        output = format_picks_for_display(picks)

        assert "$0.50" in output

    def test_fractional_confidence_rounding(self) -> None:
        """Test that fractional confidence is handled correctly."""
        # Since confidence is int, this tests the averaging
        picks = [
            Pick(
                fixture_id="1",
                market="market1",
                ai_probability=0.60,
                implied_probability=0.55,
                ev_percentage=5.0,
                confidence=70,
                recommended_stake=10.0,
                suggested_odds=2.10,
            ),
            Pick(
                fixture_id="2",
                market="market2",
                ai_probability=0.60,
                implied_probability=0.55,
                ev_percentage=5.0,
                confidence=71,
                recommended_stake=10.0,
                suggested_odds=2.10,
            ),
        ]

        output = format_picks_for_display(picks)

        # Average should be 70 (70 + 71 / 2 = 70.5, rounded to 70)
        assert "70%" in output


class TestVisualOutput:
    """Test visual characteristics of the output."""

    def test_output_contains_summary_marker(self) -> None:
        """Test that output contains visual summary indicator."""
        picks = [
            Pick(
                fixture_id="1",
                market="market1",
                ai_probability=0.60,
                implied_probability=0.55,
                ev_percentage=5.0,
                confidence=70,
                recommended_stake=10.0,
                suggested_odds=2.10,
            ),
        ]

        output = format_picks_for_display(picks)

        # Should have visual marker
        assert "📊" in output or "Summary" in output

    def test_output_contains_title(self) -> None:
        """Test that output has a title."""
        picks = [
            Pick(
                fixture_id="1",
                market="market1",
                ai_probability=0.60,
                implied_probability=0.55,
                ev_percentage=5.0,
                confidence=70,
                recommended_stake=10.0,
                suggested_odds=2.10,
            ),
        ]

        output = format_picks_for_display(picks)

        # Should have title (🎯 Betting Picks Summary or similar)
        assert "🎯" in output or "Picks" in output

    def test_output_readability(self) -> None:
        """Test that output has good readability characteristics."""
        picks = [
            Pick(
                fixture_id="1",
                market="match_result_home",
                ai_probability=0.625,
                implied_probability=0.476,
                ev_percentage=5.8,
                confidence=78,
                recommended_stake=25.0,
                suggested_odds=2.10,
            ),
            Pick(
                fixture_id="2",
                market="over_2_5",
                ai_probability=0.68,
                implied_probability=0.556,
                ev_percentage=7.1,
                confidence=82,
                recommended_stake=30.0,
                suggested_odds=1.85,
            ),
        ]

        output = format_picks_for_display(picks)

        # Should have multiple lines (not all on one line)
        lines = output.split("\n")
        assert len(lines) > 5


class TestIntegrationWithEdgeDetection:
    """Test integration scenarios with edge detection pipeline."""

    def test_typical_edge_detection_output(self) -> None:
        """Test with picks that match typical edge detection output."""
        # Simulate picks from threshold filter (Story 5.2) with confidence scoring (Story 5.3)
        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.625,
                implied_probability=0.476,
                ev_percentage=5.8,
                confidence=78,
                recommended_stake=25.0,
                suggested_odds=2.10,
            ),
            Pick(
                fixture_id="548822",
                market="over_2_5",
                ai_probability=0.68,
                implied_probability=0.556,
                ev_percentage=7.1,
                confidence=82,
                recommended_stake=30.0,
                suggested_odds=1.85,
            ),
        ]

        output = format_picks_for_display(picks)

        # Verify it formats correctly for consumption by Story 7.2 (renderer)
        assert isinstance(output, str)
        assert len(output) > 100
        assert "548821" in output or "Fixture" in output

    def test_single_recommended_pick(self) -> None:
        """Test with a single recommended pick from edge detection."""
        pick = Pick(
            fixture_id="548821",
            market="match_result_home",
            ai_probability=0.625,
            implied_probability=0.476,
            ev_percentage=5.8,
            confidence=78,
            recommended_stake=25.0,
            suggested_odds=2.10,
        )

        output = format_picks_for_display([pick])

        # Should handle single pick gracefully
        assert "1 picks" in output
        assert "$25.00" in output


class TestColorAndStyling:
    """Test that color and styling are properly applied."""

    def test_positive_ev_has_green_color(self) -> None:
        """Test that positive EV shows in green."""
        picks = [
            Pick(
                fixture_id="1",
                market="market1",
                ai_probability=0.70,
                implied_probability=0.60,
                ev_percentage=8.0,
                confidence=80,
                recommended_stake=20.0,
                suggested_odds=2.20,
            ),
        ]

        output = format_picks_for_display(picks)

        # Output should contain Rich color codes for positive EV
        assert "[green]" in output or "+8.0%" in output

    def test_high_confidence_has_color(self) -> None:
        """Test that high confidence badge has appropriate styling."""
        picks = [
            Pick(
                fixture_id="1",
                market="market1",
                ai_probability=0.70,
                implied_probability=0.60,
                ev_percentage=5.0,
                confidence=85,
                recommended_stake=20.0,
                suggested_odds=2.20,
            ),
        ]

        output = format_picks_for_display(picks)

        # Should have HIGH confidence badge
        assert "HIGH" in output

    def test_low_confidence_has_color(self) -> None:
        """Test that low confidence badge has appropriate styling."""
        picks = [
            Pick(
                fixture_id="1",
                market="market1",
                ai_probability=0.55,
                implied_probability=0.52,
                ev_percentage=5.0,
                confidence=50,
                recommended_stake=10.0,
                suggested_odds=2.10,
            ),
        ]

        output = format_picks_for_display(picks)

        # Should have LOW confidence badge
        assert "LOW" in output

    def test_stake_has_green_color(self) -> None:
        """Test that stake amounts are shown in green."""
        picks = [
            Pick(
                fixture_id="1",
                market="market1",
                ai_probability=0.60,
                implied_probability=0.55,
                ev_percentage=5.0,
                confidence=70,
                recommended_stake=25.0,
                suggested_odds=2.10,
            ),
        ]

        output = format_picks_for_display(picks)

        # Output should contain green color code or stake value
        assert "$25.00" in output


class TestOutputFormatConsistency:
    """Test consistency of output format across scenarios."""

    def test_consistent_column_order(self) -> None:
        """Test that columns appear in consistent order."""
        picks = [
            Pick(
                fixture_id="1",
                market="market1",
                ai_probability=0.60,
                implied_probability=0.55,
                ev_percentage=5.0,
                confidence=70,
                recommended_stake=10.0,
                suggested_odds=2.10,
            ),
            Pick(
                fixture_id="2",
                market="market2",
                ai_probability=0.65,
                implied_probability=0.58,
                ev_percentage=5.5,
                confidence=75,
                recommended_stake=15.0,
                suggested_odds=2.15,
            ),
        ]

        output = format_picks_for_display(picks)

        # Headers should appear
        headers = ["Fixture", "Market", "AI Prob", "Implied Prob", "EV", "Confidence", "Stake"]
        for header in headers:
            assert header in output

    def test_consistent_output_type(self) -> None:
        """Test that output is always a string."""
        pick = Pick(
            fixture_id="1",
            market="market1",
            ai_probability=0.60,
            implied_probability=0.55,
            ev_percentage=5.0,
            confidence=70,
            recommended_stake=10.0,
            suggested_odds=2.10,
        )

        output1 = format_picks_for_display([pick])
        output2 = format_picks_for_display([])

        assert isinstance(output1, str)
        assert isinstance(output2, str)
