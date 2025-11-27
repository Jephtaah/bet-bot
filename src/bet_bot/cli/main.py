"""
bet-bot CLI Entry Point

This module provides the command-line interface for the bet-bot tool using Typer.
It defines the main application structure and commands for analyzing football
betting opportunities with positive expected value.

Usage:
    python -m bet_bot.cli --help
    python -m bet_bot.cli analyze --bankroll 1000
"""

import typer
import sys

from bet_bot.config import config, validate_config
from bet_bot.utils import get_logger

# Version constant
__version__ = "0.1.0"

# Get logger for CLI module
logger = get_logger(__name__)

# Initialize Typer app with metadata
app = typer.Typer(
    name="bet-bot",
    help="Positive Expected Value Detection Tool for Football Betting",
    add_completion=False  # Disable shell completion for simplicity
)


def version_callback(value: bool) -> None:
    """
    Callback for --version flag.

    Prints the current version and exits immediately.
    """
    if value:
        typer.echo(f"bet-bot version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit"
    )
) -> None:
    """
    bet-bot: Positive Expected Value Detection Tool for Football Betting

    Use 'bet-bot analyze' to find betting opportunities with positive expected value.
    """
    # Validate configuration at startup before any command runs
    try:
        validate_config()
    except ValueError as e:
        typer.echo(f"Configuration Error: {e}", err=True)
        typer.echo("\nPlease ensure you have:", err=True)
        typer.echo("1. Created a .env file in the project root", err=True)
        typer.echo("2. Added your API keys (see .env.template for format)", err=True)
        typer.echo("3. Set OPENAI_API_KEY and API_FOOTBALL_KEY", err=True)
        raise typer.Exit(1)


@app.command()
def analyze(
    bankroll: float = typer.Option(
        ...,
        "--bankroll",
        "-b",
        help="Your betting bankroll in USD",
        min=0
    ),
    config_path: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging (DEBUG level)"
    )
) -> None:
    """
    Analyze today's fixtures and find positive EV betting opportunities.

    This command will (in future stories):
    - Fetch today's football fixtures from API-Football
    - Scrape form data from ESPN
    - Get current odds from odds providers
    - Use OpenAI to analyze betting opportunities
    - Calculate expected value and recommend stakes

    Example:
        bet-bot analyze --bankroll 1000
        bet-bot analyze --bankroll 500 --config ~/.bet-bot/config.yaml
        bet-bot analyze --bankroll 1000 --verbose

    Args:
        bankroll: Your available betting bankroll in USD (must be positive)
        config: Optional path to custom configuration file
        verbose: Enable verbose logging (shows DEBUG level logs)
    """
    # Log CLI startup
    logger.info(f"Starting bet-bot {__version__}")
    logger.debug(f"Command: analyze, Bankroll: ${bankroll:.2f}, Verbose: {verbose}")

    # Validate bankroll is positive
    if bankroll <= 0:
        logger.error("Bankroll validation failed: value must be positive")
        typer.echo("Error: Bankroll must be positive", err=True)
        raise typer.Exit(1)

    # Print confirmation message (stub implementation)
    typer.echo(f"Starting analysis with bankroll: ${bankroll:.2f}")

    # Show masked API keys for debugging (Story 1.4 - Configuration loaded)
    logger.debug(f"OpenAI API Key: {config.get_masked_key(config.openai_api_key)}")
    logger.debug(f"API-Football Key: {config.get_masked_key(config.api_football_key)}")

    typer.echo(f"OpenAI API Key: {config.get_masked_key(config.openai_api_key)}")
    typer.echo(f"API-Football Key: {config.get_masked_key(config.api_football_key)}")
    typer.echo(f"Log Level: {config.log_level}")

    # Log verbose mode
    if verbose:
        logger.info("Verbose mode enabled")
        typer.echo("Verbose logging enabled")

    # Future stories will wire in the full analysis pipeline here:
    # - Story 8.1: Wire full analysis pipeline
    if config_path:
        logger.info(f"Using custom config file: {config_path}")
        typer.echo(f"Using config file: {config_path}")

    logger.info("Analysis command completed (stub implementation)")


# Entry point for module execution
if __name__ == "__main__":
    app()
