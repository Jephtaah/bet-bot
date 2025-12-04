"""
Error display handler for bet-bot.

This module transforms exception objects into user-friendly, actionable error
messages for terminal display. It handles multiple error categories (API, Network,
Validation, Configuration, System) with appropriate formatting, guidance, and
logging.

Features:
- Error categorization (API, Network, Validation, Configuration, System)
- User-friendly messages with actionable next steps
- Full error logging to ~/.bet-bot/logs/ while showing simplified message to user
- Security: Never logs or displays API keys
- Integration with Rich library for terminal formatting

Functions:
    display_error: Main function to format exceptions into error messages
    _categorize_error: Detect error category from exception type
    _format_api_error: Format API errors with retry guidance
    _format_network_error: Format network errors with troubleshooting steps
    _format_validation_error: Format validation errors with format examples
    _format_config_error: Format configuration errors with setup instructions
    _format_system_error: Format system errors with permission/disk guidance
    _log_full_error: Log full error details to file

Usage:
    from bet_bot.display import display_error

    try:
        result = await fetch_data()
    except Exception as e:
        error_msg = display_error(e, context={"source": "api_football"})
        print(error_msg)
"""

import logging
import platform
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel

from bet_bot.exceptions import (
    APIAuthenticationError,
    APIError,
    APINotFoundError,
    APIRateLimitError,
    APIServerError,
    DataStaleError,
    DataValidationError,
    OpenAIError,
    ScraperError,
)
from bet_bot.utils.logging import ensure_log_directory, mask_value

logger = logging.getLogger(__name__)

# API documentation links
API_DOCS = {
    "api_football": "https://api-football-v1.p.rapidapi.com/",
    "openai": "https://platform.openai.com/docs/api-reference",
    "odds": "https://the-odds-api.com/docs/",
    "espn": "https://www.espn.com/",
}


def _categorize_error(error: Exception) -> str:
    """
    Detect error category from exception type and attributes.

    Args:
        error: Exception object to categorize

    Returns:
        Category string: "api", "network", "validation", "configuration", "system", or "unknown"
    """
    # API errors (custom and httpx)
    if isinstance(
        error,
        (APIError, APIAuthenticationError, APIRateLimitError, APIServerError, APINotFoundError),
    ):
        return "api"

    if isinstance(error, httpx.HTTPStatusError):
        return "api"

    # Network errors
    if isinstance(error, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)):
        return "network"

    # Validation errors
    if isinstance(error, (ValidationError, DataValidationError)):
        return "validation"

    if isinstance(error, DataStaleError):
        return "validation"

    # Configuration errors (missing keys, invalid config)
    if isinstance(error, (KeyError, ValueError)):
        error_str = str(error).lower()
        if any(
            keyword in error_str
            for keyword in ["key", "config", "environment", "api_key", "env"]
        ):
            return "configuration"

    # System errors
    if isinstance(error, (OSError, PermissionError, FileNotFoundError, RuntimeError)):
        return "system"

    # Scraper and OpenAI errors
    if isinstance(error, (ScraperError, OpenAIError)):
        return "api"

    # Default to unknown
    return "unknown"


