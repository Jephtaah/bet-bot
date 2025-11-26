"""
Odds Pydantic models for bet-bot application.

This module defines models for bookmaker odds across different betting markets.
Odds data is critical for calculating expected value and identifying edges.

Models:
    Market: Individual betting market with odds for each outcome
    Odds: Complete odds data for a fixture from a bookmaker

Usage:
    from bet_bot.models import Market, Odds

    odds = Odds(
        fixture_id="548821",
        bookmaker_name="Pinnacle",
        odds_updated_at=datetime.utcnow(),
        markets=[market1, market2]
    )
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Market(BaseModel):
    """
    Individual betting market with odds for each outcome.

    Markets include:
    - match_result: Home win, Draw, Away win
    - total_goals: Over/Under 2.5, 3.5 goals
    - corners: Over/Under 9.5 corners
    - cards: Over/Under 4.5 cards

    Attributes:
        market_type: Type of betting market
        odds: Mapping of outcome to decimal odds (e.g., {"home": 2.10, "draw": 3.50})

    Example:
        >>> market = Market(
        ...     market_type="match_result",
        ...     odds={"home": 2.10, "draw": 3.50, "away": 3.20}
        ... )
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        use_enum_values=True
    )

    market_type: str = Field(
        ...,
        description="Type of betting market (e.g., match_result, total_goals, corners, cards)",
        min_length=1
    )

    odds: dict[str, float] = Field(
        default_factory=dict,
        description="Mapping of outcome to decimal odds (e.g., {'home': 2.10, 'draw': 3.50})"
    )

    @field_validator("market_type")
    @classmethod
    def validate_market_type(cls, v: str) -> str:
        """Validate market type is not empty."""
        if not v or not v.strip():
            raise ValueError("market_type cannot be empty")
        return v.strip()

    @field_validator("odds")
    @classmethod
    def validate_odds_values(cls, v: dict[str, float]) -> dict[str, float]:
        """
        Validate all odds are >= 1.0.

        Bookmakers never offer odds below 1.0 (would guarantee loss).
        """
        for outcome, odds_value in v.items():
            if odds_value < 1.0:
                raise ValueError(
                    f"Odds must be >= 1.0. Got {odds_value} for outcome: {outcome}"
                )
        return v


class Odds(BaseModel):
    """
    Complete odds data for a fixture from a bookmaker.

    Odds freshness requirement: < 1 hour old for analysis.
    Stale odds (> 1 hour) should be rejected to prevent betting on outdated lines.

    Attributes:
        fixture_id: Unique identifier for the fixture
        bookmaker_name: Name of the bookmaker providing these odds
        odds_updated_at: Timestamp when odds were last updated (ISO 8601)
        markets: List of betting markets with odds

    Example:
        >>> odds = Odds(
        ...     fixture_id="548821",
        ...     bookmaker_name="Pinnacle",
        ...     odds_updated_at=datetime.fromisoformat("2025-11-24T14:30:00+00:00"),
        ...     markets=[
        ...         Market(market_type="match_result", odds={"home": 2.10, "draw": 3.50, "away": 3.20}),
        ...         Market(market_type="total_goals", odds={"over_2_5": 1.85, "under_2_5": 1.95})
        ...     ]
        ... )
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        use_enum_values=True
    )

    fixture_id: str = Field(
        ...,
        description="Unique identifier for the fixture",
        min_length=1
    )

    bookmaker_name: str = Field(
        ...,
        description="Name of the bookmaker providing these odds",
        min_length=1
    )

    odds_updated_at: datetime = Field(
        ...,
        description="Timestamp when odds were last updated (ISO 8601 format)"
    )

    markets: list[Market] = Field(
        default_factory=list,
        description="List of betting markets with odds"
    )

    @field_validator("fixture_id", "bookmaker_name")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate string fields are not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()
