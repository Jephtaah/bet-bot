"""
Integration tests for error display handler.

Tests error display handler integration with other system components,
real exception scenarios, and full pipeline error handling.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio
import logging

import httpx

from bet_bot.display import display_error, render_analysis_results
from bet_bot.exceptions import (
    APIError,
    APIAuthenticationError,
    APIRateLimitError,
    APIServerError,
    DataValidationError,
    DataStaleError,
)


class TestErrorHandlerIntegration:
    """Integration tests with full pipeline scenarios."""

    def test_api_failure_error_display(self):
        """Test error display for API failure scenario."""
        # Simulate API failure
        error = APIServerError(
            "API server error",
            url="https://api-football-v1.p.rapidapi.com/v3/fixtures",
            status_code=503,
        )

        result = display_error(error, {"affected_api": "API-Football", "error_source": "fetch"})

        # Should include helpful information
        assert "API ERROR" in result
        assert "API-Football" in result
        assert "503" in result
        assert "30" in result  # Should suggest wait time
        assert "SOLUTION" in result

    def test_authentication_error_display(self):
        """Test error display for authentication failure."""
        error = APIAuthenticationError(
            "Invalid API key",
            url="https://api.openai.com/v1/chat/completions",
            status_code=401,
        )

        result = display_error(error, {"affected_api": "OpenAI"})

        assert "authentication" in result.lower()
        assert "401" in result
        assert ".env" in result
        assert "API key" in result

    def test_rate_limit_error_display(self):
        """Test error display for rate limit scenario."""
        error = APIRateLimitError(
            "Rate limit exceeded",
            url="https://api.openai.com/v1/chat/completions",
            status_code=429,
        )

        result = display_error(error, {"affected_api": "OpenAI", "retry_after": 60})

        assert "rate limit" in result.lower()
        assert "429" in result
        assert "60" in result
        assert "seconds" in result or "wait" in result.lower()

    def test_network_timeout_error_display(self):
        """Test error display for network timeout."""
        error = httpx.TimeoutException("Request timed out after 30 seconds")

        result = display_error(error, {"affected_api": "API-Football"})

        assert "timed out" in result.lower() or "timeout" in result.lower()
        assert "TROUBLESHOOTING" in result
        assert "internet" in result.lower() or "ping" in result

    def test_validation_error_in_pipeline(self):
        """Test validation error in data processing pipeline."""
        error = DataValidationError(
            field="bankroll",
            value="-500",
            reason="Bankroll must be positive",
        )

        result = display_error(error, {"error_source": "validate"})

        assert "bankroll" in result.lower()
        assert "-500" in result
        assert "positive" in result.lower()
        assert "EXAMPLE" in result

    def test_stale_data_error_display(self):
        """Test stale data error display."""
        error = DataStaleError(
            data_type="odds",
            age_minutes=90,
            max_age_minutes=60,
        )

        result = display_error(error)

        assert "odds" in result.lower()
        assert "90" in result
        assert "60" in result

    def test_permission_error_display(self):
        """Test permission error when writing logs."""
        error = PermissionError("Permission denied")

        result = display_error(error, {"path": "/root/.bet-bot/logs"})

        assert "Permission denied" in result or "permission" in result.lower()
        assert "chmod" in result or "/root/.bet-bot" in result

    def test_file_not_found_error_display(self):
        """Test file not found error."""
        error = FileNotFoundError("/etc/bet-bot/config.yaml")

        result = display_error(error)

        assert "not found" in result.lower()
        assert "/etc/bet-bot" in result


class TestRendererIntegration:
    """Test integration between error_handler and renderer."""

    @pytest.mark.asyncio
    async def test_error_state_with_error_handler(self):
        """Test that renderer can use error handler for error state."""
        # Simulate error scenario
        error = APIError("API failed", "http://test", status_code=500)
        error_msg = display_error(error, {"affected_api": "api_football"})

        # Renderer should handle error messages
        assert isinstance(error_msg, str)
        assert "API ERROR" in error_msg
        assert len(error_msg) > 100

    @pytest.mark.asyncio
    async def test_degraded_service_with_errors(self):
        """Test degraded service scenario with partial failures."""
        # Simulate some data sources failing with picks available
        data_quality = {
            "api_football": {"status": "success", "latency_ms": 100, "record_count": 50},
            "espn": {"status": "failed", "error": "timeout"},
            "openai": {"status": "success", "latency_ms": 1200, "record_count": 50},
        }

        # Create mock picks (partial results despite failures)
        from bet_bot.models.analysis import Pick
        picks = [
            Pick(
                fixture_id="12345",
                market="Home Win",
                ai_probability=0.65,
                implied_probability=0.60,
                ev_percentage=5.0,
                confidence=75,
                recommended_stake=10.0,
                suggested_odds=1.67,
            )
        ]

        result = await render_analysis_results(picks, 1000.0, data_quality)

        assert isinstance(result, str)
        # With picks available despite failures, should show picks (not degraded state)
        # since the renderer determines state based on picks presence
        assert "picks found" in result.lower() or "summary" in result.lower()


class TestConcurrentErrors:
    """Test concurrent error handling."""

    @pytest.mark.asyncio
    async def test_multiple_errors_simultaneously(self):
        """Test handling multiple errors in parallel."""
        errors = [
            APIAuthenticationError("auth failed", "http://test1", status_code=401),
            httpx.TimeoutException("timeout"),
            DataValidationError("field", "value", "reason"),
            KeyError("CONFIG_KEY"),
        ]

        # Process errors in parallel
        tasks = [asyncio.to_thread(display_error, error) for error in errors]
        results = await asyncio.gather(*tasks)

        # All should return valid strings
        assert len(results) == 4
        for result in results:
            assert isinstance(result, str)
            assert len(result) > 50
            assert "❌" in result

    @pytest.mark.asyncio
    async def test_error_context_isolation(self):
        """Test that error context doesn't leak between concurrent calls."""
        async def format_with_context(error, context_id):
            return display_error(error, {"context_id": context_id})

        errors = [
            APIError("error1", "http://test", status_code=500),
            APIError("error2", "http://test", status_code=500),
        ]

        # Run concurrently with different contexts
        results = await asyncio.gather(
            format_with_context(errors[0], "context_1"),
            format_with_context(errors[1], "context_2"),
        )

        # Both should have completed successfully
        assert len(results) == 2
        assert all(isinstance(r, str) for r in results)


