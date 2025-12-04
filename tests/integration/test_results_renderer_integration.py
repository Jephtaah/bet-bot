"""
Integration tests for results renderer module.

Tests the render_analysis_results() function with real-world scenarios,
including integration with the formatter output and various data sources.
"""

import pytest

from bet_bot.display import format_picks_for_display, render_analysis_results
from bet_bot.models.analysis import Pick


class TestFormatterIntegration:
    """Test integration with formatter output."""

    @pytest.fixture
    def sample_picks(self) -> list[Pick]:
        """Create realistic sample picks."""
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
    async def test_renderer_uses_formatter_output(self, sample_picks: list[Pick]) -> None:
        """Test that renderer properly integrates formatter output."""
        # Get formatter output
        formatter_output = format_picks_for_display(sample_picks)
        assert isinstance(formatter_output, str)
        assert len(formatter_output) > 0

        # Get renderer output
        renderer_output = await render_analysis_results(sample_picks, 1000.0)
        assert isinstance(renderer_output, str)

        # Renderer output should contain/reference key pick information
        # (from formatter and added details)
        assert "5.2%" in renderer_output or "7.1%" in renderer_output

    @pytest.mark.asyncio
    async def test_combined_output_readable(self, sample_picks: list[Pick]) -> None:
        """Test that combined formatter+renderer output is readable."""
        output = await render_analysis_results(sample_picks, 1000.0)

        # Check for readability markers
        assert len(output) > 100
        assert "\n" in output  # Should have multiple lines


class TestFullPipelineScenarios:
    """Test full pipeline scenarios with realistic data."""

    @pytest.mark.asyncio
    async def test_scenario_successful_analysis_three_picks(self) -> None:
        """Test scenario: successful analysis with 3 picks."""
        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.652,
                implied_probability=0.551,
                ev_percentage=5.2,
                confidence=75,
                recommended_stake=25.00,
                suggested_odds=2.10,
            ),
            Pick(
                fixture_id="548822",
                market="over_2_5",
                ai_probability=0.68,
                implied_probability=0.556,
                ev_percentage=7.1,
                confidence=82,
                recommended_stake=30.00,
                suggested_odds=1.85,
            ),
            Pick(
                fixture_id="548823",
                market="both_teams_score",
                ai_probability=0.58,
                implied_probability=0.476,
                ev_percentage=3.8,
                confidence=65,
                recommended_stake=20.00,
                suggested_odds=2.25,
            ),
        ]

        data_quality = {
            "api_football": {"status": "success", "latency_ms": 45, "record_count": 125},
            "espn": {"status": "success", "latency_ms": 800, "record_count": 50},
            "openai": {"status": "success", "latency_ms": 1200, "record_count": 3},
            "flashscore": {"status": "success", "latency_ms": 200, "record_count": 0},
        }

        output = await render_analysis_results(picks, 1000.0, data_quality)

        assert "PICKS FOUND" in output
        assert "3" in output  # Total picks
        assert "Total Stake" in output

    @pytest.mark.asyncio
    async def test_scenario_no_picks_found(self) -> None:
        """Test scenario: no picks found (empty analysis)."""
        data_quality = {
            "api_football": {"status": "success", "record_count": 100},
            "openai": {"status": "success"},
            "fixtures_analyzed": 20,
        }

        output = await render_analysis_results([], 1000.0, data_quality)

        assert "NO PROFITABLE" in output
        assert "threshold" in output.lower()

    @pytest.mark.asyncio
    async def test_scenario_no_matches_today(self) -> None:
        """Test scenario: no matches available for analysis."""
        data_quality = {
            "api_football": {"status": "success", "record_count": 0},
            "fixtures_analyzed": 0,
        }

        output = await render_analysis_results([], 1000.0, data_quality)

        assert "NO MATCHES" in output

    @pytest.mark.asyncio
    async def test_scenario_partial_data_failure(self) -> None:
        """Test scenario: partial data failure but picks available."""
        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.652,
                implied_probability=0.551,
                ev_percentage=5.2,
                confidence=75,
                recommended_stake=25.00,
                suggested_odds=2.10,
            ),
        ]

        data_quality = {
            "api_football": {"status": "success"},
            "espn": {"status": "failed", "error": "timeout"},
            "openai": {"status": "success"},
            "injuries": {"status": "failed", "error": "stale data"},
        }

        output = await render_analysis_results(picks, 1000.0, data_quality)

        assert "DEGRADED" in output
        assert "confidence reduced" in output.lower() or "caution" in output.lower()

    @pytest.mark.asyncio
    async def test_scenario_api_failure_critical(self) -> None:
        """Test scenario: critical API failure (no results possible)."""
        data_quality = {
            "api_football": {"status": "failed", "error": "API unavailable"},
            "openai": {"status": "failed", "error": "Rate limit exceeded"},
        }

        output = await render_analysis_results([], 1000.0, data_quality)

        assert "FAILED" in output or "ERROR" in output


