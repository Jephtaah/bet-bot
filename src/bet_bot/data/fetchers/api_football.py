"""
API-Football client for bet-bot application.

This module implements the primary data fetching layer for fixtures, team form,
injuries, and odds from API-Football v3 API.

Features:
- Async HTTP client with connection pooling
- Automatic retry logic with exponential backoff
- Client-side rate limiting (100 req/min)
- Comprehensive error handling
- Pydantic model validation
- Structured logging

API Documentation: https://www.api-football.com/documentation-v3

Usage:
    from bet_bot.data.fetchers import fetch_fixtures

    fixtures = await fetch_fixtures(date="2025-11-25")
"""

import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import ValidationError
from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bet_bot.config import config
from bet_bot.exceptions import (
    APIAuthenticationError,
    APIError,
    APIRateLimitError,
    APIServerError,
)
from bet_bot.models import Fixture, InjuredPlayer, Injury, League, Market, Odds, Team, TeamForm

# Module-level logger
logger = logging.getLogger(__name__)

# API-Football base URL
API_BASE_URL = "https://api-football-v3.p.rapidapi.com/v3"

# Global HTTP client instance (singleton)
_http_client: httpx.AsyncClient | None = None


class RateLimiter:
    """
    Token bucket rate limiter for API calls.

    Prevents exceeding API rate limits by enforcing client-side throttling.
    Uses a sliding window approach to track request timestamps.

    Attributes:
        max_requests: Maximum requests allowed in time window
        time_window: Time window in seconds
        requests: Deque of request timestamps
    """

    def __init__(self, max_requests: int, time_window: int):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquire permission to make a request.

        Blocks if rate limit is reached until time window allows new requests.
        Uses a sliding window algorithm to track request timestamps.
        """
        async with self._lock:
            now = time.time()

            # Remove requests outside time window
            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()

            # Check if we're at limit
            if len(self.requests) >= self.max_requests:
                # Calculate wait time
                oldest_request = self.requests[0]
                wait_time = self.time_window - (now - oldest_request)

                if wait_time > 0:
                    logger.info(
                        f"Rate limit reached. Waiting {wait_time:.1f}s"
                    )
                    await asyncio.sleep(wait_time)
                    # Recursive call after wait
                    return await self.acquire()

            # Record this request
            self.requests.append(now)


# API-Football rate limiter (100 requests per minute to stay under 300/min limit)
api_football_limiter = RateLimiter(max_requests=100, time_window=60)


async def get_http_client() -> httpx.AsyncClient:
    """
    Get or create the global HTTP client instance.

    Uses singleton pattern to reuse connection pool across requests.
    Client is configured with:
    - 30s total timeout, 10s connect timeout
    - 100 max connections, 20 keepalive connections
    - HTTP/2 enabled for better multiplexing
    - Automatic redirect following

    Returns:
        Configured async HTTP client instance
    """
    global _http_client

    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20
            ),
            follow_redirects=True,
            http2=False  # Set to False unless httpx[http2] installed
        )
        logger.debug("Created new HTTP client instance")

    return _http_client


async def close_http_client() -> None:
    """
    Close the global HTTP client.

    Should be called on application shutdown to ensure proper cleanup
    of connection pools and resources.
    """
    global _http_client

    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
        logger.debug("Closed HTTP client instance")


def get_api_headers() -> dict[str, str]:
    """
    Get authentication headers for API-Football requests.

    Returns:
        Dictionary of HTTP headers with API key and host

    Raises:
        ValueError: If API key is not configured
    """
    if not config or not config.api_football_key:
        raise ValueError(
            "API_FOOTBALL_KEY not configured. "
            "Please set it in your .env file."
        )

    return {
        "x-rapidapi-key": config.api_football_key,
        "x-rapidapi-host": "api-football-v3.p.rapidapi.com",
        "User-Agent": "bet-bot/1.0",
        "Accept": "application/json"
    }


@retry(
    retry=retry_if_exception_type((
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.NetworkError,
    )),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO)
)
async def fetch_with_retry(
    url: str,
    **kwargs: Any
) -> httpx.Response:
    """
    Fetch URL with automatic retry logic.

    Retries transient errors (timeouts, connection errors, network errors)
    with exponential backoff: 2s, 4s, 8s, 16s, 32s (max 5 attempts).

    Does NOT retry 4xx errors (except 429 rate limit handled separately).

    Args:
        url: URL to fetch
        **kwargs: Additional arguments for httpx.get()

    Returns:
        HTTP response

    Raises:
        httpx.HTTPStatusError: For 5xx and 429 responses (triggers retry)
        httpx.TimeoutException: After all retries exhausted
        httpx.NetworkError: After all retries exhausted
    """
    client = await get_http_client()
    response = await client.get(url, **kwargs)

    # Only raise for 5xx and 429 (triggers retry)
    if response.status_code >= 500 or response.status_code == 429:
        response.raise_for_status()

    return response


async def fetch_with_rate_limit(
    url: str,
    api_name: str = "API-Football"
) -> httpx.Response | None:
    """
    Fetch URL with rate limiting and Retry-After header handling.

    Respects 429 rate limit responses and Retry-After headers.
    Implements graceful degradation for expected failures.

    Args:
        url: URL to fetch
        api_name: API name for logging

    Returns:
        HTTP response or None for graceful degradation cases

    Raises:
        APIAuthenticationError: For 401/403 responses
        APIRateLimitError: For 429 responses after Retry-After wait
        APIServerError: For 5xx responses after retry exhaustion
    """
    # Apply client-side rate limiting
    await api_football_limiter.acquire()

    try:
        response = await fetch_with_retry(url, headers=get_api_headers())

        # Handle 429 with Retry-After header
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                if retry_after.isdigit():
                    # Seconds to wait
                    wait_seconds = int(retry_after)
                else:
                    # HTTP date format
                    try:
                        retry_date = datetime.strptime(
                            retry_after,
                            "%a, %d %b %Y %H:%M:%S GMT"
                        )
                        wait_seconds = int(
                            (retry_date - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds()
                        )
                    except ValueError:
                        wait_seconds = 60  # Default wait

                logger.warning(
                    f"{api_name} rate limited. "
                    f"Waiting {wait_seconds}s before retry"
                )
                await asyncio.sleep(wait_seconds)
                # Recursive retry after wait
                return await fetch_with_rate_limit(url, api_name)

            raise APIRateLimitError(
                f"{api_name} rate limit exceeded",
                url=url,
                status_code=429
            )

        # Log successful call
        logger.info(
            f"{api_name} API call successful | "
            f"URL: {url} | Status: {response.status_code}"
        )

        return response

    except httpx.HTTPStatusError as e:
        status = e.response.status_code

        if status == 401 or status == 403:
            raise APIAuthenticationError(
                f"{api_name} authentication failed",
                url=url,
                status_code=status,
                response_body=e.response.text
            ) from e
        elif status == 404:
            logger.warning(f"{api_name} resource not found: {url}")
            return None  # Graceful degradation
        elif status >= 500:
            raise APIServerError(
                f"{api_name} server error",
                url=url,
                status_code=status,
                response_body=e.response.text
            ) from e
        else:
            raise APIError(
                f"{api_name} unexpected error",
                url=url,
                status_code=status,
                response_body=e.response.text
            ) from e

    except httpx.TimeoutException:
        logger.error(f"{api_name} timeout after 30s: {url}")
        return None  # Graceful degradation

    except httpx.NetworkError as e:
        logger.error(f"{api_name} network error: {url} | {str(e)}")
        return None  # Graceful degradation


async def fetch_fixtures(
    date: str,
    league_id: str | None = None
) -> list[Fixture]:
    """
    Fetch today's fixtures from API-Football.

    Args:
        date: Date in YYYY-MM-DD format (e.g., "2025-11-25")
        league_id: Optional league ID to filter fixtures

    Returns:
        List of Fixture objects or empty list if no fixtures found

    Raises:
        APIAuthenticationError: If API key is invalid
        ValidationError: If response doesn't match expected schema

    Example:
        fixtures = await fetch_fixtures(date="2025-11-25")
        for fixture in fixtures:
            print(f"{fixture.home_team.name} vs {fixture.away_team.name}")
    """
    url = f"{API_BASE_URL}/fixtures?date={date}"
    if league_id:
        url += f"&league={league_id}"

    response = await fetch_with_rate_limit(url)

    if response is None:
        return []  # Graceful degradation

    try:
        data = response.json()
        fixtures_data = data.get("response", [])

        if not fixtures_data:
            logger.info(f"No fixtures found for date: {date}")
            return []

        # Transform API response to Fixture objects
        fixtures = []
        for item in fixtures_data:
            try:
                # Extract nested structures
                fixture_data = item.get("fixture", {})
                teams_data = item.get("teams", {})
                league_data = item.get("league", {})

                # Manually construct Team objects
                home_team = Team(
                    id=str(teams_data.get("home", {}).get("id", "")),
                    name=teams_data.get("home", {}).get("name", "")
                )

                away_team = Team(
                    id=str(teams_data.get("away", {}).get("id", "")),
                    name=teams_data.get("away", {}).get("name", "")
                )

                # Manually construct League object
                league = League(
                    league_id=str(league_data.get("id", "")),
                    league_name=league_data.get("name", ""),
                    league_country=league_data.get("country", ""),
                    league_season=league_data.get("season", 0)
                )

                # Create Fixture object
                fixture = Fixture.model_validate({
                    "fixture.id": str(fixture_data.get("id", "")),
                    "fixture.date": fixture_data.get("date", ""),
                    "home_team": home_team,
                    "away_team": away_team,
                    "league": league
                })

                fixtures.append(fixture)

            except ValidationError as e:
                logger.warning(
                    f"Fixture validation failed: {str(e)} | "
                    f"Data: {str(item)[:200]}"
                )
                continue  # Skip invalid fixtures

        logger.info(f"Fetched {len(fixtures)} fixtures for {date}")
        return fixtures

    except Exception as e:
        logger.exception(f"Unexpected error parsing fixtures: {str(e)}")
        return []


async def fetch_team_form(
    team_id: str,
    league_id: str,
    team_name: str,
    season: int | None = None
) -> TeamForm | None:
    """
    Fetch team statistics and form from API-Football.

    Args:
        team_id: Team ID
        league_id: League ID
        team_name: Team display name (required for TeamForm model)
        season: Season year (defaults to current year)

    Returns:
        TeamForm object or None if data unavailable

    Raises:
        APIAuthenticationError: If API key is invalid

    Note:
        API-Football does not provide separate home/away goal statistics,
        so home and away averages use the same overall values.

    Example:
        form = await fetch_team_form(
            team_id="33",
            league_id="39",
            team_name="Manchester United",
            season=2025
        )
        print(f"Win %: {form.win_percentage_5}")
    """
    if season is None:
        season = datetime.now().year

    url = (
        f"{API_BASE_URL}/teams/statistics"
        f"?team={team_id}&season={season}&league={league_id}"
    )

    response = await fetch_with_rate_limit(url)

    if response is None:
        return None  # Graceful degradation

    try:
        data = response.json()
        stats = data.get("response", {})

        if not stats:
            logger.warning(
                f"No statistics found for team {team_id} "
                f"in league {league_id}"
            )
            # Return TeamForm with empty data
            return TeamForm(
                team_id=team_id,
                team_name=team_name,
                last_5_results=[],
                last_10_results=[],
                win_percentage_5=0.0,
                win_percentage_10=0.0,
                goals_avg_home=0.0,
                goals_avg_away=0.0,
                goals_against_avg_home=0.0,
                goals_against_avg_away=0.0
            )

        # Extract form data from API response
        form_data = stats.get("form", "")
        goals_data = stats.get("goals", {})

        # Parse last 5/10 results from form string (e.g., "WWDLW")
        last_5 = list(form_data[-5:]) if len(form_data) >= 5 else []
        last_10 = list(form_data[-10:]) if len(form_data) >= 10 else []

        # Calculate win percentages (0.0-1.0 range per TeamForm model definition)
        win_5 = last_5.count("W") if last_5 else 0
        win_10 = last_10.count("W") if last_10 else 0

        win_pct_5 = (win_5 / len(last_5)) if last_5 else 0.0
        win_pct_10 = (win_10 / len(last_10)) if last_10 else 0.0

        # Extract goal averages
        goals_for = goals_data.get("for", {})
        goals_against = goals_data.get("against", {})

        goals_for_avg = goals_for.get("average", {})
        goals_against_avg = goals_against.get("average", {})

        # API-Football provides overall averages, approximate for 5/10 games
        gf_avg = float(goals_for_avg.get("total", 0.0) or 0.0)
        ga_avg = float(goals_against_avg.get("total", 0.0) or 0.0)

        team_form = TeamForm(
            team_id=team_id,
            team_name=team_name,
            last_5_results=last_5,
            last_10_results=last_10,
            win_percentage_5=win_pct_5,
            win_percentage_10=win_pct_10,
            goals_avg_home=gf_avg,
            goals_avg_away=gf_avg,
            goals_against_avg_home=ga_avg,
            goals_against_avg_away=ga_avg
        )

        logger.info(f"Fetched form for team {team_id}")
        return team_form

    except ValidationError as e:
        logger.error(
            f"Team form validation failed: {str(e)} | "
            f"Team: {team_id}"
        )
        return None

    except Exception as e:
        logger.exception(
            f"Unexpected error parsing team form: {str(e)} | "
            f"Team: {team_id}"
        )
        return None


async def fetch_injuries(team_id: str) -> Injury | None:
    """
    Fetch player injuries for a team from API-Football.

    Args:
        team_id: Team ID

    Returns:
        Injury object or None if data unavailable

    Raises:
        APIAuthenticationError: If API key is invalid

    Example:
        injuries = await fetch_injuries(team_id="33")
        print(f"Missing key players: {injuries.missing_key_players_count}")
    """
    url = f"{API_BASE_URL}/injuries?team={team_id}"

    response = await fetch_with_rate_limit(url)

    if response is None:
        return None  # Graceful degradation

    try:
        data = response.json()
        injuries_data = data.get("response", [])

        if not injuries_data:
            logger.info(f"No injuries found for team {team_id}")
            return Injury(
                team_id=team_id,
                injured_players=[],
                missing_key_players_count=0,
                missing_key_players_list=[]
            )

        # Transform API response to InjuredPlayer objects
        injured_players = []
        missing_key_count = 0.0
        missing_key_names = []

        for item in injuries_data:
            try:
                player_data = item.get("player", {})
                reason = item.get("player", {}).get("reason", "")

                # Map to standard status
                status = "Out"
                if "doubt" in reason.lower():
                    status = "Doubt"
                elif "injured" in reason.lower():
                    status = "Injured"
                elif "suspended" in reason.lower():
                    status = "Suspended"

                # Estimate impact severity (simplified)
                impact = "Minor"
                if status in ["Injured", "Out", "Suspended"]:
                    impact = "Key"
                elif status == "Doubt":
                    impact = "Moderate"

                injured_player = InjuredPlayer(
                    player_id=str(player_data.get("id", "")),
                    player_name=player_data.get("name", "Unknown"),
                    position=player_data.get("position", "Unknown"),
                    injury_status=status,
                    impact_severity=impact
                )

                injured_players.append(injured_player)

                # Calculate missing key players
                if impact == "Key":
                    missing_key_count += 1
                    missing_key_names.append(injured_player.player_name)
                elif impact == "Moderate":
                    missing_key_count += 0.5

            except ValidationError as e:
                logger.warning(
                    f"Injured player validation failed: {str(e)}"
                )
                continue

        injury = Injury(
            team_id=team_id,
            injured_players=injured_players,
            missing_key_players_count=int(missing_key_count),
            missing_key_players_list=missing_key_names
        )

        logger.info(
            f"Fetched {len(injured_players)} injuries for team {team_id}"
        )
        return injury

    except ValidationError as e:
        logger.error(f"Injury validation failed: {str(e)} | Team: {team_id}")
        return None

    except Exception as e:
        logger.exception(
            f"Unexpected error parsing injuries: {str(e)} | Team: {team_id}"
        )
        return None


async def fetch_odds(fixture_id: str) -> Odds | None:
    """
    Fetch betting odds for a fixture from API-Football /v3/odds endpoint.

    Fetches odds for all available markets (match result, total goals, corners, cards).
    Handles missing markets gracefully by skipping unavailable markets.
    Validates odds freshness and logs age for each fixture.

    Args:
        fixture_id: Unique identifier for the fixture

    Returns:
        Odds object with all available markets and timestamp, or None for graceful
        degradation cases (404, timeout, network error)

    Raises:
        APIAuthenticationError: If API key is invalid or expired (401/403)
        APIServerError: For server errors (5xx) that will be retried

    Example:
        odds = await fetch_odds(fixture_id="1423864")
        if odds:
            for market in odds.markets:
                print(f"{market.market_type}: {market.odds}")
                age_minutes = (datetime.now(timezone.utc).replace(tzinfo=None) - odds.odds_updated_at).total_seconds() / 60
                print(f"Odds age: {age_minutes:.0f}m")
    """
    url = f"{API_BASE_URL}/odds?fixture={fixture_id}"

    response = await fetch_with_rate_limit(url)

    if response is None:
        return None  # Graceful degradation

    try:
        data = response.json()
        odds_data = data.get("response", [])

        if not odds_data:
            logger.warning(f"No odds found for fixture {fixture_id}")
            return None

        # Extract first bookmaker (usually most reliable)
        bookmaker_data = odds_data[0] if odds_data else {}

        # Extract timestamp from API response (update field)
        timestamp_str = bookmaker_data.get("update", "")
        try:
            # Parse ISO 8601 timestamp (e.g., "2025-11-24T14:30:00+00:00")
            odds_updated_at = datetime.fromisoformat(timestamp_str)
        except (ValueError, TypeError):
            # Fallback to current time if timestamp parsing fails
            logger.warning(
                f"Could not parse odds timestamp for fixture {fixture_id}. "
                f"Using current time. Raw timestamp: {timestamp_str}"
            )
            odds_updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        # Calculate odds age and log
        age = datetime.now(timezone.utc).replace(tzinfo=None) - odds_updated_at.replace(tzinfo=None)
        age_minutes = age.total_seconds() / 60

        if age_minutes < 0:
            # Handle timezone issues (odds_updated_at in future)
            age_minutes = 0

        logger.info(f"Odds for fixture {fixture_id} are {age_minutes:.0f}m old")

        if age_minutes > 60:
            logger.warning(
                f"Odds are stale (>60m old) but continuing for fixture {fixture_id}"
            )

        # Extract bookmaker name
        bookmakers = bookmaker_data.get("bookmakers", [])
        if bookmakers:
            bookmaker_name = bookmakers[0].get("name", "Unknown")
        else:
            bookmaker_name = "Unknown"

        # Transform bets to Market objects
        markets = []
        bets = bookmaker_data.get("bets", [])

        for bet in bets:
            try:
                market_type = bet.get("name", "Unknown")
                values = bet.get("values", [])

                if not values:
                    logger.info(
                        f"Market {market_type} not available, skipping "
                        f"for fixture {fixture_id}"
                    )
                    continue

                # Transform outcomes array to dict[str, float]
                odds_dict = {}
                for value in values:
                    outcome_name = value.get("value", "")
                    odd_str = value.get("odd", "")

                    if not outcome_name:
                        continue

                    try:
                        odds_value = float(odd_str)

                        # Validate odds value >= 1.0
                        if odds_value < 1.0:
                            logger.warning(
                                f"Skipping invalid odds value {odds_value} "
                                f"for market {market_type}, outcome {outcome_name}"
                            )
                            continue

                        if odds_value > 1000.0:
                            logger.warning(
                                f"Skipping unreasonable odds value {odds_value} "
                                f"for market {market_type}, outcome {outcome_name}"
                            )
                            continue

                        odds_dict[outcome_name] = odds_value

                    except (ValueError, TypeError):
                        logger.warning(
                            f"Could not parse odds value '{odd_str}' "
                            f"for market {market_type}, outcome {outcome_name}"
                        )
                        continue

                # Skip market if no valid outcomes
                if not odds_dict:
                    logger.info(
                        f"No valid outcomes found for market {market_type}, "
                        f"skipping for fixture {fixture_id}"
                    )
                    continue

                # Create Market object with validated odds
                try:
                    market = Market(
                        market_type=market_type,
                        odds=odds_dict
                    )
                    markets.append(market)
                except ValidationError as e:
                    logger.warning(
                        f"Market validation failed: {str(e)} | "
                        f"Market: {market_type} | Fixture: {fixture_id}"
                    )
                    continue

            except Exception as e:
                logger.warning(
                    f"Error processing market: {str(e)} | "
                    f"Market data: {str(bet)[:200]} | Fixture: {fixture_id}"
                )
                continue

        if not markets:
            logger.warning(
                f"No valid markets found for fixture {fixture_id}"
            )
            return None

        # Create Odds object
        try:
            odds = Odds(
                fixture_id=fixture_id,
                bookmaker_name=bookmaker_name,
                odds_updated_at=odds_updated_at,
                markets=markets
            )

            logger.info(
                f"Fetched odds with {len(markets)} markets for fixture {fixture_id} | "
                f"Bookmaker: {bookmaker_name} | Age: {age_minutes:.0f}m"
            )
            return odds

        except ValidationError as e:
            logger.error(
                f"Odds object validation failed: {str(e)} | "
                f"Fixture: {fixture_id}"
            )
            return None

    except Exception as e:
        logger.exception(
            f"Unexpected error parsing odds: {str(e)} | "
            f"Fixture: {fixture_id}"
        )
        return None
