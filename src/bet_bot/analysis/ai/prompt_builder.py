"""
OpenAI prompt builder for bet-bot.

This module constructs rich context prompts for OpenAI analysis.
The prompt builder takes consolidated fixture data from the data pipeline
and formats it into a human-readable prompt with structured JSON response format.

Main Entry Points:
    - build_analysis_prompt(): Constructs and validates complete prompt for OpenAI
    - export_prompt_for_api(): Wraps prompt into dict format for API client

The prompt includes:
    - Fixture details (teams, league, date, location)
    - Team form data (last 5 results, win %, goals)
    - Injury/suspension information
    - Head-to-head history
    - Current odds for key betting markets
    - Structured request for probabilities and reasoning

Token Limit: < 2000 tokens total
Output Format: Structured JSON with markets, probabilities, and reasoning
"""

import logging
from datetime import datetime, timezone
from typing import Any

from bet_bot.models.fixtures import Fixture

logger = logging.getLogger(__name__)

# Constants
SYSTEM_PROMPT = """You are an expert sports betting analyst with deep knowledge of football/soccer.
Your task is to analyze match fixtures and estimate probability distributions for betting markets.

Provide clear, concise reasoning based on data presented. Consider team form, injuries, historical matchups, and odds.
All probabilities should be realistic (0.0-1.0 range) and internally consistent."""

TOKEN_ESTIMATE_WARNING = 1800
TOKEN_HARD_LIMIT = 2500

WORD_TO_TOKEN_RATIO = 0.75  # Conservative estimate: 1 token ≈ 0.75 words


def _estimate_token_count(text: str) -> int:
    """
    Estimate token count using word-to-token ratio.

    Uses conservative OpenAI standard: tokens ≈ words / 0.75
    This provides a safety buffer to prevent exceeding API limits.

    Args:
        text: Text to estimate token count for

    Returns:
        Estimated token count
    """
    word_count = len(text.split())
    estimated_tokens = int(word_count / WORD_TO_TOKEN_RATIO)
    return estimated_tokens


def _validate_fixture_for_prompt(fixture: Fixture) -> bool:
    """
    Validate fixture has all required fields for prompt building.

    Checks:
    - fixture_id exists and non-empty
    - home_team and away_team have ids and names
    - league name exists
    - kickoff_time is in the future
    - odds dict is non-empty with at least match_result market

    Args:
        fixture: Fixture to validate

    Returns:
        True if valid, False otherwise (logs warnings for failures)

    Raises:
        ValueError: On critical validation failures
    """
    # Check fixture_id
    if not fixture.fixture_id or not fixture.fixture_id.strip():
        logger.warning(f"Fixture validation failed: fixture_id is empty")
        return False

    # Check teams
    if not fixture.home_team or not fixture.home_team.id or not fixture.home_team.name:
        logger.warning(
            f"Fixture {fixture.fixture_id}: home_team missing id or name"
        )
        return False

    if not fixture.away_team or not fixture.away_team.id or not fixture.away_team.name:
        logger.warning(
            f"Fixture {fixture.fixture_id}: away_team missing id or name"
        )
        return False

    # Check league
    if not fixture.league or not fixture.league.league_name:
        logger.warning(f"Fixture {fixture.fixture_id}: league name missing")
        return False

    # Check kickoff_time (must be in future)
    if not fixture.kickoff_time:
        logger.warning(f"Fixture {fixture.fixture_id}: kickoff_time missing")
        return False

    now_utc = datetime.now(timezone.utc)
    if fixture.kickoff_time <= now_utc:
        logger.warning(
            f"Fixture {fixture.fixture_id}: kickoff_time is in the past "
            f"(kickoff: {fixture.kickoff_time}, now: {now_utc})"
        )
        return False

    # Check odds
    if not fixture.odds or not isinstance(fixture.odds, dict):
        logger.warning(f"Fixture {fixture.fixture_id}: odds dict is empty or invalid")
        return False

    if "match_result" not in fixture.odds:
        logger.warning(
            f"Fixture {fixture.fixture_id}: match_result market not available in odds"
        )
        return False

    return True


