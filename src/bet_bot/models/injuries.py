"""
Injury and suspension Pydantic models for bet-bot application.

This module defines models for tracking player availability due to injuries
and suspensions. Injury data is critical for AI analysis to assess team strength.

Models:
    InjuredPlayer: Individual player injury/suspension status
    Injury: Team-level injury summary with impact assessment

Usage:
    from bet_bot.models import InjuredPlayer, Injury

    injury = Injury(
        team_id="123",
        injured_players=[player1, player2],
        missing_key_players_count=2,
        missing_key_players_list=["Patrick Bamford", "Luke Ayling"]
    )
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InjuredPlayer(BaseModel):
    """
    Individual player injury/suspension status.

    Attributes:
        player_id: Unique identifier for the player
        player_name: Display name of the player
        position: Player position (Forward/Midfielder/Defender/Goalkeeper)
        injury_status: Current status (Doubt/Injured/Suspended/Out)
        impact_severity: Impact on team strength (Key/Moderate/Minor)
        injury_type: Type of injury (optional)
        expected_return: Expected return date (optional)

    Example:
        >>> player = InjuredPlayer(
        ...     player_id="5001",
        ...     player_name="Patrick Bamford",
        ...     position="Forward",
        ...     injury_status="Doubt",
        ...     impact_severity="Key"
        ... )
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        use_enum_values=True
    )

    player_id: str = Field(
        ...,
        description="Unique identifier for the player",
        min_length=1
    )

    player_name: str = Field(
        ...,
        description="Display name of the player",
        min_length=1
    )

    position: str = Field(
        ...,
        description="Player position (Forward/Midfielder/Defender/Goalkeeper)",
        min_length=1
    )

    injury_status: str = Field(
        ...,
        description="Current status (Doubt/Injured/Suspended/Out)",
        min_length=1
    )

    impact_severity: str = Field(
        ...,
        description="Impact on team strength (Key/Moderate/Minor)",
        min_length=1
    )

    injury_type: str | None = Field(
        default=None,
        description="Type of injury (e.g., Muscle, Fracture, Suspension)"
    )

    expected_return: datetime | None = Field(
        default=None,
        description="Expected return date (ISO 8601 format)"
    )

    @field_validator("player_id", "player_name")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate string fields are not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("position")
    @classmethod
    def validate_position(cls, v: str) -> str:
        """Validate position is one of the allowed values."""
        valid_positions = {"Forward", "Midfielder", "Defender", "Goalkeeper"}
        if v not in valid_positions:
            raise ValueError(
                f"Position must be one of {valid_positions}. Got: {v}"
            )
        return v

    @field_validator("injury_status")
    @classmethod
    def validate_injury_status(cls, v: str) -> str:
        """Validate injury status is one of the allowed values."""
        valid_statuses = {"Doubt", "Injured", "Suspended", "Out"}
        if v not in valid_statuses:
            raise ValueError(
                f"Injury status must be one of {valid_statuses}. Got: {v}"
            )
        return v

    @field_validator("impact_severity")
    @classmethod
    def validate_impact_severity(cls, v: str) -> str:
        """Validate impact severity is one of the allowed values."""
        valid_severities = {"Key", "Moderate", "Minor"}
        if v not in valid_severities:
            raise ValueError(
                f"Impact severity must be one of {valid_severities}. Got: {v}"
            )
        return v


class Injury(BaseModel):
    """
    Team-level injury summary with impact assessment.

    This model aggregates injury data for a team to inform AI analysis.
    Injury data freshness requirement: < 12 hours old.

    Attributes:
        team_id: Unique identifier for the team
        injured_players: List of injured/suspended players
        missing_key_players_count: Number of key players unavailable
        missing_key_players_list: Names of key players unavailable

    Example:
        >>> injury = Injury(
        ...     team_id="123",
        ...     injured_players=[player1, player2],
        ...     missing_key_players_count=2,
        ...     missing_key_players_list=["Patrick Bamford", "Luke Ayling"]
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

    injured_players: list[InjuredPlayer] = Field(
        default_factory=list,
        description="List of injured/suspended players"
    )

    missing_key_players_count: int = Field(
        default=0,
        description="Number of key players unavailable",
        ge=0
    )

    missing_key_players_list: list[str] = Field(
        default_factory=list,
        description="Names of key players unavailable"
    )

    @field_validator("team_id")
    @classmethod
    def validate_team_id(cls, v: str) -> str:
        """Validate team ID is not empty."""
        if not v or not v.strip():
            raise ValueError("team_id cannot be empty")
        return v.strip()
