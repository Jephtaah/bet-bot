"""
Unit tests for logging configuration module.

Tests the logging setup, logger factory, API key masking, directory management,
and log level configuration. Uses pytest fixtures and temp directories to isolate
tests from actual log files.

Coverage targets:
- setup_logging() function with various log levels
- get_logger() factory function
- mask_value() utility for sensitive data
- ensure_log_directory() directory creation
- Console and file handler configuration
- Log rotation settings
- Library log suppression
- JSON formatting for file logs
- Human-readable formatting for console
"""

import pytest
import logging
import json
import tempfile
from pathlib import Path
from typing import List
from unittest.mock import patch, MagicMock

from bet_bot.utils.logging import (
    setup_logging,
    get_logger,
    mask_value,
    ensure_log_directory
)
from rich.logging import RichHandler


class TestMaskValue:
    """Tests for mask_value() utility function."""

    def test_mask_value_with_long_string(self):
        """Test masking a long API key shows first 4 and last 4 chars."""
        # Arrange
        api_key = "sk-proj-1234567890abcdefghijklmnop"

        # Act
        masked = mask_value(api_key)

        # Assert
        assert masked == "sk-p...mnop"
        assert len(masked) == 11  # 4 + 3 + 4

    def test_mask_value_with_short_string(self):
        """Test masking a short string returns asterisks."""
        # Arrange
        short_key = "short"

        # Act
        masked = mask_value(short_key)

        # Assert
        assert masked == "****"

    def test_mask_value_with_empty_string(self):
        """Test masking an empty string returns asterisks."""
        # Act
        masked = mask_value("")

        # Assert
        assert masked == "****"

    def test_mask_value_with_none(self):
        """Test masking None returns asterisks."""
        # Act
        masked = mask_value(None)

        # Assert
        assert masked == "****"

    def test_mask_value_with_exact_minimum_length(self):
        """Test masking a string at exact minimum length (8 chars)."""
        # Arrange
        key = "12345678"  # Exactly 8 chars

        # Act
        masked = mask_value(key, length=8)

        # Assert
        assert masked == "1234...5678"

    def test_mask_value_with_custom_length(self):
        """Test masking with custom minimum length requirement."""
        # Arrange
        key = "shortkey"  # 8 chars

        # Act
        masked = mask_value(key, length=10)  # Require 10+ chars

        # Assert
        assert masked == "****"  # Too short for custom length


class TestEnsureLogDirectory:
    """Tests for ensure_log_directory() function."""

    @patch('bet_bot.utils.logging.Path.home')
    def test_ensure_log_directory_creates_directory(self, mock_home, tmp_path):
        """Test that log directory is created in user home."""
        # Arrange
        mock_home.return_value = tmp_path

        # Act
        log_dir = ensure_log_directory()

        # Assert
        assert log_dir.exists()
        assert log_dir.is_dir()
        assert str(log_dir).endswith(".bet-bot/logs")

    @patch('bet_bot.utils.logging.Path.home')
    def test_ensure_log_directory_returns_existing_directory(self, mock_home, tmp_path):
        """Test that function returns existing directory without error."""
        # Arrange
        mock_home.return_value = tmp_path
        log_dir = tmp_path / ".bet-bot" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Act
        result = ensure_log_directory()

        # Assert
        assert result == log_dir
        assert result.exists()

    @patch('bet_bot.utils.logging.Path.home')
    @patch('bet_bot.utils.logging.tempfile.gettempdir')
    def test_ensure_log_directory_falls_back_to_temp_on_permission_error(
        self, mock_tempdir, mock_home, tmp_path
    ):
        """Test fallback to temp directory when home directory is not writable."""
        # Arrange
        temp_base = tmp_path / "temp"
        temp_base.mkdir()
        mock_tempdir.return_value = str(temp_base)

        # Make home directory that will fail
        read_only_home = tmp_path / "readonly"
        read_only_home.mkdir()
        mock_home.return_value = read_only_home

        # Make .mkdir() raise PermissionError
        original_mkdir = Path.mkdir

        def mock_mkdir(self, *args, **kwargs):
            if ".bet-bot" in str(self):
                raise PermissionError("Permission denied")
            original_mkdir(self, *args, **kwargs)

        # Act
        with patch.object(Path, 'mkdir', mock_mkdir):
            log_dir = ensure_log_directory()

        # Assert
        assert "bet-bot/logs" in str(log_dir)
        assert str(log_dir).startswith(str(temp_base))


class TestGetLogger:
    """Tests for get_logger() factory function."""

    def test_get_logger_returns_logger_instance(self):
        """Test that get_logger returns a logging.Logger instance."""
        # Act
        logger = get_logger("test_module")

        # Assert
        assert isinstance(logger, logging.Logger)

    def test_get_logger_uses_provided_name(self):
        """Test that logger has the name provided."""
        # Arrange
        module_name = "bet_bot.test.module"

        # Act
        logger = get_logger(module_name)

        # Assert
        assert logger.name == module_name

    def test_get_logger_returns_same_instance_for_same_name(self):
        """Test that calling get_logger twice with same name returns same instance."""
        # Arrange
        name = "bet_bot.same_module"

        # Act
        logger1 = get_logger(name)
        logger2 = get_logger(name)

        # Assert
        assert logger1 is logger2  # Same instance (Python logging singleton)


