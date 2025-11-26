"""
AI analysis Pydantic models for bet-bot application.

This module defines models for OpenAI analysis output and final betting picks.
These models represent the core output of the AI probability estimation pipeline.

Models:
    MarketAnalysis: AI probability estimate for a single betting market
    AIAnalysis: Complete AI analysis for a fixture across all markets
    Pick: Final betting recommendation with EV, confidence, and stake sizing

Usage:
    from bet_bot.models import AIAnalysis, MarketAnalysis, Pick

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

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MarketAnalysis(BaseModel):
    """
    AI probability estimate for a single betting market.

    Attributes:
        market_type: Type of betting market analyzed
        ai_probability: AI-estimated probability of outcome (0.0-1.0)
        reasoning: Explanation for the probability estimate
        confidence: Confidence score for this estimate (0-100)

    Example:
        >>> analysis = MarketAnalysis(
        ...     market_type="match_result",
        ...     ai_probability=0.58,
        ...     reasoning="Leeds showing strong home form (60% win rate)...",
        ...     confidence=75
        ... )
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        use_enum_values=True
    )

    market_type: str = Field(
        ...,
        description="Type of betting market analyzed (e.g., match_result, total_goals)",
        min_length=1
    )

    ai_probability: float = Field(
        ...,
        description="AI-estimated probability of outcome (0.0-1.0)",
        ge=0.0,
        le=1.0
    )

    reasoning: str = Field(
        ...,
        description="Explanation for the probability estimate",
        min_length=1
    )

    confidence: int = Field(
        ...,
        description="Confidence score for this estimate (0-100)",
        ge=0,
        le=100
    )

    @field_validator("market_type", "reasoning")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate string fields are not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class AIAnalysis(BaseModel):
    """
    Complete AI analysis for a fixture across all markets.

    This model represents the output from OpenAI GPT-4 analysis.
    Contains probability estimates for multiple betting markets.

    Attributes:
        fixture_id: Unique identifier for the fixture
        markets: List of market probability estimates
        analysis_timestamp: When this analysis was performed (ISO 8601)

    Example:
        >>> analysis = AIAnalysis(
        ...     fixture_id="548821",
        ...     markets=[market1, market2, market3],
        ...     analysis_timestamp=datetime.utcnow()
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

    markets: list[MarketAnalysis] = Field(
        default_factory=list,
        description="List of market probability estimates"
    )

    analysis_timestamp: datetime = Field(
        ...,
        description="When this analysis was performed (ISO 8601 format)"
    )

    @field_validator("fixture_id")
    @classmethod
    def validate_fixture_id(cls, v: str) -> str:
        """Validate fixture ID is not empty."""
        if not v or not v.strip():
            raise ValueError("fixture_id cannot be empty")
        return v.strip()


class Pick(BaseModel):
    """
    Final betting recommendation with EV, confidence, and stake sizing.

    This is the ultimate output shown to the user. Represents a single
    betting opportunity that meets the EV threshold (typically > 5%).

    Attributes:
        fixture_id: Unique identifier for the fixture
        market: Specific market and outcome being recommended
        ai_probability: AI-estimated probability of outcome (0.0-1.0)
        implied_probability: Probability implied by bookmaker odds (0.0-1.0)
        ev_percentage: Expected value as percentage (can be negative)
        confidence: Overall confidence score (0-100)
        recommended_stake: Suggested bet amount in currency units
        suggested_odds: Decimal odds for this pick

    Example:
        >>> pick = Pick(
        ...     fixture_id="548821",
        ...     market="match_result_home",
        ...     ai_probability=0.58,
        ...     implied_probability=0.476,
        ...     ev_percentage=5.8,
        ...     confidence=72,
        ...     recommended_stake=25.0,
        ...     suggested_odds=2.10
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

    market: str = Field(
        ...,
        description="Specific market and outcome being recommended",
        min_length=1
    )

    ai_probability: float = Field(
        ...,
        description="AI-estimated probability of outcome (0.0-1.0)",
        ge=0.0,
        le=1.0
    )

    implied_probability: float = Field(
        ...,
        description="Probability implied by bookmaker odds (0.0-1.0)",
        ge=0.0,
        le=1.0
    )

    ev_percentage: float = Field(
        ...,
        description="Expected value as percentage (can be negative)"
    )

    confidence: int = Field(
        ...,
        description="Overall confidence score (0-100)",
        ge=0,
        le=100
    )

    recommended_stake: float = Field(
        ...,
        description="Suggested bet amount in currency units",
        gt=0.0
    )

    suggested_odds: float = Field(
        ...,
        description="Decimal odds for this pick",
        ge=1.0
    )

    @field_validator("fixture_id", "market")
    @classmethod
    def validate_non_empty_strings(cls, v: str) -> str:
        """Validate string fields are not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()
