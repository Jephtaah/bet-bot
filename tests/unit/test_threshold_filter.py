"""
Unit tests for threshold_filter module (Story 5.2).

Comprehensive testing of:
- filter_picks_by_threshold() function with valid/invalid/boundary cases
- categorize_picks() function for 4-bucket categorization
- validate_threshold_enforcement() function for discipline enforcement
- verify_no_threshold_bypass() function for bypass detection
- no_picks_available_message() for user messaging
- apply_threshold_filter() for batch orchestration
- PickCategory enum values
- FilteredPick model validation

Test Strategy:
- Unit tests focus on isolated function behavior
- Mock EVResult objects for predictable test data
- Test boundary conditions (exactly 5.0% EV, negative EV)
- Test error cases (invalid thresholds, empty inputs)
- Test discipline enforcement (no picks below 5% in recommended)

Target Coverage: >=85% (Story 5.2 requirement)
"""

import pytest
from unittest.mock import MagicMock

from bet_bot.analysis.edge.ev_calculator import EVResult
from bet_bot.analysis.edge.threshold_filter import (
    PickCategory,
    FilteredPick,
    filter_picks_by_threshold,
    categorize_picks,
    validate_threshold_enforcement,
    verify_no_threshold_bypass,
    no_picks_available_message,
    apply_threshold_filter,
)


# ============================================================================
# Test Fixtures - EVResult Factory
# ============================================================================


@pytest.fixture
def make_ev_result():
    """Factory fixture for creating EVResult objects."""

    def _make_ev_result(
        market_type: str = "match_result",
        outcome: str = "home",
        ai_probability: float = 0.58,
        odds: float = 2.10,
        implied_probability: float = 0.476,
        ev_decimal: float = 0.058,
        ev_percentage: float = 5.8,
        is_valid: bool = True,
        skip_reason: str | None = None,
    ) -> EVResult:
        return EVResult(
            market_type=market_type,
            outcome=outcome,
            ai_probability=ai_probability,
            odds=odds,
            implied_probability=implied_probability,
            ev_decimal=ev_decimal,
            ev_percentage=ev_percentage,
            is_valid=is_valid,
            skip_reason=skip_reason,
        )

    return _make_ev_result


@pytest.fixture
def sample_ev_results(make_ev_result):
    """Sample EV results for testing."""
    return [
        make_ev_result(outcome="home", ev_percentage=5.8, is_valid=True),  # RECOMMENDED
        make_ev_result(outcome="draw", ev_percentage=4.2, is_valid=True),  # MARGINAL
        make_ev_result(outcome="away", ev_percentage=1.5, is_valid=True),  # LOW
        make_ev_result(
            outcome="over",
            ev_percentage=0.0,
            is_valid=False,
            skip_reason="odds <= 1.0",
        ),  # INVALID
    ]


# ============================================================================
# Test PickCategory Enum
# ============================================================================


class TestPickCategory:
    """Tests for PickCategory enum."""

    def test_pick_category_values(self):
        """Test PickCategory has 4 values."""
        assert PickCategory.RECOMMENDED.value == "RECOMMENDED"
        assert PickCategory.MARGINAL.value == "MARGINAL"
        assert PickCategory.LOW.value == "LOW"
        assert PickCategory.INVALID.value == "INVALID"

    def test_pick_category_count(self):
        """Test there are exactly 4 categories."""
        assert len(PickCategory) == 4


# ============================================================================
# Test FilteredPick Model
# ============================================================================