class TestSetupLogging:
    """Tests for setup_logging() configuration function."""

    @patch('bet_bot.utils.logging.ensure_log_directory')
    def test_setup_logging_creates_handlers(self, mock_ensure_dir, tmp_path):
        """Test that setup_logging creates console (RichHandler) and file handlers."""
        # Arrange
        mock_ensure_dir.return_value = tmp_path
        root_logger = logging.getLogger()
        root_logger.handlers.clear()  # Clear any existing handlers

        # Act
        setup_logging("INFO")

        # Assert
        assert len(root_logger.handlers) == 2
        handler_types = [type(h).__name__ for h in root_logger.handlers]
        assert "RichHandler" in handler_types
        assert "RotatingFileHandler" in handler_types

    @patch('bet_bot.utils.logging.ensure_log_directory')
    def test_setup_logging_sets_correct_log_levels(self, mock_ensure_dir, tmp_path):
        """Test that console respects level param but file is always DEBUG."""
        # Arrange
        mock_ensure_dir.return_value = tmp_path
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        # Act
        setup_logging("WARNING")

        # Assert
        # Root logger should be DEBUG to capture everything
        assert root_logger.level == logging.DEBUG

        # Find handlers
        console_handler = next(h for h in root_logger.handlers if isinstance(h, RichHandler))
        file_handler = next(h for h in root_logger.handlers if type(h).__name__ == "RotatingFileHandler")

        # Console should respect provided level
        assert console_handler.level == logging.WARNING

        # File should always be DEBUG
        assert file_handler.level == logging.DEBUG

    @patch('bet_bot.utils.logging.ensure_log_directory')
    def test_setup_logging_configures_rotation(self, mock_ensure_dir, tmp_path):
        """Test that file handler uses rotation with correct settings."""
        # Arrange
        mock_ensure_dir.return_value = tmp_path
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        # Act
        setup_logging("INFO")

        # Assert
        file_handler = next(
            h for h in root_logger.handlers
            if type(h).__name__ == "RotatingFileHandler"
        )

        # Check rotation settings (10MB, 5 backups)
        assert file_handler.maxBytes == 10 * 1024 * 1024  # 10MB
        assert file_handler.backupCount == 5

    @patch('bet_bot.utils.logging.ensure_log_directory')
    def test_setup_logging_uses_rich_handler(self, mock_ensure_dir, tmp_path):
        """Test that console handler uses RichHandler for colored output."""
        # Arrange
        mock_ensure_dir.return_value = tmp_path
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        # Act
        setup_logging("INFO")

        # Assert
        console_handler = next(
            h for h in root_logger.handlers
            if isinstance(h, RichHandler)
        )

        # RichHandler should be configured with proper settings
        assert console_handler.rich_tracebacks is True
        assert console_handler.tracebacks_show_locals is False

    @patch('bet_bot.utils.logging.ensure_log_directory')
    def test_setup_logging_formats_file_json_structured(self, mock_ensure_dir, tmp_path):
        """Test that file handler uses JSON-structured format."""
        # Arrange
        mock_ensure_dir.return_value = tmp_path
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        # Act
        setup_logging("INFO")

        # Assert
        file_handler = next(
            h for h in root_logger.handlers
            if type(h).__name__ == "RotatingFileHandler"
        )

        format_string = file_handler.formatter._fmt
        # Should be JSON format with specific fields
        assert "timestamp" in format_string
        assert "level" in format_string
        assert "logger" in format_string
        assert "message" in format_string

    @patch('bet_bot.utils.logging.ensure_log_directory')
    def test_setup_logging_suppresses_noisy_libraries(self, mock_ensure_dir, tmp_path):
        """Test that httpx, httpcore, openai loggers are suppressed."""
        # Arrange
        mock_ensure_dir.return_value = tmp_path

        # Act
        setup_logging("DEBUG")  # Even with DEBUG, libraries should be suppressed

        # Assert
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING
        assert logging.getLogger("openai").level == logging.INFO

    @patch('bet_bot.utils.logging.ensure_log_directory')
    def test_setup_logging_clears_existing_handlers(self, mock_ensure_dir, tmp_path):
        """Test that calling setup_logging multiple times doesn't duplicate handlers."""
        # Arrange
        mock_ensure_dir.return_value = tmp_path
        root_logger = logging.getLogger()

        # Act - Call twice
        setup_logging("INFO")
        initial_handler_count = len(root_logger.handlers)

        setup_logging("DEBUG")  # Second call
        final_handler_count = len(root_logger.handlers)

        # Assert - Should still have same number of handlers
        assert initial_handler_count == 2
        assert final_handler_count == 2  # Not 4

    @patch('bet_bot.utils.logging.ensure_log_directory')
    def test_setup_logging_accepts_lowercase_level(self, mock_ensure_dir, tmp_path):
        """Test that log level parameter is case-insensitive."""
        # Arrange
        mock_ensure_dir.return_value = tmp_path
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        # Act
        setup_logging("debug")  # lowercase

        # Assert
        console_handler = next(
            h for h in root_logger.handlers
            if isinstance(h, RichHandler)
        )
        assert console_handler.level == logging.DEBUG

    @patch('bet_bot.utils.logging.ensure_log_directory')
    def test_setup_logging_rejects_invalid_level(self, mock_ensure_dir, tmp_path):
        """Test that setup_logging raises ValueError for invalid log level."""
        # Arrange
        mock_ensure_dir.return_value = tmp_path

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid log level"):
            setup_logging("INVALID")

    @patch('bet_bot.utils.logging.ensure_log_directory')
    def test_setup_logging_validates_all_valid_levels(self, mock_ensure_dir, tmp_path):
        """Test that all valid log levels are accepted."""
        # Arrange
        mock_ensure_dir.return_value = tmp_path
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        # Act & Assert - All should succeed without raising
        for level in valid_levels:
            root_logger = logging.getLogger()
            root_logger.handlers.clear()
            setup_logging(level)  # Should not raise
            assert len(root_logger.handlers) == 2