def _format_fixture_details(fixture: Fixture) -> str:
    """
    Format fixture details section for prompt.

    Includes: League, teams, date/time, location (if available)

    Args:
        fixture: Fixture to format

    Returns:
        Formatted fixture details string
    """
    # Clean team names (remove extra whitespace and HTML)
    home_name = fixture.home_team.name.strip()
    away_name = fixture.away_team.name.strip()

    # Format kickoff time for readability
    kickoff_str = fixture.kickoff_time.strftime("%Y-%m-%d %H:%M %Z")

    details = (
        f"League: {fixture.league.league_name}\n"
        f"Fixture: {home_name} vs {away_name}\n"
        f"Date/Time: {kickoff_str}\n"
        f"Fixture ID: {fixture.fixture_id}"
    )

    return details


def _format_team_form(team_name: str, form_games: list[str]) -> str:
    """
    Format team form data section.

    Includes: Team name, recent form (W/D/L), win %, goals/game

    Args:
        team_name: Team name
        form_games: List of W/D/L results (recent form)

    Returns:
        Formatted team form string
    """
    if not form_games:
        return f"{team_name}: Form data unavailable"

    # Build form string (e.g., "W-W-D-L-W")
    form_str = "-".join(form_games)

    # Calculate win percentage (W=1, D=0.5, L=0)
    if form_games:
        win_points = sum(
            1.0 if result == "W" else 0.5 if result == "D" else 0.0
            for result in form_games
        )
        win_percentage = (win_points / len(form_games)) * 100
    else:
        win_percentage = 0.0

    form_output = (
        f"{team_name}:\n"
        f"  Recent Form: {form_str}\n"
        f"  Win Rate: {win_percentage:.1f}%"
    )

    return form_output


def _format_injuries(fixture: Fixture) -> str:
    """
    Format injury/suspension information section.

    Lists key injured/suspended players with positions.
    Handles cases where no injury data is available.

    Args:
        fixture: Fixture with injury data

    Returns:
        Formatted injuries string
    """
    home_injuries = fixture.home_team.injuries if fixture.home_team.injuries else []
    away_injuries = fixture.away_team.injuries if fixture.away_team.injuries else []

    if not home_injuries and not away_injuries:
        return "Injuries/Suspensions: No notable injuries reported"

    injuries_str = "Injuries/Suspensions:\n"

    if home_injuries:
        # Limit to first 5 players
        injuries_str += f"  {fixture.home_team.name}: {', '.join(home_injuries[:5])}\n"

    if away_injuries:
        injuries_str += (
            f"  {fixture.away_team.name}: {', '.join(away_injuries[:5])}\n"
        )

    return injuries_str.strip()


def _format_h2h_history(fixture: Fixture) -> str:
    """
    Format head-to-head history section.

    Shows recent H2H record and results.

    Args:
        fixture: Fixture with H2H history

    Returns:
        Formatted H2H history string
    """
    if not fixture.head_to_head_history:
        return "Head-to-Head: No previous meetings"

    h2h_results = fixture.head_to_head_history
    h2h_str = "-".join(h2h_results)

    # Calculate H2H record (from home team perspective)
    home_wins = h2h_results.count("W")
    draws = h2h_results.count("D")
    away_wins = h2h_results.count("L")

    h2h_output = (
        f"Head-to-Head (last {len(h2h_results)} matches):\n"
        f"  Results: {h2h_str}\n"
        f"  Record: {home_wins}W-{draws}D-{away_wins}L "
        f"({fixture.home_team.name} perspective)"
    )

    return h2h_output


def _get_available_markets(fixture: Fixture) -> dict[str, bool]:
    """
    Check which betting markets are available in fixture odds.

    Args:
        fixture: Fixture with odds data

    Returns:
        Dict with market availability: {"match_result": true, "total_goals": false, ...}
    """
    markets = {
        "match_result": "match_result" in fixture.odds,
        "total_goals": "total_goals" in fixture.odds,
        "corners": "corners" in fixture.odds,
        "cards": "cards" in fixture.odds,
    }

    logger.debug(f"Fixture {fixture.fixture_id}: Available markets: {markets}")
    return markets


