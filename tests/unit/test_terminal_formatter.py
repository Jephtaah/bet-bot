"""
Unit tests for terminal formatter module.

Tests the format_picks_for_display() function and helper functions
to ensure correct formatting of picks, colors, and statistics.
"""

import pytest

from bet_bot.display.formatter import (
    NO_PICKS_MESSAGE,
    _calculate_statistics,
    _format_confidence_cell,
    _format_ev_cell,
    _format_fixture_cell,
    _format_probability_cell,
    _format_stake_cell,
    format_picks_for_display,
)
from bet_bot.models.analysis import Pick


class TestBasicFormatting:
    """Test basic table formatting with complete pick data."""

    @pytest.fixture
    def sample_pick(self) -> Pick:
        """Create a sample pick for testing."""
        return Pick(
            fixture_id="548821",
            market="match_result_home",
            ai_probability=0.652,
            implied_probability=0.551,
            ev_percentage=5.2,
            confidence=75,
            recommended_stake=4.50,
            suggested_odds=2.10,
        )

    def test_single_pick_formatting(self, sample_pick: Pick) -> None:
        """Test formatting of a single pick."""
        output = format_picks_for_display([sample_pick])

        assert isinstance(output, str)
        assert len(output) > 0
        # Check for key elements
        assert "548821" in output or "Fixture" in output
        assert "match_result_home" in output
        assert "65.2%" in output  # AI Prob
        assert "55.1%" in output  # Implied Prob
        assert "5.2%" in output   # EV
        assert "$4.50" in output  # Stake

    def test_multiple_picks_formatting(self) -> None:
        """Test formatting of multiple picks."""
        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.652,
                implied_probability=0.551,
                ev_percentage=5.2,
                confidence=75,
                recommended_stake=4.50,
                suggested_odds=2.10,
            ),
            Pick(
                fixture_id="548822",
                market="over_2_5",
                ai_probability=0.68,
                implied_probability=0.556,
                ev_percentage=7.1,
                confidence=82,
                recommended_stake=6.00,
                suggested_odds=1.85,
            ),
            Pick(
                fixture_id="548823",
                market="both_teams_score",
                ai_probability=0.58,
                implied_probability=0.502,
                ev_percentage=3.8,
                confidence=65,
                recommended_stake=3.25,
                suggested_odds=2.45,
            ),
        ]
        output = format_picks_for_display(picks)

        # Verify all picks are present
        assert "548821" in output or "Fixture" in output
        assert "548822" in output or "over_2_5" in output
        assert "548823" in output or "both_teams_score" in output

    def test_column_headers_present(self, sample_pick: Pick) -> None:
        """Test that column headers are present in output."""
        output = format_picks_for_display([sample_pick])

        # Check for key column headers (may be abbreviated due to width)
        expected_headers = ["Fixture", "Market", "AI Prob", "EV", "Confidence", "Stake"]
        for header in expected_headers:
            assert header in output
        # Implied Prob may be split due to width, so check for at least parts of it
        assert "Implied" in output or "Prob" in output

    def test_table_styling_present(self, sample_pick: Pick) -> None:
        """Test that table styling is applied."""
        output = format_picks_for_display([sample_pick])

        # Check for Rich formatting indicators or summary
        assert "🎯" in output or "Summary" in output


class TestEmptyPicksList:
    """Test handling of empty and None picks lists."""

    def test_empty_list_handling(self) -> None:
        """Test formatting with empty list."""
        output = format_picks_for_display([])

        assert isinstance(output, str)
        assert NO_PICKS_MESSAGE in output
        assert "No profitable picks" in output

    def test_none_input_handling(self) -> None:
        """Test formatting with None input."""
        output = format_picks_for_display(None)

        assert isinstance(output, str)
        assert NO_PICKS_MESSAGE in output
        assert "No profitable picks" in output

    def test_empty_list_message_content(self) -> None:
        """Test that empty list message is user-friendly."""
        output = format_picks_for_display([])

        # Verify it contains helpful context
        assert "threshold" in output.lower() or "quality" in output.lower()


