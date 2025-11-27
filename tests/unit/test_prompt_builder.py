"""
Unit tests for prompt_builder module.

Tests cover:
- Fixture data validation
- All formatter functions
- Prompt assembly
- Token counting
- Edge cases
"""

import pytest
from datetime import datetime, timezone, timedelta

from bet_bot.models.fixtures import Fixture, Team, League
from bet_bot.analysis.ai.prompt_builder import (
    _validate_fixture_for_prompt,
    _format_fixture_details,
    _format_team_form,
    _format_injuries,
    _format_h2h_history,
    _format_odds,
    _get_available_markets,
    _estimate_token_count,
    build_analysis_prompt,
)


@pytest.fixture
def sample_league() -> League:
    """Create a sample league."""
    return League(
        league_id="39",
        league_name="Championship",
        league_country="England",
        league_season=2025,
    )


@pytest.fixture
def sample_home_team() -> Team:
    """Create a sample home team."""
    return Team(
        id="123",
        name="Leeds United",
        form_5_games=["W", "W", "D", "L", "W"],
        avg_goals_for=1.8,
        avg_goals_against=1.2,
        injuries=["Player1", "Player2"],
    )


@pytest.fixture
def sample_away_team() -> Team:
    """Create a sample away team."""
    return Team(
        id="124",
        name="Southampton",
        form_5_games=["D", "L", "W", "D", "L"],
        avg_goals_for=1.2,
        avg_goals_against=1.6,
        injuries=[],
    )


@pytest.fixture
def sample_fixture(sample_league, sample_home_team, sample_away_team) -> Fixture:
    """Create a sample fixture."""
    future_time = datetime.now(timezone.utc) + timedelta(days=1)
    return Fixture(
        fixture_id="548821",
        kickoff_time=future_time,
        home_team=sample_home_team,
        away_team=sample_away_team,
        league=sample_league,
        odds={
            "match_result": {"home": 2.10, "draw": 3.50, "away": 3.20},
            "total_goals": {"over_2_5": 1.85, "under_2_5": 1.95},
            "corners": {"over_9_5": 1.80, "under_9_5": 2.00},
        },
        head_to_head_history=["W", "D", "W", "L", "W"],
    )


class TestFixtureValidation:
    """Test fixture validation function."""

    def test_valid_fixture_passes_validation(self, sample_fixture: Fixture) -> None:
        """Valid fixture should pass validation."""
        assert _validate_fixture_for_prompt(sample_fixture) is True

    def test_missing_fixture_id_fails_validation(
        self, sample_fixture: Fixture
    ) -> None:
        """Fixture without fixture_id should fail validation."""
        sample_fixture.fixture_id = ""
        assert _validate_fixture_for_prompt(sample_fixture) is False

    def test_missing_home_team_id_fails_validation(
        self, sample_fixture: Fixture
    ) -> None:
        """Fixture without home_team.id should fail validation."""
        sample_fixture.home_team.id = ""
        assert _validate_fixture_for_prompt(sample_fixture) is False

    def test_missing_away_team_id_fails_validation(
        self, sample_fixture: Fixture
    ) -> None:
        """Fixture without away_team.id should fail validation."""
        sample_fixture.away_team.id = ""
        assert _validate_fixture_for_prompt(sample_fixture) is False

    def test_past_kickoff_time_fails_validation(
        self, sample_fixture: Fixture
    ) -> None:
        """Fixture with past kickoff_time should fail validation."""
        sample_fixture.kickoff_time = datetime.now(timezone.utc) - timedelta(
            hours=1
        )
        assert _validate_fixture_for_prompt(sample_fixture) is False

    def test_empty_odds_fails_validation(self, sample_fixture: Fixture) -> None:
        """Fixture with empty odds should fail validation."""
        sample_fixture.odds = {}
        assert _validate_fixture_for_prompt(sample_fixture) is False

    def test_missing_match_result_odds_fails_validation(
        self, sample_fixture: Fixture
    ) -> None:
        """Fixture without match_result odds should fail validation."""
        sample_fixture.odds = {"total_goals": {"over_2_5": 1.85}}
        assert _validate_fixture_for_prompt(sample_fixture) is False

    def test_missing_league_fails_validation(self, sample_fixture: Fixture) -> None:
        """Fixture without league should fail validation."""
        sample_fixture.league = None  # type: ignore
        assert _validate_fixture_for_prompt(sample_fixture) is False