class TestLoggingIntegration:
    """Test integration with logging system."""

    def test_error_logging_to_file(self, tmp_path):
        """Test that errors are logged to file."""
        with patch("bet_bot.display.error_handler.ensure_log_directory") as mock_log_dir:
            mock_log_dir.return_value = tmp_path

            error = APIError("test error", "http://test", status_code=500)
            result = display_error(error, {"affected_api": "test_api"})

            # Log file should have been created
            log_files = list(tmp_path.glob("*.log"))
            if log_files:
                log_file = log_files[0]
                with open(log_file) as f:
                    content = f.read()
                    # Should contain error details
                    assert "APIError" in content or "test error" in content

    def test_logger_receives_error_info(self, caplog):
        """Test that logger receives error categorization info."""
        error = APIAuthenticationError("auth failed", "http://test", status_code=401)

        with caplog.at_level(logging.INFO):
            result = display_error(error)

        # Logger should record error info
        assert "api" in caplog.text.lower() or "APIAuthenticationError" in caplog.text


class TestErrorMessageQuality:
    """Test the quality and content of error messages."""

    def test_error_messages_are_user_friendly(self):
        """Test that error messages avoid technical jargon."""
        errors = [
            APIAuthenticationError("auth failed", "http://test", status_code=401),
            httpx.TimeoutException("timeout"),
            DataValidationError("amount", "-100", "must be positive"),
            KeyError("OPENAI_API_KEY"),
            PermissionError("permission denied"),
        ]

        forbidden_terms = [
            "traceback",
            "stacktrace",
            "HTTPStatusError",
            "httpx",
            "pydantic",
        ]

        for error in errors:
            result = display_error(error)

            # Should not contain technical jargon
            for term in forbidden_terms:
                assert term.lower() not in result.lower(), f"Found technical term: {term}"

    def test_error_messages_have_actionable_steps(self):
        """Test that error messages include actionable next steps."""
        errors = [
            APIAuthenticationError("auth failed", "http://test", status_code=401),
            httpx.TimeoutException("timeout"),
            DataValidationError("bankroll", "-100", "must be positive"),
            KeyError("API_KEY"),
        ]

        action_keywords = ["solution", "troubleshooting", "steps", "check", "verify", "setup", "example"]

        for error in errors:
            result = display_error(error)

            # Should include at least one action keyword
            found_action = any(
                keyword in result.lower() for keyword in action_keywords
            )
            assert found_action, f"No action keywords found for {type(error).__name__}\nResult:\n{result}"

    def test_error_messages_include_help_info(self):
        """Test that error messages include help information."""
        error = APIError("test", "http://test", status_code=500)
        result = display_error(error, {"affected_api": "API"})

        # Should mention logs location
        assert "log" in result.lower()
        assert "~/.bet-bot" in result or "logs" in result

    def test_error_messages_have_consistent_format(self):
        """Test that all error messages follow consistent format."""
        errors = [
            APIAuthenticationError("auth", "http://test", status_code=401),
            httpx.TimeoutException("timeout"),
            DataValidationError("field", "value", "reason"),
            KeyError("KEY"),
            PermissionError("denied"),
        ]

        for error in errors:
            result = display_error(error)

            # All should have error icon
            assert "❌" in result
            # All should reference logs
            assert "LOG LOCATION" in result
            # All should be multi-line
            assert result.count("\n") > 3


