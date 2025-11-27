"""
Fixture-related Pydantic models for bet-bot application.

This module defines models for football fixtures, teams, and leagues.
All models use Pydantic v2 for validation and type safety.

Models:
    League: Football league/competition information
    Team: Team details with form and injury data
    Fixture: Complete match fixture with teams, league, and odds

Usage:
    from bet_bot.models import Fixture, Team, League

    fixture = Fixture(
        fixture_id="548821",
        kickoff_time="2025-11-24T15:00:00Z",
        home_team=team_home,
        away_team=team_away,
        league=league,
        odds={"match_result": {"home": 2.10, "draw": 3.50, "away": 3.20}}
    )
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class League(BaseModel):
    """
    Football league/competition information.

    Attributes:
        league_id: Unique identifier for the league
        league_name: Display name of the league
        league_country: Country where the league operates
        league_season: Current season year

    Example:
        >>> league = League(
        ...     league_id="39",
        ...     league_name="Championship",
        ...     league_country="England",
        ...     league_season=2025
        ... )
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        use_enum_values=True
    )

    league_id: str = Field(
        ...,
        description="Unique identifier for the league",
        min_length=1
    )

    league_name: str = Field(
        ...,
        description="Display name of the league",
        min_length=1
    )

    league_country: str = Field(
        ...,
        description="Country where the league operates",
        min_length=1
    )

    league_season: int = Field(
        ...,
        description="Current season year",
        ge=2000,
        le=2100
    )

    @field_validator("league_id", "league_name", "league_country")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate string fields are not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class Team(BaseModel):
    """
    Football team with form data and injuries.

    Attributes:
        id: Unique identifier for the team
        name: Display name of the team
        form_5_games: Recent form (last 5 games) as W/D/L array
        avg_goals_for: Average goals scored per game
        avg_goals_against: Average goals conceded per game
        injuries: List of injured player IDs (reference to InjuredPlayer model)

    Example:
        >>> team = Team(
        ...     id="123",
        ...     name="Leeds United",
        ...     form_5_games=["W", "W", "D", "L", "W"],
        ...     avg_goals_for=1.8,
        ...     avg_goals_against=1.2,
        ...     injuries=["5001", "5002"]
        ... )
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        use_enum_values=True
    )

    id: str = Field(
        ...,
        description="Unique identifier for the team",
        min_length=1
    )

    name: str = Field(
        ...,
        description="Display name of the team",
        min_length=1
    )

    form_5_games: list[str] = Field(
        default_factory=list,
        description="Recent form (last 5 games) as W/D/L array",
        max_length=5
    )

    avg_goals_for: float = Field(
        default=0.0,
        description="Average goals scored per game",
        ge=0.0
    )

    avg_goals_against: float = Field(
        default=0.0,
        description="Average goals conceded per game",
        ge=0.0
    )

    injuries: list[str] = Field(
        default_factory=list,
        description="List of injured player IDs (reference to InjuredPlayer model)"
    )

    @field_validator("id", "name")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate string fields are not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("form_5_games")
    @classmethod
    def validate_form_results(cls, v: list[str]) -> list[str]:
        """Validate form results are W/D/L only."""
        valid_results = {"W", "D", "L"}
        for result in v:
            if result not in valid_results:
                raise ValueError(f"Form result must be W, D, or L. Got: {result}")
        return v


class Fixture(BaseModel):
    """
    Complete match fixture with teams, league, and odds.

    This is the core data structure representing a single football match.
    Used throughout the pipeline for data normalization, OpenAI analysis input,
    and pick output.

    API Mapping:
        This is a DOMAIN MODEL populated by the consolidation layer, not a raw API response model.
        Field aliases fixture_id and kickoff_time map directly to API-Football:
        - fixture_id aliases "fixture.id" from API response
        - kickoff_time aliases "fixture.date" from API response

        Team and League objects must be constructed manually from nested API structures
        (teams.home, teams.away, league) by the consolidation layer before creating
        Fixture instances. See: src/bet_bot/data/consolidation/normalizer.py

    Attributes:
        fixture_id: Unique identifier for the fixture
        kickoff_time: Match kickoff time (ISO 8601 format with timezone)
        home_team: Home team details
        away_team: Away team details
        league: League information
        odds: Odds data organized by market type
        head_to_head_history: List of past results between these teams

    Example:
        >>> fixture = Fixture(
        ...     fixture_id="548821",
        ...     kickoff_time=datetime.fromisoformat("2025-11-24T15:00:00+00:00"),
        ...     home_team=team_home,
        ...     away_team=team_away,
        ...     league=league,
        ...     odds={
        ...         "match_result": {"home": 2.10, "draw": 3.50, "away": 3.20},
        ...         "total_goals": {"over_2_5": 1.85, "under_2_5": 1.95}
        ...     },
        ...     head_to_head_history=["W", "D", "W", "L", "W"]
        ... )
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        use_enum_values=True
    )

    fixture_id: str = Field(
        ...,
        alias="fixture.id",
        description="Unique identifier for the fixture",
        min_length=1
    )

    kickoff_time: datetime = Field(
        ...,
        alias="fixture.date",
        description="Match kickoff time (ISO 8601 format with timezone)"
    )

    home_team: Team = Field(
        ...,
        description="Home team details"
    )

    away_team: Team = Field(
        ...,
        description="Away team details"
    )

    league: League = Field(
        ...,
        description="League information"
    )

    odds: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Odds data organized by market type (e.g., match_result, total_goals)"
    )

    head_to_head_history: list[str] = Field(
        default_factory=list,
        description="List of past results between these teams (W/D/L from home perspective)",
        max_length=5
    )

    ai_analysis: Any = Field(
        default=None,
        description="AI analysis results from OpenAI (attached by Story 4.2). Type: AIAnalysis | None"
    )

    ev_results: Any = Field(
        default=None,
        description="EV calculation results from Story 5.1. Type: list[EVResult] | None"
    )

    error_message: str | None = Field(
        default=None,
        description="Error message if analysis failed (set by Story 4.2 on failure)"
    )

    form_last_updated: datetime | None = Field(
        default=None,
        description="Timestamp when team form data was last fetched (Story 2.3, 3.1). Used by Story 5.3 for confidence scoring."
    )

    injuries_last_checked: datetime | None = Field(
        default=None,
        description="Timestamp when injury data was last fetched (Story 2.2, 3.1). Used by Story 5.3 for confidence scoring."
    )

    odds_timestamp: datetime | None = Field(
        default=None,
        description="Timestamp when odds were last fetched (Story 2.4, 3.1). Used by Story 5.3 for confidence scoring."
    )

    @field_validator("fixture_id")
    @classmethod
    def validate_fixture_id(cls, v: str) -> str:
        """Validate fixture ID is not empty."""
        if not v or not v.strip():
            raise ValueError("fixture_id cannot be empty")
        return v.strip()

    @field_validator("home_team", "away_team")
    @classmethod
    def validate_teams_different(cls, v: Team, info: ValidationInfo) -> Team:
        """Validate home and away teams are different entities."""
        # Only validate after both teams are set
        if info.data.get("home_team") and info.field_name == "away_team":
            home_team = info.data["home_team"]
            if v.id == home_team.id:
                raise ValueError(
                    f"Home team and away team cannot be the same (both have id: {v.id})"
                )
        return v

    @field_validator("head_to_head_history")
    @classmethod
    def validate_h2h_results(cls, v: list[str]) -> list[str]:
        """Validate head-to-head results are W/D/L only."""
        valid_results = {"W", "D", "L"}
        for result in v:
            if result not in valid_results:
                raise ValueError(f"H2H result must be W, D, or L. Got: {result}")
        return v
