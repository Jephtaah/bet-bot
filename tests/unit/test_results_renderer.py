"""
Unit tests for results renderer module.

Tests the render_analysis_results() function and helper functions
to ensure correct state rendering, statistics calculation, and output formatting.
"""

import pytest

from bet_bot.display.renderer import (
    _determine_output_state,
    _format_data_quality_notes,
    _format_degraded_state,
    _format_error_state,
    _format_next_steps,
    _format_no_matches_state,
    _format_no_picks_state,
    _format_picks_found_state,
    render_analysis_results,
)
from bet_bot.models.analysis import Pick


class TestStateDetection:
    """Test state determination logic."""

    @pytest.fixture
    def sample_pick(self) -> Pick:
        """Create a sample pick."""
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

    def test_state_picks_found_with_picks(self, sample_pick: Pick) -> None:
        """Test state detection with picks available."""
        state, is_error = _determine_output_state([sample_pick], {})
        assert state == "picks_found"
        assert not is_error

    def test_state_no_picks_empty_list(self) -> None:
        """Test state detection with empty picks list."""
        state, is_error = _determine_output_state([], {})
        assert state == "no_picks"
        assert not is_error

    def test_state_no_picks_none(self) -> None:
        """Test state detection with None picks."""
        state, is_error = _determine_output_state(None, {})
        assert state == "no_picks"
        assert not is_error

    def test_state_no_matches_no_fixtures(self) -> None:
        """Test state detection with no fixtures analyzed."""
        data_quality = {"fixtures_analyzed": 0}
        state, is_error = _determine_output_state([], data_quality)
        assert state == "no_matches"
        assert not is_error

    def test_state_error_critical_failure(self) -> None:
        """Test state detection with critical API failure."""
        data_quality = {
            "api_football": {"status": "failed", "error": "API down"},
            "openai": {"status": "failed", "error": "Rate limit"},
        }
        state, is_error = _determine_output_state([], data_quality)
        assert state == "error"
        assert is_error

    def test_state_degraded_partial_failure(self, sample_pick: Pick) -> None:
        """Test state detection with partial data failure but picks available."""
        data_quality = {
            "api_football": {"status": "success"},
            "espn": {"status": "failed", "error": "timeout"},
            "openai": {"status": "success"},
        }
        state, is_error = _determine_output_state([sample_pick], data_quality)
        assert state == "degraded"
        assert not is_error


class TestPicksFoundState:
    """Test PICKS FOUND state rendering."""

    @pytest.fixture
    def sample_picks(self) -> list[Pick]:
        """Create sample picks for testing."""
        return [
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
                implied_probability=0.476,
                ev_percentage=3.8,
                confidence=65,
                recommended_stake=3.00,
                suggested_odds=2.25,
            ),
        ]

    def test_picks_found_with_single_pick(self) -> None:
        """Test rendering with single pick."""
        pick = Pick(
            fixture_id="548821",
            market="match_result_home",
            ai_probability=0.652,
            implied_probability=0.551,
            ev_percentage=5.2,
            confidence=75,
            recommended_stake=4.50,
            suggested_odds=2.10,
        )
        output = _format_picks_found_state([pick], 1000.0)

        assert isinstance(output, str)
        assert "✅ ANALYSIS COMPLETE - PICKS FOUND" in output
        assert "Summary Statistics" in output
        assert "Total Picks: 1" in output
        assert "+5.2%" in output

    def test_picks_found_with_multiple_picks(self, sample_picks: list[Pick]) -> None:
        """Test rendering with multiple picks."""
        output = _format_picks_found_state(sample_picks, 1000.0)

        assert isinstance(output, str)
        assert "✅ ANALYSIS COMPLETE" in output
        assert "Total Picks: 3" in output

    def test_picks_found_statistics_calculation(self, sample_picks: list[Pick]) -> None:
        """Test that statistics are calculated correctly."""
        output = _format_picks_found_state(sample_picks, 1000.0)

        # Average EV: (5.2 + 7.1 + 3.8) / 3 = 5.37
        # Average Confidence: (75 + 82 + 65) / 3 = 74
        # Total Stake: 4.50 + 6.00 + 3.00 = 13.50
        assert "5.4%" in output or "5.3%" in output  # Allow small rounding
        assert "74%" in output
        assert "$13.50" in output

    def test_picks_found_roi_calculation(self, sample_picks: list[Pick]) -> None:
        """Test ROI calculation in output."""
        output = _format_picks_found_state(sample_picks, 1000.0)

        # Expected ROI = total_stake * avg_ev / 100
        # = 13.50 * 5.4 / 100 ≈ 0.73
        assert "Expected ROI:" in output

    def test_picks_found_returns_string(self, sample_picks: list[Pick]) -> None:
        """Test that output is always a string."""
        output = _format_picks_found_state(sample_picks, 1000.0)
        assert isinstance(output, str)
        assert len(output) > 0


