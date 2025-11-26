"""
Data consolidation module for bet-bot.

This package normalizes data from multiple sources (API-Football, ESPN, etc.)
into unified Fixture objects. It's the second stage of the data pipeline,
following data fetching (Stage 1) and preceding data validation (Stage 3).

Main Function:
    consolidate_fixtures: Merge multi-source fixture data into unified Fixture schema

The consolidation process:
1. Takes raw output from fetch_all_data() (Story 2.5)
2. Extracts fixture data from API-Football (primary source)
3. Merges form data (API-Football primary, ESPN fallback) by team ID
4. Merges injury data by team ID
5. Merges odds data by fixture ID
6. Merges head-to-head history by fixture ID
7. Returns list of complete Fixture objects ready for validation

Example:
    >>> from bet_bot.data.consolidation import consolidate_fixtures
    >>> from bet_bot.data.fetchers import fetch_all_data
    >>>
    >>> raw_data = await fetch_all_data()
    >>> fixtures = await consolidate_fixtures(raw_data)
    >>> print(f"Consolidated {len(fixtures)} fixtures")

Architecture:
    - Input: Messy data from multiple sources, some may be missing
    - Output: Clean, normalized Fixture[] ready for downstream analysis
    - Error handling: Graceful degradation - logs issues, skips bad fixtures
    - Data quality: Tracks source metadata for validation (Story 3.2)

Files in this package:
    consolidator.py: Main consolidation orchestration (consolidate_fixtures)
    merger.py: Helper functions for conflict resolution and source tracking
"""

from bet_bot.data.consolidation.consolidator import consolidate_fixtures

__all__ = ["consolidate_fixtures"]