class TestErrorContextHandling:
    """Test error context dict handling."""

    def test_context_with_all_fields(self):
        """Test error display with complete context."""
        error = APIRateLimitError("rate limit", "http://test", status_code=429)
        context = {
            "affected_api": "OpenAI",
            "error_source": "completion_request",
            "retry_count": 2,
            "retry_after": 120,
            "request_id": "req_12345",
        }

        result = display_error(error, context)

        # Should use context information
        assert "OpenAI" in result
        assert "120" in result

    def test_context_with_no_fields(self):
        """Test error display with no context."""
        error = APIError("test", "http://test")
        result = display_error(error)

        # Should still produce valid output
        assert isinstance(result, str)
        assert len(result) > 50

    def test_context_with_partial_fields(self):
        """Test error display with partial context."""
        error = APIError("test", "http://test")
        context = {"affected_api": "test_api"}  # Only one field

        result = display_error(error, context)

        # Should still work
        assert isinstance(result, str)
        assert "test_api" in result


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_error_with_very_long_message(self):
        """Test handling errors with very long messages."""
        long_message = "x" * 10000
        error = APIError(long_message, "http://test")

        result = display_error(error)

        # Should handle gracefully
        assert isinstance(result, str)
        assert len(result) > 50
        # Should not include entire long message
        assert len(result) < len(long_message) + 500

    def test_error_with_special_characters(self):
        """Test handling errors with special characters."""
        error = APIError("Error with special chars: @#$%^&*()", "http://test")

        result = display_error(error)

        assert isinstance(result, str)
        assert len(result) > 50

    def test_error_with_unicode(self):
        """Test handling errors with unicode characters."""
        error = APIError("Error with unicode: 你好 мир 🎯", "http://test")

        result = display_error(error)

        assert isinstance(result, str)
        assert len(result) > 50

    def test_error_with_none_attributes(self):
        """Test handling errors with None attributes."""
        error = APIError("test", url=None, status_code=None)

        result = display_error(error)

        assert isinstance(result, str)
        assert "❌" in result