class TestDataQualityTracking:
    """Test data quality tracking across scenarios."""

    @pytest.mark.asyncio
    async def test_track_all_data_sources(self) -> None:
        """Test tracking all 5+ data sources."""
        data_quality = {
            "api_football": {"status": "success", "latency_ms": 45, "record_count": 125},
            "espn": {"status": "success", "latency_ms": 800, "record_count": 50},
            "flashscore": {"status": "success", "latency_ms": 200, "record_count": 75},
            "openai": {"status": "success", "latency_ms": 1200, "record_count": 3},
            "injuries": {"status": "success", "latency_ms": 150, "record_count": 12},
        }

        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.652,
                implied_probability=0.551,
                ev_percentage=5.2,
                confidence=75,
                recommended_stake=25.00,
                suggested_odds=2.10,
            ),
        ]

        output = await render_analysis_results(picks, 1000.0, data_quality)

        assert "Data Quality" in output

    @pytest.mark.asyncio
    async def test_show_source_failures(self) -> None:
        """Test showing which sources failed."""
        data_quality = {
            "api_football": {"status": "success"},
            "espn": {"status": "failed", "error": "timeout"},
            "openai": {"status": "success"},
        }

        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.652,
                implied_probability=0.551,
                ev_percentage=5.2,
                confidence=75,
                recommended_stake=25.00,
                suggested_odds=2.10,
            ),
        ]

        output = await render_analysis_results(picks, 1000.0, data_quality)

        # Should indicate that a source failed
        assert "DEGRADED" in output or "caution" in output.lower()

    @pytest.mark.asyncio
    async def test_display_latency_info(self) -> None:
        """Test displaying latency information."""
        data_quality = {
            "api_football": {"status": "success", "latency_ms": 45},
            "openai": {"status": "success", "latency_ms": 1200},
        }

        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.652,
                implied_probability=0.551,
                ev_percentage=5.2,
                confidence=75,
                recommended_stake=25.00,
                suggested_odds=2.10,
            ),
        ]

        output = await render_analysis_results(picks, 1000.0, data_quality)

        assert isinstance(output, str)

    @pytest.mark.asyncio
    async def test_display_record_counts(self) -> None:
        """Test displaying record counts from each source."""
        data_quality = {
            "api_football": {"status": "success", "record_count": 125},
            "espn": {"status": "success", "record_count": 50},
            "openai": {"status": "success", "record_count": 3},
        }

        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.652,
                implied_probability=0.551,
                ev_percentage=5.2,
                confidence=75,
                recommended_stake=25.00,
                suggested_odds=2.10,
            ),
        ]

        output = await render_analysis_results(picks, 1000.0, data_quality)

        assert isinstance(output, str)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_single_pick_display(self) -> None:
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

        output = await render_analysis_results([pick], 1000.0)

        assert "PICKS FOUND" in output
        assert "1" in output

    @pytest.mark.asyncio
    async def test_many_picks_display(self) -> None:
        """Test rendering with many picks."""
        picks = [
            Pick(
                fixture_id=f"54882{i}",
                market="match_result_home",
                ai_probability=0.652,
                implied_probability=0.551,
                ev_percentage=5.2 + (i % 5),
                confidence=65 + (i % 20),
                recommended_stake=10.0 + (i * 2),
                suggested_odds=2.10,
            )
            for i in range(20)
        ]

        output = await render_analysis_results(picks, 10000.0)

        assert "PICKS FOUND" in output
        assert "20" in output

    @pytest.mark.asyncio
    async def test_very_high_ev_picks(self) -> None:
        """Test with unusually high EV picks."""
        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.8,
                implied_probability=0.4,
                ev_percentage=50.0,  # Very high EV
                confidence=95,
                recommended_stake=100.0,
                suggested_odds=2.5,
            ),
        ]

        output = await render_analysis_results(picks, 10000.0)

        assert "PICKS FOUND" in output
        assert "50.0%" in output or "50%" in output

    @pytest.mark.asyncio
    async def test_very_low_ev_picks(self) -> None:
        """Test with very low EV picks (near threshold)."""
        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.52,
                implied_probability=0.5,
                ev_percentage=5.0,  # Barely above threshold
                confidence=50,
                recommended_stake=5.0,
                suggested_odds=2.0,
            ),
        ]

        output = await render_analysis_results(picks, 1000.0)

        assert "PICKS FOUND" in output

    @pytest.mark.asyncio
    async def test_small_bankroll(self) -> None:
        """Test with small bankroll."""
        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.652,
                implied_probability=0.551,
                ev_percentage=5.2,
                confidence=75,
                recommended_stake=10.0,
                suggested_odds=2.10,
            ),
        ]

        output = await render_analysis_results(picks, 50.0)

        assert isinstance(output, str)

    @pytest.mark.asyncio
    async def test_large_bankroll(self) -> None:
        """Test with large bankroll."""
        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.652,
                implied_probability=0.551,
                ev_percentage=5.2,
                confidence=75,
                recommended_stake=1000.0,
                suggested_odds=2.10,
            ),
        ]

        output = await render_analysis_results(picks, 100000.0)

        assert isinstance(output, str)

    @pytest.mark.asyncio
    async def test_empty_data_quality_dict(self) -> None:
        """Test with empty data quality dictionary."""
        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.652,
                implied_probability=0.551,
                ev_percentage=5.2,
                confidence=75,
                recommended_stake=25.0,
                suggested_odds=2.10,
            ),
        ]

        output = await render_analysis_results(picks, 1000.0, {})

        assert "PICKS FOUND" in output

    @pytest.mark.asyncio
    async def test_none_data_quality(self) -> None:
        """Test with None data quality."""
        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.652,
                implied_probability=0.551,
                ev_percentage=5.2,
                confidence=75,
                recommended_stake=25.0,
                suggested_odds=2.10,
            ),
        ]

        output = await render_analysis_results(picks, 1000.0, None)

        assert "PICKS FOUND" in output


class TestAsyncBehavior:
    """Test async function behavior."""

    @pytest.mark.asyncio
    async def test_async_function_awaitable(self) -> None:
        """Test that function is properly async."""
        picks = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.652,
                implied_probability=0.551,
                ev_percentage=5.2,
                confidence=75,
                recommended_stake=25.0,
                suggested_odds=2.10,
            ),
        ]

        # This should work with await
        result = await render_analysis_results(picks, 1000.0)

        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_concurrent_rendering(self) -> None:
        """Test rendering multiple analyses concurrently."""
        import asyncio

        picks1 = [
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.652,
                implied_probability=0.551,
                ev_percentage=5.2,
                confidence=75,
                recommended_stake=25.0,
                suggested_odds=2.10,
            ),
        ]

        picks2 = []

        # Render both concurrently
        results = await asyncio.gather(
            render_analysis_results(picks1, 1000.0),
            render_analysis_results(picks2, 1000.0),
        )

        assert len(results) == 2
        assert isinstance(results[0], str)
        assert isinstance(results[1], str)
        assert "PICKS FOUND" in results[0]
        assert "NO PROFITABLE" in results[1]
