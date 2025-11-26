# CLAUDE.md - bet-bot Project Rules

**Project**: bet-bot - Positive Expected Value Detection Tool for Football Betting
**Language**: Python 3.10+
**Architecture**: CLI-based async data fetching + OpenAI analysis + terminal display

---

## ANTI-AI-INCONSISTENCY ENFORCEMENT

**CRITICAL**: Before ANY implementation, you MUST search for existing patterns and replicate them EXACTLY. ZERO tolerance for variations in error handling, validation, naming, API responses, async patterns, or data structures.

**MANDATORY WORKFLOW - Follow These Steps IN ORDER**:

1. **SEARCH FIRST** (REQUIRED before implementing ANYTHING):
   ```bash
   # Search for existing implementations
   Grep pattern="class.*Fetcher|async def fetch"
   Grep pattern="APIError|RetryError|ValidationError"
   Grep pattern="@retry|exponential_backoff"
   ```

2. **USE EXISTING PATTERNS** (NO exceptions):
   - If a retry decorator exists - USE IT
   - If an error class exists - USE IT
   - If a validation pattern exists - REPLICATE IT EXACTLY
   - If an async pattern exists - FOLLOW IT IDENTICALLY

3. **STRICTLY FORBIDDEN**:
   - Creating custom error handling when standard exists
   - Using different retry strategies across modules
   - Mixing sync/async patterns inconsistently
   - Creating new validation approaches when Pydantic models exist

---

## PYTHON API CLIENT IMPLEMENTATION

### 1. HTTP Client Architecture - MANDATORY STANDARD

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS use httpx for sync/async compatibility (NOT requests or aiohttp alone)
- ALWAYS use a single global client instance with connection pooling
- NEVER instantiate multiple client instances in hot loops
- ALWAYS use async context managers for client lifecycle

**Standard Pattern** (MUST follow exactly):
```python
import httpx
from typing import Optional

# Global client instance (singleton pattern)
_http_client: Optional[httpx.AsyncClient] = None

async def get_http_client() -> httpx.AsyncClient:
    """Get or create the global HTTP client instance."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            follow_redirects=True,
            http2=True  # Enable HTTP/2 for better performance
        )
    return _http_client

async def close_http_client():
    """Close the global HTTP client."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None

# Usage in API fetchers
async def fetch_data(url: str) -> dict:
    client = await get_http_client()
    response = await client.get(url)
    response.raise_for_status()
    return response.json()
```

**Client Configuration Rules**:
- Timeout: 30s total, 10s connect (NEVER infinite)
- Connection pooling: 100 max connections, 20 keepalive
- HTTP/2: ALWAYS enable for better multiplexing
- Redirects: ALWAYS follow automatically
- Headers: Set User-Agent, Accept, and API keys consistently

---

### 2. Retry Logic - UNIVERSAL STANDARD

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS use tenacity library for retry logic (NOT custom implementations)
- ALWAYS use exponential backoff with jitter (NOT fixed delays)
- ALWAYS retry ONLY transient errors (5xx, timeouts, connection errors)
- NEVER retry 4xx errors (except 429 rate limit)
- ALWAYS log retry attempts with context

**Standard Retry Decorator** (MUST be used everywhere):
```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
import httpx
import logging

logger = logging.getLogger(__name__)

# Standard retry configuration
RETRY_CONFIG = dict(
    retry=retry_if_exception_type((
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.NetworkError,
        httpx.HTTPStatusError  # Only for 5xx and 429
    )),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),  # 2s, 4s, 8s, 16s, 32s
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO)
)

@retry(**RETRY_CONFIG)
async def fetch_with_retry(url: str, **kwargs) -> httpx.Response:
    """Fetch with automatic retry logic."""
    client = await get_http_client()
    response = await client.get(url, **kwargs)

    # Only retry 5xx and 429
    if response.status_code >= 500 or response.status_code == 429:
        response.raise_for_status()

    return response
```

**Retry-After Header Handling** (MANDATORY for 429):
```python
import asyncio
from datetime import datetime, timedelta

async def fetch_with_rate_limit_respect(url: str) -> httpx.Response:
    """Fetch with respect for Retry-After headers."""
    response = await fetch_with_retry(url)

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            if retry_after.isdigit():
                # Seconds to wait
                wait_seconds = int(retry_after)
            else:
                # HTTP date format
                retry_date = datetime.strptime(retry_after, "%a, %d %b %Y %H:%M:%S GMT")
                wait_seconds = (retry_date - datetime.utcnow()).total_seconds()

            logger.warning(f"Rate limited. Waiting {wait_seconds}s before retry")
            await asyncio.sleep(wait_seconds)
            return await fetch_with_rate_limit_respect(url)  # Recursive retry

    return response
```

**STRICTLY FORBIDDEN**:
- Custom sleep/retry loops (use tenacity)
- Retrying 4xx errors (except 429)
- Fixed backoff delays (use exponential)
- Ignoring Retry-After headers
- Infinite retry attempts (max 5)

---

### 3. Error Handling - MANDATORY PATTERNS

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS define custom exception hierarchy (NEVER use generic Exception)
- ALWAYS include context in exceptions (url, status, response body)
- ALWAYS log exceptions with structured data
- NEVER swallow exceptions silently
- ALWAYS provide actionable error messages

