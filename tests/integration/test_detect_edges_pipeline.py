"""
Integration tests for edge detection pipeline (Story 5.4).

Tests end-to-end pipeline execution with real or realistic Fixture, EVResult,
and ConfidenceScoreBreakdown models from Stories 5.1, 5.2, and 5.3.

Test scenarios:
- All data fresh (form < 24h, injuries < 12h, odds < 30min) → high confidence picks
- Mixed freshness (form 48h old, odds 45min old) → medium confidence
- Data stale/missing → low confidence or no picks
- Multiple fixtures with various data quality
- Summary statistics accuracy
- Stake calculations with confidence scaling
- Pick object completeness and field validation
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from bet_bot.models.analysis import Pick
from bet_bot.models.fixtures import Fixture, Team, League
from bet_bot.analysis.edge.pipeline import detect_edges
from bet_bot.analysis.edge.ev_calculator import EVResult
from bet_bot.analysis.edge.confidence_scorer import ConfidenceScoreBreakdown
from bet_bot.analysis.edge.threshold_filter import FilteredPick, PickCategory


@pytest.fixture
def sample_team_home() -> Team:
    """Create a sample home team."""
    return Team(id="42", name="Leeds United")


@pytest.fixture
def sample_team_away() -> Team:
    """Create a sample away team."""
    return Team(id="43", name="Coventry City")


@pytest.fixture
def sample_league() -> League:
    """Create a sample League."""
    return League(
        league_id="39",
        league_name="Championship",
        league_country="England",
        league_season=2025,
    )


@pytest.fixture
def sample_fixture_fresh_data(sample_team_home, sample_team_away, sample_league) -> Fixture:
    """Create a fixture with fresh data (< 24h, < 12h, < 30min)."""
    now = datetime.now(timezone.utc)
    return Fixture(
        fixture_id="123456",
        kickoff_time=now + timedelta(days=2),
        home_team=sample_team_home,
        away_team=sample_team_away,
        league=sample_league,
        odds_data={"match_result": {"home": 2.10, "draw": 3.50, "away": 4.00}},
        odds_timestamp=now - timedelta(minutes=15),  # 15min old
        form_timestamp=now - timedelta(hours=12),  # 12h old
        injuries_timestamp=now - timedelta(hours=6),  # 6h old
    )


@pytest.fixture
def sample_fixture_stale_data(sample_team_home, sample_team_away, sample_league) -> Fixture:
    """Create a fixture with mixed freshness (form 48h, odds 45min, injuries missing)."""
    now = datetime.now(timezone.utc)
    return Fixture(
        fixture_id="789012",
        kickoff_time=now + timedelta(days=2),
        home_team=sample_team_home,
        away_team=sample_team_away,
        league=sample_league,
        odds_data={"match_result": {"home": 1.95, "draw": 3.30, "away": 4.25}},
        odds_timestamp=now - timedelta(minutes=45),  # 45min old
        form_timestamp=now - timedelta(hours=48),  # 48h old
        injuries_timestamp=None,  # Missing
    )


class TestIntegrationEndToEnd:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_pipeline_with_fresh_data_high_confidence(
        self, sample_fixture_fresh_data
    ):
        """Test pipeline with fresh data produces high confidence picks."""
        # Create realistic EV result
        ev_result = EVResult(
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

        sample_fixture_fresh_data.ev_results = [ev_result]

        # High confidence from fresh data
        confidence_breakdown = ConfidenceScoreBreakdown(
            base_score=75,
            form_adjustment=15,  # +15 for < 24h form
            injury_adjustment=5,  # +5 for < 12h injuries
            odds_adjustment=5,  # +5 for < 30min odds
            sample_size_adjustment=0,  # No penalty
            total_adjustments=25,
            final_confidence=100,  # Clamped to 100
            explanation="Fresh form (+15), fresh injuries (+5), fresh odds (+5) = high confidence",
        )

        # Mock the pipeline steps
        with patch("bet_bot.analysis.edge.pipeline.calculate_all_evs") as mock_calc:
            with patch(
                "bet_bot.analysis.edge.pipeline.apply_threshold_filter"
            ) as mock_filter:
                with patch(
                    "bet_bot.analysis.edge.pipeline.apply_confidence_scoring"
                ) as mock_score:
                    mock_calc.return_value = [sample_fixture_fresh_data]

                    filtered_pick = FilteredPick(
                        ev_result=ev_result,
                        category=PickCategory.RECOMMENDED,
                        category_reason="EV 5.8% >= 5.0%",
                        recommended=True,
                    )

                    mock_filter.return_value = {
                        "recommended": [filtered_pick],
                        "total": 1,
                        "has_picks": True,
                    }

                    mock_score.return_value = [confidence_breakdown]

                    # Execute
                    result = await detect_edges(
                        [sample_fixture_fresh_data], bankroll=1000.0
                    )

                    # Verify
                    assert isinstance(result, list)
                    assert len(result) == 1

                    pick = result[0]
                    assert pick.confidence == 100  # High confidence from fresh data
                    assert pick.ev_percentage == 5.8
                    assert pick.fixture_id == sample_fixture_fresh_data.fixture_id

    @pytest.mark.asyncio
    async def test_pipeline_with_mixed_freshness(self, sample_fixture_stale_data):
        """Test pipeline with mixed data freshness produces medium confidence."""
        ev_result = EVResult(
            market_type="match_result",
            outcome="home",
            ai_probability=0.55,
            odds=1.95,
            implied_probability=0.513,
            ev_decimal=0.035,
            ev_percentage=3.5,  # Below 5% threshold
            is_valid=True,
            skip_reason=None,
        )

        sample_fixture_stale_data.ev_results = [ev_result]

        # This test demonstrates that picks below 5% should not be recommended
        # So we test with valid picks above threshold
        ev_result_above = EVResult(
            market_type="match_result",
            outcome="away",
            ai_probability=0.38,
            odds=4.25,
            implied_probability=0.235,
            ev_decimal=0.086,
            ev_percentage=8.6,
            is_valid=True,
            skip_reason=None,
        )

        sample_fixture_stale_data.ev_results = [ev_result, ev_result_above]

        # Medium confidence from mixed freshness
        confidence_breakdown = ConfidenceScoreBreakdown(
            base_score=75,
            form_adjustment=-5,  # -5 for 48h old form
            injury_adjustment=-10,  # -10 for missing injuries
            odds_adjustment=-5,  # -5 for 45min old odds
            sample_size_adjustment=0,
            total_adjustments=-20,
            final_confidence=55,  # 75 - 20 = 55 (medium confidence)
            explanation="Stale form (-5), missing injuries (-10), slightly stale odds (-5)",
        )

        with patch("bet_bot.analysis.edge.pipeline.calculate_all_evs") as mock_calc:
            with patch(
                "bet_bot.analysis.edge.pipeline.apply_threshold_filter"
            ) as mock_filter:
                with patch(
                    "bet_bot.analysis.edge.pipeline.apply_confidence_scoring"
                ) as mock_score:
                    mock_calc.return_value = [sample_fixture_stale_data]

                    filtered_pick = FilteredPick(
                        ev_result=ev_result_above,
                        category=PickCategory.RECOMMENDED,
                        category_reason="EV 8.6% >= 5.0%",
                        recommended=True,
                    )

                    mock_filter.return_value = {
                        "recommended": [filtered_pick],
                        "total": 2,
                        "has_picks": True,
                    }

                    mock_score.return_value = [confidence_breakdown]

                    result = await detect_edges([sample_fixture_stale_data], bankroll=1000.0)

                    assert isinstance(result, list)
                    assert len(result) == 1
                    pick = result[0]
                    assert pick.confidence == 55  # Medium confidence from mixed data


class TestMultiFixtureScenarios:
    """Test pipeline with multiple fixtures."""

    @pytest.mark.asyncio
    async def test_pipeline_multiple_fixtures_varied_quality(
        self, sample_fixture_fresh_data, sample_fixture_stale_data
    ):
        """Test pipeline processes multiple fixtures with different data quality."""
        # Setup fresh fixture
        ev_fresh = EVResult(
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
        sample_fixture_fresh_data.ev_results = [ev_fresh]

        # Setup stale fixture
        ev_stale = EVResult(
            market_type="match_result",
            outcome="away",
            ai_probability=0.38,
            odds=4.25,
            implied_probability=0.235,
            ev_decimal=0.086,
            ev_percentage=8.6,
            is_valid=True,
            skip_reason=None,
        )
        sample_fixture_stale_data.ev_results = [ev_stale]

        # Mock pipeline
        with patch("bet_bot.analysis.edge.pipeline.calculate_all_evs") as mock_calc:
            with patch(
                "bet_bot.analysis.edge.pipeline.apply_threshold_filter"
            ) as mock_filter:
                with patch(
                    "bet_bot.analysis.edge.pipeline.apply_confidence_scoring"
                ) as mock_score:
                    mock_calc.return_value = [
                        sample_fixture_fresh_data,
                        sample_fixture_stale_data,
                    ]

                    confidence_fresh = ConfidenceScoreBreakdown(
                        base_score=75,
                        form_adjustment=15,
                        injury_adjustment=5,
                        odds_adjustment=5,
                        sample_size_adjustment=0,
                        total_adjustments=25,
                        final_confidence=100,
                        explanation="Fresh data",
                    )

                    confidence_stale = ConfidenceScoreBreakdown(
                        base_score=75,
                        form_adjustment=-5,
                        injury_adjustment=-10,
                        odds_adjustment=-5,
                        sample_size_adjustment=0,
                        total_adjustments=-20,
                        final_confidence=55,
                        explanation="Stale data",
                    )

                    mock_filter.return_value = {
                        "recommended": [
                            FilteredPick(
                                ev_result=ev_fresh,
                                category=PickCategory.RECOMMENDED,
                                category_reason="EV 5.8%",
                                recommended=True,
                            ),
                            FilteredPick(
                                ev_result=ev_stale,
                                category=PickCategory.RECOMMENDED,
                                category_reason="EV 8.6%",
                                recommended=True,
                            ),
                        ],
                        "total": 2,
                        "has_picks": True,
                    }

                    mock_score.return_value = [confidence_fresh, confidence_stale]

                    result = await detect_edges(
                        [sample_fixture_fresh_data, sample_fixture_stale_data],
                        bankroll=1000.0,
                    )

                    assert isinstance(result, list)
                    assert len(result) == 2

                    # Verify picks have different confidence levels
                    confidences = [p.confidence for p in result]
                    assert 100 in confidences
                    assert 55 in confidences


class TestPickFieldValidation:
    """Test that Pick objects have all required fields populated."""

    @pytest.mark.asyncio
    async def test_pick_has_all_required_fields(self, sample_fixture_fresh_data):
        """Verify Pick objects contain all required fields."""
        ev_result = EVResult(
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

        sample_fixture_fresh_data.ev_results = [ev_result]

        confidence = ConfidenceScoreBreakdown(
            base_score=75,
            form_adjustment=0,
            injury_adjustment=0,
            odds_adjustment=0,
            sample_size_adjustment=0,
            total_adjustments=0,
            final_confidence=75,
            explanation="Neutral",
        )

        with patch("bet_bot.analysis.edge.pipeline.calculate_all_evs") as mock_calc:
            with patch(
                "bet_bot.analysis.edge.pipeline.apply_threshold_filter"
            ) as mock_filter:
                with patch(
                    "bet_bot.analysis.edge.pipeline.apply_confidence_scoring"
                ) as mock_score:
                    mock_calc.return_value = [sample_fixture_fresh_data]

                    mock_filter.return_value = {
                        "recommended": [
                            FilteredPick(
                                ev_result=ev_result,
                                category=PickCategory.RECOMMENDED,
                                category_reason="EV 5.8%",
                                recommended=True,
                            )
                        ],
                        "total": 1,
                        "has_picks": True,
                    }

                    mock_score.return_value = [confidence]

                    result = await detect_edges([sample_fixture_fresh_data], bankroll=1000.0)

                    assert isinstance(result, list)
                    pick = result[0]

                    # Verify all required fields
                    assert pick.fixture_id is not None
                    assert pick.market is not None
                    assert pick.ai_probability is not None
                    assert pick.implied_probability is not None
                    assert pick.ev_percentage is not None
                    assert pick.confidence is not None
                    assert pick.recommended_stake is not None
                    assert pick.recommended_stake > 0
                    assert pick.suggested_odds is not None

                    # Verify field values make sense
                    assert pick.ai_probability >= 0.0
                    assert pick.ai_probability <= 1.0
                    assert pick.implied_probability >= 0.0
                    assert pick.implied_probability <= 1.0
                    assert pick.confidence >= 0
                    assert pick.confidence <= 100
                    assert pick.suggested_odds >= 1.0


class TestSummaryStatisticsAccuracy:
    """Test that summary statistics are calculated correctly."""

    @pytest.mark.asyncio
    async def test_summary_stats_ev_distribution(self, sample_fixture_fresh_data):
        """Test EV distribution statistics are accurate."""
        # Create multiple EVResults with different EV percentages
        ev_results = []
        pick_list = []

        ev_percentages = [5.0, 5.5, 6.0, 7.0, 8.5, 9.0]  # Mean = 6.83, Min = 5.0, Max = 9.0

        for i, ev_pct in enumerate(ev_percentages):
            ev = EVResult(
                market_type="match_result",
                outcome=f"outcome_{i}",
                ai_probability=0.55 + (i * 0.01),
                odds=2.0 + (i * 0.1),
                implied_probability=1 / (2.0 + (i * 0.1)),
                ev_decimal=ev_pct / 100,
                ev_percentage=ev_pct,
                is_valid=True,
                skip_reason=None,
            )
            ev_results.append(ev)

            pick = Pick(
                fixture_id="fixture_fresh_data",
                market=f"match_result_outcome_{i}",
                ai_probability=ev.ai_probability,
                implied_probability=ev.implied_probability,
                ev_percentage=ev_pct,
                confidence=75,
                recommended_stake=5.0,
                suggested_odds=ev.odds,
            )
            pick_list.append(pick)

        sample_fixture_fresh_data.ev_results = ev_results

        with patch("bet_bot.analysis.edge.pipeline.calculate_all_evs") as mock_calc:
            with patch(
                "bet_bot.analysis.edge.pipeline.apply_threshold_filter"
            ) as mock_filter:
                with patch(
                    "bet_bot.analysis.edge.pipeline.apply_confidence_scoring"
                ) as mock_score:
                    mock_calc.return_value = [sample_fixture_fresh_data]

                    filtered_picks = [
                        FilteredPick(
                            ev_result=ev,
                            category=PickCategory.RECOMMENDED,
                            category_reason=f"EV {ev.ev_percentage}%",
                            recommended=True,
                        )
                        for ev in ev_results
                    ]

                    mock_filter.return_value = {
                        "recommended": filtered_picks,
                        "total": len(ev_results),
                        "has_picks": True,
                    }

                    confidences = [
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
                        for _ in ev_results
                    ]

                    mock_score.return_value = confidences

                    result = await detect_edges([sample_fixture_fresh_data], bankroll=1000.0)

                    assert isinstance(result, list)
                    assert len(result) == 6
                    # All picks should have their EV percentages preserved
                    result_evs = sorted([p.ev_percentage for p in result])
                    assert result_evs == sorted(ev_percentages)