class TestFilteredPickModel:
    """Tests for FilteredPick Pydantic model."""

    def test_filtered_pick_valid(self, make_ev_result):
        """Test creating valid FilteredPick."""
        ev = make_ev_result(ev_percentage=5.8)
        pick = FilteredPick(
            ev_result=ev,
            category=PickCategory.RECOMMENDED,
            category_reason="EV 5.8% >= 5.0% threshold",
            recommended=True,
        )
        assert pick.category == PickCategory.RECOMMENDED
        assert pick.recommended is True

    def test_filtered_pick_consistency_violation(self, make_ev_result):
        """Test FilteredPick enforces category/recommended consistency."""
        ev = make_ev_result(ev_percentage=5.8)
        # RECOMMENDED with recommended=False should fail
        with pytest.raises(ValueError):
            FilteredPick(
                ev_result=ev,
                category=PickCategory.RECOMMENDED,
                category_reason="EV 5.8%",
                recommended=False,  # Inconsistent!
            )

    def test_filtered_pick_non_recommended_with_true(self, make_ev_result):
        """Test non-RECOMMENDED category cannot have recommended=True."""
        ev = make_ev_result(ev_percentage=4.2)
        with pytest.raises(ValueError):
            FilteredPick(
                ev_result=ev,
                category=PickCategory.MARGINAL,
                category_reason="EV 4.2%",
                recommended=True,  # Inconsistent!
            )


# ============================================================================
# Test filter_picks_by_threshold()
# ============================================================================