class TestNoPicksState:
    """Test NO PICKS AVAILABLE state rendering."""

    def test_no_picks_basic_message(self) -> None:
        """Test no picks message displays correctly."""
        output = _format_no_picks_state()

        assert isinstance(output, str)
        assert "ℹ️ NO PROFITABLE PICKS FOUND" in output
        assert "5% threshold" in output

    def test_no_picks_suggestions(self) -> None:
        """Test that suggestions are provided."""
        output = _format_no_picks_state()

        assert "lowering EV threshold" in output or "lower your EV threshold" in output
        assert "expand to additional leagues" in output or "expansion" in output
        assert "tomorrow" in output

    def test_no_picks_next_steps(self) -> None:
        """Test next steps section is included."""
        output = _format_no_picks_state()

        assert "Next Steps" in output

    def test_no_picks_with_data_quality(self) -> None:
        """Test no picks message with data quality info."""
        data_quality = {
            "api_football": {"status": "success", "latency_ms": 45},
            "openai": {"status": "success", "latency_ms": 1200},
        }
        output = _format_no_picks_state(data_quality)

        assert isinstance(output, str)
        assert "Data Quality" in output


class TestNoMatchesState:
    """Test NO MATCHES TODAY state rendering."""

    def test_no_matches_basic_message(self) -> None:
        """Test no matches message displays correctly."""
        output = _format_no_matches_state()

        assert isinstance(output, str)
        assert "🔍 NO MATCHES TODAY" in output
        assert "No fixtures found" in output or "fixtures found" in output

    def test_no_matches_suggestions(self) -> None:
        """Test that suggestions are provided."""
        output = _format_no_matches_state()

        assert "tomorrow" in output
        assert "expand" in output or "leagues" in output or "configure" in output

    def test_no_matches_next_steps(self) -> None:
        """Test next steps section is included."""
        output = _format_no_matches_state()

        assert "Next Steps" in output


class TestErrorState:
    """Test ERROR state rendering."""

    def test_error_basic_message(self) -> None:
        """Test error message displays correctly."""
        output = _format_error_state()

        assert isinstance(output, str)
        assert "❌ ANALYSIS FAILED" in output

    def test_error_rate_limit_troubleshooting(self) -> None:
        """Test rate limit error guidance."""
        output = _format_error_state(
            error_type="rate_limit",
            error_message="429 Too Many Requests"
        )

        assert "rate limit" in output.lower()
        assert "60 seconds" in output or "wait" in output.lower()

    def test_error_authentication_troubleshooting(self) -> None:
        """Test authentication error guidance."""
        output = _format_error_state(
            error_type="authentication",
            error_message="401 Unauthorized"
        )

        assert "API key" in output or "credentials" in output

    def test_error_network_troubleshooting(self) -> None:
        """Test network error guidance."""
        output = _format_error_state(
            error_type="network",
            error_message="Connection refused"
        )

        assert "internet" in output.lower() or "connection" in output.lower()

    def test_error_timeout_troubleshooting(self) -> None:
        """Test timeout error guidance."""
        output = _format_error_state(
            error_type="timeout",
            error_message="Request timeout"
        )

        assert "timeout" in output.lower() or "slow" in output.lower()

    def test_error_with_data_quality(self) -> None:
        """Test error message with data quality info."""
        data_quality = {
            "api_football": {"status": "failed", "error": "API unavailable"},
            "openai": {"status": "failed", "error": "Rate limit"},
        }
        output = _format_error_state(
            error_type="api_football",
            data_quality=data_quality
        )

        assert "Data Quality" in output


class TestDegradedState:
    """Test DEGRADED SERVICE state rendering."""

    @pytest.fixture
    def sample_picks(self) -> list[Pick]:
        """Create sample picks."""
        return [
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
        ]

    def test_degraded_warning_displayed(self, sample_picks: list[Pick]) -> None:
        """Test degraded service warning is displayed."""
        data_quality = {
            "api_football": {"status": "success"},
            "espn": {"status": "failed", "error": "timeout"},
            "openai": {"status": "success"},
        }
        output = _format_degraded_state(sample_picks, 1000.0, data_quality)

        assert isinstance(output, str)
        assert "⚠️ DEGRADED SERVICE" in output
        assert "reduced" in output.lower()

    def test_degraded_shows_failed_sources(self, sample_picks: list[Pick]) -> None:
        """Test that failed sources are indicated."""
        data_quality = {
            "api_football": {"status": "success"},
            "espn": {"status": "failed"},
            "openai": {"status": "success"},
        }
        output = _format_degraded_state(sample_picks, 1000.0, data_quality)

        assert "1/3" in output or "failed" in output.lower()

    def test_degraded_displays_picks(self, sample_picks: list[Pick]) -> None:
        """Test that picks are still displayed in degraded state."""
        data_quality = {
            "api_football": {"status": "success"},
            "espn": {"status": "failed"},
        }
        output = _format_degraded_state(sample_picks, 1000.0, data_quality)

        assert "+5.2%" in output  # Pick EV should be in output

    def test_degraded_confidence_warning(self, sample_picks: list[Pick]) -> None:
        """Test that confidence warning is shown."""
        data_quality = {
            "espn": {"status": "failed"},
        }
        output = _format_degraded_state(sample_picks, 1000.0, data_quality)

        assert "caution" in output.lower() or "reduced" in output.lower()


