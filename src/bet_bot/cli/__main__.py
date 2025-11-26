"""
Entry point for running bet-bot CLI as a module.

This allows execution via: python -m bet_bot.cli
"""

from bet_bot.cli.main import app

if __name__ == "__main__":
    app()
