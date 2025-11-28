"""
Edge detection module for bet-bot.

This package provides complete edge detection pipeline: EV calculation, threshold filtering,
confidence scoring, and orchestration for identifying positive EV betting opportunities.

Modules:
- pipeline: Orchestrate complete edge detection pipeline (Story 5.4)
- ev_calculator: Calculate expected value and extract EV results (Story 5.1)
- threshold_filter: Filter EV results by threshold (Story 5.2)
- confidence_scorer: Score data quality for confidence (Story 5.3)

Main entry point (Story 5.4):
- detect_edges(fixtures, bankroll) -> list[Pick] | str: Complete pipeline orchestrator

Exports from ev_calculator (Story 5.1):
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
    from bet_bot.analysis.edge import detect_edges, EVResult, PickCategory, ConfidenceScoreBreakdown

    # Orchestrate complete pipeline
    picks = await detect_edges(
        fixtures=fixtures_with_ai_analysis,
        bankroll=1000.0
    )

    if isinstance(picks, str):
        print(picks)  # NO_PICKS message
    else:
        for pick in picks:
            print(f"{pick.market}: +{pick.ev_percentage:.1f}% EV @ {pick.suggested_odds}")
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
from bet_bot.analysis.edge.pipeline import detect_edges

__all__ = [
    # Pipeline orchestrator (Story 5.4)
    "detect_edges",
    # EV Calculator exports (Story 5.1)
    "EVResult",
    "calculate_ev",
    "calculate_implied_probability",
    "calculate_ev_percentage",
    "calculate_all_evs",
    "filter_evs_by_threshold",
    # Threshold Filter exports (Story 5.2)
    "PickCategory",
    "FilteredPick",
    "filter_picks_by_threshold",
    "categorize_picks",
    "apply_threshold_filter",
    # Confidence Scorer exports (Story 5.3)
    "ConfidenceScoreBreakdown",
    "calculate_base_score",
    "score_form_freshness",
    "score_injury_freshness",
    "score_odds_freshness",
    "score_form_sample_size",
    "score_pick",
    "apply_confidence_scoring",
]