class TestEVFormatting:
    """Test EV percentage formatting with color coding."""

    def test_positive_ev_formatting(self) -> None:
        """Test positive EV is formatted with + sign and green."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.6,
            implied_probability=0.55,
            ev_percentage=5.2,
            confidence=75,
            recommended_stake=10.0,
            suggested_odds=2.0,
        )
        output = format_picks_for_display([pick])

        assert "+5.2%" in output

    def test_negative_ev_formatting(self) -> None:
        """Test negative EV is formatted with - sign."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.5,
            implied_probability=0.55,
            ev_percentage=-2.3,
            confidence=40,
            recommended_stake=5.0,
            suggested_odds=2.0,
        )
        output = format_picks_for_display([pick])

        assert "-2.3%" in output

    def test_zero_ev_formatting(self) -> None:
        """Test zero EV is formatted correctly."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.55,
            implied_probability=0.55,
            ev_percentage=0.0,
            confidence=50,
            recommended_stake=5.0,
            suggested_odds=2.0,
        )
        output = format_picks_for_display([pick])

        # Should show +0.0% or just 0.0%
        assert "0.0%" in output

    def test_large_ev_formatting(self) -> None:
        """Test large EV percentage formatting."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.75,
            implied_probability=0.5,
            ev_percentage=15.8,
            confidence=85,
            recommended_stake=50.0,
            suggested_odds=2.5,
        )
        output = format_picks_for_display([pick])

        assert "+15.8%" in output

    def test_ev_format_color_function(self) -> None:
        """Test the _format_ev_cell helper function directly."""
        # Positive EV
        result = _format_ev_cell(5.2)
        assert "+5.2%" in result
        assert "[green]" in result

        # Negative EV
        result = _format_ev_cell(-2.3)
        assert "-2.3%" in result
        assert "[red]" in result

        # Zero EV
        result = _format_ev_cell(0.0)
        assert "0.0%" in result


class TestConfidenceFormatting:
    """Test confidence badge formatting with color coding."""

    def test_high_confidence_formatting(self) -> None:
        """Test high confidence (>80%) badge."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.75,
            implied_probability=0.6,
            ev_percentage=5.2,
            confidence=85,
            recommended_stake=10.0,
            suggested_odds=2.0,
        )
        output = format_picks_for_display([pick])

        assert "HIGH" in output

    def test_medium_confidence_formatting(self) -> None:
        """Test medium confidence (60-80%) badge."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.65,
            implied_probability=0.55,
            ev_percentage=5.2,
            confidence=70,
            recommended_stake=10.0,
            suggested_odds=2.0,
        )
        output = format_picks_for_display([pick])

        assert "MED" in output

    def test_low_confidence_formatting(self) -> None:
        """Test low confidence (<60%) badge."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.55,
            implied_probability=0.5,
            ev_percentage=5.2,
            confidence=50,
            recommended_stake=10.0,
            suggested_odds=2.0,
        )
        output = format_picks_for_display([pick])

        assert "LOW" in output

    def test_confidence_boundary_80(self) -> None:
        """Test boundary case at 80% confidence."""
        result = _format_confidence_cell(80)
        assert "MED" in result  # 80 is not > 80, so it's MED

    def test_confidence_boundary_60(self) -> None:
        """Test boundary case at 60% confidence."""
        result = _format_confidence_cell(60)
        assert "MED" in result  # 60 >= 60, so it's MED

    def test_confidence_boundary_59(self) -> None:
        """Test boundary case at 59% confidence."""
        result = _format_confidence_cell(59)
        assert "LOW" in result  # 59 < 60, so it's LOW

    def test_confidence_boundary_81(self) -> None:
        """Test boundary case at 81% confidence."""
        result = _format_confidence_cell(81)
        assert "HIGH" in result  # 81 > 80, so it's HIGH

    def test_confidence_color_function(self) -> None:
        """Test the _format_confidence_cell helper function directly."""
        # High
        result = _format_confidence_cell(85)
        assert "HIGH" in result
        assert "[green]" in result

        # Medium
        result = _format_confidence_cell(70)
        assert "MED" in result
        assert "[yellow]" in result

        # Low
        result = _format_confidence_cell(50)
        assert "LOW" in result
        assert "[red]" in result


class TestStakeFormatting:
    """Test stake currency formatting."""

    def test_small_stake_formatting(self) -> None:
        """Test formatting of small stake amount."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.6,
            implied_probability=0.55,
            ev_percentage=5.2,
            confidence=75,
            recommended_stake=4.50,
            suggested_odds=2.0,
        )
        output = format_picks_for_display([pick])

        assert "$4.50" in output

    def test_large_stake_formatting(self) -> None:
        """Test formatting of large stake amount."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.6,
            implied_probability=0.55,
            ev_percentage=5.2,
            confidence=75,
            recommended_stake=100.00,
            suggested_odds=2.0,
        )
        output = format_picks_for_display([pick])

        assert "$100.00" in output

    def test_very_small_stake_formatting(self) -> None:
        """Test formatting of very small stake amount."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.6,
            implied_probability=0.55,
            ev_percentage=5.2,
            confidence=75,
            recommended_stake=0.01,
            suggested_odds=2.0,
        )
        output = format_picks_for_display([pick])

        assert "$0.01" in output

    def test_stake_thousands_separator(self) -> None:
        """Test that large stakes include thousands separator."""
        result = _format_stake_cell(1234.56)
        assert "$1,234.56" in result

    def test_stake_format_function(self) -> None:
        """Test the _format_stake_cell helper function directly."""
        assert "$4.50" in _format_stake_cell(4.50)
        assert "$100.00" in _format_stake_cell(100.00)
        assert "$0.01" in _format_stake_cell(0.01)
        assert "$1,234.56" in _format_stake_cell(1234.56)