def _format_api_error(error: Exception, context: dict | None = None) -> str:
    """
    Format API error with which API failed, status code, and retry guidance.

    Args:
        error: API exception object
        context: Optional context dict with error_source, affected_api, retry_count, etc.

    Returns:
        Formatted error message string
    """
    context = context or {}

    # Extract API name
    api_name = context.get("affected_api", "Unknown API")
    if isinstance(error, httpx.HTTPStatusError):
        api_name = context.get("affected_api", "API")
        status_code = error.response.status_code
    elif isinstance(error, (APIError, APIAuthenticationError, APIRateLimitError)):
        api_name = context.get("affected_api", _extract_api_from_url(getattr(error, "url", "")))
        status_code = getattr(error, "status_code", None)
    else:
        status_code = None

    # Format error message
    lines = []
    lines.append("❌ API ERROR")
    lines.append("")

    # Status details
    if status_code == 401 or isinstance(error, APIAuthenticationError):
        lines.append(f"{api_name} authentication failed (401)")
        lines.append("")
        lines.append("SOLUTION:")
        lines.append(f"  1. Check your API key in ~/.env file")
        lines.append(f"  2. Verify the key is valid: {API_DOCS.get(api_name.lower().replace(' ', '_'), '#')}")
        lines.append(f"  3. Ensure key has necessary permissions")
        lines.append(f"  4. Try again")

    elif status_code == 403:
        lines.append(f"{api_name} permission denied (403)")
        lines.append("")
        lines.append("SOLUTION:")
        lines.append(f"  1. Verify your API plan includes required endpoints")
        lines.append(f"  2. Check if your account is active")
        lines.append(f"  3. Contact {api_name} support if persists")

    elif status_code == 429 or isinstance(error, APIRateLimitError):
        retry_after = context.get("retry_after", 60)
        lines.append(f"{api_name} rate limit exceeded (429)")
        lines.append("")
        lines.append("SOLUTION:")
        lines.append(f"  • Wait {retry_after} seconds before retrying")
        lines.append(f"  • Consider lowering request frequency")
        lines.append(f"  • Check rate limits: {API_DOCS.get(api_name.lower().replace(' ', '_'), '#')}")

    elif status_code == 404 or isinstance(error, APINotFoundError):
        lines.append(f"{api_name} resource not found (404)")
        lines.append("")
        lines.append("This may be expected if no data is available.")
        lines.append("")
        lines.append("SOLUTION:")
        lines.append(f"  • Check if data exists for your query")
        lines.append(f"  • Try a different date or search criteria")

    elif (status_code and status_code >= 500) or isinstance(error, APIServerError):
        lines.append(f"{api_name} server error ({status_code or '5xx'})")
        lines.append("")
        lines.append("SOLUTION:")
        lines.append(f"  • Wait 30-60 seconds and retry")
        lines.append(f"  • Check service status: {API_DOCS.get(api_name.lower().replace(' ', '_'), '#')}")

    elif isinstance(error, TimeoutError):
        lines.append(f"{api_name} request timed out")
        lines.append("")
        lines.append("SOLUTION:")
        lines.append(f"  • Check your internet connection")
        lines.append(f"  • Check if {api_name} is responding")
        lines.append(f"  • Try again in a few moments")

    else:
        lines.append(f"{api_name} error occurred")
        lines.append(f"Details: {str(error)[:200]}")
        lines.append("")
        lines.append("SOLUTION:")
        lines.append(f"  • Retry the operation")
        lines.append(f"  • Check logs: ~/.bet-bot/logs/")
        lines.append(f"  • Contact support if issue persists")

    lines.append("")
    lines.append("📋 LOG LOCATION: ~/.bet-bot/logs/")

    return "\n".join(lines)


def _format_network_error(error: Exception, context: dict | None = None) -> str:
    """
    Format network error with troubleshooting steps.

    Args:
        error: Network exception object
        context: Optional context dict with source API information

    Returns:
        Formatted error message string
    """
    context = context or {}
    api_name = context.get("affected_api", "API")

    lines = []
    lines.append("❌ NETWORK ERROR")
    lines.append("")

    if isinstance(error, httpx.TimeoutException):
        lines.append(f"Connection to {api_name} timed out after 30 seconds")
        lines.append("")
        lines.append("TROUBLESHOOTING:")
        lines.append("  1. Check your internet connection:")
        lines.append("     $ ping google.com")
        lines.append(f"  2. Check if {api_name} is reachable")
        lines.append("  3. Try again in a few moments")
        lines.append("  4. Contact your ISP if issue persists")

    elif isinstance(error, httpx.ConnectError):
        lines.append(f"Cannot connect to {api_name} (connection refused)")
        lines.append("")
        lines.append("TROUBLESHOOTING:")
        lines.append(f"  1. Verify {api_name} is online")
        lines.append("  2. Check your firewall/proxy settings")
        lines.append("  3. Try from a different network if possible")
        lines.append("  4. Check your DNS configuration")

    elif isinstance(error, httpx.NetworkError):
        lines.append(f"Network error connecting to {api_name}")
        lines.append("")
        lines.append("TROUBLESHOOTING:")
        lines.append("  1. Check internet connection stability")
        lines.append(f"  2. Verify {api_name} is not blocked by firewall")
        lines.append("  3. Try again in a few moments")

    else:
        lines.append(f"Network error: {str(error)[:200]}")
        lines.append("")
        lines.append("TROUBLESHOOTING:")
        lines.append("  1. Check your internet connection")
        lines.append("  2. Verify network configuration")
        lines.append("  3. Check system firewall")
        lines.append("  4. Try again after a short delay")

    lines.append("")
    lines.append("📋 LOG LOCATION: ~/.bet-bot/logs/")

    return "\n".join(lines)


