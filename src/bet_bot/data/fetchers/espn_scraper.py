"""
ESPN web scraper for team form data as a backup source.

This module implements web scraping of ESPN team statistics pages to extract
team form data when API-Football is unavailable. This is a BACKUP-ONLY source.

Features:
- Async HTML fetching with httpx (reuses global client from api_football.py)
- BeautifulSoup4 for robust HTML parsing
- Automatic retry logic with exponential backoff (2 attempts max)
- Client-side rate limiting (1 request per 2 seconds, 30 per minute)
- Graceful error handling with partial data fallback
- Structured logging with context
- Pydantic validation of final output

Rate Limiting Rationale:
- ESPN blocks aggressive scrapers (429/403 responses)
- 1 request per 2 seconds = 30/minute is safe
- Prevents detection and temporary blocks

Important Notes:
- This scraper is fragile - ESPN redesigns website regularly
- Missing HTML elements are expected - we gracefully degrade
- Never retry 403/404 responses (ESPN explicitly blocking)
- Always return None on failure (never raise to caller)

Usage:
    from bet_bot.data.fetchers.espn_scraper import fetch_team_form_espn

    form = await fetch_team_form_espn(team_name="Leeds United", league="Championship")
    if form:
        print(f"Win %: {form.win_percentage_5}")
    else:
        print("ESPN scraping failed - no backup form data available")
"""

import asyncio
import logging
import time
from collections import deque
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from pydantic import ValidationError
from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bet_bot.exceptions import ScraperError
from bet_bot.models import TeamForm

# Module-level logger
logger = logging.getLogger(__name__)

# Import global HTTP client to reuse connection pool
from bet_bot.data.fetchers.api_football import get_http_client

# Public API exports
__all__ = [
    'RateLimiter',
    'fetch_team_form_espn',
    'parse_match_results',
    'parse_goals_averages',
    'calculate_win_percentages',
    'build_espn_url',
    'fetch_html_with_retry',
]


