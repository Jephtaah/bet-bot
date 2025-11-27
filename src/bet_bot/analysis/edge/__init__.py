"""
Edge detection module for bet-bot.

This package provides edge detection capabilities: EV calculation, threshold filtering,
and confidence scoring for identifying positive EV betting opportunities.

Modules:
- ev_calculator: Calculate expected value and extract EV results
- threshold_filter: Filter EV results by threshold (Story 5.2)
- confidence_scorer: Score data quality for confidence (Story 5.3)

Main exports from ev_calculator (Story 5.1):
- EVResult: Pydantic model for single EV calculation
- calculate_ev: Core EV calculation function
- calculate_implied_probability: Implied probability from odds
- calculate_all_evs: Batch processing async function
- filter_evs_by_threshold: Threshold filtering helper

Exports from threshold_filter (Story 5.2):
- PickCategory: Enum for pick classification (RECOMMENDED, MARGINAL, LOW, INVALID)
- FilteredPick: Pydantic model for categorized pick with reasoning
- filter_picks_by_threshold: Separate picks by threshold
- categorize_picks: Categorize picks into 4 buckets
- apply_threshold_filter: Batch orchestration

Exports from confidence_scorer (Story 5.3):
- ConfidenceScoreBreakdown: Pydantic model for confidence scoring result
- calculate_base_score: Return baseline confidence (75%)
- score_form_freshness: Score form data age
- score_injury_freshness: Score injury data availability
- score_odds_freshness: Score odds data age
- score_form_sample_size: Score form sample size
- score_pick: Single pick confidence scoring
- apply_confidence_scoring: Batch confidence scoring

Usage:
    from bet_bot.analysis.edge import (
        EVResult, calculate_all_evs, PickCategory, apply_threshold_filter,
        ConfidenceScoreBreakdown, score_pick, apply_confidence_scoring
    )
"""

from bet_bot.analysis.edge.ev_calculator import (
    EVResult,
    calculate_all_evs,
    calculate_ev,
    calculate_ev_percentage,
    calculate_implied_probability,
    filter_evs_by_threshold,
)
from bet_bot.analysis.edge.threshold_filter import (
    FilteredPick,
    PickCategory,
    apply_threshold_filter,
    categorize_picks,
    filter_picks_by_threshold,
)
from bet_bot.analysis.edge.confidence_scorer import (
    ConfidenceScoreBreakdown,
    apply_confidence_scoring,
    calculate_base_score,
    score_form_freshness,
    score_form_sample_size,
    score_injury_freshness,
    score_odds_freshness,
    score_pick,
)

__all__ = [
    "EVResult",
    "calculate_ev",
    "calculate_implied_probability",
    "calculate_ev_percentage",
    "calculate_all_evs",
    "filter_evs_by_threshold",
    "PickCategory",
    "FilteredPick",
    "filter_picks_by_threshold",
    "categorize_picks",
    "apply_threshold_filter",
    "ConfidenceScoreBreakdown",
    "calculate_base_score",
    "score_form_freshness",
    "score_injury_freshness",
    "score_odds_freshness",
    "score_form_sample_size",
    "score_pick",
    "apply_confidence_scoring",
]