def _format_odds(fixture: Fixture) -> str:
    """
    Format odds section for prompt.

    Includes odds for key markets: match_result, total_goals, corners, cards.
    Shows implied probabilities based on odds.

    Args:
        fixture: Fixture with odds data

    Returns:
        Formatted odds string
    """
    if not fixture.odds:
        return "Current Odds: Not available"

    odds_str = "Current Odds:\n"

    # Match result market
    if "match_result" in fixture.odds:
        mr_odds = fixture.odds["match_result"]
        odds_str += f"  Match Result:\n"
        if isinstance(mr_odds, dict):
            for outcome, odd_value in mr_odds.items():
                # Calculate implied probability
                implied_prob = (1.0 / odd_value * 100) if odd_value > 0 else 0.0
                odds_str += f"    {outcome}: {odd_value:.2f} (implied: {implied_prob:.1f}%)\n"
        odds_str += "\n"
    else:
        odds_str += "  Match Result: Not available\n\n"

    # Total goals market
    if "total_goals" in fixture.odds:
        tg_odds = fixture.odds["total_goals"]
        odds_str += f"  Total Goals:\n"
        if isinstance(tg_odds, dict):
            for outcome, odd_value in tg_odds.items():
                implied_prob = (1.0 / odd_value * 100) if odd_value > 0 else 0.0
                odds_str += f"    {outcome}: {odd_value:.2f} (implied: {implied_prob:.1f}%)\n"
        odds_str += "\n"
    else:
        odds_str += "  Total Goals: Not available\n\n"

    # Corners market
    if "corners" in fixture.odds:
        c_odds = fixture.odds["corners"]
        odds_str += f"  Corners:\n"
        if isinstance(c_odds, dict):
            for outcome, odd_value in c_odds.items():
                implied_prob = (1.0 / odd_value * 100) if odd_value > 0 else 0.0
                odds_str += f"    {outcome}: {odd_value:.2f} (implied: {implied_prob:.1f}%)\n"
        odds_str += "\n"
    else:
        odds_str += "  Corners: Not available\n\n"

    # Cards market
    if "cards" in fixture.odds:
        c_odds = fixture.odds["cards"]
        odds_str += f"  Cards:\n"
        if isinstance(c_odds, dict):
            for outcome, odd_value in c_odds.items():
                implied_prob = (1.0 / odd_value * 100) if odd_value > 0 else 0.0
                odds_str += f"    {outcome}: {odd_value:.2f} (implied: {implied_prob:.1f}%)\n"
    else:
        odds_str += "  Cards: Not available"

    return odds_str.rstrip()


def _format_analysis_request() -> str:
    """
    Format analysis request section.

    Specifies what probabilities and reasoning AI should provide.
    Includes example JSON response format.

    Returns:
        Formatted analysis request string
    """
    request_str = """ANALYSIS REQUEST:

Please provide probability estimates for the following markets:
1. Match Result: Probability for Home Win, Draw, and Away Win
2. Total Goals: Probability for Over 2.5 and Under 2.5
3. Corners: Probability for Over 9.5 and Under 9.5 (or appropriate line)
4. Cards: Probability for Over 5.0 and Under 5.0 (or appropriate line)

For each market, provide:
- Your estimated probability for each outcome (0.0-1.0 range)
- Brief reasoning (max 1-2 sentences per market)
- Confidence level (0-100)

RESPONSE FORMAT:
Return your analysis as JSON with the following structure:
{
  "markets": [
    {
      "type": "match_result",
      "outcomes": {
        "home": 0.45,
        "draw": 0.28,
        "away": 0.27
      },
      "reasoning": "Brief explanation here",
      "confidence": 75
    },
    {
      "type": "total_goals",
      "outcomes": {
        "over_2_5": 0.62,
        "under_2_5": 0.38
      },
      "reasoning": "Brief explanation here",
      "confidence": 68
    },
    {
      "type": "corners",
      "outcomes": {
        "over_9_5": 0.55,
        "under_9_5": 0.45
      },
      "reasoning": "Brief explanation here",
      "confidence": 62
    },
    {
      "type": "cards",
      "outcomes": {
        "over_5_0": 0.48,
        "under_5_0": 0.52
      },
      "reasoning": "Brief explanation here",
      "confidence": 58
    }
  ]
}

Key Requirements:
- Probabilities for each market must sum to 1.0 (or 100%)
- Keep reasoning concise and evidence-based
- Only include markets with valid odds data above
- Return ONLY the JSON object, no additional text"""

    return request_str