class RateLimiter:
    """
    Token bucket rate limiter for ESPN scraper requests.

    Prevents ESPN from blocking our scraper by enforcing delays between requests.
    Separate from API-Football rate limiter due to different limits.

    Attributes:
        max_requests: Maximum requests allowed in time window (30/min for ESPN)
        time_window: Time window in seconds (60 for per-minute limit)
    """

    def __init__(self, max_requests: int, time_window: int):
        """
        Initialize rate limiter for ESPN scraper.

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
                        f"ESPN scraper rate limit reached. "
                        f"Waiting {wait_time:.1f}s"
                    )
                    await asyncio.sleep(wait_time)
                    # Recursive call after wait
                    return await self.acquire()

            # Record this request
            self.requests.append(now)


# ESPN rate limiter (1 request per 2 seconds = 30 per minute max)
espn_limiter = RateLimiter(max_requests=30, time_window=60)


def build_espn_url(team_name: str, league: str) -> str:
    """
    Build ESPN team statistics URL for web scraping.

    Constructs a URL to ESPN's team statistics page based on team name and league.

    **FRAGILITY WARNING**: ESPN URLs vary by league and change frequently.
    This implementation uses the pattern: /soccer/team/_/name/{team-slug}

    Known alternatives that ESPN may use:
    - /soccer/team/_/id/{team-id}/{team-slug} (team ID + slug)
    - /soccer/team/_/id/{team-id} (just team ID)
    - League-specific URLs with different patterns

    If scraping fails with 404, this URL pattern likely needs updating.

    Args:
        team_name: Team name (e.g., "Leeds United")
        league: League name (e.g., "Championship", "Premier League")
            Note: Currently not used in URL construction but may be needed

    Returns:
        ESPN team statistics URL

    Example:
        url = build_espn_url("Leeds United", "Championship")
        # Returns: https://www.espn.com/soccer/team/_/name/leeds-united
    """
    # Normalize team name for URL (lowercase, replace spaces with hyphens)
    team_slug = team_name.lower().replace(" ", "-")
    # Normalize league name
    league_slug = league.lower().replace(" ", "-")

    # ESPN soccer URLs follow pattern: /soccer/team/_/name/{team-slug}
    url = f"https://www.espn.com/soccer/team/_/name/{team_slug}"

    logger.debug(
        f"Built ESPN URL for {team_name} | "
        f"URL: {url}"
    )

    return url


@retry(
    retry=retry_if_exception_type((
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.NetworkError,
    )),
    stop=stop_after_attempt(2),  # Only 2 attempts for scraper (vs 5 for API)
    wait=wait_exponential(multiplier=1, min=1, max=8),  # 1s, 2s max
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO)
)
async def fetch_html_with_retry(url: str) -> str:
    """
    Fetch HTML from ESPN with automatic retry logic.

    Retries transient errors (timeouts, connection errors) but NOT 403/404
    (ESPN explicitly blocks scrapers).

    Max 2 attempts with exponential backoff: 1s, 2s.

    Args:
        url: URL to fetch

    Returns:
        HTML response text

    Raises:
        httpx.HTTPStatusError: For 5xx responses (triggers retry)
        httpx.TimeoutException: After all retries exhausted
        httpx.ConnectError: After all retries exhausted
    """
    client = await get_http_client()

    # ESPN can be slow - use 10s timeout (vs 30s for API-Football)
    response = await client.get(
        url,
        timeout=httpx.Timeout(10.0),
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
    )

    # Don't retry on 403/404 - ESPN is blocking us
    if response.status_code in (403, 404):
        logger.warning(
            f"ESPN blocking scraper or page not found | "
            f"URL: {url} | Status: {response.status_code}"
        )
        raise httpx.HTTPStatusError(
            "ESPN blocking scraper",
            request=response.request,
            response=response
        )

    # Only retry 5xx
    if response.status_code >= 500:
        response.raise_for_status()

    return response.text


def parse_match_results(html: str) -> list[str]:
    """
    Parse match results from ESPN HTML.

    Extracts recent match results (W/D/L) from the results table on ESPN
    team pages. Returns gracefully with empty list if table is missing.

    Args:
        html: HTML content of ESPN team page

    Returns:
        List of results (W/D/L) from most recent games (max 10)

    Example:
        >>> results = parse_match_results(espn_html)
        >>> print(results)
        ['W', 'L', 'D', 'W', 'W']
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')

        # ESPN uses tables with class 'Table' for results
        table = soup.find('table', class_='Table')
        if not table:
            logger.warning(
                "Match results table not found on ESPN page | "
                "Page structure may have changed"
            )
            return []

        # Extract rows (skip header)
        rows = table.find_all('tr')[1:]  # Skip header row
        if not rows:
            logger.warning("No match result rows found in table")
            return []

        results = []
        for row in rows[:10]:  # Last 10 games max
            try:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    # Result is typically in 3rd column (0-indexed: cells[2])
                    result_cell = cells[2].get_text(strip=True).upper()

                    # Check if it's a valid result
                    if result_cell in ['W', 'D', 'L']:
                        results.append(result_cell)
            except (AttributeError, IndexError):
                # Missing elements in this row - skip and continue
                continue

        logger.debug(f"Extracted {len(results)} match results from ESPN")
        return results

    except Exception as e:
        logger.error(
            f"Error parsing match results from ESPN | "
            f"Error: {type(e).__name__}: {str(e)}"
        )
        return []  # Graceful degradation


