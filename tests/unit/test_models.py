"""
Unit tests for Pydantic models.

Tests all model validation, serialization, and business logic.
Follows pytest conventions with clear test names and comprehensive coverage.

Test Coverage:
- Valid instance creation for all models
- Invalid data raises ValidationError with clear messages
- Model serialization to/from JSON
- Field alias support for API response mapping
- Boundary value testing (probabilities, odds, etc.)
- Enum validation (W/D/L, positions, statuses)

Target: 95%+ code coverage on models module
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from bet_bot.models import (
    AIAnalysis,
    Fixture,
    InjuredPlayer,
    Injury,
    League,
    Market,
    MarketAnalysis,
    Odds,
    Pick,
    RecentResult,
    Team,
    TeamForm,
)


# ============================================================================
# FIXTURES MODULE TESTS
# ============================================================================


class TestLeague:
    """Tests for League model."""

    def test_valid_league_creation(self):
        """Test creating a valid League instance."""
        league = League(
            league_id="39",
            league_name="Championship",
            league_country="England",
            league_season=2025
        )

        assert league.league_id == "39"
        assert league.league_name == "Championship"
        assert league.league_country == "England"
        assert league.league_season == 2025

    def test_league_empty_id_raises_error(self):
        """Test empty league_id raises ValidationError."""
        with pytest.raises(ValidationError, match="at least 1 character"):
            League(
                league_id="",
                league_name="Championship",
                league_country="England",
                league_season=2025
            )

    def test_league_whitespace_name_raises_error(self):
        """Test whitespace-only league_name raises ValidationError."""
        with pytest.raises(ValidationError, match="Field cannot be empty"):
            League(
                league_id="39",
                league_name="   ",
                league_country="England",
                league_season=2025
            )

    def test_league_invalid_season_raises_error(self):
        """Test invalid season year raises ValidationError."""
        with pytest.raises(ValidationError, match="greater than or equal to 2000"):
            League(
                league_id="39",
                league_name="Championship",
                league_country="England",
                league_season=1999
            )

    def test_league_serialization(self):
        """Test League can be serialized to and from JSON."""
        league = League(
            league_id="39",
            league_name="Championship",
            league_country="England",
            league_season=2025
        )

        # Serialize to dict
        data = league.model_dump()
        assert data["league_id"] == "39"
        assert data["league_season"] == 2025

        # Deserialize from dict
        league_restored = League(**data)
        assert league_restored.league_id == league.league_id
        assert league_restored.league_season == league.league_season


class TestTeam:
    """Tests for Team model."""

    def test_valid_team_creation(self):
        """Test creating a valid Team instance."""
        team = Team(
            id="123",
            name="Leeds United",
            form_5_games=["W", "W", "D", "L", "W"],
            avg_goals_for=1.8,
            avg_goals_against=1.2,
            injuries=["5001", "5002"]
        )

        assert team.id == "123"
        assert team.name == "Leeds United"
        assert team.form_5_games == ["W", "W", "D", "L", "W"]
        assert team.avg_goals_for == 1.8
        assert team.avg_goals_against == 1.2
        assert len(team.injuries) == 2

    def test_team_defaults(self):
        """Test Team model with default values."""
        team = Team(id="123", name="Leeds United")

        assert team.form_5_games == []
        assert team.avg_goals_for == 0.0
        assert team.avg_goals_against == 0.0
        assert team.injuries == []

    def test_team_invalid_form_raises_error(self):
        """Test invalid form result raises ValidationError."""
        with pytest.raises(ValidationError, match="Form result must be W, D, or L"):
            Team(
                id="123",
                name="Leeds United",
                form_5_games=["W", "X", "D"]  # X is invalid
            )

    def test_team_negative_goals_raises_error(self):
        """Test negative goal averages raise ValidationError."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            Team(
                id="123",
                name="Leeds United",
                avg_goals_for=-1.5
            )

    def test_team_form_max_length(self):
        """Test form_5_games enforces max length of 5."""
        with pytest.raises(ValidationError, match="at most 5 items"):
            Team(
                id="123",
                name="Leeds United",
                form_5_games=["W", "W", "D", "L", "W", "W"]  # 6 items
            )