def _format_validation_error(error: Exception, context: dict | None = None) -> str:
    """
    Format validation error with field, expected format, and example.

    Args:
        error: Validation exception object
        context: Optional context dict

    Returns:
        Formatted error message string
    """
    context = context or {}

    lines = []
    lines.append("❌ VALIDATION ERROR")
    lines.append("")

    if isinstance(error, DataValidationError):
        field = error.field
        value = str(error.value)[:100]
        reason = error.reason

        lines.append(f"Invalid value for '{field}'")
        lines.append(f"Received: {value}")
        lines.append(f"Problem: {reason}")
        lines.append("")
        lines.append("VALID FORMAT:")

        # Provide field-specific examples
        if "bankroll" in field.lower():
            lines.append("  • Must be a positive number")
            lines.append("  • Minimum: $1")
            lines.append("  • Maximum: $1,000,000")
            lines.append("")
            lines.append("EXAMPLE:")
            lines.append("  bet-bot analyze --bankroll 1000")

        elif "threshold" in field.lower():
            lines.append("  • Must be between 0 and 100")
            lines.append("  • Example: 5.0 for 5% EV threshold")
            lines.append("")
            lines.append("EXAMPLE:")
            lines.append("  bet-bot analyze --threshold 5.0")

        else:
            lines.append(f"  • Review the field constraints")
            lines.append(f"  • Provide value matching: {reason}")

    elif isinstance(error, DataStaleError):
        data_type = error.data_type
        age_minutes = error.age_minutes
        max_age = error.max_age_minutes

        lines.append(f"{data_type.title()} data is too old")
        lines.append(f"Age: {age_minutes} minutes (max allowed: {max_age} minutes)")
        lines.append("")
        lines.append("SOLUTION:")
        lines.append(f"  • Wait for fresh {data_type} data to be fetched")
        lines.append(f"  • Or retry the operation (will refetch data)")

    elif isinstance(error, ValidationError):
        # Pydantic ValidationError
        lines.append("Data validation failed")
        error_details = str(error)[:300]
        lines.append(f"Details: {error_details}")
        lines.append("")
        lines.append("SOLUTION:")
        lines.append("  • Check your input data format")
        lines.append("  • Verify all required fields are provided")
        lines.append("  • Review error details in logs")

    else:
        lines.append(f"Validation error: {str(error)[:200]}")
        lines.append("")
        lines.append("SOLUTION:")
        lines.append("  • Check input data format")
        lines.append("  • Verify all required fields")
        lines.append("  • Review logs for details")

    lines.append("")
    lines.append("📋 LOG LOCATION: ~/.bet-bot/logs/")

    return "\n".join(lines)


def _format_config_error(error: Exception, context: dict | None = None) -> str:
    """
    Format configuration error with missing key, file location, setup instructions.

    Args:
        error: Configuration exception object
        context: Optional context dict

    Returns:
        Formatted error message string
    """
    context = context or {}

    lines = []
    lines.append("❌ CONFIGURATION ERROR")
    lines.append("")

    # Try to extract missing key from error message
    error_str = str(error)
    missing_key = None

    if isinstance(error, KeyError):
        missing_key = str(error).strip("'\"")
    elif isinstance(error, ValueError):
        # Try to extract key name from ValueError message
        if "OPENAI_API_KEY" in error_str:
            missing_key = "OPENAI_API_KEY"
        elif "API_FOOTBALL_KEY" in error_str:
            missing_key = "API_FOOTBALL_KEY"
        elif "ODDS_API_KEY" in error_str:
            missing_key = "ODDS_API_KEY"

    if missing_key:
        lines.append(f"Missing required configuration: {missing_key}")
    else:
        lines.append(f"Configuration error: {error_str[:200]}")

    lines.append("")
    lines.append("SETUP INSTRUCTIONS:")
    lines.append("  1. Create or edit: ~/.env")
    lines.append(f"  2. Add your API key: {missing_key or 'API_KEY'}=your-key-here")
    lines.append("  3. Save the file")
    lines.append("  4. Run bet-bot again")
    lines.append("")

    lines.append("REQUIRED KEYS:")
    lines.append("  • OPENAI_API_KEY - Get from: https://platform.openai.com/api-keys")
    lines.append("  • API_FOOTBALL_KEY - Get from: https://api-football-v1.p.rapidapi.com")
    lines.append("")
    lines.append("OPTIONAL KEYS:")
    lines.append("  • ODDS_API_KEY - Get from: https://the-odds-api.com")
    lines.append("")

    lines.append("Note: .env file should never be committed to version control")
    lines.append("📋 LOG LOCATION: ~/.bet-bot/logs/")

    return "\n".join(lines)


