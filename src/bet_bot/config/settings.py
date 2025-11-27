"""
Configuration settings for bet-bot application.

This module defines the application configuration using Pydantic for validation.
All settings are loaded from environment variables via python-dotenv.

Security Notes:
- API keys are NEVER hardcoded - always loaded from environment
- Use get_masked_key() for safe logging (never log full keys)
- Validation runs at startup to catch missing required keys early

Usage:
    from bet_bot.config import config

    # Access configuration
    api_key = config.openai_api_key

    # Safe logging
    print(f"Using key: {config.get_masked_key(config.openai_api_key)}")
"""

import os

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

# Load environment variables from .env file at module import time
load_dotenv()


class Config(BaseModel):
    """
    Application configuration loaded from environment variables.

    This class uses Pydantic for automatic validation and type checking.
    All API keys must be non-empty strings. Optional settings have defaults.

    Required Environment Variables:
        OPENAI_API_KEY: OpenAI API key for AI analysis
        API_FOOTBALL_KEY: API-Football key for fixtures/odds/injuries

    Optional Environment Variables:
        ODDS_API_KEY: Odds-API key (backup odds source)
        LOG_LEVEL: Logging level (default: INFO)

    Raises:
        ValueError: If required environment variables are missing or invalid
    """

    model_config = ConfigDict(
        # Allow using field names or environment variable names
        populate_by_name=True,
        # Validate on assignment
        validate_assignment=True,
        # Use enum values
        use_enum_values=True
    )

    # Required API keys
    openai_api_key: str = Field(
        ...,  # Required (no default)
        alias="OPENAI_API_KEY",
        description="OpenAI API key for GPT-4 analysis",
        min_length=1
    )

    api_football_key: str = Field(
        ...,  # Required (no default)
        alias="API_FOOTBALL_KEY",
        description="API-Football key for fixtures and team data",
        min_length=1
    )

    # Optional settings with defaults
    odds_api_key: str | None = Field(
        default=None,
        alias="ODDS_API_KEY",
        description="Odds-API key for backup odds source (optional)"
    )

    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    # OpenAI-specific settings
    openai_model: str = Field(
        default="gpt-3.5-turbo",
        alias="OPENAI_MODEL",
        description="OpenAI model to use (gpt-3.5-turbo or gpt-4)"
    )

    openai_timeout_seconds: int = Field(
        default=30,
        alias="OPENAI_TIMEOUT_SECONDS",
        description="Timeout for OpenAI API calls (seconds)",
        ge=5,
        le=120
    )

    openai_max_retries: int = Field(
        default=3,
        alias="OPENAI_MAX_RETRIES",
        description="Maximum retry attempts for transient OpenAI errors",
        ge=1,
        le=10
    )

    openai_cost_threshold: float = Field(
        default=5.0,
        alias="OPENAI_COST_THRESHOLD",
        description="Cost threshold warning for single run (USD)",
        ge=0.01,
        le=100.0
    )

    @field_validator("openai_api_key", "api_football_key")
    @classmethod
    def validate_required_keys(cls, v: str, info: ValidationInfo) -> str:
        """
        Validate required API keys are not empty or placeholder values.

        Args:
            v: The field value to validate
            info: Validation context with field name

        Returns:
            The validated value

        Raises:
            ValueError: If key is empty or contains placeholder text
        """
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty")

        # Check for obvious placeholder values
        placeholder_indicators = ["xxx", "your-key", "placeholder", "replace-me"]
        if any(indicator in v.lower() for indicator in placeholder_indicators):
            raise ValueError(
                f"{info.field_name} appears to be a placeholder. "
                f"Please set a valid API key in your .env file."
            )

        return v.strip()

    @field_validator("openai_model")
    @classmethod
    def validate_openai_model(cls, v: str) -> str:
        """
        Validate OpenAI model is a supported option.

        Args:
            v: The model name

        Returns:
            The validated model name

        Raises:
            ValueError: If model is not supported
        """
        valid_models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]
        v_lower = v.lower()

        if v_lower not in valid_models:
            raise ValueError(
                f"openai_model must be one of {valid_models}, got: {v}"
            )

        return v_lower

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """
        Validate log level is a recognized logging level.

        Args:
            v: The log level string

        Returns:
            The validated log level in uppercase

        Raises:
            ValueError: If log level is not recognized
        """
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()

        if v_upper not in valid_levels:
            raise ValueError(
                f"log_level must be one of {valid_levels}, got: {v}"
            )

        return v_upper

    @classmethod
    def validate_environment(cls) -> bool:
        """
        Validate that all required environment variables are present.

        This method checks the environment without instantiating the Config.
        Useful for startup validation before creating the singleton instance.

        Returns:
            True if all required variables are present

        Raises:
            ValueError: If required environment variables are missing
        """
        required_vars = {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "API_FOOTBALL_KEY": os.getenv("API_FOOTBALL_KEY")
        }

        missing = [key for key, value in required_vars.items() if not value]

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                f"Please create a .env file in the project root with these variables.\n"
                f"See .env.template for an example."
            )

        return True

    def get_masked_key(self, key: str) -> str:
        """
        Return a masked version of an API key for safe logging.

        This method masks the middle portion of keys to prevent accidental
        exposure in logs while still allowing identification of which key
        is being used.

        Args:
            key: The API key to mask

        Returns:
            Masked key in format "xxxx...xxxx" or "****" for short keys

        Example:
            >>> config.get_masked_key("sk-proj-1234567890abcdef")
            "sk-p...cdef"
        """
        if not key or len(key) < 8:
            return "****"

        return f"{key[:4]}...{key[-4:]}"


def validate_config() -> bool:
    """
    Validate configuration at startup.

    This function provides a simple boolean check for configuration validity.
    It's designed to be called from CLI or application startup code.

    Returns:
        True if configuration is valid

    Raises:
        ValueError: If configuration validation fails
    """
    try:
        Config.validate_environment()
        return True
    except ValueError as e:
        raise ValueError(f"Configuration validation failed: {e}") from e


# Create singleton instance
# This will be instantiated when the module is imported
# Validation happens at instantiation time
try:
    config = Config(  # type: ignore[call-arg]
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        api_football_key=os.getenv("API_FOOTBALL_KEY", ""),
        odds_api_key=os.getenv("ODDS_API_KEY"),
        log_level=os.getenv("LOG_LEVEL", "INFO")
    )
except Exception as e:
    # If config fails to load, we want a clear error message
    # but we don't want to crash the import
    # The validate_config() function will provide proper startup validation
    config = None  # type: ignore
    _config_error = str(e)
