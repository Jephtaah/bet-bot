"""
Custom exceptions for bet-bot application.

This module defines the exception hierarchy for all bet-bot errors.
Exceptions are organized by category (API errors, data errors, etc.) and
include context information for debugging.

Exception Hierarchy:
    BetBotError (base)
    ├── APIError (base for all API errors)
    │   ├── APIAuthenticationError (401, 403)
    │   ├── APIRateLimitError (429)
    │   ├── APINotFoundError (404)
    │   └── APIServerError (5xx)
    ├── DataValidationError (invalid data)
    ├── DataStaleError (data too old)
    ├── ScraperError (web scraping failed)
    └── OpenAIError (OpenAI API error)

Usage:
    from bet_bot.exceptions import APIAuthenticationError

    raise APIAuthenticationError(
        "API-Football authentication failed",
        url="https://api.example.com/v3/fixtures",
        status_code=401,
        response_body="Invalid API key"
    )
"""

from typing import Any


class BetBotError(Exception):
    """Base exception for all bet-bot errors."""

    pass


class APIError(BetBotError):
    """
    Base class for API-related errors.

    Attributes:
        message: Human-readable error description
        url: The URL that was requested
        status_code: HTTP status code (if applicable)
        response_body: Response body snippet for debugging
    """

    def __init__(
        self,
        message: str,
        url: str,
        status_code: int | None = None,
        response_body: str | None = None
    ):
        """
        Initialize API error with context.

        Args:
            message: Human-readable error description
            url: The URL that was requested
            status_code: HTTP status code
            response_body: Response body snippet for debugging
        """
        self.url = url
        self.status_code = status_code
        self.response_body = response_body

        # Truncate response body if too long
        if response_body and len(response_body) > 500:
            response_body = response_body[:500] + "... (truncated)"

        error_msg = f"{message} | URL: {url}"
        if status_code:
            error_msg += f" | Status: {status_code}"
        if response_body:
            error_msg += f" | Response: {response_body}"

        super().__init__(error_msg)


class APIAuthenticationError(APIError):
    """
    Authentication failed (401, 403).

    Raised when API key is invalid or permissions are insufficient.
    This error should NOT be retried - the API key needs to be fixed.
    """

    pass


class APIRateLimitError(APIError):
    """
    Rate limit exceeded (429).

    Raised when too many requests are made in a time window.
    Should be handled by rate limiter with exponential backoff.
    Check Retry-After header for wait time.
    """

    pass


class APINotFoundError(APIError):
    """
    Resource not found (404).

    Raised when requested resource doesn't exist.
    This is often expected (e.g., no fixtures today) and should
    be handled gracefully with None return value.
    """

    pass


class APIServerError(APIError):
    """
    Server error (5xx).

    Raised when API server has an internal error.
    Should be retried with exponential backoff (transient error).
    """

    pass


class DataValidationError(BetBotError):
    """
    Data validation failed.

    Raised when data doesn't match expected schema or business rules.

    Attributes:
        field: The field that failed validation
        value: The invalid value
        reason: Why validation failed
    """

    def __init__(self, field: str, value: Any, reason: str):
        """
        Initialize data validation error.

        Args:
            field: The field that failed validation
            value: The invalid value
            reason: Why validation failed
        """
        self.field = field
        self.value = value
        self.reason = reason

        # Truncate value if too long for error message
        value_str = str(value)
        if len(value_str) > 100:
            value_str = value_str[:100] + "... (truncated)"

        super().__init__(
            f"Validation failed for {field}={value_str}: {reason}"
        )


class DataStaleError(BetBotError):
    """
    Data is too old to use.

    Raised when data freshness requirements aren't met.

    Attributes:
        data_type: Type of data (e.g., 'odds', 'injuries')
        age_minutes: How old the data is in minutes
        max_age_minutes: Maximum allowed age in minutes
    """

    def __init__(
        self,
        data_type: str,
        age_minutes: int,
        max_age_minutes: int
    ):
        """
        Initialize data staleness error.

        Args:
            data_type: Type of data (e.g., 'odds', 'injuries')
            age_minutes: How old the data is in minutes
            max_age_minutes: Maximum allowed age in minutes
        """
        self.data_type = data_type
        self.age_minutes = age_minutes
        self.max_age_minutes = max_age_minutes

        super().__init__(
            f"{data_type} data is {age_minutes}m old "
            f"(max: {max_age_minutes}m)"
        )


class ScraperError(BetBotError):
    """
    Web scraping failed.

    Raised when web scraping encounters errors (page structure changed,
    network error, parsing error, etc.).

    Attributes:
        url: The URL being scraped
        reason: Why scraping failed
    """

    def __init__(self, url: str, reason: str):
        """
        Initialize scraper error.

        Args:
            url: The URL being scraped
            reason: Why scraping failed
        """
        self.url = url
        self.reason = reason

        super().__init__(f"Scraping failed for {url}: {reason}")


class OpenAIError(BetBotError):
    """
    OpenAI API error.

    Raised when OpenAI API call fails or returns unexpected data.

    Attributes:
        message: Error description
        request_id: OpenAI request ID (if available)
    """

    def __init__(self, message: str, request_id: str | None = None):
        """
        Initialize OpenAI error.

        Args:
            message: Error description
            request_id: OpenAI request ID (if available)
        """
        self.request_id = request_id

        error_msg = f"OpenAI API error: {message}"
        if request_id:
            error_msg += f" | Request ID: {request_id}"

        super().__init__(error_msg)