class TestFilterPicksByThreshold:
    """Tests for filter_picks_by_threshold() function."""

    def test_filter_with_valid_picks_above_threshold(self, make_ev_result):
        """Test filtering picks where some are above threshold."""
        ev_results = [
            make_ev_result(ev_percentage=5.8),  # Above
            make_ev_result(ev_percentage=4.2),  # Below
            make_ev_result(ev_percentage=6.0),  # Above
        ]
        above, below = filter_picks_by_threshold(ev_results, 5.0)
        assert len(above) == 2
        assert len(below) == 1
        assert above[0].ev_percentage == 5.8
        assert above[1].ev_percentage == 6.0
        assert below[0].ev_percentage == 4.2

    def test_filter_boundary_at_threshold(self, make_ev_result):
        """Test boundary condition: EV exactly at threshold (inclusive)."""
        ev_results = [
            make_ev_result(ev_percentage=5.0),  # Exactly at threshold
            make_ev_result(ev_percentage=4.99),  # Just below
        ]
        above, below = filter_picks_by_threshold(ev_results, 5.0)
        assert len(above) == 1
        assert len(below) == 1
        assert above[0].ev_percentage == 5.0  # Inclusive: >= threshold

    def test_filter_with_invalid_picks(self, make_ev_result):
        """Test that invalid picks go to below_threshold."""
        ev_results = [
            make_ev_result(ev_percentage=6.0, is_valid=True),
            make_ev_result(ev_percentage=0.0, is_valid=False, skip_reason="bad odds"),
        ]
        above, below = filter_picks_by_threshold(ev_results, 5.0)
        assert len(above) == 1
        assert len(below) == 1
        assert below[0].is_valid is False

    def test_filter_empty_list(self):
        """Test filtering empty list returns empty tuples."""
        above, below = filter_picks_by_threshold([], 5.0)
        assert above == []
        assert below == []

    def test_filter_all_above_threshold(self, make_ev_result):
        """Test filtering where all picks are above threshold."""
        ev_results = [
            make_ev_result(ev_percentage=5.8),
            make_ev_result(ev_percentage=6.2),
        ]
        above, below = filter_picks_by_threshold(ev_results, 5.0)
        assert len(above) == 2
        assert len(below) == 0

    def test_filter_all_below_threshold(self, make_ev_result):
        """Test filtering where all picks are below threshold."""
        ev_results = [
            make_ev_result(ev_percentage=4.2),
            make_ev_result(ev_percentage=3.1),
        ]
        above, below = filter_picks_by_threshold(ev_results, 5.0)
        assert len(above) == 0
        assert len(below) == 2

    def test_filter_negative_threshold_raises(self):
        """Test negative threshold raises ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            filter_picks_by_threshold([], threshold_pct=-1.0)

    def test_filter_threshold_exceeds_100_raises(self):
        """Test threshold > 100% raises ValueError."""
        with pytest.raises(ValueError, match="exceed 100%"):
            filter_picks_by_threshold([], threshold_pct=101.0)

    def test_filter_custom_threshold(self, make_ev_result):
        """Test filtering with custom threshold (not default 5%)."""
        ev_results = [
            make_ev_result(ev_percentage=3.5),  # Above 3%, below 5%
            make_ev_result(ev_percentage=2.5),  # Below 3%
        ]
        above, below = filter_picks_by_threshold(ev_results, 3.0)
        assert len(above) == 1
        assert len(below) == 1
        assert above[0].ev_percentage == 3.5


# ============================================================================
# Test categorize_picks()
# ============================================================================


class TestCategorizePicks:
    """Tests for categorize_picks() function."""

    def test_categorize_all_buckets(self, sample_ev_results):
        """Test categorization into all 4 buckets."""
        categorized = categorize_picks(sample_ev_results)
        assert len(categorized["RECOMMENDED"]) == 1
        assert len(categorized["MARGINAL"]) == 1
        assert len(categorized["LOW"]) == 1
        assert len(categorized["INVALID"]) == 1

    def test_categorize_recommended(self, make_ev_result):
        """Test RECOMMENDED category: EV >= 5%."""
        ev_results = [
            make_ev_result(ev_percentage=5.0),  # Boundary
            make_ev_result(ev_percentage=5.8),
            make_ev_result(ev_percentage=10.0),
        ]
        categorized = categorize_picks(ev_results)
        assert len(categorized["RECOMMENDED"]) == 3
        assert all(
            ev.ev_percentage >= 5.0 for ev in categorized["RECOMMENDED"]
        )

    def test_categorize_marginal(self, make_ev_result):
        """Test MARGINAL category: 2% <= EV < 5%."""
        ev_results = [
            make_ev_result(ev_percentage=2.0),  # Boundary
            make_ev_result(ev_percentage=3.5),
            make_ev_result(ev_percentage=4.99),
        ]
        categorized = categorize_picks(ev_results)
        assert len(categorized["MARGINAL"]) == 3
        assert all(
            2.0 <= ev.ev_percentage < 5.0 for ev in categorized["MARGINAL"]
        )

    def test_categorize_low(self, make_ev_result):
        """Test LOW category: 0% <= EV < 2%."""
        ev_results = [
            make_ev_result(ev_percentage=0.0),  # Boundary
            make_ev_result(ev_percentage=1.0),
            make_ev_result(ev_percentage=1.99),
        ]
        categorized = categorize_picks(ev_results)
        assert len(categorized["LOW"]) == 3
        assert all(
            0.0 <= ev.ev_percentage < 2.0 for ev in categorized["LOW"]
        )

    def test_categorize_invalid(self, make_ev_result):
        """Test INVALID category: is_valid == False."""
        ev_results = [
            make_ev_result(is_valid=False, skip_reason="bad odds"),
            make_ev_result(is_valid=False, skip_reason="bad probability"),
        ]
        categorized = categorize_picks(ev_results)
        assert len(categorized["INVALID"]) == 2
        assert all(not ev.is_valid for ev in categorized["INVALID"])

    def test_categorize_all_picks_accounted_for(self, sample_ev_results):
        """Test sum of categories equals input size."""
        categorized = categorize_picks(sample_ev_results)
        total_categorized = sum(len(picks) for picks in categorized.values())
        assert total_categorized == len(sample_ev_results)

    def test_categorize_empty_list(self):
        """Test categorizing empty list."""
        categorized = categorize_picks([])
        assert all(len(picks) == 0 for picks in categorized.values())

    def test_categorize_negative_ev(self, make_ev_result):
        """Test categorizing negative EV (below 0%)."""
        ev_results = [make_ev_result(ev_percentage=-5.0)]
        categorized = categorize_picks(ev_results)
        assert len(categorized["LOW"]) == 1  # Negative EV still goes to LOW


# ============================================================================
# Test validate_threshold_enforcement()
# ============================================================================


class TestValidateThresholdEnforcement:
    """Tests for validate_threshold_enforcement() function."""

    def test_validate_all_above_threshold(self, make_ev_result):
        """Test validation passes when all picks >= 5%."""
        picks = [
            make_ev_result(ev_percentage=5.0),
            make_ev_result(ev_percentage=5.8),
            make_ev_result(ev_percentage=10.0),
        ]
        assert validate_threshold_enforcement(picks) is True

    def test_validate_one_below_threshold_raises(self, make_ev_result):
        """Test validation raises ValueError if any pick < 5%."""
        picks = [
            make_ev_result(ev_percentage=5.8),
            make_ev_result(ev_percentage=4.5),  # Below 5%!
        ]
        with pytest.raises(ValueError, match="violates 5% threshold"):
            validate_threshold_enforcement(picks)

    def test_validate_empty_list(self):
        """Test validation passes for empty list."""
        assert validate_threshold_enforcement([]) is True

    def test_validate_boundary_at_5_percent(self, make_ev_result):
        """Test validation with pick exactly at 5.0%."""
        picks = [make_ev_result(ev_percentage=5.0)]
        assert validate_threshold_enforcement(picks) is True


# ============================================================================
# Test verify_no_threshold_bypass()
# ============================================================================


class TestVerifyNoThresholdBypass:
    """Tests for verify_no_threshold_bypass() function."""

    def test_verify_valid_subset(self, make_ev_result):
        """Test verification passes for valid subset."""
        pick1 = make_ev_result(ev_percentage=5.8)
        pick2 = make_ev_result(ev_percentage=6.2)
        pick3 = make_ev_result(ev_percentage=4.2)
        all_picks = [pick1, pick2, pick3]
        recommended = [pick1, pick2]
        assert verify_no_threshold_bypass(recommended, all_picks) is True

    def test_verify_tampering_detected(self, make_ev_result):
        """Test verification detects tampering (pick added)."""
        pick1 = make_ev_result(
            market_type="match_result", outcome="home", ev_percentage=5.8
        )
        pick2 = make_ev_result(
            market_type="total_goals", outcome="over", ev_percentage=5.0
        )
        all_picks = [pick1]
        recommended = [pick1, pick2]  # pick2 not in all_picks
        assert verify_no_threshold_bypass(recommended, all_picks) is False

    def test_verify_below_threshold_detected(self, make_ev_result):
        """Test verification detects pick below 5% in recommended."""
        pick = make_ev_result(ev_percentage=4.5)
        recommended = [pick]
        all_picks = [pick]
        # This shouldn't happen, but verify detects it
        assert verify_no_threshold_bypass(recommended, all_picks) is False


# ============================================================================
# Test no_picks_available_message()
# ============================================================================


class TestNoPicksAvailableMessage:
    """Tests for no_picks_available_message() function."""

    def test_message_contains_title(self, sample_ev_results):
        """Test message contains 'NO PICKS AVAILABLE' title."""
        msg = no_picks_available_message(sample_ev_results, 5.0)
        assert "NO PICKS AVAILABLE" in msg

    def test_message_includes_counts(self, sample_ev_results):
        """Test message includes category counts."""
        msg = no_picks_available_message(sample_ev_results, 5.0)
        assert "MARGINAL" in msg
        assert "LOW" in msg
        assert "INVALID" in msg

    def test_message_includes_suggestions(self, sample_ev_results):
        """Test message includes next steps."""
        msg = no_picks_available_message(sample_ev_results, 5.0)
        assert "Next Steps" in msg
        assert "data quality" in msg.lower()

    def test_message_with_all_marginal(self, make_ev_result):
        """Test message when all picks are MARGINAL."""
        ev_results = [
            make_ev_result(ev_percentage=4.5),
            make_ev_result(ev_percentage=3.2),
        ]
        msg = no_picks_available_message(ev_results, 5.0)
        assert "2 pick" in msg  # plural
        assert "MARGINAL" in msg

    def test_message_with_custom_threshold(self, make_ev_result):
        """Test message respects custom threshold."""
        ev_results = [make_ev_result(ev_percentage=3.0)]
        msg = no_picks_available_message(ev_results, 4.0)
        assert "4.0%" in msg


# ============================================================================
# Test apply_threshold_filter()
# ============================================================================


class TestApplyThresholdFilterAsync:
    """Tests for apply_threshold_filter() async batch function."""

    @pytest.mark.asyncio
    async def test_apply_filter_basic(self, make_ev_result):
        """Test batch filtering with basic fixtures."""
        # Create mock fixtures
        fixture1 = MagicMock()
        fixture1.fixture_id = "fixture1"
        fixture1.home_team.name = "Team A"
        fixture1.away_team.name = "Team B"
        fixture1.ev_results = [
            make_ev_result(ev_percentage=5.8),
            make_ev_result(ev_percentage=4.2),
        ]

        results = await apply_threshold_filter([fixture1], 5.0)

        assert results["total_evaluated"] == 2
        assert results["total_recommended"] == 1
        assert results["threshold_pct"] == 5.0
        assert results["has_picks"] is True
        assert results["no_picks_message"] is None

    @pytest.mark.asyncio
    async def test_apply_filter_no_recommended_picks(self, make_ev_result):
        """Test batch filtering when no picks meet threshold."""
        fixture1 = MagicMock()
        fixture1.fixture_id = "fixture1"
        fixture1.home_team.name = "Team A"
        fixture1.away_team.name = "Team B"
        fixture1.ev_results = [
            make_ev_result(ev_percentage=4.2),
            make_ev_result(ev_percentage=1.5),
        ]

        results = await apply_threshold_filter([fixture1], 5.0)

        assert results["total_recommended"] == 0
        assert results["has_picks"] is False
        assert results["no_picks_message"] is not None
        assert "NO PICKS AVAILABLE" in results["no_picks_message"]

    @pytest.mark.asyncio
    async def test_apply_filter_multiple_fixtures(self, make_ev_result):
        """Test batch filtering with multiple fixtures."""
        fixture1 = MagicMock()
        fixture1.fixture_id = "fixture1"
        fixture1.home_team.name = "Team A"
        fixture1.away_team.name = "Team B"
        fixture1.ev_results = [make_ev_result(ev_percentage=5.8)]

        fixture2 = MagicMock()
        fixture2.fixture_id = "fixture2"
        fixture2.home_team.name = "Team C"
        fixture2.away_team.name = "Team D"
        fixture2.ev_results = [make_ev_result(ev_percentage=6.2)]

        results = await apply_threshold_filter([fixture1, fixture2], 5.0)

        assert results["total_evaluated"] == 2
        assert results["total_recommended"] == 2

    @pytest.mark.asyncio
    async def test_apply_filter_empty_fixtures(self):
        """Test batch filtering with empty fixture list."""
        results = await apply_threshold_filter([], 5.0)

        assert results["total_evaluated"] == 0
        assert results["has_picks"] is False
        assert results["no_picks_message"] is not None

    @pytest.mark.asyncio
    async def test_apply_filter_fixture_without_ev_results(self):
        """Test batch filtering when fixture missing ev_results."""
        fixture1 = MagicMock()
        fixture1.fixture_id = "fixture1"
        fixture1.home_team.name = "Team A"
        fixture1.away_team.name = "Team B"
        # No ev_results attribute

        results = await apply_threshold_filter([fixture1], 5.0)

        assert results["total_evaluated"] == 0
        assert results["has_picks"] is False

    @pytest.mark.asyncio
    async def test_apply_filter_categories_populated(self, make_ev_result):
        """Test batch filtering returns all categories."""
        fixture1 = MagicMock()
        fixture1.fixture_id = "fixture1"
        fixture1.home_team.name = "Team A"
        fixture1.away_team.name = "Team B"
        fixture1.ev_results = [
            make_ev_result(ev_percentage=5.8),  # RECOMMENDED
            make_ev_result(ev_percentage=4.2),  # MARGINAL
            make_ev_result(ev_percentage=1.5),  # LOW
            make_ev_result(
                ev_percentage=0.0, is_valid=False, skip_reason="bad"
            ),  # INVALID
        ]

        results = await apply_threshold_filter([fixture1], 5.0)

        assert len(results["recommended"]) == 1
        assert len(results["marginal"]) == 1
        assert len(results["low"]) == 1
        assert len(results["invalid"]) == 1


# ============================================================================
# Integration Tests - Story 5.1 Compatibility
# ============================================================================


class TestStory51Integration:
    """Tests ensuring compatibility with Story 5.1 (EVResult)."""

    def test_filter_uses_story51_ev_result(self, make_ev_result):
        """Test filtering works with Story 5.1 EVResult objects."""
        # Simulate real EVResult from Story 5.1
        ev = make_ev_result(
            market_type="match_result",
            outcome="home",
            ai_probability=0.58,
            odds=2.10,
            implied_probability=0.476,
            ev_decimal=0.058,
            ev_percentage=5.8,
            is_valid=True,
        )
        ev_results = [ev]
        above, below = filter_picks_by_threshold(ev_results, 5.0)
        assert len(above) == 1
        assert above[0].market_type == "match_result"
        assert above[0].outcome == "home"

    def test_categorize_with_multiple_markets(self, make_ev_result):
        """Test categorizing picks from multiple market types."""
        ev_results = [
            make_ev_result(market_type="match_result", outcome="home", ev_percentage=5.8),
            make_ev_result(market_type="total_goals", outcome="over", ev_percentage=4.2),
            make_ev_result(market_type="corners", outcome="under", ev_percentage=1.5),
        ]
        categorized = categorize_picks(ev_results)
        assert categorized["RECOMMENDED"][0].market_type == "match_result"
        assert categorized["MARGINAL"][0].market_type == "total_goals"
        assert categorized["LOW"][0].market_type == "corners"


# ============================================================================
# Edge Cases and Error Conditions
# ============================================================================


class TestEdgeCasesAndErrors:
    """Tests for edge cases and error conditions."""

    def test_filter_with_zero_threshold(self, make_ev_result):
        """Test filtering with 0% threshold."""
        ev_results = [
            make_ev_result(ev_percentage=1.5),
            make_ev_result(ev_percentage=-5.0),
        ]
        above, below = filter_picks_by_threshold(ev_results, 0.0)
        assert len(above) == 1
        assert len(below) == 1

    def test_categorize_with_large_positive_ev(self, make_ev_result):
        """Test categorizing very high EV (>50%)."""
        ev_results = [make_ev_result(ev_percentage=50.0)]
        categorized = categorize_picks(ev_results)
        assert len(categorized["RECOMMENDED"]) == 1

    def test_categorize_with_large_negative_ev(self, make_ev_result):
        """Test categorizing large negative EV (loss)."""
        ev_results = [make_ev_result(ev_percentage=-20.0)]
        categorized = categorize_picks(ev_results)
        assert len(categorized["LOW"]) == 1  # Negative EV in LOW bucket

    def test_filter_maintains_ev_result_integrity(self, make_ev_result):
        """Test that filtering doesn't modify EVResult objects."""
        original_ev = make_ev_result(ev_percentage=5.8)
        ev_results = [original_ev]
        above, _ = filter_picks_by_threshold(ev_results, 5.0)
        assert above[0].ev_percentage == original_ev.ev_percentage
        assert above[0].is_valid == original_ev.is_valid