**Standard Exception Hierarchy** (MUST be defined in `exceptions.py`):
```python
class BetBotError(Exception):
    """Base exception for all bet-bot errors."""
    pass

class APIError(BetBotError):
    """Base class for API-related errors."""
    def __init__(self, message: str, url: str, status_code: int = None, response_body: str = None):
        self.url = url
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"{message} | URL: {url} | Status: {status_code}")

class APIRateLimitError(APIError):
    """Rate limit exceeded."""
    pass

class APIAuthenticationError(APIError):
    """Authentication failed (401, 403)."""
    pass

class APINotFoundError(APIError):
    """Resource not found (404)."""
    pass

class APIServerError(APIError):
    """Server error (5xx)."""
    pass

class DataValidationError(BetBotError):
    """Data validation failed."""
    def __init__(self, field: str, value: any, reason: str):
        self.field = field
        self.value = value
        self.reason = reason
        super().__init__(f"Validation failed for {field}={value}: {reason}")

class DataStaleError(BetBotError):
    """Data is too old to use."""
    def __init__(self, data_type: str, age_minutes: int, max_age_minutes: int):
        self.data_type = data_type
        self.age_minutes = age_minutes
        self.max_age_minutes = max_age_minutes
        super().__init__(f"{data_type} data is {age_minutes}m old (max: {max_age_minutes}m)")

class ScraperError(BetBotError):
    """Web scraping failed."""
    pass

class OpenAIError(BetBotError):
    """OpenAI API error."""
    pass
```

**Error Handling Pattern** (MUST follow in all API calls):
```python
import httpx
from typing import Optional

async def safe_api_call(url: str, api_name: str) -> Optional[dict]:
    """
    Safe API call with comprehensive error handling.

    Returns None on failure (graceful degradation).
    Logs all errors with context.
    """
    try:
        response = await fetch_with_rate_limit_respect(url)
        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as e:
        status = e.response.status_code

        if status == 401 or status == 403:
            raise APIAuthenticationError(
                f"{api_name} authentication failed",
                url=url,
                status_code=status,
                response_body=e.response.text
            )
        elif status == 404:
            logger.warning(f"{api_name} resource not found: {url}")
            return None  # Graceful degradation
        elif status == 429:
            raise APIRateLimitError(
                f"{api_name} rate limit exceeded",
                url=url,
                status_code=status
            )
        elif status >= 500:
            raise APIServerError(
                f"{api_name} server error",
                url=url,
                status_code=status,
                response_body=e.response.text
            )
        else:
            raise APIError(
                f"{api_name} unexpected error",
                url=url,
                status_code=status,
                response_body=e.response.text
            )

    except httpx.TimeoutException as e:
        logger.error(f"{api_name} timeout after 30s: {url}")
        return None  # Graceful degradation

    except httpx.NetworkError as e:
        logger.error(f"{api_name} network error: {url} | {str(e)}")
        return None  # Graceful degradation

    except Exception as e:
        logger.exception(f"{api_name} unexpected error: {url}")
        return None  # Last resort graceful degradation
```

**STRICTLY FORBIDDEN**:
- Bare except clauses (`except:`)
- Raising generic Exception
- Swallowing errors without logging
- Missing context in exceptions
- Raising exceptions for expected failures (use None + logging)

---

### 4. Response Validation - MANDATORY PATTERN

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS validate response structure before processing
- ALWAYS use Pydantic models for response parsing
- ALWAYS handle missing fields gracefully
- NEVER assume API response structure
- ALWAYS validate JSON deserialization

**Standard Response Validation** (MUST use Pydantic):
```python
from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List
from datetime import datetime

class APIFootballFixture(BaseModel):
    """API-Football fixture response model."""
    fixture_id: str = Field(..., alias="fixture.id")
    kickoff_time: datetime = Field(..., alias="fixture.date")
    home_team_id: str = Field(..., alias="teams.home.id")
    home_team_name: str = Field(..., alias="teams.home.name")
    away_team_id: str = Field(..., alias="teams.away.id")
    away_team_name: str = Field(..., alias="teams.away.name")
    league_name: str = Field(..., alias="league.name")

    class Config:
        allow_population_by_field_name = True

    @validator("fixture_id", "home_team_id", "away_team_id")
    def validate_ids(cls, v):
        if not v or v.strip() == "":
            raise ValueError("ID cannot be empty")
        return str(v)

    @validator("kickoff_time")
    def validate_kickoff_future(cls, v):
        if v < datetime.utcnow():
            raise ValueError("Kickoff time must be in the future")
        return v

# Usage
async def fetch_fixtures() -> List[APIFootballFixture]:
    """Fetch and validate fixtures."""
    data = await safe_api_call(url, "API-Football")

    if data is None:
        return []

    try:
        # Parse and validate with Pydantic
        fixtures = [APIFootballFixture(**item) for item in data.get("response", [])]
        return fixtures
    except Exception as e:
        logger.error(f"Fixture validation failed: {str(e)}")
        return []
```

**JSON Deserialization Safety**:
```python
import json
from typing import Any

def safe_json_parse(text: str, default: Any = None) -> Any:
    """Safely parse JSON with fallback."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {str(e)} | Text: {text[:200]}")
        return default
```

---

## ASYNC/AWAIT PATTERNS