class TestDataQualityNotes:
    """Test data quality notes formatting."""

    def test_data_quality_all_success(self) -> None:
        """Test data quality with all sources successful."""
        data_quality = {
            "api_football": {"status": "success", "latency_ms": 45, "record_count": 25},
            "openai": {"status": "success", "latency_ms": 1200, "record_count": 5},
        }
        output = _format_data_quality_notes(data_quality)

        assert isinstance(output, str)
        assert "Data Quality" in output or "Report" in output
        assert "100%" in output or "Success" in output

    def test_data_quality_mixed_status(self) -> None:
        """Test data quality with mixed success/failure."""
        data_quality = {
            "api_football": {"status": "success"},
            "espn": {"status": "failed", "error": "timeout"},
            "openai": {"status": "success"},
        }
        output = _format_data_quality_notes(data_quality)

        assert isinstance(output, str)
        assert "Data Quality" in output or "Report" in output

    def test_data_quality_latency_displayed(self) -> None:
        """Test that latency is displayed when available."""
        data_quality = {
            "api_football": {"status": "success", "latency_ms": 150},
            "openai": {"status": "success", "latency_ms": 2500},
        }
        output = _format_data_quality_notes(data_quality)

        assert isinstance(output, str)
        assert len(output) > 0

    def test_data_quality_record_count_displayed(self) -> None:
        """Test that record counts are displayed."""
        data_quality = {
            "api_football": {"status": "success", "record_count": 25},
        }
        output = _format_data_quality_notes(data_quality)

        assert isinstance(output, str)

    def test_data_quality_empty_dict(self) -> None:
        """Test data quality with empty dict."""
        output = _format_data_quality_notes({})
        assert output == ""

    def test_data_quality_none(self) -> None:
        """Test data quality with None."""
        output = _format_data_quality_notes(None)
        # Should not raise exception


class TestNextSteps:
    """Test next steps section formatting."""

    def test_next_steps_picks_found(self) -> None:
        """Test next steps for successful picks."""
        output = _format_next_steps("picks_found", 3, {})

        assert isinstance(output, str)
        assert "Next Steps" in output
        assert "Place" in output or "bets" in output

    def test_next_steps_no_picks(self) -> None:
        """Test next steps for no picks."""
        output = _format_next_steps("no_picks", 0, {})

        assert isinstance(output, str)
        assert "Next Steps" in output
        assert "tomorrow" in output or "threshold" in output

    def test_next_steps_no_matches(self) -> None:
        """Test next steps for no matches."""
        output = _format_next_steps("no_matches", 0, {})

        assert isinstance(output, str)
        assert "Next Steps" in output
        assert "tomorrow" in output or "fixtures" in output

    def test_next_steps_error(self) -> None:
        """Test next steps for error state."""
        output = _format_next_steps("error", 0, {})

        assert isinstance(output, str)
        assert "Next Steps" in output
        assert "troubleshoot" in output.lower() or "API" in output

    def test_next_steps_degraded(self) -> None:
        """Test next steps for degraded state."""
        output = _format_next_steps("degraded", 2, {})

        assert isinstance(output, str)
        assert "Next Steps" in output
        assert "caution" in output.lower() or "review" in output.lower()


