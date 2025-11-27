"""
Data fetchers for bet-bot application.

This package contains modules for fetching data from various sources:
- API-Football: Primary data source for fixtures, form, injuries, odds
- ESPN: Backup form data and head-to-head history
- FlashScore: Backup odds data
- Odds-API: Alternative odds aggregation

All fetchers use async/await patterns for parallel data retrieval.
"""

import asyncio
import logging
from typing import Any

from bet_bot.data.fetchers.api_football import (
    fetch_fixtures,
    fetch_injuries,
    fetch_odds,
    fetch_team_form,
)
from bet_bot.data.fetchers.espn_scraper import fetch_team_form_espn
from bet_bot.exceptions import (
    APIAuthenticationError,
    APIRateLimitError,
    APIServerError,
    ScraperError,
)
from bet_bot.models import Fixture, Injury, TeamForm

logger = logging.getLogger(__name__)


async def fetch_team_form_with_fallback(
    team_id: str,
    league_id: str,
    team_name: str,
    league: str
) -> TeamForm | None:
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


async def fetch_all_data(
    fixture_date: str | None = None,
    leagues: list[str] | None = None
) -> dict[str, Any] | None:
    """
    Fetch data from all sources with graceful degradation and fallback logic.

    This is the main orchestration function for Phase 2 (Data Fetching Layer).
    It coordinates fetching from API-Football and ESPN scraper with automatic
    fallback: if API-Football fails, try ESPN; if all fail, continue with missing data.

    Args:
        fixture_date: Optional date filter (YYYY-MM-DD format). If None, API-Football
                     assumes today's date.
        leagues: Optional list of league names to filter by (e.g., ["Championship", "Premier League"])

    Returns:
        Optional[dict] with keys:
        - fixtures: list[Fixture] or []
        - form_data: dict[team_id, TeamForm] or {}
        - injuries: dict[team_id, list[Injury]] or {}
        - odds: dict[fixture_id, Odds] or {}
        - h2h: dict[fixture_id, list[str]] or {}

        Returns None only on critical failures (authentication error).
        Returns dict with empty values if no data retrieved.

    Raises:
        APIAuthenticationError: If API-Football auth fails (401/403) - halts pipeline

    Example:
        data = await fetch_all_data(fixture_date="2025-11-25", leagues=["Championship"])
        if data:
            print(f"Fetched {len(data['fixtures'])} fixtures")
            print(f"Form data for {len(data['form_data'])} teams")
        else:
            print("Authentication error - cannot continue")
    """
    logger.info(
        f"Starting graceful degradation fetch | "
        f"Date: {fixture_date or 'today'} | "
        f"Leagues: {', '.join(leagues) if leagues else 'all'}"
    )

    # Initialize result structure with all required keys
    result: dict[str, Any] = {
        "fixtures": list[Fixture]([]),
        "form_data": dict[str, TeamForm]({}),
        "injuries": dict[str, Any]({}),
        "odds": dict[str, Any]({}),
        "h2h": dict[str, Any]({})
    }

    # Track which sources succeeded/failed for logging
    sources_used: dict[str, Any] = {
        "api_football": {"fixtures": False, "form": False, "injuries": False, "odds": False, "h2h": False},
        "espn_form": False
    }

    # ========== PHASE 1: Fetch Fixtures ==========
    try:
        logger.info("Fetching fixtures from API-Football")
        fixtures = await fetch_fixtures(date=fixture_date or "", league_id=None)

        if fixtures:
            result["fixtures"] = fixtures
            sources_used["api_football"]["fixtures"] = True
            logger.info(f"✓ Fetched {len(fixtures)} fixtures from API-Football")
        else:
            logger.info(f"No fixtures found for date: {fixture_date or 'today'}")

    except APIAuthenticationError as e:
        logger.critical(f"API-Football authentication failed - halting pipeline: {str(e)}")
        return None

    except APIRateLimitError as e:
        logger.error(f"API-Football rate limit exceeded: {str(e)}")
        return None

    except APIServerError as e:
        logger.error(f"API-Football server error: {str(e)}")
        # Continue without fixtures - non-critical

    except (TimeoutError, asyncio.TimeoutError, Exception) as e:
        logger.warning(f"API-Football timeout/network error: {str(e)}")
        # Continue without fixtures - non-critical

    # If no fixtures, return early (no point fetching form/injuries/odds without fixtures)
    if not result["fixtures"]:
        logger.warning("No fixtures available - skipping form/injuries/odds/h2h fetching")
        logger.info(
            f"Fetching complete: 0 fixtures | "
            f"Sources used: API-Football"
        )
        return result

    # ========== PHASE 2: Fetch Form Data (with ESPN fallback) ==========
    logger.info(f"Fetching form data for {len(result['fixtures'])} teams")
    form_semaphore = asyncio.Semaphore(5)  # Limit ESPN scraper concurrency

    async def fetch_form_for_fixture(fixture: Fixture) -> tuple[str, TeamForm | None, TeamForm | None]:
        """Fetch form for both home and away teams in a fixture."""
        home_form = None
        away_form = None

        # Home team form
        try:
            home_form = await fetch_team_form_with_fallback(
                team_id=fixture.home_team.id,
                league_id=fixture.league.league_id,
                team_name=fixture.home_team.name,
                league=fixture.league.league_name
            )
            if home_form:
                sources_used["api_football"]["form"] = True
        except Exception as e:
            logger.warning(f"Failed to fetch form for home team {fixture.home_team.name}: {str(e)}")

        # Away team form
        try:
            away_form = await fetch_team_form_with_fallback(
                team_id=fixture.away_team.id,
                league_id=fixture.league.league_id,
                team_name=fixture.away_team.name,
                league=fixture.league.league_name
            )
            if away_form:
                sources_used["api_football"]["form"] = True
        except Exception as e:
            logger.warning(f"Failed to fetch form for away team {fixture.away_team.name}: {str(e)}")

        return fixture.fixture_id, home_form, away_form

    # Fetch form for all fixtures
    try:
        form_tasks = [fetch_form_for_fixture(f) for f in result["fixtures"]]
        form_results = await asyncio.gather(*form_tasks, return_exceptions=True)

        form_count = 0
        for form_result in form_results:
            if isinstance(form_result, BaseException):
                logger.warning(f"Form fetch task failed: {str(form_result)}")
                continue

            fixture_id, home_form, away_form = form_result
            if home_form:
                result["form_data"][home_form.team_id] = home_form
                form_count += 1
            if away_form:
                result["form_data"][away_form.team_id] = away_form
                form_count += 1

        logger.info(f"✓ Fetched form data for {form_count} teams")

    except Exception as e:
        logger.error(f"Form data fetching failed: {str(e)}")

    # ========== PHASE 3: Fetch Injuries ==========
    logger.info(f"Fetching injury data for {len(result['fixtures'])} teams")

    async def fetch_injuries_for_team(team_id: str, team_name: str) -> tuple[str, Injury | None]:
        """Fetch injuries for a team."""
        try:
            injuries = await fetch_injuries(team_id)
            if injuries:
                sources_used["api_football"]["injuries"] = True
                return team_id, injuries
        except Exception as e:
            logger.warning(f"Failed to fetch injuries for team {team_name} ({team_id}): {str(e)}")

        return team_id, None

    # Collect unique teams from fixtures
    team_ids = set()
    for fixture in result["fixtures"]:
        team_ids.add((fixture.home_team.id, fixture.home_team.name))
        team_ids.add((fixture.away_team.id, fixture.away_team.name))

    try:
        injury_tasks = [fetch_injuries_for_team(tid, tname) for tid, tname in team_ids]
        injury_results = await asyncio.gather(*injury_tasks, return_exceptions=True)

        injuries_count = 0
        for injury_result in injury_results:
            if isinstance(injury_result, BaseException):
                logger.warning(f"Injury fetch task failed: {str(injury_result)}")
                continue

            team_id, injuries = injury_result
            if injuries:
                result["injuries"][team_id] = injuries
                injuries_count += 1

        logger.info(f"✓ Fetched injury data for {injuries_count} teams")

    except Exception as e:
        logger.error(f"Injury data fetching failed: {str(e)}")

    # ========== PHASE 4: Fetch Odds ==========
    logger.info(f"Fetching odds for {len(result['fixtures'])} fixtures")

    async def fetch_odds_for_fixture(fixture_id: str) -> tuple[str, Any | None]:
        """Fetch odds for a fixture."""
        try:
            odds = await fetch_odds(fixture_id)
            if odds:
                sources_used["api_football"]["odds"] = True
                return fixture_id, odds
        except Exception as e:
            logger.warning(f"Failed to fetch odds for fixture {fixture_id}: {str(e)}")

        return fixture_id, None

    try:
        odds_tasks = [fetch_odds_for_fixture(f.fixture_id) for f in result["fixtures"]]
        odds_results = await asyncio.gather(*odds_tasks, return_exceptions=True)

        odds_count = 0
        for odds_result in odds_results:
            if isinstance(odds_result, BaseException):
                logger.warning(f"Odds fetch task failed: {str(odds_result)}")
                continue

            fixture_id, odds = odds_result
            if odds:
                result["odds"][fixture_id] = odds
                odds_count += 1

        logger.info(f"✓ Fetched odds for {odds_count} fixtures")

    except Exception as e:
        logger.error(f"Odds fetching failed: {str(e)}")

    # ========== PHASE 5: Fetch Head-to-Head ==========
    # Note: fetch_h2h not yet implemented in API-Football integration
    # Story 2.5 placeholder - h2h returns empty dict for now
    logger.info(f"Head-to-head data fetching not yet implemented (planned for future story)")
    result["h2h"] = {}

    # ========== COMPLETION ==========
    logger.info(
        f"Fetching complete: {len(result['fixtures'])} fixtures | "
        f"Form: {len(result['form_data'])} teams | "
        f"Injuries: {len(result['injuries'])} teams | "
        f"Odds: {len(result['odds'])} fixtures | "
        f"H2H: {len(result['h2h'])} fixtures"
    )
    logger.info(
        f"Sources used: API-Football "
        f"(fixtures={sources_used['api_football']['fixtures']}, "
        f"form={sources_used['api_football']['form']}, "
        f"injuries={sources_used['api_football']['injuries']}, "
        f"odds={sources_used['api_football']['odds']}) | "
        f"ESPN form backup: {sources_used['espn_form']}"
    )

    return result


__all__ = [
    "fetch_fixtures",
    "fetch_team_form",
    "fetch_team_form_with_fallback",
    "fetch_injuries",
    "fetch_odds",
    "fetch_all_data",
]