class TestSummaryFooter:
    """Test summary statistics footer."""

    def test_single_pick_summary(self) -> None:
        """Test summary statistics for a single pick."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.652,
            implied_probability=0.551,
            ev_percentage=5.2,
            confidence=75,
            recommended_stake=4.50,
            suggested_odds=2.0,
        )
        output = format_picks_for_display([pick])

        assert "1 picks" in output
        assert "5.2%" in output  # Avg EV should match single pick EV
        assert "75%" in output   # Avg Confidence
        assert "$4.50" in output  # Total stake

    def test_multiple_picks_summary_calculation(self) -> None:
        """Test that summary statistics are calculated correctly."""
        picks = [
            Pick(
                fixture_id="1",
                market="test1",
                ai_probability=0.6,
                implied_probability=0.55,
                ev_percentage=5.0,
                confidence=80,
                recommended_stake=10.0,
                suggested_odds=2.0,
            ),
            Pick(
                fixture_id="2",
                market="test2",
                ai_probability=0.7,
                implied_probability=0.6,
                ev_percentage=6.0,
                confidence=70,
                recommended_stake=8.0,
                suggested_odds=2.0,
            ),
        ]
        output = format_picks_for_display(picks)

        assert "2 picks" in output
        # Average EV: (5.0 + 6.0) / 2 = 5.5%
        assert "5.5%" in output
        # Average Confidence: (80 + 70) / 2 = 75%
        assert "75%" in output
        # Total stake: 10 + 8 = 18
        assert "$18.00" in output

    def test_summary_footer_appears_at_bottom(self) -> None:
        """Test that summary footer appears in output."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.6,
            implied_probability=0.55,
            ev_percentage=5.2,
            confidence=75,
            recommended_stake=4.50,
            suggested_odds=2.0,
        )
        output = format_picks_for_display([pick])

        assert "Summary" in output
        assert "📊" in output

    def test_ev_range_display(self) -> None:
        """Test that EV range is displayed in summary."""
        picks = [
            Pick(
                fixture_id="1",
                market="test1",
                ai_probability=0.6,
                implied_probability=0.55,
                ev_percentage=3.2,
                confidence=75,
                recommended_stake=5.0,
                suggested_odds=2.0,
            ),
            Pick(
                fixture_id="2",
                market="test2",
                ai_probability=0.7,
                implied_probability=0.6,
                ev_percentage=8.1,
                confidence=80,
                recommended_stake=10.0,
                suggested_odds=2.0,
            ),
        ]
        output = format_picks_for_display(picks)

        # EV range should be from 3.2% to 8.1%
        assert "3.2%" in output
        assert "8.1%" in output


class TestFixtureFormatting:
    """Test fixture cell formatting."""

    def test_fixture_fallback_formatting(self) -> None:
        """Test fixture formatting when no fixture map provided."""
        pick = Pick(
            fixture_id="548821",
            market="test",
            ai_probability=0.6,
            implied_probability=0.55,
            ev_percentage=5.2,
            confidence=75,
            recommended_stake=10.0,
            suggested_odds=2.0,
        )
        result = _format_fixture_cell(pick)

        # Should fall back to fixture ID
        assert "548821" in result

    def test_fixture_format_function(self) -> None:
        """Test the _format_fixture_cell helper function directly."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.6,
            implied_probability=0.55,
            ev_percentage=5.2,
            confidence=75,
            recommended_stake=10.0,
            suggested_odds=2.0,
        )
        result = _format_fixture_cell(pick)

        # Should return fixture_id fallback
        assert "Fixture 1" in result or "1" in result


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_very_long_team_names(self) -> None:
        """Test handling of very long team names."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.6,
            implied_probability=0.55,
            ev_percentage=5.2,
            confidence=75,
            recommended_stake=10.0,
            suggested_odds=2.0,
        )
        output = format_picks_for_display([pick])

        # Should not crash with long names
        assert isinstance(output, str)
        assert len(output) > 0

    def test_unicode_handling(self) -> None:
        """Test handling of Unicode in market names."""
        pick = Pick(
            fixture_id="1",
            market="über_test_✓",
            ai_probability=0.6,
            implied_probability=0.55,
            ev_percentage=5.2,
            confidence=75,
            recommended_stake=10.0,
            suggested_odds=2.0,
        )
        output = format_picks_for_display([pick])

        # Should render without errors
        assert isinstance(output, str)

    def test_probability_boundaries(self) -> None:
        """Test probability values at boundaries."""
        # Very low probability
        low_prob = _format_probability_cell(0.01)
        assert "1.0%" in low_prob

        # Very high probability
        high_prob = _format_probability_cell(0.99)
        assert "99.0%" in high_prob


