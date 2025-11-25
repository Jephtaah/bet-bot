"""
Configuration management module.

This module provides application-wide configuration management through a
singleton Config instance. All configuration is loaded from environment
variables for security.

Usage:
    from bet_bot.config import config, validate_config

    # Validate config at startup
    if not validate_config():
        sys.exit(1)

    # Access configuration
    api_key = config.openai_api_key

    # Safe logging
    masked = config.get_masked_key(config.openai_api_key)
    logger.info(f"Using OpenAI key: {masked}")

Security:
    - API keys are never hardcoded
    - Full keys are never logged (use get_masked_key())
    - .env file is gitignored
    - Validation runs at startup

The singleton pattern ensures configuration is loaded once and accessible
throughout the application without re-reading environment variables.

Note:
    Logging is automatically initialized when this module is imported.
    The log level is determined by the LOG_LEVEL environment variable
    or defaults to INFO if not set.
"""

from bet_bot.config.settings import Config, config, validate_config

# Auto-initialize logging when config is imported
# This ensures logging is set up before any module uses it
if config is not None:
    from bet_bot.utils.logging import setup_logging
    setup_logging(config.log_level)

__all__ = ["config", "validate_config", "Config"]
