"""
Utility functions and helpers.

This module provides common utilities used throughout the bet-bot application,
including logging configuration and helper functions.
"""

from bet_bot.utils.logging import setup_logging, get_logger, mask_value, ensure_log_directory

__all__ = ["setup_logging", "get_logger", "mask_value", "ensure_log_directory"]