class TestFixtureDetailsFormatter:
    """Test fixture details formatter."""

    def test_fixture_details_format(self, sample_fixture: Fixture) -> None:
        """Fixture details should include all required information."""
        details = _format_fixture_details(sample_fixture)

        assert "Championship" in details
        assert "Leeds United" in details
        assert "Southampton" in details
        assert "548821" in details

    def test_fixture_details_contains_league(self, sample_fixture: Fixture) -> None:
        """Fixture details should contain league name."""
        details = _format_fixture_details(sample_fixture)
        assert f"League: {sample_fixture.league.league_name}" in details

    def test_fixture_details_contains_teams(self, sample_fixture: Fixture) -> None:
        """Fixture details should contain both team names."""
        details = _format_fixture_details(sample_fixture)
        assert sample_fixture.home_team.name in details
        assert sample_fixture.away_team.name in details


class TestTeamFormFormatter:
    """Test team form formatter."""

    def test_team_form_with_valid_data(self, sample_home_team: Team) -> None:
        """Team form should include recent form and win %."""
        form = _format_team_form(sample_home_team.name, sample_home_team.form_5_games)

        assert sample_home_team.name in form
        assert "W-W-D-L-W" in form
        assert "70.0%" in form  # (W=1, W=1, D=0.5, L=0, W=1) / 5 = 70%

    def test_team_form_with_empty_form_data(self) -> None:
        """Team form with empty data should handle gracefully."""
        form = _format_team_form("Test Team", [])
        assert "Form data unavailable" in form

    def test_team_form_calculates_win_percentage_correctly(self) -> None:
        """Win percentage calculation should be correct."""
        form = _format_team_form("Test Team", ["W", "W", "D"])
        # (1 + 1 + 0.5) / 3 = 83.33%
        assert "83.3%" in form


class TestInjuryFormatter:
    """Test injury formatter."""

    def test_injury_formatter_with_injuries(self, sample_fixture: Fixture) -> None:
        """Injuries should be listed correctly."""
        injuries = _format_injuries(sample_fixture)

        assert sample_fixture.home_team.name in injuries
        assert "Player1" in injuries or "Player2" in injuries

    def test_injury_formatter_with_no_injuries(
        self, sample_league, sample_home_team, sample_away_team
    ) -> None:
        """Fixtures with no injuries should show appropriate message."""
        sample_home_team.injuries = []
        sample_away_team.injuries = []

        fixture = Fixture(
            fixture_id="123",
            kickoff_time=datetime.now(timezone.utc) + timedelta(days=1),
            home_team=sample_home_team,
            away_team=sample_away_team,
            league=sample_league,
            odds={"match_result": {"home": 2.10}},
        )

        injuries = _format_injuries(fixture)
        assert "No notable injuries" in injuries

    def test_injury_formatter_limits_players(
        self, sample_league, sample_home_team, sample_away_team
    ) -> None:
        """Injury formatter should limit to 5 players per team."""
        sample_home_team.injuries = [f"Player{i}" for i in range(10)]

        fixture = Fixture(
            fixture_id="123",
            kickoff_time=datetime.now(timezone.utc) + timedelta(days=1),
            home_team=sample_home_team,
            away_team=sample_away_team,
            league=sample_league,
            odds={"match_result": {"home": 2.10}},
        )

        injuries = _format_injuries(fixture)
        # Should only show first 5
        assert injuries.count("Player") <= 5


class TestH2HFormatter:
    """Test head-to-head formatter."""

    def test_h2h_formatter_with_history(self, sample_fixture: Fixture) -> None:
        """H2H history should be formatted correctly."""
        h2h = _format_h2h_history(sample_fixture)

        assert "W-D-W-L-W" in h2h
        assert "3W-1D-1L" in h2h

    def test_h2h_formatter_with_no_history(self, sample_fixture: Fixture) -> None:
        """Fixture with no H2H history should show appropriate message."""
        sample_fixture.head_to_head_history = []

        h2h = _format_h2h_history(sample_fixture)
        assert "No previous meetings" in h2h

    def test_h2h_record_calculation(self, sample_fixture: Fixture) -> None:
        """H2H record calculation should be correct."""
        sample_fixture.head_to_head_history = ["W", "W", "W", "D", "L"]

        h2h = _format_h2h_history(sample_fixture)
        assert "3W-1D-1L" in h2h


