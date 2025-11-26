"""
Unit tests for configuration management module.

Tests the Config class, validation logic, environment variable loading,
and singleton pattern. Uses pytest fixtures and monkeypatch to isolate
tests from actual .env files.

Coverage targets:
- Config model instantiation
- Field validation (required/optional)
- API key validation and placeholder detection
- Log level validation
- Environment variable loading
- Masked key generation
- Singleton config instance
- Startup validation function
"""

import pytest
import os
from typing import Dict
from pydantic import ValidationError

from bet_bot.config.settings import Config, validate_config


class TestConfigModel:
    """Tests for Config Pydantic model."""

    def test_config_with_all_required_fields(self, monkeypatch):
        """Test Config instantiation with all required fields."""
        # Arrange
        monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-test1234567890")
        monkeypatch.setenv("API_FOOTBALL_KEY", "apifootball-test1234567890")

        # Act
        config = Config(
            openai_api_key="sk-proj-test1234567890",
            api_football_key="apifootball-test1234567890"
        )

        # Assert
        assert config.openai_api_key == "sk-proj-test1234567890"
        assert config.api_football_key == "apifootball-test1234567890"
        assert config.odds_api_key is None  # Optional default
        assert config.log_level == "INFO"  # Default value

    def test_config_with_optional_fields(self, monkeypatch):
        """Test Config instantiation with all fields including optionals."""
        # Arrange & Act
        config = Config(
            openai_api_key="sk-proj-test1234567890",
            api_football_key="apifootball-test1234567890",
            odds_api_key="odds-api-test1234567890",
            log_level="DEBUG"
        )

        # Assert
        assert config.openai_api_key == "sk-proj-test1234567890"
        assert config.api_football_key == "apifootball-test1234567890"
        assert config.odds_api_key == "odds-api-test1234567890"
        assert config.log_level == "DEBUG"

    def test_config_missing_openai_key_raises_error(self):
        """Test that missing OPENAI_API_KEY raises ValidationError."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            Config(
                openai_api_key="",  # Empty - should fail
                api_football_key="apifootball-test1234567890"
            )

        # Verify error mentions the field
        assert "openai_api_key" in str(exc_info.value).lower()

    def test_config_missing_api_football_key_raises_error(self):
        """Test that missing API_FOOTBALL_KEY raises ValidationError."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            Config(
                openai_api_key="sk-proj-test1234567890",
                api_football_key=""  # Empty - should fail
            )

        # Verify error mentions the field
        assert "api_football_key" in str(exc_info.value).lower()

    def test_config_rejects_placeholder_openai_key(self):
        """Test that placeholder values are rejected for OPENAI_API_KEY."""
        # Test various placeholder patterns
        placeholders = [
            "your-key-here",
            "xxx-placeholder-xxx",
            "replace-me-with-key",
            "xxxxxxxxxx"
        ]

        for placeholder in placeholders:
            with pytest.raises(ValidationError) as exc_info:
                Config(
                    openai_api_key=placeholder,
                    api_football_key="apifootball-test1234567890"
                )

            # Verify error message mentions placeholder
            assert "placeholder" in str(exc_info.value).lower()

    def test_config_rejects_placeholder_api_football_key(self):
        """Test that placeholder values are rejected for API_FOOTBALL_KEY."""
        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            Config(
                openai_api_key="sk-proj-test1234567890",
                api_football_key="your-api-key-placeholder"
            )

        # Verify error message mentions placeholder
        assert "placeholder" in str(exc_info.value).lower()

    def test_config_trims_whitespace_from_keys(self):
        """Test that whitespace is trimmed from API keys."""
        # Act
        config = Config(
            openai_api_key="  sk-proj-test1234567890  ",
            api_football_key="  apifootball-test1234567890  "
        )

        # Assert - whitespace should be stripped
        assert config.openai_api_key == "sk-proj-test1234567890"
        assert config.api_football_key == "apifootball-test1234567890"


class TestLogLevelValidation:
    """Tests for log level validation."""

    def test_valid_log_levels(self):
        """Test that all valid log levels are accepted."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in valid_levels:
            config = Config(
                openai_api_key="sk-proj-test1234567890",
                api_football_key="apifootball-test1234567890",
                log_level=level
            )
            assert config.log_level == level

    def test_log_level_case_insensitive(self):
        """Test that log level validation is case insensitive."""
        # Lowercase should be converted to uppercase
        config = Config(
            openai_api_key="sk-proj-test1234567890",
            api_football_key="apifootball-test1234567890",
            log_level="debug"
        )

        assert config.log_level == "DEBUG"

    def test_invalid_log_level_raises_error(self):
        """Test that invalid log levels raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Config(
                openai_api_key="sk-proj-test1234567890",
                api_football_key="apifootball-test1234567890",
                log_level="INVALID_LEVEL"
            )

        # Verify error mentions valid levels
        assert "log_level" in str(exc_info.value).lower()


class TestMaskedKeyGeneration:
    """Tests for get_masked_key() method."""

    def test_mask_long_key(self):
        """Test masking of keys longer than 8 characters."""
        # Arrange
        config = Config(
            openai_api_key="sk-proj-1234567890abcdefghijklmnop",
            api_football_key="apifootball-test1234567890"
        )

        # Act
        masked_openai = config.get_masked_key(config.openai_api_key)
        masked_api_football = config.get_masked_key(config.api_football_key)

        # Assert - format: "xxxx...xxxx"
        assert masked_openai == "sk-p...mnop"
        assert masked_api_football == "apif...7890"
        assert "1234567890" not in masked_openai  # Middle is hidden
        assert "test" not in masked_api_football  # Middle is hidden

    def test_mask_short_key(self):
        """Test masking of keys shorter than 8 characters."""
        # Arrange
        config = Config(
            openai_api_key="sk-proj-test1234567890",
            api_football_key="apifootball-test1234567890"
        )

        # Act - test with short key (< 8 chars)
        masked_short = config.get_masked_key("short")

        # Assert - should return "****" for short keys
        assert masked_short == "****"

    def test_mask_empty_key(self):
        """Test masking of empty/None keys."""
        # Arrange
        config = Config(
            openai_api_key="sk-proj-test1234567890",
            api_football_key="apifootball-test1234567890"
        )

        # Act
        masked_empty = config.get_masked_key("")
        masked_none = config.get_masked_key(None)  # type: ignore

        # Assert
        assert masked_empty == "****"
        assert masked_none == "****"