def _format_system_error(error: Exception, context: dict | None = None) -> str:
    """
    Format system error with file/directory, permissions, disk space guidance.

    Args:
        error: System exception object
        context: Optional context dict

    Returns:
        Formatted error message string
    """
    context = context or {}

    lines = []
    lines.append("❌ SYSTEM ERROR")
    lines.append("")

    if isinstance(error, PermissionError):
        file_path = context.get("path", "unknown location")
        lines.append(f"Permission denied: {file_path}")
        lines.append("")
        lines.append("TROUBLESHOOTING:")
        lines.append(f"  1. Check permissions: ls -la {file_path}")
        lines.append(f"  2. Fix permissions: chmod 755 {file_path}")
        lines.append(f"  3. Or run as user with appropriate permissions")
        lines.append(f"  4. Retry the operation")

    elif isinstance(error, FileNotFoundError):
        file_path = str(error)
        lines.append(f"File not found: {file_path}")
        lines.append("")
        lines.append("TROUBLESHOOTING:")
        lines.append(f"  1. Verify the file path is correct")
        lines.append(f"  2. Create missing directory if needed: mkdir -p")
        lines.append(f"  3. Check if file should be installed with the package")
        lines.append(f"  4. Reinstall bet-bot if needed")

    elif isinstance(error, OSError):
        error_str = str(error)
        if "disk" in error_str.lower() or "space" in error_str.lower():
            lines.append("Insufficient disk space")
            lines.append("")
            lines.append("TROUBLESHOOTING:")
            lines.append("  1. Check available disk space: df -h")
            lines.append("  2. Free up space by:")
            lines.append("     • Removing old log files: rm ~/.bet-bot/logs/*.log.*")
            lines.append("     • Clearing temporary files: rm -rf /tmp/*")
            lines.append("  3. Retry the operation")

        else:
            lines.append(f"System error: {error_str[:200]}")
            lines.append("")
            lines.append("TROUBLESHOOTING:")
            lines.append("  1. Check system logs")
            lines.append("  2. Verify disk space: df -h")
            lines.append("  3. Check file permissions")
            lines.append("  4. Retry the operation")

    else:
        lines.append(f"System error: {str(error)[:200]}")
        lines.append("")
        lines.append("TROUBLESHOOTING:")
        lines.append("  1. Check system configuration")
        lines.append("  2. Verify file/directory permissions")
        lines.append("  3. Check available resources (disk, memory)")
        lines.append("  4. Retry the operation")

    lines.append("")
    lines.append("📋 LOG LOCATION: ~/.bet-bot/logs/")

    return "\n".join(lines)


def _extract_api_from_url(url: str) -> str:
    """Extract API name from URL."""
    if not url:
        return "Unknown API"

    if "api-football" in url:
        return "API-Football"
    elif "openai" in url or "api.openai.com" in url:
        return "OpenAI"
    elif "odds" in url:
        return "Odds API"
    elif "espn" in url:
        return "ESPN"

    return "API"