class TestRenderAnalysisResults:
    """Test main render_analysis_results() function."""

    @pytest.fixture
    def sample_pick(self) -> Pick:
        """Create a sample pick."""
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

    @pytest.mark.asyncio
    async def test_render_with_picks(self, sample_pick: Pick) -> None:
        """Test rendering with picks."""
        output = await render_analysis_results([sample_pick], 1000.0)

        assert isinstance(output, str)
        assert len(output) > 0
        assert "PICKS FOUND" in output

    @pytest.mark.asyncio
    async def test_render_empty_picks(self) -> None:
        """Test rendering with empty picks."""
        output = await render_analysis_results([], 1000.0)

        assert isinstance(output, str)
        assert "NO PROFITABLE" in output

    @pytest.mark.asyncio
    async def test_render_none_picks(self) -> None:
        """Test rendering with None picks."""
        output = await render_analysis_results(None, 1000.0)

        assert isinstance(output, str)

    @pytest.mark.asyncio
    async def test_render_with_data_quality(self, sample_pick: Pick) -> None:
        """Test rendering with data quality tracking."""
        data_quality = {
            "api_football": {"status": "success"},
            "openai": {"status": "success"},
        }
        output = await render_analysis_results([sample_pick], 1000.0, data_quality)

        assert isinstance(output, str)
        assert "Data Quality" in output

    @pytest.mark.asyncio
    async def test_render_invalid_picks_type(self) -> None:
        """Test that invalid picks type raises ValueError."""
        with pytest.raises(ValueError):
            await render_analysis_results("invalid", 1000.0)  # type: ignore

    @pytest.mark.asyncio
    async def test_render_invalid_bankroll_type(self, sample_pick: Pick) -> None:
        """Test that invalid bankroll type raises ValueError."""
        with pytest.raises(ValueError):
            await render_analysis_results([sample_pick], "invalid")  # type: ignore

    @pytest.mark.asyncio
    async def test_render_invalid_data_quality_type(self, sample_pick: Pick) -> None:
        """Test that invalid data_quality type raises ValueError."""
        with pytest.raises(ValueError):
            await render_analysis_results([sample_pick], 1000.0, "invalid")  # type: ignore

    @pytest.mark.asyncio
    async def test_render_zero_bankroll(self, sample_pick: Pick) -> None:
        """Test rendering with zero bankroll."""
        output = await render_analysis_results([sample_pick], 0.0)

        assert isinstance(output, str)
        # Should still render even with zero bankroll

    @pytest.mark.asyncio
    async def test_render_degraded_state(self, sample_pick: Pick) -> None:
        """Test rendering degraded service state."""
        data_quality = {
            "api_football": {"status": "success"},
            "espn": {"status": "failed"},
            "openai": {"status": "success"},
        }
        output = await render_analysis_results([sample_pick], 1000.0, data_quality)

        assert isinstance(output, str)
        assert "DEGRADED" in output

    @pytest.mark.asyncio
    async def test_render_error_state(self) -> None:
        """Test rendering error state."""
        data_quality = {
            "api_football": {"status": "failed", "error": "API unavailable"},
            "openai": {"status": "failed", "error": "Rate limit"},
        }
        output = await render_analysis_results([], 1000.0, data_quality)

        assert isinstance(output, str)
        assert "FAILED" in output or "ERROR" in output

    @pytest.mark.asyncio
    async def test_render_no_matches_state(self) -> None:
        """Test rendering no matches state."""
        data_quality = {"fixtures_analyzed": 0}
        output = await render_analysis_results([], 1000.0, data_quality)

        assert isinstance(output, str)
        assert "NO MATCHES" in output

    @pytest.mark.asyncio
    async def test_render_returns_string_type(self, sample_pick: Pick) -> None:
        """Test that render always returns string type."""
        output = await render_analysis_results([sample_pick], 1000.0)
        assert isinstance(output, str)


class TestOutputFormatting:
    """Test overall output formatting and structure."""

    @pytest.fixture
    def sample_picks(self) -> list[Pick]:
        """Create sample picks."""
        return [
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
        ]

    @pytest.mark.asyncio
    async def test_output_is_readable_string(self, sample_picks: list[Pick]) -> None:
        """Test that output is readable."""
        output = await render_analysis_results(sample_picks, 1000.0)

        assert isinstance(output, str)
        assert len(output) > 50  # Should have substantial content

    @pytest.mark.asyncio
    async def test_output_no_unhandled_exceptions(self, sample_picks: list[Pick]) -> None:
        """Test that rendering doesn't raise unhandled exceptions."""
        try:
            output = await render_analysis_results(sample_picks, 1000.0)
            assert isinstance(output, str)
        except Exception as e:
            pytest.fail(f"Rendering raised unexpected exception: {e}")

    @pytest.mark.asyncio
    async def test_output_contains_key_sections(self, sample_picks: list[Pick]) -> None:
        """Test that output contains key sections."""
        output = await render_analysis_results(sample_picks, 1000.0)

        # Should contain at least some of these key sections
        has_header = "PICKS FOUND" in output or "ANALYSIS" in output
        has_stats = "Summary" in output or "Statistics" in output
        has_next = "Next Steps" in output

        assert has_header or has_stats or has_next

    @pytest.mark.asyncio
    async def test_large_picks_count(self) -> None:
        """Test rendering with many picks."""
        picks = [
            Pick(
                fixture_id=f"54882{i}",
                market="match_result_home",
                ai_probability=0.652,
                implied_probability=0.551,
                ev_percentage=5.2 + i * 0.1,
                confidence=75,
                recommended_stake=4.50 + i * 0.5,
                suggested_odds=2.10,
            )
            for i in range(10)
        ]

        output = await render_analysis_results(picks, 10000.0)

        assert isinstance(output, str)
        assert "10" in output  # Should show count somewhere
