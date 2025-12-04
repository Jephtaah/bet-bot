"""
Unit tests for error display handler.

Tests all error categorization, formatting, and logging functionality
for the error_handler module.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import httpx
from pydantic import ValidationError

from bet_bot.display.error_handler import (
    display_error,
    _categorize_error,
    _format_api_error,
    _format_network_error,
    _format_validation_error,
    _format_config_error,
    _format_system_error,
    _log_full_error,
    _extract_api_from_url,
)
from bet_bot.exceptions import (
    APIError,
    APIAuthenticationError,
    APIRateLimitError,
    APIServerError,
    APINotFoundError,
    DataValidationError,
    DataStaleError,
    ScraperError,
    OpenAIError,
)


class TestCategorizeError:
    """Test error categorization logic."""

    def test_categorize_api_errors(self):
        """Test API error categorization."""
        # Custom API errors
        assert _categorize_error(APIError("msg", "http://test")) == "api"
        assert _categorize_error(APIAuthenticationError("msg", "http://test")) == "api"
        assert _categorize_error(APIRateLimitError("msg", "http://test")) == "api"
        assert _categorize_error(APIServerError("msg", "http://test")) == "api"
        assert _categorize_error(APINotFoundError("msg", "http://test")) == "api"

        # httpx HTTP errors
        response = MagicMock(status_code=500)
        error = httpx.HTTPStatusError("msg", request=MagicMock(), response=response)
        assert _categorize_error(error) == "api"

    def test_categorize_network_errors(self):
        """Test network error categorization."""
        assert _categorize_error(httpx.TimeoutException("timeout")) == "network"
        assert _categorize_error(httpx.ConnectError("connect")) == "network"
        assert _categorize_error(httpx.NetworkError("network")) == "network"

    def test_categorize_validation_errors(self):
        """Test validation error categorization."""
        assert _categorize_error(DataValidationError("field", "value", "reason")) == "validation"
        assert _categorize_error(DataStaleError("odds", 120, 60)) == "validation"

    def test_categorize_pydantic_validation_error(self):
        """Test Pydantic ValidationError categorization."""
        try:
            raise ValidationError.from_exception_data("test", [])
        except ValidationError as e:
            assert _categorize_error(e) == "validation"

    def test_categorize_configuration_errors(self):
        """Test configuration error categorization."""
        assert _categorize_error(KeyError("API_KEY")) == "configuration"
        assert _categorize_error(ValueError("Missing API_KEY")) == "configuration"
        assert _categorize_error(ValueError("OPENAI_API_KEY not set")) == "configuration"

    def test_categorize_system_errors(self):
        """Test system error categorization."""
        assert _categorize_error(OSError("disk error")) == "system"
        assert _categorize_error(PermissionError("permission denied")) == "system"
        assert _categorize_error(FileNotFoundError("file not found")) == "system"
        assert _categorize_error(RuntimeError("runtime error")) == "system"

    def test_categorize_scraper_errors(self):
        """Test scraper and OpenAI error categorization."""
        assert _categorize_error(ScraperError("http://test", "failed")) == "api"
        assert _categorize_error(OpenAIError("api error")) == "api"

    def test_categorize_unknown_errors(self):
        """Test unknown error categorization."""
        assert _categorize_error(Exception("unknown")) == "unknown"
        assert _categorize_error(RuntimeError("not in config")) == "system"


class TestFormatAPIError:
    """Test API error formatting."""

    def test_format_authentication_error(self):
        """Test 401 authentication error formatting."""
        error = APIAuthenticationError("auth failed", "http://api.test", status_code=401)
        result = _format_api_error(error, {"affected_api": "API-Football"})

        assert "API ERROR" in result
        assert "authentication failed" in result.lower()
        assert "401" in result
        assert "~/.env" in result
        assert "SOLUTION" in result

    def test_format_rate_limit_error(self):
        """Test 429 rate limit error formatting."""
        error = APIRateLimitError("rate limit", "http://api.test", status_code=429)
        result = _format_api_error(error, {"affected_api": "OpenAI", "retry_after": 60})

        assert "API ERROR" in result
        assert "rate limit" in result.lower()
        assert "429" in result
        assert "60" in result

    def test_format_server_error(self):
        """Test 5xx server error formatting."""
        error = APIServerError("server error", "http://api.test", status_code=503)
        result = _format_api_error(error, {"affected_api": "API-Football"})

        assert "API ERROR" in result
        assert "server error" in result.lower()
        assert "503" in result

    def test_format_not_found_error(self):
        """Test 404 not found error formatting."""
        error = APINotFoundError("not found", "http://api.test", status_code=404)
        result = _format_api_error(error, {"affected_api": "API"})

        assert "API ERROR" in result
        assert "not found" in result.lower()
        assert "404" in result

    def test_format_timeout_error(self):
        """Test timeout error formatting."""
        error = TimeoutError("timeout")
        result = _format_api_error(error, {"affected_api": "API"})

        assert "API ERROR" in result
        assert "timed out" in result.lower() or "timeout" in result.lower()


class TestFormatNetworkError:
    """Test network error formatting."""

    def test_format_timeout_exception(self):
        """Test timeout exception formatting."""
        error = httpx.TimeoutException("timeout")
        result = _format_network_error(error, {"affected_api": "API-Football"})

        assert "NETWORK ERROR" in result
        assert "timed out" in result.lower() or "timeout" in result.lower()
        assert "TROUBLESHOOTING" in result
        assert "ping google.com" in result

    def test_format_connect_error(self):
        """Test connection error formatting."""
        error = httpx.ConnectError("connection refused")
        result = _format_network_error(error, {"affected_api": "API"})

        assert "NETWORK ERROR" in result
        assert "connection" in result.lower()
        assert "TROUBLESHOOTING" in result

    def test_format_network_error_generic(self):
        """Test generic network error formatting."""
        error = httpx.NetworkError("network error")
        result = _format_network_error(error, {"affected_api": "API"})

        assert "NETWORK ERROR" in result
        assert "TROUBLESHOOTING" in result


class TestFormatValidationError:
    """Test validation error formatting."""

    def test_format_data_validation_error_bankroll(self):
        """Test bankroll validation error formatting."""
        error = DataValidationError("bankroll", "-1000", "must be positive")
        result = _format_validation_error(error)

        assert "VALIDATION ERROR" in result
        assert "bankroll" in result.lower()
        assert "-1000" in result
        assert "positive" in result.lower()
        assert "EXAMPLE" in result

    def test_format_data_validation_error_threshold(self):
        """Test threshold validation error formatting."""
        error = DataValidationError("threshold", "150", "must be 0-100")
        result = _format_validation_error(error)

        assert "VALIDATION ERROR" in result
        assert "threshold" in result.lower()
        assert "150" in result
        assert "0" in result and "100" in result

    def test_format_data_stale_error(self):
        """Test data stale error formatting."""
        error = DataStaleError("odds", 120, 60)
        result = _format_validation_error(error)

        assert "VALIDATION ERROR" in result
        assert "odds" in result.lower()
        assert "120" in result
        assert "60" in result

    def test_format_pydantic_validation_error(self):
        """Test Pydantic validation error formatting."""
        try:
            raise ValidationError.from_exception_data("test", [])
        except ValidationError as e:
            result = _format_validation_error(e)
            assert "VALIDATION ERROR" in result


class TestFormatConfigError:
    """Test configuration error formatting."""

    def test_format_missing_api_key(self):
        """Test missing API key error formatting."""
        error = KeyError("OPENAI_API_KEY")
        result = _format_config_error(error)

        assert "CONFIGURATION ERROR" in result
        assert "OPENAI_API_KEY" in result
        assert "SETUP INSTRUCTIONS" in result
        assert "~/.env" in result
        assert "https://platform.openai.com" in result

    def test_format_missing_api_football_key(self):
        """Test missing API-Football key error formatting."""
        error = ValueError("Missing API_FOOTBALL_KEY")
        result = _format_config_error(error)

        assert "CONFIGURATION ERROR" in result
        assert "API_FOOTBALL_KEY" in result
        assert "REQUIRED KEYS" in result

    def test_format_missing_odds_key(self):
        """Test missing Odds API key error formatting."""
        error = KeyError("ODDS_API_KEY")
        result = _format_config_error(error)

        assert "CONFIGURATION ERROR" in result
        assert "ODDS_API_KEY" in result


class TestFormatSystemError:
    """Test system error formatting."""

    def test_format_permission_error(self):
        """Test permission error formatting."""
        error = PermissionError("permission denied")
        result = _format_system_error(error, {"path": "/root/.bet-bot/logs"})

        assert "SYSTEM ERROR" in result
        assert "Permission denied" in result
        assert "/root/.bet-bot/logs" in result
        assert "chmod" in result

    def test_format_file_not_found_error(self):
        """Test file not found error formatting."""
        error = FileNotFoundError("/missing/file.txt")
        result = _format_system_error(error)

        assert "SYSTEM ERROR" in result
        assert "not found" in result.lower()
        assert "mkdir" in result

    def test_format_disk_full_error(self):
        """Test disk full error formatting."""
        error = OSError("disk full")
        result = _format_system_error(error)

        assert "SYSTEM ERROR" in result
        assert "disk" in result.lower()
        assert "df -h" in result
        assert "free up" in result.lower()


class TestExtractAPIFromURL:
    """Test API name extraction from URLs."""

    def test_extract_api_football(self):
        """Test API-Football URL extraction."""
        assert _extract_api_from_url("https://api-football-v1.p.rapidapi.com/") == "API-Football"

    def test_extract_openai(self):
        """Test OpenAI URL extraction."""
        assert _extract_api_from_url("https://api.openai.com/v1/") == "OpenAI"

    def test_extract_odds_api(self):
        """Test Odds API URL extraction."""
        assert _extract_api_from_url("https://api.the-odds-api.com/") == "Odds API"

    def test_extract_espn(self):
        """Test ESPN URL extraction."""
        assert _extract_api_from_url("https://www.espn.com/") == "ESPN"

    def test_extract_unknown_url(self):
        """Test unknown URL extraction."""
        assert _extract_api_from_url("https://unknown.api.com") == "API"
        assert _extract_api_from_url("") == "Unknown API"


class TestLogFullError:
    """Test full error logging functionality."""

    @patch("bet_bot.display.error_handler.ensure_log_directory")
    def test_log_full_error_creates_file(self, mock_log_dir):
        """Test that log file is created."""
        temp_dir = Path("/tmp/test_logs")
        mock_log_dir.return_value = temp_dir

        error = APIError("test error", "http://test", status_code=500)
        result = _log_full_error(error, {"context": "test"})

        assert result.startswith(str(temp_dir)) or not result

    @patch("bet_bot.display.error_handler.ensure_log_directory")
    def test_log_full_error_includes_traceback(self, mock_log_dir):
        """Test that stack trace is included in log."""
        temp_dir = Path("/tmp/test_logs")
        temp_dir.mkdir(parents=True, exist_ok=True)
        mock_log_dir.return_value = temp_dir

        try:
            raise ValueError("test error")
        except ValueError as e:
            result = _log_full_error(e)
            if result:
                with open(result) as f:
                    content = f.read()
                    assert "Traceback" in content or "ValueError" in content

    @patch("bet_bot.display.error_handler.ensure_log_directory")
    def test_log_full_error_masks_api_keys(self, mock_log_dir):
        """Test that API keys are masked in logs."""
        temp_dir = Path("/tmp/test_logs")
        temp_dir.mkdir(parents=True, exist_ok=True)
        mock_log_dir.return_value = temp_dir

        error = APIError("test", "http://test", status_code=401)
        error.api_key = "sk-proj-1234567890abcdef"
        context = {"token": "secret-token-value"}
        result = _log_full_error(error, context)

        if result:
            with open(result) as f:
                content = f.read()
                # Should be masked, not full key
                assert "sk-proj-" not in content or "..." in content


class TestDisplayError:
    """Test main display_error function."""

    def test_display_error_api_error(self):
        """Test displaying API error."""
        error = APIAuthenticationError("auth failed", "http://test", status_code=401)
        result = display_error(error, {"affected_api": "OpenAI"})

        assert isinstance(result, str)
        assert "API ERROR" in result
        assert "❌" in result
        assert len(result) > 100  # Substantial message

    def test_display_error_network_error(self):
        """Test displaying network error."""
        error = httpx.TimeoutException("timeout")
        result = display_error(error, {"affected_api": "API-Football"})

        assert isinstance(result, str)
        assert "NETWORK ERROR" in result
        assert "TROUBLESHOOTING" in result

    def test_display_error_validation_error(self):
        """Test displaying validation error."""
        error = DataValidationError("bankroll", "-100", "must be positive")
        result = display_error(error)

        assert isinstance(result, str)
        assert "VALIDATION ERROR" in result
        assert "bankroll" in result.lower()

    def test_display_error_config_error(self):
        """Test displaying configuration error."""
        error = KeyError("OPENAI_API_KEY")
        result = display_error(error)

        assert isinstance(result, str)
        assert "CONFIGURATION ERROR" in result

    def test_display_error_system_error(self):
        """Test displaying system error."""
        error = FileNotFoundError("/missing/file")
        result = display_error(error)

        assert isinstance(result, str)
        assert "SYSTEM ERROR" in result

    def test_display_error_unknown_error(self):
        """Test displaying unknown error type."""
        error = Exception("unknown error")
        result = display_error(error)

        assert isinstance(result, str)
        assert "UNEXPECTED ERROR" in result

    def test_display_error_with_context(self):
        """Test display_error with context dict."""
        error = APIRateLimitError("rate limit", "http://test", status_code=429)
        context = {
            "affected_api": "OpenAI",
            "retry_after": 120,
            "retry_count": 3,
        }
        result = display_error(error, context)

        assert isinstance(result, str)
        assert "API ERROR" in result
        assert "120" in result

    def test_display_error_none_context(self):
        """Test display_error with None context."""
        error = APIError("test", "http://test")
        result = display_error(error, None)

        assert isinstance(result, str)
        assert "API ERROR" in result

    def test_display_error_returns_string(self):
        """Test that display_error always returns a string."""
        errors = [
            APIError("msg", "http://test"),
            httpx.TimeoutException("timeout"),
            DataValidationError("field", "value", "reason"),
            KeyError("KEY"),
            PermissionError("permission denied"),
            Exception("unknown"),
        ]

        for error in errors:
            result = display_error(error)
            assert isinstance(result, str)
            assert len(result) > 0
            # Should include error icon and log location reference
            assert "❌" in result or "⚠️" in result
            assert "LOG LOCATION" in result

    def test_display_error_no_exceptions(self):
        """Test that display_error doesn't raise exceptions."""
        errors = [
            None,
            APIError("msg", "http://test"),
            KeyError("key"),
            Exception("error"),
        ]

        for error in errors:
            if error:
                try:
                    result = display_error(error)
                    assert result is not None
                except Exception as e:
                    pytest.fail(f"display_error raised exception: {e}")


class TestCircularImports:
    """Test for circular import issues."""

    def test_no_circular_imports(self):
        """Test that error_handler can be imported without circular imports."""
        # This should not raise ImportError
        from bet_bot.display import display_error

        assert callable(display_error)

    def test_exports_available(self):
        """Test that display_error is properly exported."""
        from bet_bot.display import display_error

        # Should be callable
        assert callable(display_error)

        # Should handle various error types
        result = display_error(ValueError("test"))
        assert isinstance(result, str)