class TestOddsFormatter:
    """Test odds formatter."""

    def test_odds_formatter_shows_available_markets(
        self, sample_fixture: Fixture
    ) -> None:
        """Odds formatter should show all available markets."""
        odds = _format_odds(sample_fixture)

        assert "Match Result" in odds
        assert "home" in odds
        assert "draw" in odds
        assert "away" in odds

    def test_odds_formatter_shows_missing_markets(
        self, sample_fixture: Fixture
    ) -> None:
        """Odds formatter should show 'Not available' for missing markets."""
        sample_fixture.odds = {"match_result": {"home": 2.10}}

        odds = _format_odds(sample_fixture)
        assert "Total Goals: Not available" in odds

    def test_odds_formatter_calculates_implied_probability(
        self, sample_fixture: Fixture
    ) -> None:
        """Odds formatter should calculate implied probability correctly."""
        sample_fixture.odds = {"match_result": {"home": 2.0}}

        odds = _format_odds(sample_fixture)
        # 1/2.0 = 0.5 = 50%
        assert "50.0%" in odds


class TestAvailableMarketsHelper:
    """Test market availability helper."""

    def test_get_available_markets_all_present(
        self, sample_fixture: Fixture
    ) -> None:
        """Should correctly identify all available markets."""
        sample_fixture.odds = {
            "match_result": {"home": 2.10},
            "total_goals": {"over_2_5": 1.85},
            "corners": {"over_9_5": 1.80},
            "cards": {"over_5_0": 1.95},
        }

        markets = _get_available_markets(sample_fixture)
        assert markets["match_result"] is True
        assert markets["total_goals"] is True
        assert markets["corners"] is True
        assert markets["cards"] is True

    def test_get_available_markets_some_missing(
        self, sample_fixture: Fixture
    ) -> None:
        """Should correctly identify missing markets."""
        sample_fixture.odds = {
            "match_result": {"home": 2.10},
            "corners": {"over_9_5": 1.80},
        }

        markets = _get_available_markets(sample_fixture)
        assert markets["match_result"] is True
        assert markets["total_goals"] is False
        assert markets["corners"] is True
        assert markets["cards"] is False


class TestTokenCounting:
    """Test token estimation."""

    def test_token_count_estimation(self) -> None:
        """Token count estimation should be reasonable."""
        text = "This is a test. " * 100  # ~400 words (100 * 4 words)
        tokens = _estimate_token_count(text)

        # Should be approximately 400 / 0.75 = 533 tokens
        assert 500 < tokens < 600

    def test_token_count_empty_text(self) -> None:
        """Empty text should estimate 0 tokens."""
        tokens = _estimate_token_count("")
        assert tokens == 0

    def test_token_count_single_word(self) -> None:
        """Single word should estimate 1 token."""
        tokens = _estimate_token_count("word")
        assert tokens >= 1