### 1. Concurrent Fetching - MANDATORY PATTERN

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS use asyncio.gather for parallel API calls
- ALWAYS use return_exceptions=True to prevent one failure from blocking others
- ALWAYS limit concurrency with asyncio.Semaphore
- NEVER use threading or multiprocessing for I/O-bound tasks
- ALWAYS collect results and handle failures individually

**Standard Concurrent Pattern**:
```python
import asyncio
from typing import List, Optional, Dict

async def fetch_all_fixture_data(fixture_ids: List[str]) -> Dict[str, dict]:
    """
    Fetch data for multiple fixtures concurrently.

    Uses semaphore to limit concurrent requests.
    Handles individual failures gracefully.
    """
    # Limit concurrent requests (API rate limits)
    semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests

    async def fetch_with_semaphore(fixture_id: str) -> tuple[str, Optional[dict]]:
        async with semaphore:
            data = await safe_api_call(f"/fixtures/{fixture_id}", "API-Football")
            return fixture_id, data

    # Execute all fetches concurrently
    tasks = [fetch_with_semaphore(fid) for fid in fixture_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Separate successes from failures
    fixture_data = {}
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Fetch failed: {str(result)}")
            continue

        fixture_id, data = result
        if data is not None:
            fixture_data[fixture_id] = data

    return fixture_data
```

**Parallel Data Source Fetching**:
```python
async def fetch_all_data_sources() -> dict:
    """
    Fetch from multiple data sources in parallel.

    Each source failure is independent - doesn't block others.
    """
    # Define all fetch tasks
    tasks = {
        "fixtures": safe_api_call("/fixtures", "API-Football"),
        "odds": safe_api_call("/odds", "Odds-API"),
        "form": scrape_espn_form(),
        "injuries": safe_api_call("/injuries", "API-Football"),
        "h2h": scrape_flashscore_h2h()
    }

    # Execute all in parallel
    results = await asyncio.gather(
        *tasks.values(),
        return_exceptions=True
    )

    # Map results back to source names
    data_by_source = {}
    for (source_name, _), result in zip(tasks.items(), results):
        if isinstance(result, Exception):
            logger.warning(f"{source_name} fetch failed: {str(result)}")
            data_by_source[source_name] = None
        else:
            data_by_source[source_name] = result

    return data_by_source
```

---

### 2. Async Context Managers - MANDATORY USAGE

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS use async context managers for resource cleanup
- ALWAYS define __aenter__ and __aexit__ for custom async resources
- NEVER leak HTTP connections or file handles
- ALWAYS clean up even on exceptions

**Standard Pattern**:
```python
from contextlib import asynccontextmanager
from typing import AsyncIterator

@asynccontextmanager
async def api_client_context() -> AsyncIterator[httpx.AsyncClient]:
    """Context manager for HTTP client lifecycle."""
    client = await get_http_client()
    try:
        yield client
    finally:
        # Cleanup happens automatically via global client
        pass

# Usage
async def fetch_data():
    async with api_client_context() as client:
        response = await client.get(url)
        return response.json()
```

---

### 3. Async Error Handling - MANDATORY PATTERN

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS wrap async calls in try/except
- ALWAYS use asyncio.CancelledError for graceful shutdown
- ALWAYS log async exceptions with task context
- NEVER ignore CancelledError
- ALWAYS clean up resources in finally blocks

**Standard Pattern**:
```python
async def safe_async_task(task_name: str):
    """Safe async task with proper error handling."""
    try:
        result = await some_async_operation()
        return result

    except asyncio.CancelledError:
        logger.info(f"{task_name} cancelled - cleaning up")
        # Perform cleanup
        raise  # Re-raise to propagate cancellation

    except Exception as e:
        logger.exception(f"{task_name} failed: {str(e)}")
        return None

    finally:
        # Always cleanup
        await cleanup_resources()
```

---

## THIRD-PARTY API INTEGRATION

### 1. API Key Management - MANDATORY SECURITY

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS store API keys in environment variables (NEVER in code)
- ALWAYS validate API keys exist at startup
- ALWAYS use python-dotenv for local development
- NEVER log API keys (even partially)
- ALWAYS use different keys for dev/staging/prod

**Standard Pattern** (MUST be in `config.py`):
```python
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Application configuration from environment variables."""

    # API Keys (REQUIRED)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    API_FOOTBALL_KEY: str = os.getenv("API_FOOTBALL_KEY", "")
    ODDS_API_KEY: str = os.getenv("ODDS_API_KEY", "")

    # Validation
    @classmethod
    def validate(cls):
        """Validate required config exists."""
        required = {
            "OPENAI_API_KEY": cls.OPENAI_API_KEY,
            "API_FOOTBALL_KEY": cls.API_FOOTBALL_KEY
        }

        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    # Masked logging (for debugging)
    @classmethod
    def get_masked_key(cls, key: str) -> str:
        """Return masked version of API key for logging."""
        if not key or len(key) < 8:
            return "****"
        return f"{key[:4]}...{key[-4:]}"

# Validate on import
Config.validate()
```

**Environment File** (`.env` example):
```bash
# OpenAI
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# API-Football
API_FOOTBALL_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Odds API (optional)
ODDS_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Logging
LOG_LEVEL=INFO
```

**STRICTLY FORBIDDEN**:
- Hardcoded API keys in source code
- Committing .env files to git
- Logging full API keys
- Using same keys across environments

---