def parse_goals_averages(html: str) -> tuple[float, float, float, float]:
    """
    Parse goal averages from ESPN HTML.

    Extracts goals for and goals against averages from team statistics
    on ESPN pages. Returns gracefully with 0.0 values if data is missing.

    Returns tuple of:
    - goals_avg_home: Average goals scored at home
    - goals_avg_away: Average goals scored away
    - goals_against_avg_home: Average goals conceded at home
    - goals_against_avg_away: Average goals conceded away

    Args:
        html: HTML content of ESPN team page

    Returns:
        Tuple of (goals_for_home, goals_for_away, goals_against_home, goals_against_away)

    Example:
        >>> gf_home, gf_away, ga_home, ga_away = parse_goals_averages(html)
        >>> print(f"Home: {gf_home} GF, {ga_home} GA")
        Home: 1.8 GF, 1.2 GA
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Initialize with defaults (0.0) - graceful degradation
        goals_for_home = 0.0
        goals_for_away = 0.0
        goals_against_home = 0.0
        goals_against_away = 0.0

        # Look for statistics table with goal information
        # ESPN typically has a stats summary with home/away breakdowns
        stat_tables = soup.find_all('table', class_='Table')

        for table in stat_tables:
            # Look for rows with goal statistics
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    stat_label = cells[0].get_text(strip=True).lower()

                    # Multiple patterns to try (ESPN changes HTML frequently)
                    goal_for_patterns = [
                        'goals for',
                        'goals scored',
                        'goals avg',
                        'goals/game',
                        'gls for',
                        'avg goals'
                    ]
                    goal_against_patterns = [
                        'goals against',
                        'goals conceded',
                        'goals allowed',
                        'gls against',
                        'goals/game against'
                    ]

                    # Check if this row matches any pattern
                    is_goals_for = any(pattern in stat_label for pattern in goal_for_patterns)
                    is_goals_against = any(pattern in stat_label for pattern in goal_against_patterns)

                    if is_goals_for or is_goals_against:
                        # Try to extract home and away values
                        try:
                            # Typical format: "Label | Home | Away"
                            if len(cells) >= 3:
                                home_val = cells[1].get_text(strip=True)
                                away_val = cells[2].get_text(strip=True)
                                # Extract numeric part (might have extra text)
                                home_avg = float(home_val.split()[0])
                                away_avg = float(away_val.split()[0])

                                if is_goals_against:
                                    goals_against_home = home_avg
                                    goals_against_away = away_avg
                                else:
                                    goals_for_home = home_avg
                                    goals_for_away = away_avg
                        except (ValueError, IndexError):
                            # Can't parse this row - skip
                            continue

        logger.debug(
            f"Extracted goal averages | "
            f"GF Home: {goals_for_home}, GF Away: {goals_for_away}, "
            f"GA Home: {goals_against_home}, GA Away: {goals_against_away}"
        )

        # Check if all values are still 0.0 (parsing failed)
        if all(v == 0.0 for v in [goals_for_home, goals_for_away, goals_against_home, goals_against_away]):
            logger.warning(
                f"All goal averages returned 0.0 | "
                f"ESPN page structure may have changed - selectors need updating"
            )

        return goals_for_home, goals_for_away, goals_against_home, goals_against_away

    except Exception as e:
        logger.warning(
            f"Error parsing goal averages from ESPN | "
            f"Error: {type(e).__name__}: {str(e)} | "
            f"Using defaults (0.0 for all)"
        )
        return 0.0, 0.0, 0.0, 0.0  # Graceful degradation


def calculate_win_percentages(
    last_5_results: list[str],
    last_10_results: list[str]
) -> tuple[float, float]:
    """
    Calculate win percentages from match results.

    Converts W/D/L results to win percentages in 0.0-1.0 range.

    Args:
        last_5_results: List of results from last 5 games
        last_10_results: List of results from last 10 games

    Returns:
        Tuple of (win_percentage_5, win_percentage_10) in 0.0-1.0 range
    """
    win_pct_5 = 0.0
    win_pct_10 = 0.0

    if last_5_results:
        if len(last_5_results) < 5:
            logger.debug(
                f"Only {len(last_5_results)} results available for last_5 "
                f"(expected 5) - win percentage may be less accurate"
            )
        win_count_5 = last_5_results.count('W')
        win_pct_5 = win_count_5 / len(last_5_results)

    if last_10_results:
        if len(last_10_results) < 10:
            logger.debug(
                f"Only {len(last_10_results)} results available for last_10 "
                f"(expected 10) - win percentage may be less accurate"
            )
        win_count_10 = last_10_results.count('W')
        win_pct_10 = win_count_10 / len(last_10_results)

    logger.debug(
        f"Calculated win percentages | "
        f"5-game: {win_pct_5:.2%}, 10-game: {win_pct_10:.2%}"
    )

    return win_pct_5, win_pct_10


async def fetch_team_form_espn(
    team_name: str,
    league: str
) -> Optional[TeamForm]:
    """
    Fetch team form data from ESPN as a backup source.

    BACKUP-ONLY scraper. Only call if API-Football fails.

    This function:
    1. Builds ESPN team URL based on team name/league
    2. Fetches HTML with automatic retry (2 attempts max)
    3. Parses HTML to extract: match results, goal averages
    4. Constructs TeamForm object with all required fields
    5. Returns TeamForm on success, None on failure (graceful degradation)

    Args:
        team_name: Team name (e.g., "Leeds United")
        league: League name (e.g., "Championship")

    Returns:
        TeamForm object with scraped data, or None if scraping fails

    Raises:
        None - all errors are caught and logged. Returns None instead.

    Example:
        form = await fetch_team_form_espn("Leeds United", "Championship")
        if form:
            print(f"Win %: {form.win_percentage_5}")
        else:
            print("ESPN scraping unavailable")
    """
    # Rate limit to prevent ESPN blocking us
    await espn_limiter.acquire()

    try:
        # Build ESPN URL
        url = build_espn_url(team_name, league)

        # Fetch HTML with retry logic
        start_time = time.time()
        try:
            html = await fetch_html_with_retry(url)
        except httpx.HTTPStatusError as e:
            # 403/404 from ESPN blocking us - return None
            logger.warning(
                f"ESPN scraper blocked or page not found | "
                f"Team: {team_name} | League: {league} | "
                f"Status: {e.response.status_code}"
            )
            return None

        fetch_time = time.time() - start_time
        logger.info(
            f"ESPN scraper fetched HTML | "
            f"Team: {team_name} | Time: {fetch_time:.2f}s | "
            f"Size: {len(html)} bytes"
        )

        # Parse match results once (returns up to 10)
        all_results = parse_match_results(html)
        last_5_results = all_results[:5]   # First 5 results
        last_10_results = all_results[:10] # All 10 results

        # Parse goal averages
        gf_home, gf_away, ga_home, ga_away = parse_goals_averages(html)

        # Calculate win percentages
        win_pct_5, win_pct_10 = calculate_win_percentages(
            last_5_results,
            last_10_results
        )

        # Construct TeamForm object
        # Note: ESPN scraper doesn't provide team_id, using team_name as fallback
        form = TeamForm(
            team_id=team_name,  # Fallback to name since ESPN doesn't provide ID
            team_name=team_name,
            last_5_results=last_5_results,
            last_10_results=last_10_results,
            win_percentage_5=win_pct_5,
            win_percentage_10=win_pct_10,
            goals_avg_home=gf_home,
            goals_avg_away=gf_away,
            goals_against_avg_home=ga_home,
            goals_against_avg_away=ga_away
        )

        logger.info(
            f"ESPN scraper succeeded | "
            f"Team: {team_name} | League: {league} | "
            f"Results: {len(last_5_results)} games | "
            f"Win %: {win_pct_5:.1%}"
        )

        return form

    except ValidationError as e:
        logger.error(
            f"ESPN scraper validation failed | "
            f"Team: {team_name} | League: {league} | "
            f"Error: {str(e)}"
        )
        return None  # Graceful degradation

    except httpx.TimeoutException:
        logger.warning(
            f"ESPN scraper timeout (10s) | "
            f"Team: {team_name} | League: {league}"
        )
        return None  # Graceful degradation

    except httpx.NetworkError as e:
        logger.warning(
            f"ESPN scraper network error | "
            f"Team: {team_name} | League: {league} | "
            f"Error: {str(e)}"
        )
        return None  # Graceful degradation

    except Exception as e:
        logger.error(
            f"ESPN scraper unexpected error | "
            f"Team: {team_name} | League: {league} | "
            f"Error: {type(e).__name__}: {str(e)}"
        )
        return None  # Graceful degradation - never crash
