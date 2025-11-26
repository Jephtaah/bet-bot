"""
Team form Pydantic models for bet-bot application.

This module defines models for tracking team performance and recent results.
Form data is critical for AI analysis to assess team momentum and scoring trends.

Models:
    RecentResult: Single match result with goals and opponent
    TeamForm: Comprehensive team form data with win percentages and goal averages

Usage:
    from bet_bot.models import TeamForm, RecentResult

    form = TeamForm(
        team_id="123",
        team_name="Leeds United",
        last_5_results=["W", "W", "D", "L", "W"],
        win_percentage_5=0.60,
        goals_avg_home=1.9,
        goals_avg_away=1.7
    )
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RecentResult(BaseModel):
    """
    Single match result with goals and opponent.

    Attributes:
        result: Match result (W/D/L from team perspective)
        opponent: Opponent team name
        goals_for: Goals scored by the team
        goals_against: Goals conceded by the team
        date: Match date (ISO 8601 format)

    Example:
        >>> result = RecentResult(
        ...     result="W",
        ...     opponent="West Brom",
        ...     goals_for=2,
        ...     goals_against=1,
        ...     date=datetime.fromisoformat("2025-11-20T15:00:00+00:00")
        ... )
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        use_enum_values=True
    )

    result: str = Field(
        ...,
        description="Match result (W/D/L from team perspective)",
        min_length=1,
        max_length=1
    )

    opponent: str = Field(
        ...,
        description="Opponent team name",
        min_length=1
    )

    goals_for: int = Field(
        ...,
        description="Goals scored by the team",
        ge=0
    )

    goals_against: int = Field(
        ...,
        description="Goals conceded by the team",
        ge=0
    )

    date: datetime = Field(
        ...,
        description="Match date (ISO 8601 format)"
    )

    @field_validator("result")
    @classmethod
    def validate_result(cls, v: str) -> str:
        """Validate result is W, D, or L."""
        valid_results = {"W", "D", "L"}
        v_upper = v.upper()
        if v_upper not in valid_results:
            raise ValueError(f"Result must be W, D, or L. Got: {v}")
        return v_upper

    @field_validator("opponent")
    @classmethod
    def validate_opponent(cls, v: str) -> str:
        """Validate opponent name is not empty."""
        if not v or not v.strip():
            raise ValueError("Opponent name cannot be empty")
        return v.strip()


class TeamForm(BaseModel):
    """
    Comprehensive team form data with win percentages and goal averages.

    This model tracks recent team performance to inform AI probability estimates.
    Form data freshness requirement: < 24 hours old.

    Attributes:
        team_id: Unique identifier for the team
        team_name: Display name of the team
        last_5_results: Recent form (last 5 games) as W/D/L array
        last_10_results: Extended form (last 10 games) as W/D/L array
        win_percentage_5: Win rate over last 5 games (0.0-1.0)
        win_percentage_10: Win rate over last 10 games (0.0-1.0)
        goals_avg_home: Average goals scored at home
        goals_avg_away: Average goals scored away
        goals_against_avg_home: Average goals conceded at home
        goals_against_avg_away: Average goals conceded away

    Example:
        >>> form = TeamForm(
        ...     team_id="123",
        ...     team_name="Leeds United",
        ...     last_5_results=["W", "W", "D", "L", "W"],
        ...     last_10_results=["W", "W", "D", "L", "W", "L", "D", "W", "W", "D"],
        ...     win_percentage_5=0.60,
        ...     win_percentage_10=0.55,
        ...     goals_avg_home=1.9,
        ...     goals_avg_away=1.7,
        ...     goals_against_avg_home=1.1,
        ...     goals_against_avg_away=1.3
        ... )
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        use_enum_values=True
    )

    team_id: str = Field(
        ...,
        description="Unique identifier for the team",
        min_length=1
    )

    team_name: str = Field(
        ...,
        description="Display name of the team",
        min_length=1
    )

    last_5_results: list[str] = Field(
        default_factory=list,
        description="Recent form (last 5 games) as W/D/L array",
        max_length=5
    )

    last_10_results: list[str] = Field(
        default_factory=list,
        description="Extended form (last 10 games) as W/D/L array",
        max_length=10
    )

    win_percentage_5: float = Field(
        default=0.0,
        description="Win rate over last 5 games (0.0-1.0)",
        ge=0.0,
        le=1.0
    )

    win_percentage_10: float = Field(
        default=0.0,
        description="Win rate over last 10 games (0.0-1.0)",
        ge=0.0,
        le=1.0
    )

    goals_avg_home: float = Field(
        default=0.0,
        description="Average goals scored at home",
        ge=0.0
    )

    goals_avg_away: float = Field(
        default=0.0,
        description="Average goals scored away",
        ge=0.0
    )

    goals_against_avg_home: float = Field(
        default=0.0,
        description="Average goals conceded at home",
        ge=0.0
    )

    goals_against_avg_away: float = Field(
        default=0.0,
        description="Average goals conceded away",
        ge=0.0
    )

    @field_validator("team_id", "team_name")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate string fields are not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("last_5_results", "last_10_results")
    @classmethod
    def validate_results(cls, v: list[str]) -> list[str]:
        """Validate all results are W, D, or L."""
        valid_results = {"W", "D", "L"}
        for result in v:
            if result not in valid_results:
                raise ValueError(f"Result must be W, D, or L. Got: {result}")
        return v