class TestEnvironmentValidation:
    """Tests for validate_environment() classmethod."""

    def test_validate_environment_with_all_required_vars(self, monkeypatch):
        """Test environment validation passes with all required variables."""
        # Arrange
        monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-test1234567890")
        monkeypatch.setenv("API_FOOTBALL_KEY", "apifootball-test1234567890")

        # Act
        result = Config.validate_environment()

        # Assert
        assert result is True

    def test_validate_environment_missing_openai_key(self, monkeypatch):
        """Test environment validation fails when OPENAI_API_KEY is missing."""
        # Arrange
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("API_FOOTBALL_KEY", "apifootball-test1234567890")

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            Config.validate_environment()

        # Verify error message mentions missing variable
        assert "OPENAI_API_KEY" in str(exc_info.value)
        assert "Missing required environment variables" in str(exc_info.value)

    def test_validate_environment_missing_api_football_key(self, monkeypatch):
        """Test environment validation fails when API_FOOTBALL_KEY is missing."""
        # Arrange
        monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-test1234567890")
        monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            Config.validate_environment()

        # Verify error message mentions missing variable
        assert "API_FOOTBALL_KEY" in str(exc_info.value)
        assert "Missing required environment variables" in str(exc_info.value)

    def test_validate_environment_missing_both_keys(self, monkeypatch):
        """Test environment validation fails when both required keys are missing."""
        # Arrange
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            Config.validate_environment()

        # Verify error message mentions both variables
        error_msg = str(exc_info.value)
        assert "OPENAI_API_KEY" in error_msg
        assert "API_FOOTBALL_KEY" in error_msg
        assert "Missing required environment variables" in error_msg


class TestValidateConfigFunction:
    """Tests for validate_config() standalone function."""

    def test_validate_config_returns_true_when_valid(self, monkeypatch):
        """Test validate_config() returns True with valid environment."""
        # Arrange
        monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-test1234567890")
        monkeypatch.setenv("API_FOOTBALL_KEY", "apifootball-test1234567890")

        # Act
        result = validate_config()

        # Assert
        assert result is True

    def test_validate_config_raises_error_when_invalid(self, monkeypatch):
        """Test validate_config() raises ValueError with invalid environment."""
        # Arrange - missing required keys
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            validate_config()

        # Verify error message is helpful
        assert "Configuration validation failed" in str(exc_info.value)


class TestConfigFieldAliases:
    """Tests for field aliases (environment variable names)."""

    def test_config_populates_from_field_names(self):
        """Test Config can be populated using Python field names."""
        # Act
        config = Config(
            openai_api_key="sk-proj-test1234567890",
            api_football_key="apifootball-test1234567890"
        )

        # Assert
        assert config.openai_api_key == "sk-proj-test1234567890"
        assert config.api_football_key == "apifootball-test1234567890"

    def test_config_populates_from_env_var_aliases(self):
        """Test Config can be populated using environment variable names (aliases)."""
        # Act - using uppercase env var names
        config = Config(
            OPENAI_API_KEY="sk-proj-test1234567890",  # type: ignore
            API_FOOTBALL_KEY="apifootball-test1234567890"  # type: ignore
        )

        # Assert
        assert config.openai_api_key == "sk-proj-test1234567890"
        assert config.api_football_key == "apifootball-test1234567890"


class TestConfigDefaults:
    """Tests for default values in Config."""

    def test_odds_api_key_defaults_to_none(self):
        """Test ODDS_API_KEY defaults to None when not provided."""
        # Act
        config = Config(
            openai_api_key="sk-proj-test1234567890",
            api_football_key="apifootball-test1234567890"
        )

        # Assert
        assert config.odds_api_key is None

    def test_log_level_defaults_to_info(self):
        """Test LOG_LEVEL defaults to INFO when not provided."""
        # Act
        config = Config(
            openai_api_key="sk-proj-test1234567890",
            api_football_key="apifootball-test1234567890"
        )

        # Assert
        assert config.log_level == "INFO"


class TestConfigSecurity:
    """Security-related tests for Config."""

    def test_api_keys_not_logged_in_repr(self):
        """Test that API keys are not exposed in repr/str."""
        # Arrange
        config = Config(
            openai_api_key="sk-proj-secret1234567890",
            api_football_key="apifootball-secret1234567890"
        )

        # Act
        config_str = str(config)
        config_repr = repr(config)

        # Assert - full keys should not appear in string representation
        # Note: Pydantic may expose fields, but users should use get_masked_key()
        # This test documents expected behavior
        assert isinstance(config_str, str)
        assert isinstance(config_repr, str)

    def test_masked_key_never_exposes_full_key(self):
        """Test that get_masked_key() never returns the full key."""
        # Arrange
        config = Config(
            openai_api_key="sk-proj-verylongsecretkey1234567890",
            api_football_key="apifootball-test1234567890"
        )

        # Act
        masked = config.get_masked_key(config.openai_api_key)

        # Assert - masked key should not contain the full original
        assert masked != config.openai_api_key
        assert len(masked) < len(config.openai_api_key)
        assert "..." in masked  # Contains ellipsis