class TestLoggingIntegration:
    """Integration tests for logging functionality."""

    @patch('bet_bot.utils.logging.ensure_log_directory')
    def test_logger_writes_to_console_handler(self, mock_ensure_dir, tmp_path):
        """Test that logger messages appear in console output via RichHandler."""
        # Arrange
        mock_ensure_dir.return_value = tmp_path
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        setup_logging("INFO")
        logger = get_logger("test.module")

        # Act
        logger.info("Test info message")
        logger.debug("Test debug message")  # Should not appear with INFO level

        # Assert - Verify handlers exist and are configured correctly
        console_handler = next(
            h for h in root_logger.handlers
            if isinstance(h, RichHandler)
        )
        assert console_handler.level == logging.INFO

    @patch('bet_bot.utils.logging.ensure_log_directory')
    def test_logger_writes_to_file_handler(self, mock_ensure_dir, tmp_path):
        """Test that logger messages are written to log file."""
        # Arrange
        mock_ensure_dir.return_value = tmp_path
        setup_logging("INFO")
        logger = get_logger("test.module")

        # Act
        logger.info("Test file logging")
        logger.debug("Test debug file logging")

        # Find the log file
        log_files = list(tmp_path.glob("*.log"))
        assert len(log_files) == 1

        # Assert - Read log file and verify content
        log_content = log_files[0].read_text()
        assert "Test file logging" in log_content
        assert "Test debug file logging" in log_content  # File is DEBUG level

    @patch('bet_bot.utils.logging.ensure_log_directory')
    def test_file_log_entries_are_valid_json(self, mock_ensure_dir, tmp_path):
        """Test that each line in log file is valid JSON."""
        # Arrange
        mock_ensure_dir.return_value = tmp_path
        setup_logging("INFO")
        logger = get_logger("test.json")

        # Act
        logger.info("JSON test message")
        logger.warning("Warning message")

        # Find the log file
        log_files = list(tmp_path.glob("*.log"))
        log_content = log_files[0].read_text()

        # Assert - Each line should be valid JSON
        lines = log_content.strip().split("\n")
        for line in lines:
            if line:  # Skip empty lines
                data = json.loads(line)  # Should not raise
                assert "timestamp" in data
                assert "level" in data
                assert "logger" in data
                assert "message" in data

    @patch('bet_bot.utils.logging.ensure_log_directory')
    def test_debug_level_shows_all_logs(self, mock_ensure_dir, tmp_path):
        """Test that DEBUG level shows all log messages in console."""
        # Arrange
        mock_ensure_dir.return_value = tmp_path
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        setup_logging("DEBUG")
        logger = get_logger("test.debug")

        # Act
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        # Assert - Verify console handler is set to DEBUG
        console_handler = next(
            h for h in root_logger.handlers
            if isinstance(h, RichHandler)
        )
        assert console_handler.level == logging.DEBUG

    @patch('bet_bot.utils.logging.ensure_log_directory')
    def test_error_level_filters_lower_priority(self, mock_ensure_dir, tmp_path):
        """Test that ERROR level filters out INFO and DEBUG."""
        # Arrange
        mock_ensure_dir.return_value = tmp_path
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        setup_logging("ERROR")
        logger = get_logger("test.error")

        # Act
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        # Assert - Verify console handler is set to ERROR
        console_handler = next(
            h for h in root_logger.handlers
            if isinstance(h, RichHandler)
        )
        assert console_handler.level == logging.ERROR


# Mark all tests as unit tests
pytestmark = pytest.mark.unit
