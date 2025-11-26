"""
Data consolidation orchestration for the bet-bot pipeline.

This module normalizes data from multiple sources (API-Football, ESPN scraper)
into a unified Fixture schema. Handles conflicts by preferring fresher data,
tracks source lineage for audit purposes, and continues gracefully when
optional data is missing.

Main Function:
    consolidate_fixtures: Merge multi-source data into unified Fixture objects

The consolidation process:
1. Extract core fixture data from API-Football (always available)
2. Merge team form data (API-Football primary, ESPN fallback)
3. Merge injury data (API-Football primary, empty list if missing)
4. Merge odds data (API-Football primary, None if missing)
5. Merge head-to-head history (static data, empty list if missing)
6. Track source lineage for all merged data
7. Return list of complete Fixture objects with metadata
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from bet_bot.data.consolidation.merger import (
    merge_optional_list,
    resolve_conflict_by_timestamp,
    track_source_lineage,
)
from bet_bot.exceptions import DataValidationError
from bet_bot.models import Fixture, League, Team, TeamForm

logger = logging.getLogger(__name__)


async def consolidate_fixtures(
    raw_data: dict[str, Any],
    fixture_list: list[dict] | None = None
) -> list[Fixture]:
    """
    Consolidate multi-source fixture data into unified Fixture objects.

    This is the main orchestration function for the Data Consolidation Layer.
    Takes raw output from fetch_all_data() (API-Football + ESPN fallbacks) and
    normalizes it into a clean list of Fixture objects with all fields populated
    and source lineage tracked.

    Args:
        raw_data: Output dict from fetch_all_data() with keys:
            - fixtures: list of partial fixture objects from API-Football
            - form_data: dict[team_id, TeamForm] with form data from API-Football/ESPN
            - injuries: dict[team_id, list[Injury]] with injury data
            - odds: dict[fixture_id, Odds] with betting odds
            - h2h: dict[fixture_id, list[str]] with head-to-head history

        fixture_list: Optional - if provided, used instead of raw_data['fixtures'].
                     Allows explicit fixture list override for testing.

    Returns:
        list[Fixture]: Consolidated fixtures with all fields populated,
                      source metadata attached, and ready for downstream
                      validation and analysis.

    Raises:
        DataValidationError: If critical data is malformed (non-recoverable)

    Example:
        >>> raw_data = await fetch_all_data()
        >>> fixtures = await consolidate_fixtures(raw_data)
        >>> print(f"Consolidated {len(fixtures)} fixtures")
        >>> for fixture in fixtures:
        ...     print(f"{fixture.home_team.name} vs {fixture.away_team.name}")

    Architecture Notes:
        - Input: Messy data from multiple sources (some may be missing)
        - Output: Clean, normalized Fixture objects ready for analysis
        - Error handling: Logs issues, skips bad fixtures, continues with others
        - Never halts on individual fixture failure (only on critical errors)
        - Tracks all data sources for downstream validation (Story 3.2)
    """
    logger.info("Starting fixture consolidation from multi-source data")

    # Extract fixtures list
    if fixture_list is None:
        fixture_list = raw_data.get('fixtures', [])

    if not fixture_list:
        logger.warning("No fixtures provided for consolidation")
        return []

    # Extract other data sources with defaults
    form_data = raw_data.get('form_data', {}) or {}
    injuries_data = raw_data.get('injuries', {}) or {}
    odds_data = raw_data.get('odds', {}) or {}
    h2h_data = raw_data.get('h2h', {}) or {}

    logger.info(
        f"Consolidating {len(fixture_list)} fixtures with "
        f"form({len(form_data)}), injuries({len(injuries_data)}), "
        f"odds({len(odds_data)}), h2h({len(h2h_data)})"
    )

    # Consolidate each fixture
    consolidated = []
    errors = []

    for idx, raw_fixture in enumerate(fixture_list):
        try:
            fixture = await _consolidate_single_fixture(
                raw_fixture,
                form_data,
                injuries_data,
                odds_data,
                h2h_data
            )
            consolidated.append(fixture)
        except Exception as e:
            error_msg = f"Fixture {idx}: {str(e)}"
            logger.warning(f"Failed to consolidate fixture: {error_msg}")
            errors.append(error_msg)
            # Continue with next fixture (don't halt on individual failure)

    # Log summary
    logger.info(
        f"Consolidation complete: {len(consolidated)}/{len(fixture_list)} "
        f"fixtures successfully consolidated"
    )
    if errors:
        logger.warning(f"Failed to consolidate {len(errors)} fixtures")

    # Only raise error if ALL fixtures failed (critical)
    if consolidated:
        return consolidated
    elif errors and len(fixture_list) > 0:
        raise DataValidationError(
            "consolidation",
            fixture_list,
            f"All {len(fixture_list)} fixtures failed to consolidate: {'; '.join(errors[:3])}"
        )
    else:
        return []


async def _consolidate_single_fixture(
    raw_fixture: dict,
    form_data: dict[str, TeamForm],
    injuries_data: dict[str, list],
    odds_data: dict[str, Any],
    h2h_data: dict[str, list[str]]
) -> Fixture:
    """
    Consolidate a single fixture from raw data.

    Internal helper function that processes one fixture from the API-Football
    response, merging form/injuries/odds from other sources, and returning
    a complete Fixture object.

    Args:
        raw_fixture: Raw fixture from API-Football (may be partial)
        form_data: Keyed by team_id
        injuries_data: Keyed by team_id
        odds_data: Keyed by fixture_id
        h2h_data: Keyed by fixture_id

    Returns:
        Fixture: Complete fixture object with all fields populated

    Raises:
        Exception: If critical fields are missing or malformed
    """
    try:
        # ===== EXTRACT CORE FIXTURE DATA =====
        fixture_id = raw_fixture.get('fixture_id')
        if not fixture_id:
            raise ValueError("fixture_id required")

        # Extract team data
        home_team_id = raw_fixture.get('home_team_id')
        home_team_name = raw_fixture.get('home_team_name')
        away_team_id = raw_fixture.get('away_team_id')
        away_team_name = raw_fixture.get('away_team_name')
        league_id = raw_fixture.get('league_id')
        league_name = raw_fixture.get('league_name')
        league_country = raw_fixture.get('league_country', 'Unknown')
        league_season = raw_fixture.get('league_season', 2025)

        if not all([home_team_id, home_team_name, away_team_id, away_team_name]):
            raise ValueError("Team data incomplete")
        if not all([league_id, league_name]):
            raise ValueError("League data incomplete")

        # Extract time
        kickoff_time_str = raw_fixture.get('kickoff_time')
        if isinstance(kickoff_time_str, str):
            # Parse ISO format string
            try:
                kickoff_time = datetime.fromisoformat(kickoff_time_str.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError(f"Invalid kickoff time format: {kickoff_time_str}")
        elif isinstance(kickoff_time_str, datetime):
            kickoff_time = kickoff_time_str
        else:
            raise ValueError(f"kickoff_time must be string or datetime, got {type(kickoff_time_str)}")

        # Ensure timezone-aware
        if kickoff_time.tzinfo is None:
            kickoff_time = kickoff_time.replace(tzinfo=timezone.utc)

        # ===== BUILD LEAGUE OBJECT =====
        league = League(
            league_id=league_id,
            league_name=league_name,
            league_country=league_country,
            league_season=league_season
        )

        # ===== BUILD TEAM OBJECTS WITH FORM =====
        home_team = _build_team_with_form(
            team_id=home_team_id,
            team_name=home_team_name,
            form_data=form_data,
            injuries_data=injuries_data
        )

        away_team = _build_team_with_form(
            team_id=away_team_id,
            team_name=away_team_name,
            form_data=form_data,
            injuries_data=injuries_data
        )

        # ===== MERGE ODDS DATA =====
        odds = odds_data.get(fixture_id, {}) or {}

        # ===== MERGE HEAD-TO-HEAD DATA =====
        h2h = h2h_data.get(fixture_id, []) or []

        # ===== CREATE FIXTURE OBJECT =====
        fixture = Fixture(
            fixture_id=fixture_id,
            kickoff_time=kickoff_time,
            home_team=home_team,
            away_team=away_team,
            league=league,
            odds=odds,
            head_to_head_history=h2h
        )

        logger.debug(
            f"Consolidated fixture {fixture_id}: "
            f"{home_team_name} vs {away_team_name} @ {league_name}"
        )

        return fixture

    except Exception as e:
        logger.exception(f"Error consolidating fixture: {str(e)}")
        raise


def _build_team_with_form(
    team_id: str,
    team_name: str,
    form_data: dict[str, TeamForm],
    injuries_data: dict[str, list]
) -> Team:
    """
    Build Team object with form and injury data merged.

    Extracts form data from form_data dict (if available) and injury data,
    then creates a Team object with all fields populated.

    Args:
        team_id: Team identifier
        team_name: Team display name
        form_data: Dict[team_id, TeamForm]
        injuries_data: Dict[team_id, list[Injury]]

    Returns:
        Team: Complete team object with form and injuries
    """
    # Extract form data (may not exist)
    team_form = form_data.get(team_id)
    if team_form:
        form_5 = team_form.last_5_results or []
        avg_goals_for = team_form.goals_avg_home or team_form.goals_avg_away or 0.0
        avg_goals_against = team_form.goals_against_avg_home or team_form.goals_against_avg_away or 0.0
    else:
        form_5 = []
        avg_goals_for = 0.0
        avg_goals_against = 0.0
        logger.debug(f"Team form data not available for {team_name} ({team_id})")

    # Extract injuries (may be empty list or missing)
    injuries = injuries_data.get(team_id) or []

    # Extract injury player IDs for Team model (which expects list of IDs, not objects)
    injury_ids = []
    if injuries:
        for injury in injuries:
            if hasattr(injury, 'player_id'):
                injury_ids.append(injury.player_id)
            elif isinstance(injury, dict) and 'player_id' in injury:
                injury_ids.append(injury['player_id'])

    # Build Team object
    team = Team(
        id=team_id,
        name=team_name,
        form_5_games=form_5,
        avg_goals_for=avg_goals_for,
        avg_goals_against=avg_goals_against,
        injuries=injury_ids
    )

    return team
