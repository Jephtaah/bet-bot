"""
Structured logging configuration for bet-bot.

This module provides centralized logging configuration with:
- Console output (human-readable with color-coded log levels via rich)
- File output (JSON-structured, rotated)
- Configurable log levels via environment variable
- API key masking for security
- Suppression of noisy third-party libraries

Usage:
    from bet_bot.utils.logging import setup_logging, get_logger

    # Initialize logging (typically called once at startup)
    setup_logging(level="INFO")

    # Get a logger for your module
    logger = get_logger(__name__)
    logger.info("Application started")
    logger.debug("Debug information", extra={"user_id": 123})

Console Output:
    Color-coded log levels (via rich library):
    - DEBUG: Blue
    - INFO: Blue
    - WARNING: Yellow
    - ERROR: Red
    - CRITICAL: Red

Security:
    - NEVER log full API keys - use mask_value() for sensitive data
    - File logs are stored in ~/.bet-bot/logs/ (user home directory)
    - Log rotation prevents disk space issues (10MB max, 5 backups)

Architecture:
    Based on CLAUDE.md - Logging Configuration - MANDATORY STANDARD
    - Console: human-readable format with rich-enabled colored output
    - File: JSON-structured for parsing/analysis
    - Separate log levels (console respects LOG_LEVEL, file always DEBUG)
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional
import tempfile
from rich.logging import RichHandler


def ensure_log_directory() -> Path:
    """
    Create and return the log directory path.

    Creates ~/.bet-bot/logs/ if it doesn't exist. Handles permission errors
    gracefully by falling back to a temporary directory.

    Returns:
        Path to the log directory (either ~/.bet-bot/logs/ or temp fallback)

    Example:
        >>> log_dir = ensure_log_directory()
        >>> log_file = log_dir / "app.log"
    """
    # Primary location: user home directory
    try:
        log_dir = Path.home() / ".bet-bot" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Test write permissions
        test_file = log_dir / ".test_write"
        test_file.touch()
        test_file.unlink()

        return log_dir

    except (PermissionError, OSError) as e:
        # Fallback to temporary directory
        temp_dir = Path(tempfile.gettempdir()) / "bet-bot" / "logs"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Log warning about fallback (but we can't use logger yet if this is called during setup)
        print(
            f"Warning: Cannot write to ~/.bet-bot/logs (permission denied). "
            f"Using temporary directory: {temp_dir}",
            file=sys.stderr
        )

        return temp_dir


def mask_value(value: str, length: int = 8) -> str:
    """
    Mask sensitive values for safe logging output.

    Shows first 4 characters + "..." + last 4 characters to allow identification
    while preventing exposure of full sensitive data.

    Args:
        value: The sensitive value to mask
        length: Minimum length required for masking (default: 8)

    Returns:
        Masked value in format "xxxx...xxxx" or "****" for short values

    Examples:
        >>> mask_value("sk-proj-1234567890abcdef")
        "sk-p...cdef"

        >>> mask_value("short")
        "****"

        >>> mask_value("")
        "****"
    """
    if not value or len(value) < length:
        return "****"

    return f"{value[:4]}...{value[-4:]}"


def setup_logging(level: str = "INFO") -> None:
    """
    Configure application logging with console and file handlers.

    This function sets up the root logger with:
    - Console handler: human-readable format with rich-enabled colors (respects level parameter)
    - File handler: JSON-structured format (always DEBUG level)
    - Log rotation: 10MB per file, keep 5 backups
    - Suppressed libraries: httpx, httpcore (WARNING), openai (INFO)

    Args:
        level: Logging level for console output (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               File logging is always DEBUG to capture full detail.

    Raises:
        ValueError: If level is not a valid logging level

    Example:
        >>> setup_logging("DEBUG")  # Console shows all logs in color
        >>> logger = get_logger(__name__)
        >>> logger.debug("This appears in both console and file")

        >>> setup_logging("WARNING")  # Console only shows warnings and errors
        >>> logger.info("This only appears in file, not console")

    Note:
        This should be called once at application startup, typically from
        config/__init__.py after Config is loaded.
    """
    # Validate log level parameter
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    level_upper = level.upper()
    if level_upper not in valid_levels:
        raise ValueError(
            f"Invalid log level: {level}. Must be one of {valid_levels}"
        )

    # Ensure log directory exists
    log_dir = ensure_log_directory()
    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything at root level

    # Clear any existing handlers (prevent duplicates on re-initialization)
    root_logger.handlers.clear()

    # === Console Handler (human-readable with rich colors) ===
    console_handler = RichHandler(
        rich_tracebacks=True,
        tracebacks_show_locals=False,
        markup=False  # Don't interpret markup in log messages
    )
    console_handler.setLevel(level_upper)  # Respect provided level

    # RichHandler manages its own formatting with color coding
    # No need to set formatter explicitly
    root_logger.addHandler(console_handler)

    # === File Handler (JSON-structured, rotated) ===
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)  # Always DEBUG to file

    file_formatter = logging.Formatter(
        fmt='{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%SZ"
    )
    file_handler.setFormatter(file_formatter)

    # Add file handler to root logger (console already added above)
    root_logger.addHandler(file_handler)

    # === Suppress noisy third-party libraries ===
    # These libraries log too much connection/transport detail
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.INFO)

    # Log successful initialization (only to file to avoid noise)
    logger = logging.getLogger(__name__)
    logger.debug(
        f"Logging initialized: console={level_upper}, file=DEBUG, "
        f"log_dir={log_dir}, log_file={log_file.name}"
    )


def get_logger(name: str) -> logging.Logger:
    """
    Factory function to create logger instances.

    This is a simple wrapper around logging.getLogger() that follows
    the standard logger factory pattern. It ensures consistent logger
    creation throughout the application.

    Args:
        name: Logger name (typically __name__ from calling module)

    Returns:
        Logger instance configured by setup_logging()

    Example:
        >>> # In your module
        >>> logger = get_logger(__name__)
        >>> logger.info("Module initialized")
        [2025-11-24 14:30:00] INFO [my_module:15] Module initialized (in blue color)

    Note:
        setup_logging() must be called before using loggers. When setup_logging()
        is called with RichHandler, console output will be color-coded:
        - DEBUG/INFO: Blue
        - WARNING: Yellow
        - ERROR/CRITICAL: Red
    """
    return logging.getLogger(name)


# Module-level logger for this file
logger = get_logger(__name__)
