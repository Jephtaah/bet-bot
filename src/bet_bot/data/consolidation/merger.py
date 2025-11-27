"""
Data merging utilities for the consolidation layer.

This module provides helper functions for merging data from multiple sources,
resolving conflicts by timestamp preference, and tracking source lineage.

Functions:
    resolve_conflict_by_timestamp: Choose fresher data when sources conflict
    track_source_lineage: Build audit trail of data sources for each field
    merge_optional_list: Safely merge optional lists of data
"""

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def resolve_conflict_by_timestamp(
    value1: Any,
    timestamp1: datetime | None,
    source1: str,
    value2: Any,
    timestamp2: datetime | None,
    source2: str,
    field_name: str
) -> tuple[Any, str]:
    """
    Resolve conflict between two data sources by preferring fresher data.

    When multiple sources provide data for the same field, this function
    compares timestamps and returns the fresher value. Logs the resolution
    decision for audit purposes.

    Args:
        value1: Data from first source
        timestamp1: When value1 was fetched (None if unknown)
        source1: Name of first source (e.g., "api_football")
        value2: Data from second source
        timestamp2: When value2 was fetched (None if unknown)
        source2: Name of second source (e.g., "espn_scraper")
        field_name: Name of field being merged (for logging)

    Returns:
        Tuple of (selected_value, selected_source)

    Example:
        >>> api_form = TeamForm(team_id="123", ...)
        >>> espn_form = TeamForm(team_id="123", ...)
        >>> api_time = datetime(2025, 11, 26, 14, 0, 0, tzinfo=timezone.utc)
        >>> espn_time = datetime(2025, 11, 26, 12, 0, 0, tzinfo=timezone.utc)
        >>> value, source = resolve_conflict_by_timestamp(
        ...     api_form, api_time, "api_football",
        ...     espn_form, espn_time, "espn_scraper",
        ...     "form_data"
        ... )
        >>> print(f"Using {source} form (fresher)")
        Using api_football form (fresher)
    """
    # If both timestamps available, compare them
    if timestamp1 is not None and timestamp2 is not None:
        if timestamp1 > timestamp2:
            logger.info(
                f"{field_name}: Preferring {source1} over {source2} "
                f"({timestamp1.isoformat()} vs {timestamp2.isoformat()})"
            )
            return value1, source1
        elif timestamp2 > timestamp1:
            logger.info(
                f"{field_name}: Preferring {source2} over {source1} "
                f"({timestamp2.isoformat()} vs {timestamp1.isoformat()})"
            )
            return value2, source2
        else:
            # Same timestamp, prefer source1 (arbitrary but consistent)
            logger.debug(f"{field_name}: Sources have same timestamp, using {source1}")
            return value1, source1

    # If only one timestamp available, prefer that one
    if timestamp1 is not None:
        logger.debug(f"{field_name}: Only {source1} has timestamp, using it")
        return value1, source1
    if timestamp2 is not None:
        logger.debug(f"{field_name}: Only {source2} has timestamp, using it")
        return value2, source2

    # No timestamps available - use value1 by default
    logger.debug(f"{field_name}: No timestamps available, defaulting to {source1}")
    return value1, source1


def track_source_lineage(
    fixture_id: str,
    field_name: str,
    source: str,
    timestamp: datetime | None = None
) -> dict[str, Any]:
    """
    Create source lineage entry for audit trail.

    Each piece of data in the consolidated fixture should be tracked with
    its original source and fetch timestamp. This enables downstream consumers
    (Story 3.2 validation, Story 3.3 quality scoring) to assess data reliability.

    Args:
        fixture_id: ID of fixture being consolidated
        field_name: Name of data field (e.g., "form_home", "injuries_away")
        source: Source identifier (e.g., "api_football", "espn_scraper")
        timestamp: When data was fetched (if available)

    Returns:
        Dictionary with source metadata for tracking

    Example:
        >>> lineage = track_source_lineage(
        ...     fixture_id="548821",
        ...     field_name="form_home",
        ...     source="api_football",
        ...     timestamp=datetime.now(timezone.utc)
        ... )
        >>> print(lineage)
        {
            'field': 'form_home',
            'source': 'api_football',
            'timestamp': '2025-11-26T15:30:45.123456+00:00'
        }
    """
    return {
        'field': field_name,
        'source': source,
        'timestamp': timestamp.isoformat() if timestamp else None
    }


def merge_optional_list(
    list1: list[Any] | None,
    list2: list[Any] | None,
    field_name: str
) -> list[Any]:
    """
    Safely merge two optional lists, preferring non-empty ones.

    When consolidating optional data (injuries, h2h history), handles
    the case where one or both sources might have None or empty values.

    Args:
        list1: First list (may be None or empty)
        list2: Second list (may be None or empty)
        field_name: Name of field being merged (for logging)

    Returns:
        Merged list (non-empty if either input is non-empty, empty list if both None)

    Example:
        >>> injuries1 = [Injury(player_id="p1", ...)]
        >>> injuries2 = None
        >>> result = merge_optional_list(injuries1, injuries2, "home_team_injuries")
        >>> print(len(result))
        1
    """
    # Convert None to empty list for easier handling
    list1 = list1 or []
    list2 = list2 or []

    # If both empty, return empty list
    if not list1 and not list2:
        logger.debug(f"{field_name}: Both sources empty, returning empty list")
        return []

    # Prefer non-empty list, or combine if both have data
    if list1 and list2:
        # Both have data - return first source (primary wins)
        logger.debug(f"{field_name}: Both sources have data, using primary source ({len(list1)} items)")
        return list1
    elif list1:
        logger.debug(f"{field_name}: Using primary source ({len(list1)} items)")
        return list1
    else:
        logger.debug(f"{field_name}: Using fallback source ({len(list2)} items)")
        return list2