class TestFixture:
    """Tests for Fixture model."""

    @pytest.fixture
    def sample_league(self):
        """Create a sample League for testing."""
        return League(
            league_id="39",
            league_name="Championship",
            league_country="England",
            league_season=2025
        )

    @pytest.fixture
    def sample_home_team(self):
        """Create a sample home Team for testing."""
        return Team(
            id="123",
            name="Leeds United",
            form_5_games=["W", "W", "D"],
            avg_goals_for=1.8,
            avg_goals_against=1.2
        )

    @pytest.fixture
    def sample_away_team(self):
        """Create a sample away Team for testing."""
        return Team(
            id="456",
            name="West Brom",
            form_5_games=["L", "D", "W"],
            avg_goals_for=1.5,
            avg_goals_against=1.4
        )

    def test_valid_fixture_creation(self, sample_league, sample_home_team, sample_away_team):
        """Test creating a valid Fixture instance."""
        fixture = Fixture(
            fixture_id="548821",
            kickoff_time=datetime(2025, 11, 24, 15, 0, 0, tzinfo=timezone.utc),
            home_team=sample_home_team,
            away_team=sample_away_team,
            league=sample_league,
            odds={"match_result": {"home": 2.10, "draw": 3.50, "away": 3.20}},
            head_to_head_history=["W", "D", "W", "L", "W"]
        )

        assert fixture.fixture_id == "548821"
        assert fixture.home_team.name == "Leeds United"
        assert fixture.away_team.name == "West Brom"
        assert fixture.league.league_name == "Championship"
        assert "match_result" in fixture.odds

    def test_fixture_with_field_name(self, sample_league, sample_home_team, sample_away_team):
        """Test Fixture can be created using standard field name."""
        fixture = Fixture(
            fixture_id="548821",
            kickoff_time=datetime(2025, 11, 24, 15, 0, 0, tzinfo=timezone.utc),
            home_team=sample_home_team,
            away_team=sample_away_team,
            league=sample_league
        )
        assert fixture.fixture_id == "548821"

    def test_fixture_same_team_raises_error(self, sample_league, sample_home_team):
        """Test home and away teams cannot be the same."""
        with pytest.raises(ValidationError, match="cannot be the same"):
            Fixture(
                fixture_id="548821",
                kickoff_time=datetime(2025, 11, 24, 15, 0, 0, tzinfo=timezone.utc),
                home_team=sample_home_team,
                away_team=sample_home_team,  # Same as home team
                league=sample_league
            )

    def test_fixture_invalid_h2h_result(self, sample_league, sample_home_team, sample_away_team):
        """Test invalid H2H result raises ValidationError."""
        with pytest.raises(ValidationError, match="H2H result must be W, D, or L"):
            Fixture(
                fixture_id="548821",
                kickoff_time=datetime(2025, 11, 24, 15, 0, 0, tzinfo=timezone.utc),
                home_team=sample_home_team,
                away_team=sample_away_team,
                league=sample_league,
                head_to_head_history=["W", "X", "D"]  # X is invalid
            )


# ============================================================================
# FORM MODULE TESTS
# ============================================================================