async def build_analysis_prompt(fixture: Fixture) -> str:
    """
    Build complete OpenAI analysis prompt for a fixture.

    This is the main entry point. Validates fixture data, assembles all
    context sections, enforces token limit, and returns complete prompt
    ready for OpenAI API.

    Process:
    1. Validate fixture data
    2. Build all context sections (fixture details, form, injuries, h2h, odds)
    3. Assemble with system prompt and analysis request
    4. Count tokens and warn if approaching limit
    5. Return complete prompt string

    Args:
        fixture: Fixture object from consolidation pipeline (with quality score)

    Returns:
        Complete prompt string ready for OpenAI API

    Raises:
        ValueError: If fixture validation fails or token count exceeds hard limit
    """
    # Step 1: Validate fixture data
    if not _validate_fixture_for_prompt(fixture):
        raise ValueError(
            f"Fixture {fixture.fixture_id} failed validation - missing required fields"
        )

    # Log fixture summary
    logger.info(
        f"Building prompt for fixture {fixture.fixture_id}: "
        f"{fixture.home_team.name} vs {fixture.away_team.name} ({fixture.league.league_name})"
    )

    # Step 2: Build fixture details section
    fixture_details = _format_fixture_details(fixture)

    # Step 3 & 4: Build team form sections
    home_form = _format_team_form(fixture.home_team.name, fixture.home_team.form_5_games)
    away_form = _format_team_form(fixture.away_team.name, fixture.away_team.form_5_games)

    # Step 5: Build injuries section
    injuries = _format_injuries(fixture)

    # Step 6: Build H2H section
    h2h = _format_h2h_history(fixture)

    # Step 7: Build odds section
    odds = _format_odds(fixture)

    # Step 8: Build analysis request section
    analysis_request = _format_analysis_request()

    # Step 9: Assemble all sections with clear headers and spacing
    user_message = (
        f"{fixture_details}\n\n"
        f"=== TEAM FORM ===\n"
        f"{home_form}\n\n"
        f"{away_form}\n\n"
        f"=== {injuries.split(':')[0].upper()} ===\n"
        f"{injuries}\n\n"
        f"=== H2H HISTORY ===\n"
        f"{h2h}\n\n"
        f"=== {odds.split(':')[0].upper()} ===\n"
        f"{odds}\n\n"
        f"=== {analysis_request.split(':')[0].upper()} ===\n"
        f"{analysis_request}"
    )

    # Step 11: Validate total token count
    system_tokens = _estimate_token_count(SYSTEM_PROMPT)
    user_tokens = _estimate_token_count(user_message)
    total_tokens = system_tokens + user_tokens

    logger.info(
        f"Fixture {fixture.fixture_id}: Prompt token estimate - "
        f"system: {system_tokens}, user: {user_tokens}, total: {total_tokens}"
    )

    if total_tokens > TOKEN_ESTIMATE_WARNING:
        logger.warning(
            f"Fixture {fixture.fixture_id}: Prompt approaching token limit "
            f"({total_tokens} > {TOKEN_ESTIMATE_WARNING})"
        )

    if total_tokens > TOKEN_HARD_LIMIT:
        raise ValueError(
            f"Fixture {fixture.fixture_id}: Prompt exceeds hard token limit "
            f"({total_tokens} > {TOKEN_HARD_LIMIT})"
        )

    # Step 13: Create comprehensive logging
    logger.debug(
        f"Fixture {fixture.fixture_id}: Complete prompt (first 500 chars): "
        f"{user_message[:500]}"
    )

    # Step 12: Return complete prompt string
    # Note: System prompt is returned separately in export_prompt_for_api()
    return user_message


async def export_prompt_for_api(fixture: Fixture) -> dict[str, str]:
    """
    Export prompt in format ready for OpenAI API client.

    Wraps build_analysis_prompt() output into dict format with
    "system_prompt" and "user_message" keys for easy integration
    with OpenAI client in Story 4.2.

    Args:
        fixture: Fixture object from consolidation pipeline

    Returns:
        Dict with keys: "system_prompt", "user_message"

    Example:
        >>> prompt_dict = await export_prompt_for_api(fixture)
        >>> # Ready for OpenAI client:
        >>> response = client.chat.completions.create(
        ...     model="gpt-4",
        ...     system_prompt=prompt_dict["system_prompt"],
        ...     user_message=prompt_dict["user_message"]
        ... )
    """
    try:
        # Call build_analysis_prompt (async) and get user message
        user_message = await build_analysis_prompt(fixture)

        if not user_message:
            logger.error(f"Fixture {fixture.fixture_id}: empty prompt generated")
            raise ValueError("build_analysis_prompt returned empty message")

    except Exception as e:
        logger.error(f"Failed to build prompt for fixture {fixture.fixture_id}: {str(e)}")
        raise

    return {
        "system_prompt": SYSTEM_PROMPT,
        "user_message": user_message,
    }