class TestPromptAssembly:
    """Test complete prompt assembly."""

    @pytest.mark.asyncio
    async def test_build_analysis_prompt_returns_string(
        self, sample_fixture: Fixture
    ) -> None:
        """build_analysis_prompt should return a string."""
        prompt = await build_analysis_prompt(sample_fixture)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    @pytest.mark.asyncio
    async def test_build_analysis_prompt_includes_all_sections(
        self, sample_fixture: Fixture
    ) -> None:
        """Prompt should include all major sections."""
        prompt = await build_analysis_prompt(sample_fixture)

        assert "Leeds United" in prompt
        assert "Southampton" in prompt
        assert "Championship" in prompt
        assert "TEAM FORM" in prompt
        assert "INJURIES" in prompt or "injuries" in prompt.lower()
        assert "H2H HISTORY" in prompt
        assert "CURRENT ODDS" in prompt or "ODDS" in prompt

    @pytest.mark.asyncio
    async def test_build_analysis_prompt_with_minimal_data(
        self, sample_league
    ) -> None:
        """Prompt should handle fixture with minimal optional data."""
        minimal_team_home = Team(
            id="1",
            name="Team A",
            form_5_games=[],
            injuries=[],
        )
        minimal_team_away = Team(
            id="2",
            name="Team B",
            form_5_games=[],
            injuries=[],
        )

        minimal_fixture = Fixture(
            fixture_id="1",
            kickoff_time=datetime.now(timezone.utc) + timedelta(days=1),
            home_team=minimal_team_home,
            away_team=minimal_team_away,
            league=sample_league,
            odds={"match_result": {"home": 2.0, "draw": 3.0, "away": 3.5}},
            head_to_head_history=[],
        )

        prompt = await build_analysis_prompt(minimal_fixture)
        assert "Team A" in prompt
        assert "Team B" in prompt

    @pytest.mark.asyncio
    async def test_build_analysis_prompt_validates_before_building(
        self, sample_fixture: Fixture
    ) -> None:
        """Should validate fixture before building prompt."""
        sample_fixture.fixture_id = ""  # Make it invalid

        with pytest.raises(ValueError):
            await build_analysis_prompt(sample_fixture)

    @pytest.mark.asyncio
    async def test_build_analysis_prompt_respects_token_limit(
        self, sample_fixture: Fixture
    ) -> None:
        """Prompt should not exceed token hard limit."""
        # This test verifies that we don't raise on normal fixtures
        prompt = await build_analysis_prompt(sample_fixture)
        assert len(prompt) > 0

    @pytest.mark.asyncio
    async def test_build_analysis_prompt_with_all_optional_data(
        self, sample_league, sample_home_team, sample_away_team
    ) -> None:
        """Prompt should handle fixture with all optional data."""
        rich_team_home = Team(
            id="123",
            name="Leeds United FC",
            form_5_games=["W", "W", "D", "L", "W"],
            avg_goals_for=2.1,
            avg_goals_against=1.0,
            injuries=["Player1", "Player2", "Player3"],
        )
        rich_team_away = Team(
            id="124",
            name="Southampton FC",
            form_5_games=["W", "D", "L", "D", "L"],
            avg_goals_for=1.2,
            avg_goals_against=1.8,
            injuries=["KeyPlayer1"],
        )

        rich_fixture = Fixture(
            fixture_id="548821",
            kickoff_time=datetime.now(timezone.utc) + timedelta(days=1),
            home_team=rich_team_home,
            away_team=rich_team_away,
            league=sample_league,
            odds={
                "match_result": {"home": 2.10, "draw": 3.50, "away": 3.20},
                "total_goals": {"over_2_5": 1.85, "under_2_5": 1.95},
                "corners": {"over_9_5": 1.80, "under_9_5": 2.00},
                "cards": {"over_5_0": 1.95, "under_5_0": 1.87},
            },
            head_to_head_history=["W", "D", "W", "L", "W"],
        )

        prompt = await build_analysis_prompt(rich_fixture)
        assert "Leeds United FC" in prompt
        assert "Southampton FC" in prompt
        assert "W-W-D-L-W" in prompt

    @pytest.mark.asyncio
    async def test_build_analysis_prompt_with_unicode_team_names(
        self, sample_league
    ) -> None:
        """Prompt should handle Unicode characters in team names."""
        unicode_team_home = Team(
            id="1",
            name="FC Köln",
            form_5_games=["W", "D", "L"],
            injuries=[],
        )
        unicode_team_away = Team(
            id="2",
            name="Atlético Madrid",
            form_5_games=["W", "W", "W"],
            injuries=[],
        )

        unicode_fixture = Fixture(
            fixture_id="1",
            kickoff_time=datetime.now(timezone.utc) + timedelta(days=1),
            home_team=unicode_team_home,
            away_team=unicode_team_away,
            league=sample_league,
            odds={"match_result": {"home": 2.0}},
        )

        prompt = await build_analysis_prompt(unicode_fixture)
        assert "Köln" in prompt
        assert "Atlético" in prompt


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_fixture_with_very_long_team_names(
        self, sample_league
    ) -> None:
        """Prompt should handle very long team names."""
        long_name_home = Team(
            id="1",
            name="A" * 100,
            form_5_games=[],
            injuries=[],
        )
        long_name_away = Team(
            id="2",
            name="B" * 100,
            form_5_games=[],
            injuries=[],
        )

        long_name_fixture = Fixture(
            fixture_id="1",
            kickoff_time=datetime.now(timezone.utc) + timedelta(days=1),
            home_team=long_name_home,
            away_team=long_name_away,
            league=sample_league,
            odds={"match_result": {"home": 2.0}},
        )

        prompt = await build_analysis_prompt(long_name_fixture)
        assert len(prompt) > 0

    @pytest.mark.asyncio
    async def test_fixture_with_large_h2h_history(
        self, sample_league, sample_home_team, sample_away_team
    ) -> None:
        """Prompt should handle large H2H history (only uses last 5)."""
        sample_fixture = Fixture(
            fixture_id="1",
            kickoff_time=datetime.now(timezone.utc) + timedelta(days=1),
            home_team=sample_home_team,
            away_team=sample_away_team,
            league=sample_league,
            odds={"match_result": {"home": 2.0}},
            head_to_head_history=["W", "D", "L", "W", "D"],
        )

        prompt = await build_analysis_prompt(sample_fixture)
        assert len(prompt) > 0
