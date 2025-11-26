"""
Pydantic models for bet-bot application.

This module provides all data models used throughout the application
for type safety, validation, and structured data handling.

Models are organized by domain:
- fixtures: Fixture, Team, League (match and team data)
- form: TeamForm, RecentResult (performance tracking)
- injuries: InjuredPlayer, Injury (player availability)
- odds: Market, Odds (bookmaker odds data)
- analysis: AIAnalysis, MarketAnalysis, Pick (AI output and recommendations)

Usage:
    from bet_bot.models import Fixture, Team, AIAnalysis, Pick

    # Create a fixture
    fixture = Fixture(
        fixture_id="548821",
        kickoff_time=datetime.utcnow(),
        home_team=home_team,
        away_team=away_team,
        league=league
    )

    # Create a pick
    pick = Pick(
        fixture_id="548821",
        market="match_result_home",
        ai_probability=0.58,
        implied_probability=0.476,
        ev_percentage=5.8,
        confidence=72,
        recommended_stake=25.0,
        suggested_odds=2.10
    )
"""

# Fixture models
# Analysis models
from bet_bot.models.analysis import AIAnalysis, MarketAnalysis, Pick
from bet_bot.models.fixtures import Fixture, League, Team

# Form models
from bet_bot.models.form import RecentResult, TeamForm

# Injury models
from bet_bot.models.injuries import InjuredPlayer, Injury

# Odds models
from bet_bot.models.odds import Market, Odds

# Export all models
__all__ = [
    # Fixture models
    "Fixture",
    "Team",
    "League",
    # Form models
    "TeamForm",
    "RecentResult",
    # Injury models
    "InjuredPlayer",
    "Injury",
    # Odds models
    "Odds",
    "Market",
    # Analysis models
    "AIAnalysis",
    "MarketAnalysis",
    "Pick",
]