def _log_full_error(error: Exception, context: dict | None = None) -> str:
    """
    Log full error details to ~/.bet-bot/logs/ including stack trace and system info.

    Args:
        error: Exception object to log
        context: Optional context dict with request/error metadata

    Returns:
        Path to log file containing full error details
    """
    context = context or {}

    try:
        # Get log directory
        log_dir = ensure_log_directory()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")
        log_file = log_dir / f"error-{timestamp}.log"

        # Collect error information
        error_lines = []
        error_lines.append("=" * 80)
        error_lines.append(f"FULL ERROR LOG - {datetime.now(timezone.utc).isoformat()}")
        error_lines.append("=" * 80)
        error_lines.append("")

        # Exception type and message
        error_lines.append(f"Exception Type: {type(error).__name__}")
        error_lines.append(f"Message: {str(error)}")
        error_lines.append("")

        # Stack trace
        error_lines.append("Stack Trace:")
        error_lines.append("-" * 80)
        error_lines.append(traceback.format_exc())
        error_lines.append("")

        # Exception attributes (context from our exception classes)
        error_lines.append("Exception Attributes:")
        error_lines.append("-" * 80)
        for attr_name in dir(error):
            if not attr_name.startswith("_"):
                try:
                    value = getattr(error, attr_name)
                    # Skip methods
                    if callable(value):
                        continue
                    # Mask sensitive values
                    if "key" in attr_name.lower() or "token" in attr_name.lower():
                        value = mask_value(str(value))
                    error_lines.append(f"  {attr_name}: {value}")
                except Exception:
                    pass

        error_lines.append("")

        # Context provided to display_error
        if context:
            error_lines.append("Context:")
            error_lines.append("-" * 80)
            for key, value in context.items():
                # Mask sensitive context values
                if "key" in key.lower() or "token" in key.lower():
                    value = mask_value(str(value))
                error_lines.append(f"  {key}: {value}")
            error_lines.append("")

        # System information
        error_lines.append("System Information:")
        error_lines.append("-" * 80)
        error_lines.append(f"  Platform: {platform.platform()}")
        error_lines.append(f"  Python: {platform.python_version()}")
        error_lines.append(f"  Machine: {platform.machine()}")
        error_lines.append("")

        # Write to log file
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("\n".join(error_lines))

        logger.debug(f"Full error logged to: {log_file}")
        return str(log_file)

    except Exception as e:
        logger.error(f"Failed to write full error log: {str(e)}", exc_info=True)
        return ""


def display_error(error: Exception, context: dict | None = None) -> str:
    """
    Format an exception into a user-friendly error message for terminal display.

    Main entry point. Takes any exception and optional context, categorizes it,
    logs full details to file, and returns a simplified user-friendly message.

    Args:
        error: Exception object to format
        context: Optional dict with context information:
            - affected_api: Which API failed (e.g., 'api_football', 'openai')
            - error_source: Where error originated ('fetch', 'parse', 'validate', etc.)
            - retry_count: Number of retry attempts
            - retry_after: Seconds to wait before retry (for rate limits)
            - path: File path (for system errors)
            - request_data: Request that caused error (not logged if sensitive)

    Returns:
        Formatted error message string ready for terminal display

    Example:
        >>> try:
        ...     result = await fetch_data()
        ... except Exception as e:
        ...     error_msg = display_error(e, context={"affected_api": "api_football"})
        ...     print(error_msg)
    """
    context = context or {}

    # Log full error details to file
    log_file = _log_full_error(error, context)
    if log_file and "log_file" not in context:
        context["log_file"] = log_file

    # Categorize error
    category = _categorize_error(error)

    # Format based on category
    if category == "api":
        message = _format_api_error(error, context)
    elif category == "network":
        message = _format_network_error(error, context)
    elif category == "validation":
        message = _format_validation_error(error, context)
    elif category == "configuration":
        message = _format_config_error(error, context)
    elif category == "system":
        message = _format_system_error(error, context)
    else:
        # Unknown error - show generic message
        message = (
            "❌ UNEXPECTED ERROR\n\n"
            f"An unexpected error occurred: {str(error)[:200]}\n\n"
            "SOLUTION:\n"
            "  • Check logs: ~/.bet-bot/logs/\n"
            "  • Try the operation again\n"
            "  • Contact support if issue persists\n\n"
            "📋 LOG LOCATION: ~/.bet-bot/logs/"
        )

    logger.info(f"Error formatted: {category} | {type(error).__name__}")

    return message
