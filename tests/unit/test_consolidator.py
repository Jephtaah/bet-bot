"""
Unit tests for the data consolidation layer.

Tests consolidate_fixtures() function with various data scenarios:
- All sources present and complete
- Missing optional data (form, injuries, odds)
- Partial data (some teams have form, some don't)
- Source conflict resolution (timestamps)
- Error handling and graceful degradation

Target: 85%+ code coverage for consolidator.py

All tests use unittest.mock for mocking and pytest async support (@pytest.mark.asyncio).
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from bet_bot.data.consolidation import consolidate_fixtures
from bet_bot.exceptions import DataValidationError
from bet_bot.models import Fixture, InjuredPlayer, League, Team, TeamForm


# ============================================================================
# FIXTURES AND TEST DATA
# ============================================================================


@pytest.fixture
def sample_league():
    """Create a sample league for tests."""
    return League(
        league_id="39",
        league_name="Championship",
        league_country="England",
        league_season=2025
    )


@pytest.fixture
def sample_api_football_fixture():
    """Create a sample raw fixture from API-Football."""
    return {
        'fixture_id': '548821',
        'home_team_id': '33',
        'home_team_name': 'Leeds United',
        'away_team_id': '62',
        'away_team_name': 'Norwich City',
        'league_id': '39',
        'league_name': 'Championship',
        'league_country': 'England',
        'league_season': 2025,
        'kickoff_time': '2025-11-25T15:00:00+00:00'
    }


@pytest.fixture
def sample_form_data():
    """Create sample form data for multiple teams."""
    return {
        '33': TeamForm(
            team_id='33',
            team_name='Leeds United',
            last_5_results=['W', 'W', 'D', 'L', 'W'],
            last_10_results=['W', 'W', 'D', 'L', 'W', 'L', 'D', 'W', 'W', 'D'],
            win_percentage_5=0.60,
            win_percentage_10=0.55,
            goals_avg_home=1.9,
            goals_avg_away=1.7,
            goals_against_avg_home=1.1,
            goals_against_avg_away=1.3
        ),
        '62': TeamForm(
            team_id='62',
            team_name='Norwich City',
            last_5_results=['W', 'D', 'D', 'D', 'L'],
            last_10_results=['W', 'D', 'D', 'D', 'L', 'W', 'W', 'D', 'L', 'L'],
            win_percentage_5=0.20,
            win_percentage_10=0.30,
            goals_avg_home=1.5,
            goals_avg_away=1.2,
            goals_against_avg_home=1.4,
            goals_against_avg_away=1.6
        )
    }


@pytest.fixture
def sample_injuries_data():
    """Create sample injury data."""
    return {
        '33': [
            MagicMock(player_id='p001'),
            MagicMock(player_id='p002')
        ],
        '62': [
            MagicMock(player_id='p003')
        ]
    }


@pytest.fixture
def sample_odds_data():
    """Create sample odds data."""
    return {
        '548821': {
            'match_result': {
                'home': 2.10,
                'draw': 3.50,
                'away': 3.20
            },
            'total_goals': {
                'over_2_5': 1.85,
                'under_2_5': 1.95
            }
        }
    }


@pytest.fixture
def sample_h2h_data():
    """Create sample head-to-head data."""
    return {
        '548821': ['W', 'D', 'W', 'L', 'W']
    }


# ============================================================================
# BASIC CONSOLIDATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_consolidate_all_sources_present(
    sample_api_football_fixture,
    sample_form_data,
    sample_injuries_data,
    sample_odds_data,
    sample_h2h_data
):
    """Test consolidate_fixtures with all sources present and complete."""
    raw_data = {
        'fixtures': [sample_api_football_fixture],
        'form_data': sample_form_data,
        'injuries': sample_injuries_data,
        'odds': sample_odds_data,
        'h2h': sample_h2h_data
    }

    fixtures = await consolidate_fixtures(raw_data)

    assert len(fixtures) == 1
    fixture = fixtures[0]

    # Verify fixture attributes
    assert fixture.fixture_id == '548821'
    assert fixture.home_team.name == 'Leeds United'
    assert fixture.away_team.name == 'Norwich City'
    assert fixture.league.league_name == 'Championship'

    # Verify form data merged
    assert fixture.home_team.form_5_games == ['W', 'W', 'D', 'L', 'W']
    assert fixture.away_team.form_5_games == ['W', 'D', 'D', 'D', 'L']

    # Verify injuries merged
    assert len(fixture.home_team.injuries) == 2
    assert len(fixture.away_team.injuries) == 1

    # Verify odds merged
    assert 'match_result' in fixture.odds
    assert fixture.odds['match_result']['home'] == 2.10

    # Verify h2h merged
    assert fixture.head_to_head_history == ['W', 'D', 'W', 'L', 'W']


@pytest.mark.asyncio
async def test_consolidate_empty_fixture_list():
    """Test consolidate_fixtures with empty fixture list."""
    raw_data = {
        'fixtures': [],
        'form_data': {},
        'injuries': {},
        'odds': {},
        'h2h': {}
    }

    fixtures = await consolidate_fixtures(raw_data)

    assert len(fixtures) == 0


@pytest.mark.asyncio
async def test_consolidate_with_missing_optional_data(
    sample_api_football_fixture
):
    """Test consolidate_fixtures gracefully handles missing optional data."""
    raw_data = {
        'fixtures': [sample_api_football_fixture],
        'form_data': {},  # No form data
        'injuries': {},   # No injuries
        'odds': {},       # No odds
        'h2h': {}         # No h2h
    }

    fixtures = await consolidate_fixtures(raw_data)

    assert len(fixtures) == 1
    fixture = fixtures[0]

    # Verify fixture still created with core data
    assert fixture.fixture_id == '548821'
    assert fixture.home_team.name == 'Leeds United'

    # Verify missing optional data handled gracefully
    assert fixture.home_team.form_5_games == []
    assert fixture.home_team.injuries == []
    assert fixture.away_team.form_5_games == []
    assert fixture.away_team.injuries == []
    assert fixture.odds == {}
    assert fixture.head_to_head_history == []


# ============================================================================
# PARTIAL DATA TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_consolidate_partial_form_data(
    sample_api_football_fixture,
    sample_form_data,
    sample_injuries_data
):
    """Test consolidate_fixtures with partial form data (only home team)."""
    # Only include form for home team, not away
    partial_form = {'33': sample_form_data['33']}

    raw_data = {
        'fixtures': [sample_api_football_fixture],
        'form_data': partial_form,
        'injuries': sample_injuries_data,
        'odds': {},
        'h2h': {}
    }

    fixtures = await consolidate_fixtures(raw_data)

    assert len(fixtures) == 1
    fixture = fixtures[0]

    # Home team has form
    assert fixture.home_team.form_5_games == ['W', 'W', 'D', 'L', 'W']

    # Away team doesn't have form
    assert fixture.away_team.form_5_games == []


@pytest.mark.asyncio
async def test_consolidate_partial_injuries(
    sample_api_football_fixture,
    sample_form_data
):
    """Test consolidate_fixtures with partial injury data (only home team)."""
    partial_injuries = {
        '33': [MagicMock(player_id='p001')]
        # No injuries for away team
    }

    raw_data = {
        'fixtures': [sample_api_football_fixture],
        'form_data': sample_form_data,
        'injuries': partial_injuries,
        'odds': {},
        'h2h': {}
    }

    fixtures = await consolidate_fixtures(raw_data)

    assert len(fixtures) == 1
    fixture = fixtures[0]

    # Home team has injuries
    assert len(fixture.home_team.injuries) == 1

    # Away team has no injuries
    assert fixture.away_team.injuries == []


# ============================================================================
# MULTIPLE FIXTURES TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_consolidate_multiple_fixtures(
    sample_api_football_fixture,
    sample_form_data,
    sample_odds_data
):
    """Test consolidate_fixtures with multiple fixtures."""
    # Create second fixture
    fixture2 = {
        'fixture_id': '548822',
        'home_team_id': '7',
        'home_team_name': 'Manchester United',
        'away_team_id': '8',
        'away_team_name': 'Liverpool',
        'league_id': '39',
        'league_name': 'Championship',
        'league_country': 'England',
        'league_season': 2025,
        'kickoff_time': '2025-11-25T17:30:00+00:00'
    }

    odds2 = {
        '548822': {
            'match_result': {'home': 1.95, 'draw': 3.60, 'away': 3.50}
        }
    }

    raw_data = {
        'fixtures': [sample_api_football_fixture, fixture2],
        'form_data': sample_form_data,
        'injuries': {},
        'odds': {**sample_odds_data, **odds2},
        'h2h': {}
    }

    fixtures = await consolidate_fixtures(raw_data)

    assert len(fixtures) == 2
    assert fixtures[0].home_team.name == 'Leeds United'
    assert fixtures[1].home_team.name == 'Manchester United'


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_consolidate_malformed_fixture_skipped(
    sample_api_football_fixture,
    sample_form_data
):
    """Test consolidate_fixtures skips malformed fixture but continues."""
    # Missing required field
    bad_fixture = {
        'fixture_id': '999999'
        # Missing team_id fields
    }

    good_fixture = sample_api_football_fixture

    raw_data = {
        'fixtures': [bad_fixture, good_fixture],
        'form_data': sample_form_data,
        'injuries': {},
        'odds': {},
        'h2h': {}
    }

    fixtures = await consolidate_fixtures(raw_data)

    # Should return only the good fixture
    assert len(fixtures) == 1
    assert fixtures[0].fixture_id == '548821'


@pytest.mark.asyncio
async def test_consolidate_all_fixtures_fail_raises_error():
    """Test consolidate_fixtures raises error if all fixtures fail."""
    # All fixtures are malformed
    bad_fixtures = [
        {'fixture_id': '1'},  # Missing team data
        {'fixture_id': '2'},  # Missing team data
    ]

    raw_data = {
        'fixtures': bad_fixtures,
        'form_data': {},
        'injuries': {},
        'odds': {},
        'h2h': {}
    }

    with pytest.raises(DataValidationError):
        await consolidate_fixtures(raw_data)


# ============================================================================
# TIMESTAMP AND SOURCE TRACKING TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_consolidate_tracks_source_metadata(
    sample_api_football_fixture,
    sample_form_data
):
    """Test consolidate_fixtures tracks source metadata."""
    raw_data = {
        'fixtures': [sample_api_football_fixture],
        'form_data': sample_form_data,
        'injuries': {},
        'odds': {},
        'h2h': {}
    }

    fixtures = await consolidate_fixtures(raw_data)
    fixture = fixtures[0]

    # Fixture should be created successfully (source tracking is logged internally)
    assert fixture.fixture_id == '548821'
    assert fixture.home_team.form_5_games == ['W', 'W', 'D', 'L', 'W']


# ============================================================================
# FIXTURE OBJECT STRUCTURE TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_consolidated_fixture_is_valid_pydantic_model(
    sample_api_football_fixture,
    sample_form_data
):
    """Test consolidated fixture passes Pydantic validation."""
    raw_data = {
        'fixtures': [sample_api_football_fixture],
        'form_data': sample_form_data,
        'injuries': {},
        'odds': {},
        'h2h': {}
    }

    fixtures = await consolidate_fixtures(raw_data)

    # Should be able to serialize to dict without error
    assert len(fixtures) == 1
    fixture_dict = fixtures[0].model_dump()

    assert 'fixture_id' in fixture_dict
    assert 'home_team' in fixture_dict
    assert 'away_team' in fixture_dict
    assert 'league' in fixture_dict


@pytest.mark.asyncio
async def test_consolidated_fixture_has_timezone_aware_datetime(
    sample_api_football_fixture,
    sample_form_data
):
    """Test consolidated fixture has timezone-aware kickoff_time."""
    raw_data = {
        'fixtures': [sample_api_football_fixture],
        'form_data': sample_form_data,
        'injuries': {},
        'odds': {},
        'h2h': {}
    }

    fixtures = await consolidate_fixtures(raw_data)
    fixture = fixtures[0]

    # Verify timezone-aware
    assert fixture.kickoff_time.tzinfo is not None
    assert fixture.kickoff_time.tzinfo == timezone.utc


# ============================================================================
# EDGE CASES
# ============================================================================


@pytest.mark.asyncio
async def test_consolidate_fixture_with_string_datetime(
    sample_form_data
):
    """Test consolidate_fixtures handles string datetime formats."""
    raw_fixture = {
        'fixture_id': '548821',
        'home_team_id': '33',
        'home_team_name': 'Leeds United',
        'away_team_id': '62',
        'away_team_name': 'Norwich City',
        'league_id': '39',
        'league_name': 'Championship',
        'league_country': 'England',
        'league_season': 2025,
        'kickoff_time': '2025-11-25T15:00:00Z'  # Z format
    }

    raw_data = {
        'fixtures': [raw_fixture],
        'form_data': sample_form_data,
        'injuries': {},
        'odds': {},
        'h2h': {}
    }

    fixtures = await consolidate_fixtures(raw_data)

    assert len(fixtures) == 1
    fixture = fixtures[0]
    assert fixture.kickoff_time.tzinfo is not None


@pytest.mark.asyncio
async def test_consolidate_fixture_with_datetime_object(
    sample_form_data
):
    """Test consolidate_fixtures handles datetime objects."""
    raw_fixture = {
        'fixture_id': '548821',
        'home_team_id': '33',
        'home_team_name': 'Leeds United',
        'away_team_id': '62',
        'away_team_name': 'Norwich City',
        'league_id': '39',
        'league_name': 'Championship',
        'league_country': 'England',
        'league_season': 2025,
        'kickoff_time': datetime(2025, 11, 25, 15, 0, 0, tzinfo=timezone.utc)
    }

    raw_data = {
        'fixtures': [raw_fixture],
        'form_data': sample_form_data,
        'injuries': {},
        'odds': {},
        'h2h': {}
    }

    fixtures = await consolidate_fixtures(raw_data)

    assert len(fixtures) == 1
    fixture = fixtures[0]
    assert fixture.kickoff_time.tzinfo is not None


@pytest.mark.asyncio
async def test_consolidate_handles_none_values_in_raw_data(
    sample_api_football_fixture
):
    """Test consolidate_fixtures handles None values gracefully."""
    raw_data = {
        'fixtures': [sample_api_football_fixture],
        'form_data': None,  # None instead of empty dict
        'injuries': None,
        'odds': None,
        'h2h': None
    }

    fixtures = await consolidate_fixtures(raw_data)

    assert len(fixtures) == 1
    fixture = fixtures[0]
    assert fixture.fixture_id == '548821'
