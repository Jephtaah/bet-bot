"""
Data fetchers for bet-bot application.

This package contains modules for fetching data from various sources:
- API-Football: Primary data source for fixtures, form, injuries, odds
- ESPN: Backup form data and head-to-head history
- FlashScore: Backup odds data
- Odds-API: Alternative odds aggregation

All fetchers use async/await patterns for parallel data retrieval.
"""

import logging
from typing import Optional

from bet_bot.data.fetchers.api_football import (
    fetch_fixtures,
    fetch_injuries,
    fetch_odds,
    fetch_team_form,
)
from bet_bot.data.fetchers.espn_scraper import fetch_team_form_espn
from bet_bot.models import TeamForm

logger = logging.getLogger(__name__)


async def fetch_team_form_with_fallback(
    team_id: str,
    league_id: str,
    team_name: str,
    league: str
) -> Optional[TeamForm]:
    """
    Fetch team form with API-Football primary, ESPN scraper backup.

    This function implements the backup-only pattern for ESPN scraper:
    1. Try API-Football first (primary data source)
    2. If API-Football fails (returns None), try ESPN scraper
    3. Return result from whichever source succeeds
    4. Log which source was used for transparency

    Args:
        team_id: Team ID (for API-Football)
        league_id: League ID (for API-Football)
        team_name: Team name (for ESPN scraper)
        league: League name (for ESPN scraper)

    Returns:
        TeamForm object from API-Football or ESPN, or None if both fail

    Example:
        form = await fetch_team_form_with_fallback(
            team_id="33",
            league_id="39",
            team_name="Leeds United",
            league="Championship"
        )
        if form:
            print(f"Source: API-Football/ESPN | Win %: {form.win_percentage_5}")
        else:
            print("No form data available from any source")
    """
    # Try API-Football first (primary source)
    form = await fetch_team_form(
        team_id=team_id,
        league_id=league_id,
        team_name=team_name
    )

    if form is not None:
        logger.info(
            f"Fetched team form from API-Football | "
            f"Team: {team_name} | ID: {team_id}"
        )
        return form

    # API-Football failed - try ESPN scraper as backup
    logger.info(
        f"API-Football form unavailable, trying ESPN scraper | "
        f"Team: {team_name}"
    )

    form = await fetch_team_form_espn(
        team_name=team_name,
        league=league
    )

    if form is not None:
        logger.info(
            f"Fetched team form from ESPN scraper (backup) | "
            f"Team: {team_name}"
        )
        return form

    # Both sources failed
    logger.warning(
        f"Team form unavailable from all sources | "
        f"Team: {team_name} | "
        f"API-Football and ESPN scraper both failed"
    )
    return None


__all__ = [
    "fetch_fixtures",
    "fetch_team_form",
    "fetch_team_form_with_fallback",
    "fetch_injuries",
    "fetch_odds",
]