### 2. Rate Limiting - CLIENT-SIDE ENFORCEMENT

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS implement client-side rate limiting (don't rely on API 429)
- ALWAYS use token bucket algorithm for rate limiting
- ALWAYS respect API rate limit headers
- NEVER exceed documented API limits
- ALWAYS implement per-API rate limiters

**Standard Rate Limiter** (MUST be used for all APIs):
```python
import asyncio
import time
from collections import deque
from typing import Deque

class RateLimiter:
    """
    Token bucket rate limiter for API calls.

    Prevents exceeding API rate limits by enforcing delays.
    """

    def __init__(self, max_requests: int, time_window: int):
        """
        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Acquire permission to make a request (blocks if rate limit reached)."""
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
                    logger.info(f"Rate limit reached. Waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    # Recursive call after wait
                    return await self.acquire()

            # Record this request
            self.requests.append(now)

# Per-API rate limiters
api_football_limiter = RateLimiter(max_requests=100, time_window=60)  # 100/min
openai_limiter = RateLimiter(max_requests=500, time_window=60)  # 500/min
odds_api_limiter = RateLimiter(max_requests=50, time_window=60)  # 50/min

# Usage
async def fetch_api_football(url: str) -> dict:
    """Fetch from API-Football with rate limiting."""
    await api_football_limiter.acquire()  # Wait if needed
    return await safe_api_call(url, "API-Football")
```

---

### 3. Authentication - MANDATORY PATTERNS

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS send API keys in headers (NOT query params)
- ALWAYS use HTTPS (reject HTTP)
- ALWAYS implement exponential backoff for auth failures
- NEVER retry 401/403 more than once without intervention
- ALWAYS validate auth on startup

**Standard Auth Pattern**:
```python
from typing import Dict

def get_api_headers(api_name: str) -> Dict[str, str]:
    """Get authentication headers for API."""
    headers = {
        "User-Agent": "bet-bot/1.0",
        "Accept": "application/json"
    }

    if api_name == "API-Football":
        headers["x-rapidapi-key"] = Config.API_FOOTBALL_KEY
        headers["x-rapidapi-host"] = "api-football-v1.p.rapidapi.com"

    elif api_name == "OpenAI":
        headers["Authorization"] = f"Bearer {Config.OPENAI_API_KEY}"

    elif api_name == "Odds-API":
        # Odds API uses query param (exception)
        pass

    return headers

# Test auth on startup
async def validate_api_auth():
    """Validate all API authentications on startup."""
    validations = []

    # API-Football test
    try:
        response = await safe_api_call(
            "https://api-football-v1.p.rapidapi.com/v3/status",
            "API-Football"
        )
        if response:
            validations.append(("API-Football", True))
        else:
            validations.append(("API-Football", False))
    except APIAuthenticationError:
        validations.append(("API-Football", False))

    # Report
    for api, valid in validations:
        if not valid:
            raise APIAuthenticationError(f"{api} authentication failed on startup", url="", status_code=401)
        logger.info(f"{api} authentication validated")
```

---

### 4. Data Freshness Validation - MANDATORY

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS validate data age against requirements
- ALWAYS reject odds >1h old
- ALWAYS reject injuries >12h old
- ALWAYS reject form >24h old
- ALWAYS include timestamps in API responses

**Standard Freshness Validation**:
```python
from datetime import datetime, timedelta
from typing import Optional

class DataFreshnessValidator:
    """Validates data freshness against requirements."""

    # Freshness requirements (from data dictionary)
    ODDS_MAX_AGE_MINUTES = 60
    INJURIES_MAX_AGE_HOURS = 12
    FORM_MAX_AGE_HOURS = 24

    @classmethod
    def validate_odds_freshness(cls, odds_timestamp: datetime) -> bool:
        """Validate odds are fresh enough."""
        age = datetime.utcnow() - odds_timestamp
        max_age = timedelta(minutes=cls.ODDS_MAX_AGE_MINUTES)

        if age > max_age:
            age_minutes = age.total_seconds() / 60
            raise DataStaleError(
                "odds",
                age_minutes=int(age_minutes),
                max_age_minutes=cls.ODDS_MAX_AGE_MINUTES
            )

        return True

    @classmethod
    def validate_injury_freshness(cls, injury_timestamp: datetime) -> bool:
        """Validate injury data is fresh enough."""
        age = datetime.utcnow() - injury_timestamp
        max_age = timedelta(hours=cls.INJURIES_MAX_AGE_HOURS)

        if age > max_age:
            age_hours = age.total_seconds() / 3600
            logger.warning(f"Injury data {age_hours:.1f}h old (max: {cls.INJURIES_MAX_AGE_HOURS}h)")
            return False  # Warning, not error

        return True

    @classmethod
    def calculate_confidence_penalty(cls, timestamp: datetime, data_type: str) -> int:
        """Calculate confidence penalty for data age."""
        age = datetime.utcnow() - timestamp

        if data_type == "form":
            if age < timedelta(hours=24):
                return 0
            elif age < timedelta(hours=48):
                return -10
            else:
                return -20

        elif data_type == "odds":
            age_minutes = age.total_seconds() / 60
            if age_minutes < 30:
                return 0
            elif age_minutes < 60:
                return -5
            else:
                return -10  # Reject

        return 0
```

---

## CLI SCRIPT DEVELOPMENT

### 1. Typer CLI Structure - MANDATORY PATTERN

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS use Typer for CLI (NOT argparse)
- ALWAYS use type hints for arguments
- ALWAYS provide help text for all commands
- ALWAYS validate inputs at CLI boundary
- ALWAYS use rich for beautiful output

**Standard CLI Pattern** (MUST be in `cli/main.py`):
```python
import typer
from typing import Optional
from rich.console import Console
from rich.progress import Progress
import asyncio

app = typer.Typer(
    name="bet-bot",
    help="Positive Expected Value Detection Tool for Football Betting",
    add_completion=False
)
console = Console()

@app.command()
def analyze(
    bankroll: float = typer.Option(
        ...,
        "--bankroll",
        "-b",
        help="Your betting bankroll in USD",
        min=0
    ),
    league: Optional[str] = typer.Option(
        None,
        "--league",
        "-l",
        help="Filter by league (e.g., 'Championship')"
    ),
    threshold: float = typer.Option(
        5.0,
        "--threshold",
        "-t",
        help="Minimum EV threshold percentage (default: 5.0)",
        min=0.0,
        max=100.0
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging"
    )
):
    """
    Analyze today's fixtures and find positive EV betting opportunities.

    Example:
        bet-bot analyze --bankroll 1000 --threshold 5.0
    """
    # Validate inputs
    if bankroll <= 0:
        console.print("[red]Error: Bankroll must be positive[/red]")
        raise typer.Exit(1)

    # Configure logging
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(log_level)

    # Run async analysis
    try:
        asyncio.run(run_analysis(bankroll, league, threshold))
    except KeyboardInterrupt:
        console.print("\n[yellow]Analysis cancelled by user[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        logger.exception("Analysis failed")
        raise typer.Exit(1)

@app.command()
def config():
    """View and update configuration."""
    console.print("[cyan]bet-bot Configuration[/cyan]")
    console.print(f"OpenAI API Key: {Config.get_masked_key(Config.OPENAI_API_KEY)}")
    console.print(f"API-Football Key: {Config.get_masked_key(Config.API_FOOTBALL_KEY)}")

if __name__ == "__main__":
    app()
```

---

### 2. Logging Configuration - MANDATORY STANDARD

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS use structured logging (JSON format)
- ALWAYS log to file AND console
- ALWAYS include context (timestamps, levels, module)
- NEVER use print() for logging
- ALWAYS rotate log files

**Standard Logging Setup** (MUST be in `utils/logging.py`):
```python
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime

def setup_logging(level: str = "INFO"):
    """
    Configure application logging.

    Logs to:
    - Console (formatted for humans)
    - File (JSON structured logs, rotated)
    """
    log_dir = Path.home() / ".bet-bot" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Console handler (human-readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)

    # File handler (JSON structured)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)  # Always DEBUG to file
    file_formatter = logging.Formatter(
        fmt='{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%SZ"
    )
    file_handler.setFormatter(file_formatter)

    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Suppress noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.INFO)

# Usage
logger = logging.getLogger(__name__)
logger.info("Application started")
logger.debug("Debug info", extra={"user_id": 123, "action": "fetch"})
```

---

### 3. Input Validation - MANDATORY WITH PYDANTIC

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS validate CLI inputs with Pydantic
- ALWAYS validate environment variables with Pydantic
- ALWAYS provide clear validation error messages
- NEVER trust user input
- ALWAYS sanitize file paths

**Standard Validation Pattern**:
```python
from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional
from pathlib import Path

class AnalysisConfig(BaseModel):
    """Configuration for analysis run (validated)."""

    bankroll: float = Field(..., gt=0, description="Betting bankroll")
    threshold: float = Field(5.0, ge=0, le=100, description="EV threshold %")
    league: Optional[str] = Field(None, description="League filter")
    verbose: bool = Field(False, description="Verbose logging")

    @validator("bankroll")
    def validate_bankroll_reasonable(cls, v):
        if v > 1_000_000:
            raise ValueError("Bankroll >$1M seems unrealistic")
        return v

    @validator("league")
    def validate_league_format(cls, v):
        if v and len(v) < 3:
            raise ValueError("League name too short")
        return v

# Usage
def parse_cli_args(bankroll: float, threshold: float, league: str, verbose: bool) -> AnalysisConfig:
    """Parse and validate CLI arguments."""
    try:
        config = AnalysisConfig(
            bankroll=bankroll,
            threshold=threshold,
            league=league,
            verbose=verbose
        )
        return config
    except Exception as e:
        logger.error(f"Invalid arguments: {str(e)}")
        raise typer.Exit(1)
```

---

## SECURITY & AUTHENTICATION

### 1. Secrets Management - MANDATORY

**CRITICAL (ZERO TOLERANCE)**:
- NEVER hardcode secrets
- ALWAYS use environment variables
- ALWAYS validate secrets exist at startup
- NEVER log secrets (even masked)
- ALWAYS use .gitignore for .env files

**.gitignore** (MUST include):
```
# Environment variables
.env
.env.local
.env.*.local

# Logs
logs/
*.log

# API keys
*.key
secrets/
```

---

### 2. Input Sanitization - MANDATORY

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS sanitize user inputs (CLI, env vars)
- ALWAYS validate file paths (prevent directory traversal)
- ALWAYS escape shell commands (use subprocess with list args)
- NEVER use eval() or exec() on user input
- ALWAYS use parameterized queries (if using SQL)

**Standard Sanitization**:
```python
import re
from pathlib import Path

def sanitize_file_path(path: str) -> Path:
    """Sanitize file path to prevent directory traversal."""
    # Resolve to absolute path
    path_obj = Path(path).resolve()

    # Ensure it's within allowed directory
    allowed_base = Path.home() / ".bet-bot"
    if not str(path_obj).startswith(str(allowed_base)):
        raise ValueError(f"Path outside allowed directory: {path}")

    return path_obj

def sanitize_league_name(name: str) -> str:
    """Sanitize league name for API calls."""
    # Allow only alphanumeric, spaces, hyphens
    if not re.match(r'^[\w\s\-]+$', name):
        raise ValueError(f"Invalid league name: {name}")
    return name.strip()
```

---

### 3. Safe Deserialization - MANDATORY

**CRITICAL (ZERO TOLERANCE)**:
- NEVER use pickle for untrusted data
- ALWAYS use JSON for data interchange
- ALWAYS validate JSON schema with Pydantic
- NEVER deserialize without validation
- ALWAYS use safe YAML loaders (SafeLoader)

**Standard Deserialization**:
```python
import json
from typing import Any
from pydantic import ValidationError

def safe_deserialize(data: str, model_class: type) -> Any:
    """
    Safely deserialize JSON to Pydantic model.

    Validates schema and prevents code injection.
    """
    try:
        # Parse JSON
        raw_data = json.loads(data)

        # Validate with Pydantic
        validated = model_class(**raw_data)
        return validated

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {str(e)}")
        raise DataValidationError("json", data[:100], "Invalid JSON format")

    except ValidationError as e:
        logger.error(f"Schema validation failed: {str(e)}")
        raise DataValidationError("schema", data[:100], str(e))

# NEVER do this
import pickle
data = pickle.loads(untrusted_data)  # FORBIDDEN - CODE INJECTION RISK
```

---

## ANTI-PATTERNS TO AVOID

### STRICTLY FORBIDDEN - ZERO TOLERANCE

1. **API Client Anti-Patterns**:
   - Creating multiple HTTP client instances (use singleton)
   - Not closing HTTP clients (connection leaks)
   - Retrying 4xx errors (except 429)
   - Ignoring Retry-After headers
   - Using requests library (use httpx for async)

2. **Async Anti-Patterns**:
   - Mixing sync and async code inconsistently
   - Not using asyncio.gather for parallel calls
   - Blocking the event loop with time.sleep() (use asyncio.sleep)
   - Not handling CancelledError
   - Creating tasks without awaiting them

3. **Error Handling Anti-Patterns**:
   - Bare except clauses
   - Swallowing exceptions silently
   - Raising generic Exception
   - Not logging errors with context
   - Retrying forever without backoff

4. **Security Anti-Patterns**:
   - Hardcoded API keys
   - Logging secrets
   - Using pickle for deserialization
   - Not validating user input
   - Using eval/exec on user data

5. **Data Validation Anti-Patterns**:
   - Assuming API response structure
   - Not validating data freshness
   - Trusting external data without validation
   - Not using Pydantic models
   - Missing error handling in validation

6. **CLI Anti-Patterns**:
   - Using print() instead of logging
   - Not validating CLI arguments
   - Missing help text
   - Not handling KeyboardInterrupt
   - Exposing stack traces to users

---

## PYTHON 3.14+ DEPRECATION AVOIDANCE

**Project Target**: Python 3.14+ compatibility (ZERO deprecation warnings)

### 1. Datetime Handling - CRITICAL CHANGES

**CRITICAL (ZERO TOLERANCE)**:
- NEVER use `datetime.utcnow()` - DEPRECATED in 3.12, REMOVED in 3.14
- NEVER use `datetime.now()` without timezone for UTC
- ALWAYS use `datetime.now(timezone.utc)` for UTC time
- ALWAYS include `timezone.utc` when working with UTC
- NEVER use naive datetimes for comparisons with aware datetimes

**DEPRECATED (Python 3.12+)**:
```python
# FORBIDDEN - REMOVED in Python 3.14
from datetime import datetime
utc_now = datetime.utcnow()  # ❌ DEPRECATED

# WRONG - Naive datetime
now = datetime.now()  # ❌ WRONG - no timezone info
```

**CORRECT (Python 3.14+)**:
```python
from datetime import datetime, timezone

# Always use timezone-aware UTC
utc_now = datetime.now(timezone.utc)  # ✓ CORRECT

# For comparisons
age = datetime.now(timezone.utc) - some_datetime  # ✓ CORRECT

# Safe timezone handling
timestamp = datetime.fromisoformat(iso_string)  # ✓ Returns aware datetime
if timestamp.tzinfo is None:
    timestamp = timestamp.replace(tzinfo=timezone.utc)  # Make aware if naive
```

**Code Pattern Migration**:
```python
# OLD (Python 3.10-3.12)
from datetime import datetime
delta = datetime.utcnow() - some_datetime

# NEW (Python 3.13+)
from datetime import datetime, timezone
delta = datetime.now(timezone.utc) - some_datetime.replace(tzinfo=timezone.utc)
```

---

### 2. Type Hints - MODERN SYNTAX ONLY

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS use `dict[str, str]` NOT `Dict[str, str]` (PEP 585)
- ALWAYS use `list[X]` NOT `List[X]` (PEP 585)
- ALWAYS use `tuple[X, ...]` NOT `Tuple[X, ...]` (PEP 585)
- ALWAYS use `X | None` NOT `Optional[X]` (PEP 604)
- ALWAYS use `X | Y` NOT `Union[X, Y]` (PEP 604)
- NEVER import from `typing` for built-in types (dict, list, tuple, set, frozenset)
- ONLY import from `typing` for: `Any`, `TypeVar`, `Generic`, `Protocol`, `Callable`

**DEPRECATED (Python 3.9-3.13)**:
```python
from typing import Dict, List, Optional, Union

# FORBIDDEN - old style type hints
def process(data: Dict[str, str]) -> List[int]:
    items: Optional[str] = None
    value: Union[str, int] = "test"
```

**CORRECT (Python 3.14+)**:
```python
# NO imports needed for built-in types
def process(data: dict[str, str]) -> list[int]:
    items: str | None = None
    value: str | int = "test"

# Modern imports (only when needed)
from typing import Any, TypeVar, Callable

T = TypeVar("T")

def generic_func(callback: Callable[[str], Any]) -> T:
    pass
```

**Type Hints Pattern Guide**:
```python
from typing import Any, Callable, TypeVar
from collections.abc import Sequence, Mapping, Iterator

# ✓ CORRECT - Use built-in generics
def fetch_data(
    urls: list[str],
    params: dict[str, str | int],
    timeout: int | None = None
) -> dict[str, Any]:
    pass

# ✓ CORRECT - Use collections.abc for abstract types
def process_items(items: Sequence[str]) -> Iterator[str]:
    pass

# ✓ CORRECT - Union syntax for multiple types
def parse_value(value: str | int | float) -> str:
    return str(value)

# ✓ CORRECT - Callable for functions
def apply_operation(
    values: list[int],
    operation: Callable[[int], int]
) -> list[int]:
    return [operation(v) for v in values]
```

---

### 3. String Formatting - CONSISTENT STYLE

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS use f-strings (NOT % formatting or .format())
- ALWAYS use raw f-strings for regex patterns: `rf"pattern"`
- NEVER use implicit string concatenation across lines without backslash
- ALWAYS use explicit line continuation

**DEPRECATED (Pre-Python 3.6)**:
```python
# FORBIDDEN - old string formatting
msg = "Error: %s code: %d" % (error, code)  # ❌
msg = "Error: {} code: {}".format(error, code)  # ❌
```

**CORRECT (Python 3.6+)**:
```python
# ✓ CORRECT - f-strings
msg = f"Error: {error} code: {code}"

# ✓ CORRECT - regex with raw f-strings
pattern = rf"^{team_name}\s+\d+"

# ✓ CORRECT - multi-line strings with f-strings
error_msg = (
    f"Failed to fetch data for {fixture_id}. "
    f"Status: {status_code}. "
    f"Body: {response_body[:200]}"
)
```

---

### 4. Async/Await - STRICT PATTERNS

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS use `asyncio.Runner()` for top-level async in Python 3.11+ (replaces `asyncio.run()`)
- ALWAYS use `async with` for context managers (NOT `await`)
- NEVER use `asyncio.get_event_loop().run_until_complete()`
- ALWAYS handle `asyncio.CancelledError` explicitly
- NEVER use `loop.run_forever()` in new code

**DEPRECATED (Python 3.10+)**:
```python
# CONDITIONAL - asyncio.run() still works but avoid
import asyncio
asyncio.run(main())  # Works but deprecated pattern
```

**CORRECT (Python 3.11+)**:
```python
import asyncio

async def main():
    await fetch_data()

# ✓ Modern style (Python 3.11+)
if __name__ == "__main__":
    with asyncio.Runner() as runner:
        runner.run(main())

# Fallback for older Python 3.10
# (keep for compatibility, but mark for removal when 3.14 becomes baseline)
try:
    asyncio.run(main())
except AttributeError:
    # Python 3.10 fallback
    asyncio.get_event_loop().run_until_complete(main())
```

**Async Context Managers**:
```python
# ✓ CORRECT - async with for async context managers
async with httpx.AsyncClient() as client:
    response = await client.get(url)

# ❌ FORBIDDEN - don't await context managers
# await httpx.AsyncClient()  # WRONG
```

---

### 5. Pydantic - V2 SYNTAX ONLY

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS use Pydantic v2 syntax (NOT v1)
- NEVER use `@validator` decorator (use `field_validator` in v2)
- NEVER use `@root_validator` (use `model_validator` in v2)
- ALWAYS use `ConfigDict` instead of `Config` class
- NEVER use `allow_population_by_field_name` (use `populate_by_name` in v2)
- ALWAYS use `field_validator` with `mode="before"` or `mode="after"`

**DEPRECATED (Pydantic v1 - MUST UPGRADE)**:
```python
from pydantic import BaseModel, validator, root_validator

class MyModel(BaseModel):
    value: str

    class Config:
        allow_population_by_field_name = True

    @validator("value")
    def validate_value(cls, v):
        return v.upper()

    @root_validator
    def validate_root(cls, values):
        return values
```

**CORRECT (Pydantic v2)**:
```python
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

class MyModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    value: str

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def validate_model(self) -> "MyModel":
        # Post-validation logic
        return self
```

**Pydantic v2 Pattern for Nested Fields**:
```python
from pydantic import BaseModel, Field

class Team(BaseModel):
    team_id: str = Field(..., alias="id")
    team_name: str = Field(..., alias="name")

class Fixture(BaseModel):
    fixture_id: str = Field(..., alias="fixture.id")
    home_team: Team = Field(..., alias="teams.home")

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True
    )
```

---

### 6. Module Imports - AVOID DEPRECATED MODULES

**CRITICAL (ZERO TOLERANCE)**:
- NEVER import from `distutils` (REMOVED in 3.12, scheduled removal)
- NEVER use `asyncore` or `asynchat` (REMOVED in 3.12)
- NEVER use `smtpd` (REMOVED in 3.12)
- NEVER use `imp` (REMOVED in 3.12)
- ALWAYS use `importlib` for dynamic imports
- ALWAYS use `packaging` for version comparisons (NOT home-grown code)

**DEPRECATED (Removed in Python 3.12+)**:
```python
# FORBIDDEN - removed modules
from distutils.version import LooseVersion  # ❌
import smtpd  # ❌
import imp  # ❌
```

**CORRECT (Python 3.14+)**:
```python
from importlib import import_module, resources
from packaging import version

# ✓ Dynamic imports
module = import_module("module.name")

# ✓ Version comparison
v1 = version.parse("1.0.0")
v2 = version.parse("2.0.0")
if v1 < v2:
    pass
```

---

### 7. Regex - STRICT PATTERNS

**CRITICAL (ZERO TOLERANCE)**:
- ALWAYS use raw f-strings for regex patterns: `rf"..."`
- NEVER use regex string without escaping special chars properly
- ALWAYS compile regexes that are used multiple times
- NEVER ignore `re.escape()` for user input patterns

**CORRECT PATTERN**:
```python
import re

# ✓ Compiled regex for reuse
PATTERN = re.compile(rf"^{re.escape('team_name')}\s+(\d+)$")

# ✓ Raw f-string for patterns
def validate_id(team_name: str) -> bool:
    pattern = rf"^{re.escape(team_name)}\s+\d+$"
    return bool(re.match(pattern, "test"))
```

---

### 8. Exception Handling - STRICT PATTERNS

**CRITICAL (ZERO TOLERANCE)**:
- NEVER use bare `except:` clause
- NEVER use `except Exception:` as catch-all (be specific)
- ALWAYS use exception chaining with `from e`
- ALWAYS use modern exception groups in Python 3.11+ (ExceptionGroup)
- NEVER swallow exceptions without logging

**CORRECT PATTERN**:
```python
import asyncio

try:
    result = await fetch_data()
except httpx.TimeoutException as e:
    logger.error(f"Timeout: {str(e)}")
    raise APIError("Request timeout") from e

except asyncio.CancelledError:
    # Always re-raise cancellation
    logger.info("Task cancelled")
    raise

except (ValueError, KeyError) as e:
    logger.exception("Data error")
    return None
```

---

### 9. Performance Deprecations

**CRITICAL (ZERO TOLERANCE)**:
- NEVER use direct socket programming for HTTP (use httpx)
- NEVER use threading for I/O (use asyncio)
- NEVER use `time.time()` for durations (use `time.monotonic()`)
- ALWAYS use `asyncio.TaskGroup()` in Python 3.11+ (replaces manual gathering)

**CORRECT PATTERN (Python 3.11+)**:
```python
import asyncio

async def fetch_multiple():
    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(fetch_data1())
        task2 = tg.create_task(fetch_data2())
    # Tasks complete automatically, exceptions propagated
    return task1.result(), task2.result()

# Fallback for Python 3.10
async def fetch_multiple_legacy():
    results = await asyncio.gather(
        fetch_data1(),
        fetch_data2(),
        return_exceptions=True
    )
    return results
```

---

## ENFORCEMENT CHECKLIST

Before committing ANY code, verify:

- [ ] Did you search for existing patterns first?
- [ ] Are you using httpx (NOT requests) for HTTP?
- [ ] Are you using tenacity for retry logic?
- [ ] Are all API keys in environment variables?
- [ ] Are all responses validated with Pydantic v2?
- [ ] Are all async calls using proper error handling?
- [ ] Are you using asyncio.gather for parallel calls?
- [ ] Are all exceptions properly typed (not generic)?
- [ ] Are all logs using logger (NOT print)?
- [ ] Are all CLI arguments validated?
- [ ] Is rate limiting implemented for all APIs?
- [ ] Are Retry-After headers respected?
- [ ] Are connections properly closed?
- [ ] Is data freshness validated?
- [ ] Are secrets never logged?
- [ ] **NO `datetime.utcnow()` - use `datetime.now(timezone.utc)`**
- [ ] **NO old-style type hints - use `list[X]` and `X | None`**
- [ ] **NO `@validator` - use `@field_validator` (Pydantic v2)**
- [ ] **NO bare except clauses - be specific with exceptions**
- [ ] **NO deprecated modules (distutils, asyncore, imp, etc.)**
- [ ] **Using f-strings for all string formatting**
- [ ] **All async code uses proper context managers**

---

_This document defines the ZERO-TOLERANCE rules for bet-bot Python development. Every violation must be corrected immediately. Consistency is non-negotiable. Python 3.14+ compatibility is MANDATORY._