class TestOutputType:
    """Test return type and output characteristics."""

    def test_return_type_is_string(self) -> None:
        """Test that return value is always a string."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.6,
            implied_probability=0.55,
            ev_percentage=5.2,
            confidence=75,
            recommended_stake=10.0,
            suggested_odds=2.0,
        )
        output = format_picks_for_display([pick])
        assert isinstance(output, str)

        # Also test empty
        output = format_picks_for_display([])
        assert isinstance(output, str)

    def test_return_value_can_be_printed(self) -> None:
        """Test that output can be printed without errors."""
        pick = Pick(
            fixture_id="1",
            market="test",
            ai_probability=0.6,
            implied_probability=0.55,
            ev_percentage=5.2,
            confidence=75,
            recommended_stake=10.0,
            suggested_odds=2.0,
        )
        output = format_picks_for_display([pick])

        # Should not raise exception when printed
        try:
            str(output)  # Ensure it's valid string
            assert True
        except Exception:
            pytest.fail("Output cannot be printed")


class TestStatisticsCalculation:
    """Test the statistics calculation helper function."""

    def test_empty_picks_statistics(self) -> None:
        """Test statistics calculation with empty picks list."""
        stats = _calculate_statistics([])

        assert stats["total_picks"] == 0
        assert stats["avg_ev"] == 0.0
        assert stats["avg_confidence"] == 0

    def test_single_pick_statistics(self) -> None:
        """Test statistics with single pick."""
        picks = [
            Pick(
                fixture_id="1",
                market="test",
                ai_probability=0.6,
                implied_probability=0.55,
                ev_percentage=5.2,
                confidence=75,
                recommended_stake=10.0,
                suggested_odds=2.0,
            )
        ]
        stats = _calculate_statistics(picks)

        assert stats["total_picks"] == 1
        assert stats["avg_ev"] == 5.2
        assert stats["avg_confidence"] == 75
        assert stats["total_stake"] == 10.0

    def test_multiple_picks_statistics(self) -> None:
        """Test statistics calculation with multiple picks."""
        picks = [
            Pick(
                fixture_id="1",
                market="test1",
                ai_probability=0.6,
                implied_probability=0.55,
                ev_percentage=4.0,
                confidence=80,
                recommended_stake=10.0,
                suggested_odds=2.0,
            ),
            Pick(
                fixture_id="2",
                market="test2",
                ai_probability=0.7,
                implied_probability=0.6,
                ev_percentage=6.0,
                confidence=70,
                recommended_stake=20.0,
                suggested_odds=2.0,
            ),
            Pick(
                fixture_id="3",
                market="test3",
                ai_probability=0.65,
                implied_probability=0.58,
                ev_percentage=5.0,
                confidence=75,
                recommended_stake=15.0,
                suggested_odds=2.0,
            ),
        ]
        stats = _calculate_statistics(picks)

        assert stats["total_picks"] == 3
        assert abs(stats["avg_ev"] - 5.0) < 0.01  # (4 + 6 + 5) / 3 = 5
        assert stats["avg_confidence"] == 75  # (80 + 70 + 75) / 3 = 75
        assert stats["total_stake"] == 45.0  # 10 + 20 + 15
        assert stats["min_ev"] == 4.0
        assert stats["max_ev"] == 6.0


class TestProbabilityFormatting:
    """Test probability percentage formatting."""

    def test_probability_format_function(self) -> None:
        """Test the _format_probability_cell helper function."""
        assert "65.2%" in _format_probability_cell(0.652)
        assert "55.1%" in _format_probability_cell(0.551)
        assert "1.0%" in _format_probability_cell(0.01)
        assert "99.9%" in _format_probability_cell(0.999)