class TestRecentResult:
    """Tests for RecentResult model."""

    def test_valid_recent_result(self):
        """Test creating a valid RecentResult instance."""
        result = RecentResult(
            result="W",
            opponent="West Brom",
            goals_for=2,
            goals_against=1,
            date=datetime(2025, 11, 20, 15, 0, 0, tzinfo=timezone.utc)
        )

        assert result.result == "W"
        assert result.opponent == "West Brom"
        assert result.goals_for == 2
        assert result.goals_against == 1

    def test_recent_result_lowercase_converted(self):
        """Test lowercase result is converted to uppercase."""
        result = RecentResult(
            result="w",
            opponent="West Brom",
            goals_for=2,
            goals_against=1,
            date=datetime(2025, 11, 20, 15, 0, 0, tzinfo=timezone.utc)
        )

        assert result.result == "W"

    def test_recent_result_invalid_result(self):
        """Test invalid result character raises ValidationError."""
        with pytest.raises(ValidationError, match="Result must be W, D, or L"):
            RecentResult(
                result="X",
                opponent="West Brom",
                goals_for=2,
                goals_against=1,
                date=datetime(2025, 11, 20, 15, 0, 0, tzinfo=timezone.utc)
            )

    def test_recent_result_negative_goals(self):
        """Test negative goals raise ValidationError."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            RecentResult(
                result="W",
                opponent="West Brom",
                goals_for=-1,
                goals_against=1,
                date=datetime(2025, 11, 20, 15, 0, 0, tzinfo=timezone.utc)
            )


class TestTeamForm:
    """Tests for TeamForm model."""

    def test_valid_team_form(self):
        """Test creating a valid TeamForm instance."""
        form = TeamForm(
            team_id="123",
            team_name="Leeds United",
            last_5_results=["W", "W", "D", "L", "W"],
            last_10_results=["W", "W", "D", "L", "W", "L", "D", "W", "W", "D"],
            win_percentage_5=0.60,
            win_percentage_10=0.55,
            goals_avg_home=1.9,
            goals_avg_away=1.7,
            goals_against_avg_home=1.1,
            goals_against_avg_away=1.3
        )

        assert form.team_id == "123"
        assert form.win_percentage_5 == 0.60
        assert len(form.last_5_results) == 5
        assert len(form.last_10_results) == 10

    def test_team_form_invalid_win_percentage(self):
        """Test win percentage outside 0.0-1.0 raises ValidationError."""
        with pytest.raises(ValidationError, match="less than or equal to 1"):
            TeamForm(
                team_id="123",
                team_name="Leeds United",
                win_percentage_5=1.5  # Invalid: > 1.0
            )

    def test_team_form_invalid_results(self):
        """Test invalid result in list raises ValidationError."""
        with pytest.raises(ValidationError, match="Result must be W, D, or L"):
            TeamForm(
                team_id="123",
                team_name="Leeds United",
                last_5_results=["W", "W", "X", "L", "W"]  # X is invalid
            )


# ============================================================================
# INJURIES MODULE TESTS
# ============================================================================


class TestInjuredPlayer:
    """Tests for InjuredPlayer model."""

    def test_valid_injured_player(self):
        """Test creating a valid InjuredPlayer instance."""
        player = InjuredPlayer(
            player_id="5001",
            player_name="Patrick Bamford",
            position="Forward",
            injury_status="Doubt",
            impact_severity="Key"
        )

        assert player.player_id == "5001"
        assert player.player_name == "Patrick Bamford"
        assert player.position == "Forward"
        assert player.injury_status == "Doubt"
        assert player.impact_severity == "Key"

    def test_injured_player_invalid_position(self):
        """Test invalid position raises ValidationError."""
        with pytest.raises(ValidationError, match="Position must be one of"):
            InjuredPlayer(
                player_id="5001",
                player_name="Patrick Bamford",
                position="Striker",  # Invalid: should be "Forward"
                injury_status="Doubt",
                impact_severity="Key"
            )

    def test_injured_player_invalid_status(self):
        """Test invalid injury status raises ValidationError."""
        with pytest.raises(ValidationError, match="Injury status must be one of"):
            InjuredPlayer(
                player_id="5001",
                player_name="Patrick Bamford",
                position="Forward",
                injury_status="Healthy",  # Invalid
                impact_severity="Key"
            )

    def test_injured_player_invalid_impact(self):
        """Test invalid impact severity raises ValidationError."""
        with pytest.raises(ValidationError, match="Impact severity must be one of"):
            InjuredPlayer(
                player_id="5001",
                player_name="Patrick Bamford",
                position="Forward",
                injury_status="Doubt",
                impact_severity="Critical"  # Invalid: should be Key/Moderate/Minor
            )


class TestInjury:
    """Tests for Injury model."""

    def test_valid_injury(self):
        """Test creating a valid Injury instance."""
        player1 = InjuredPlayer(
            player_id="5001",
            player_name="Patrick Bamford",
            position="Forward",
            injury_status="Injured",
            impact_severity="Key"
        )

        injury = Injury(
            team_id="123",
            injured_players=[player1],
            missing_key_players_count=1,
            missing_key_players_list=["Patrick Bamford"]
        )

        assert injury.team_id == "123"
        assert len(injury.injured_players) == 1
        assert injury.missing_key_players_count == 1

    def test_injury_empty_list(self):
        """Test Injury with no injured players."""
        injury = Injury(
            team_id="123",
            injured_players=[],
            missing_key_players_count=0,
            missing_key_players_list=[]
        )

        assert len(injury.injured_players) == 0
        assert injury.missing_key_players_count == 0


# ============================================================================
# ODDS MODULE TESTS
# ============================================================================


class TestMarket:
    """Tests for Market model."""

    def test_valid_market(self):
        """Test creating a valid Market instance."""
        market = Market(
            market_type="match_result",
            odds={"home": 2.10, "draw": 3.50, "away": 3.20}
        )

        assert market.market_type == "match_result"
        assert market.odds["home"] == 2.10
        assert len(market.odds) == 3

    def test_market_odds_below_one_raises_error(self):
        """Test odds below 1.0 raise ValidationError."""
        with pytest.raises(ValidationError, match="Odds must be >= 1.0"):
            Market(
                market_type="match_result",
                odds={"home": 0.5, "draw": 3.50}  # 0.5 is invalid
            )

    def test_market_empty_type_raises_error(self):
        """Test empty market_type raises ValidationError."""
        with pytest.raises(ValidationError, match="at least 1 character"):
            Market(
                market_type="",
                odds={"home": 2.10}
            )


class TestOdds:
    """Tests for Odds model."""

    def test_valid_odds(self):
        """Test creating a valid Odds instance."""
        market1 = Market(
            market_type="match_result",
            odds={"home": 2.10, "draw": 3.50, "away": 3.20}
        )

        odds = Odds(
            fixture_id="548821",
            bookmaker_name="Pinnacle",
            odds_updated_at=datetime(2025, 11, 24, 14, 30, 0, tzinfo=timezone.utc),
            markets=[market1]
        )

        assert odds.fixture_id == "548821"
        assert odds.bookmaker_name == "Pinnacle"
        assert len(odds.markets) == 1

    def test_odds_empty_bookmaker_raises_error(self):
        """Test empty bookmaker_name raises ValidationError."""
        with pytest.raises(ValidationError, match="Field cannot be empty"):
            Odds(
                fixture_id="548821",
                bookmaker_name="   ",
                odds_updated_at=datetime(2025, 11, 24, 14, 30, 0, tzinfo=timezone.utc),
                markets=[]
            )


# ============================================================================
# ANALYSIS MODULE TESTS
# ============================================================================


class TestMarketAnalysis:
    """Tests for MarketAnalysis model."""

    def test_valid_market_analysis(self):
        """Test creating a valid MarketAnalysis instance."""
        analysis = MarketAnalysis(
            market_type="match_result",
            ai_probability=0.58,
            reasoning="Leeds showing strong home form (60% win rate)...",
            confidence=75
        )

        assert analysis.market_type == "match_result"
        assert analysis.ai_probability == 0.58
        assert analysis.confidence == 75

    def test_market_analysis_invalid_probability(self):
        """Test probability outside 0.0-1.0 raises ValidationError."""
        with pytest.raises(ValidationError, match="less than or equal to 1"):
            MarketAnalysis(
                market_type="match_result",
                ai_probability=1.5,  # Invalid: > 1.0
                reasoning="Test",
                confidence=75
            )

    def test_market_analysis_invalid_confidence(self):
        """Test confidence outside 0-100 raises ValidationError."""
        with pytest.raises(ValidationError, match="less than or equal to 100"):
            MarketAnalysis(
                market_type="match_result",
                ai_probability=0.58,
                reasoning="Test",
                confidence=150  # Invalid: > 100
            )


class TestAIAnalysis:
    """Tests for AIAnalysis model."""

    def test_valid_ai_analysis(self):
        """Test creating a valid AIAnalysis instance."""
        market1 = MarketAnalysis(
            market_type="match_result",
            ai_probability=0.58,
            reasoning="Strong home form",
            confidence=75
        )

        analysis = AIAnalysis(
            fixture_id="548821",
            markets=[market1],
            analysis_timestamp=datetime(2025, 11, 24, 14, 45, 0, tzinfo=timezone.utc)
        )

        assert analysis.fixture_id == "548821"
        assert len(analysis.markets) == 1


class TestPick:
    """Tests for Pick model."""

    def test_valid_pick(self):
        """Test creating a valid Pick instance."""
        pick = Pick(
            fixture_id="548821",
            market="match_result_home",
            ai_probability=0.58,
            implied_probability=0.476,
            ev_percentage=5.8,
            confidence=72,
            recommended_stake=25.0,
            suggested_odds=2.10
        )

        assert pick.fixture_id == "548821"
        assert pick.ev_percentage == 5.8
        assert pick.confidence == 72

    def test_pick_negative_ev_allowed(self):
        """Test negative EV is allowed (for comparison/filtering)."""
        pick = Pick(
            fixture_id="548821",
            market="match_result_away",
            ai_probability=0.17,
            implied_probability=0.313,
            ev_percentage=-4.6,  # Negative EV is valid
            confidence=65,
            recommended_stake=1.0,
            suggested_odds=3.20
        )

        assert pick.ev_percentage == -4.6

    def test_pick_zero_stake_raises_error(self):
        """Test zero recommended_stake raises ValidationError."""
        with pytest.raises(ValidationError, match="greater than 0"):
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.58,
                implied_probability=0.476,
                ev_percentage=5.8,
                confidence=72,
                recommended_stake=0.0,  # Invalid: must be > 0
                suggested_odds=2.10
            )

    def test_pick_odds_below_one_raises_error(self):
        """Test odds below 1.0 raise ValidationError."""
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            Pick(
                fixture_id="548821",
                market="match_result_home",
                ai_probability=0.58,
                implied_probability=0.476,
                ev_percentage=5.8,
                confidence=72,
                recommended_stake=25.0,
                suggested_odds=0.5  # Invalid: < 1.0
            )


# ============================================================================
# SERIALIZATION TESTS
# ============================================================================


class TestSerialization:
    """Test JSON serialization and deserialization for all models."""

    def test_fixture_json_round_trip(self):
        """Test Fixture can be serialized to JSON and back."""
        league = League(
            league_id="39",
            league_name="Championship",
            league_country="England",
            league_season=2025
        )

        home_team = Team(id="123", name="Leeds United")
        away_team = Team(id="456", name="West Brom")

        fixture = Fixture(
            fixture_id="548821",
            kickoff_time=datetime(2025, 11, 24, 15, 0, 0, tzinfo=timezone.utc),
            home_team=home_team,
            away_team=away_team,
            league=league
        )

        # Serialize to JSON
        json_data = fixture.model_dump_json()
        assert isinstance(json_data, str)

        # Deserialize from JSON
        fixture_restored = Fixture.model_validate_json(json_data)
        assert fixture_restored.fixture_id == "548821"
        assert fixture_restored.home_team.name == "Leeds United"

    def test_pick_json_round_trip(self):
        """Test Pick can be serialized to JSON and back."""
        pick = Pick(
            fixture_id="548821",
            market="match_result_home",
            ai_probability=0.58,
            implied_probability=0.476,
            ev_percentage=5.8,
            confidence=72,
            recommended_stake=25.0,
            suggested_odds=2.10
        )

        # Serialize to dict
        data = pick.model_dump()
        assert data["ev_percentage"] == 5.8

        # Deserialize from dict
        pick_restored = Pick(**data)
        assert pick_restored.fixture_id == pick.fixture_id
        assert pick_restored.ev_percentage == pick.ev_percentage
