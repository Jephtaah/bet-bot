"""
OpenAI API client for bet-bot application.

This module implements the AI analysis layer for OpenAI GPT-4 (or GPT-3.5-turbo)
integration. It handles client initialization, API calls, retry logic, rate limiting,
and graceful error handling for fixture analysis.

Features:
- Async OpenAI client with singleton pattern
- Automatic retry logic with exponential backoff (tenacity)
- Client-side rate limiting with token bucket algorithm
- Token cost tracking and budget monitoring
- Timeout enforcement (30s per fixture)
- Graceful degradation (mark failed fixtures, continue processing)
- Comprehensive structured logging

Architecture:
- analyze_fixture(): Analyze single fixture (main entry point)
- analyze_all_fixtures(): Batch orchestrator for multiple fixtures
- _parse_openai_response(): Parse JSON response to MarketAnalysis models
- _attach_analysis_to_fixture(): Augment fixture with AI analysis
- _estimate_token_cost(): Calculate cost for monitoring budget
- RateLimiter: Token bucket rate limiter

Integration:
- Receives fixtures from Story 3.3 (with quality_score)
- Calls Story 4.1 export_prompt_for_api() for structured prompt
- Outputs fixtures with ai_analysis field populated
- Feeds into Story 5.1 EV calculation pipeline

Usage:
    from bet_bot.analysis.ai import analyze_fixture, analyze_all_fixtures

    # Single fixture
    fixture_with_analysis = await analyze_fixture(fixture)

    # Batch
    fixtures_with_analysis = await analyze_all_fixtures(fixtures)
"""

import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI
from pydantic import ValidationError
from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bet_bot.analysis.ai.prompt_builder import export_prompt_for_api
from bet_bot.config import config
from bet_bot.exceptions import (
    APIAuthenticationError,
    APIRateLimitError,
    APIServerError,
    OpenAIError,
)
from bet_bot.models import AIAnalysis, Fixture, MarketAnalysis

# Module-level logger
logger = logging.getLogger(__name__)

# Global OpenAI client instance (singleton)
_openai_client: AsyncOpenAI | None = None

# Token cost tracking (cumulative per run)
_total_tokens_used = 0
_total_cost = 0.0

# GPT-3.5-turbo pricing (per 1M tokens)
GPT_35_INPUT_COST = 0.50
GPT_35_OUTPUT_COST = 1.50


class RateLimiter:
    """
    Token bucket rate limiter for OpenAI API calls.

    Implements sliding window algorithm to enforce rate limits
    without relying on server 429 responses. Prevents exceeding
    API rate limits by blocking requests until quota is available.

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

        Example:
            >>> limiter = RateLimiter(max_requests=500, time_window=60)
            >>> await limiter.acquire()  # Blocks if at limit
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquire permission to make a request.

        Blocks if rate limit is reached until time window allows new requests.
        Uses a sliding window algorithm tracking request timestamps.

        This method is idempotent - can be called multiple times safely.
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
                        f"Rate limit reached. Waiting {wait_time:.1f}s "
                        f"({len(self.requests)}/{self.max_requests} requests in window)"
                    )
                    await asyncio.sleep(wait_time)
                    # Recursive call after wait
                    return await self.acquire()

            # Record this request
            self.requests.append(now)


# OpenAI rate limiter (500 requests/minute for free tier)
openai_limiter = RateLimiter(max_requests=500, time_window=60)


async def get_openai_client() -> AsyncOpenAI:
    """
    Get or create the global OpenAI client instance.

    Uses singleton pattern to reuse client across all fixture analysis.
    Client is configured with:
    - API key from config
    - Timeout: 30s (handled separately in analyze_fixture)
    - Organization ID if available

    Returns:
        Configured AsyncOpenAI client instance

    Raises:
        ValueError: If OPENAI_API_KEY is not configured
        APIAuthenticationError: If API key is invalid

    Example:
        >>> client = await get_openai_client()
        >>> response = await client.chat.completions.create(...)
    """
    global _openai_client

    if _openai_client is None:
        # Validate API key exists
        if not config or not config.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY not configured. "
                "Please set it in your .env file."
            )

        try:
            _openai_client = AsyncOpenAI(
                api_key=config.openai_api_key,
                timeout=30.0,  # 30s timeout for all requests
            )
            logger.debug("Created new OpenAI client instance")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            raise APIAuthenticationError(
                "OpenAI client initialization failed",
                url="https://api.openai.com/v1/chat/completions",
                status_code=None,
                response_body=str(e)
            ) from e

    return _openai_client


async def close_openai_client() -> None:
    """
    Close the global OpenAI client.

    Should be called on application shutdown to ensure proper cleanup.
    """
    global _openai_client

    if _openai_client is not None:
        await _openai_client.close()
        _openai_client = None
        logger.debug("Closed OpenAI client instance")


def _estimate_token_cost(input_tokens: int, output_tokens: int) -> dict[str, float]:
    """
    Estimate cost for OpenAI API call.

    Calculates cost based on GPT-3.5-turbo pricing:
    - Input: $0.50 per 1M tokens
    - Output: $1.50 per 1M tokens

    This is used for monitoring budget and warning when approaching limits.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Dict with keys: input_cost, output_cost, total_cost (all in USD)

    Example:
        >>> cost_info = _estimate_token_cost(500, 200)
        >>> print(f"Cost: ${cost_info['total_cost']:.4f}")
    """
    input_cost = (input_tokens * GPT_35_INPUT_COST) / 1_000_000
    output_cost = (output_tokens * GPT_35_OUTPUT_COST) / 1_000_000
    total_cost = input_cost + output_cost

    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost
    }


def _parse_openai_response(response_text: str) -> list[MarketAnalysis]:
    """
    Parse OpenAI response and convert to MarketAnalysis models.

    Extracts JSON from response, validates structure, and converts
    each market to a MarketAnalysis Pydantic model.

    Response format expected (from prompt_builder):
    {
        "markets": [
            {
                "market_type": "match_result",
                "probabilities": {"home": 0.58, "draw": 0.25, "away": 0.17},
                "reasoning": "..."
            },
            ...
        ]
    }

    Args:
        response_text: Raw response from OpenAI API

    Returns:
        List of MarketAnalysis objects (empty if parsing fails)

    Side Effects:
        Logs validation failures at WARNING level (doesn't raise)
    """
    try:
        # Parse JSON response
        response_data = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI response as JSON: {str(e)} | Response: {response_text[:200]}")
        return []

    # Extract markets array
    markets_data = response_data.get("markets", [])
    if not isinstance(markets_data, list):
        logger.warning(f"Markets field is not a list: {type(markets_data)}")
        return []

    markets = []
    for idx, market_data in enumerate(markets_data):
        try:
            # Extract fields from market data
            market_type = market_data.get("market_type", "unknown")
            probabilities = market_data.get("probabilities", {})
            reasoning = market_data.get("reasoning", "No reasoning provided")

            # Calculate confidence from probabilities (0-100)
            # Use max probability as confidence (market clarity)
            max_prob = max(probabilities.values()) if probabilities else 0.5
            confidence = int(max_prob * 100)

            # Validate probabilities are in [0.0, 1.0]
            for outcome, prob in probabilities.items():
                if not isinstance(prob, (int, float)):
                    logger.warning(
                        f"Invalid probability type for {market_type}/{outcome}: {type(prob)}"
                    )
                    prob = 0.5

                # Clip to valid range
                if prob < 0.0 or prob > 1.0:
                    logger.warning(
                        f"Probability out of range for {market_type}/{outcome}: {prob}, clipping"
                    )
                    prob = max(0.0, min(1.0, prob))

            # Validate probability sum for multi-outcome markets
            if probabilities:
                prob_sum = sum(probabilities.values())
                expected_sum = len(probabilities)  # Should sum to ~1.0 per outcome

                if abs(prob_sum - 1.0) > 0.1:  # More than 10% off
                    logger.warning(
                        f"Probability sum mismatch for {market_type}: {prob_sum:.2f} (expected ~1.0)"
                    )

            # Create MarketAnalysis with highest probability outcome
            if probabilities:
                highest_prob = max(probabilities.values())
                market = MarketAnalysis(
                    market_type=market_type,
                    ai_probability=highest_prob,
                    reasoning=reasoning.strip() if reasoning else "No reasoning provided",
                    confidence=confidence
                )
                markets.append(market)
            else:
                logger.warning(f"Market {idx} has no probabilities data")

        except Exception as e:
            logger.warning(f"Failed to parse market {idx}: {str(e)}")
            continue

    if not markets:
        logger.error("No valid markets parsed from OpenAI response")

    return markets


def _attach_analysis_to_fixture(
    fixture: Fixture,
    markets: list[MarketAnalysis]
) -> Fixture:
    """
    Attach AI analysis to fixture object.

    Creates AIAnalysis model with market data and attaches to fixture.
    Adds metadata (analysis_timestamp, model_used) for tracking.

    Args:
        fixture: The fixture to augment
        markets: List of MarketAnalysis objects from OpenAI response

    Returns:
        Augmented fixture with ai_analysis field populated

    Example:
        >>> markets = _parse_openai_response(response)
        >>> fixture = _attach_analysis_to_fixture(fixture, markets)
    """
    if not fixture or not fixture.fixture_id:
        logger.warning("Cannot attach analysis to invalid fixture")
        return fixture

    try:
        # Create AIAnalysis object
        analysis = AIAnalysis(
            fixture_id=fixture.fixture_id,
            markets=markets,
            analysis_timestamp=datetime.now(timezone.utc)
        )

        # Attach to fixture
        fixture.ai_analysis = analysis

        logger.debug(
            f"Attached AI analysis to fixture {fixture.fixture_id}: "
            f"{len(markets)} markets analyzed"
        )

        return fixture

    except ValidationError as e:
        logger.error(
            f"Failed to create AIAnalysis for fixture {fixture.fixture_id}: {str(e)}"
        )
        return fixture


@retry(
    retry=retry_if_exception_type((
        TimeoutError,
        asyncio.TimeoutError,
        OSError,
    )),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO),
    reraise=False
)
async def _call_openai_with_retry(
    client: AsyncOpenAI,
    system_prompt: str,
    user_message: str,
    fixture_id: str
) -> str | None:
    """
    Call OpenAI API with retry logic and timeout.

    Internal helper for analyze_fixture. Handles:
    - Rate limiting (waits if needed)
    - Timeouts (30s per fixture)
    - Retry logic (max 3 attempts on transient errors)
    - Error logging with context

    Args:
        client: OpenAI async client
        system_prompt: System prompt from Story 4.1
        user_message: User message from Story 4.1
        fixture_id: Fixture ID for logging context

    Returns:
        Response JSON string or None if failed

    Raises:
        (Internally caught and logged, never propagates)
    """
    try:
        # Wait if rate limited
        await openai_limiter.acquire()

        # Call OpenAI with timeout
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=config.openai_model if config else "gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.7,
                    max_tokens=1000,
                    response_format={"type": "json_object"}
                ),
                timeout=30.0
            )

            # Extract response content
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
            else:
                logger.error(f"Empty response from OpenAI for fixture {fixture_id}")
                return None

        except asyncio.TimeoutError:
            logger.error(f"OpenAI API timeout for fixture {fixture_id} (30s)")
            return None

    except APIAuthenticationError:
        # Don't retry auth errors
        raise
    except APIRateLimitError as e:
        # Handle rate limit with wait
        logger.warning(f"Rate limited for fixture {fixture_id}: {str(e)}")
        if hasattr(e, 'response_body') and e.response_body:
            # Try to extract Retry-After header from response body
            retry_after = e.response_body.get('retry_after')
            if retry_after:
                await asyncio.sleep(float(retry_after))
        return None
    except Exception as e:
        logger.error(f"OpenAI API error for fixture {fixture_id}: {str(e)}")
        return None


async def analyze_fixture(fixture: Fixture | None) -> Fixture | None:
    """
    Analyze single fixture with OpenAI and attach AI analysis.

    Main entry point for single-fixture analysis. Handles:
    1. Input validation
    2. Prompt generation (via Story 4.1)
    3. OpenAI API call with retry/timeout
    4. Response parsing to MarketAnalysis
    5. Fixture augmentation with AI analysis
    6. Graceful error handling (no exceptions raised)

    This function NEVER raises exceptions. All errors are logged
    and marked on the fixture for downstream handling.

    Args:
        fixture: Fixture to analyze (from Story 3.3)

    Returns:
        Fixture with ai_analysis attached, or None if invalid

    Side Effects:
        - Updates global token/cost counters
        - Logs analysis progress, token usage, and errors
        - May wait for rate limiting

    Example:
        >>> fixture = await fetch_fixture(fixture_id)
        >>> analyzed = await analyze_fixture(fixture)
        >>> if analyzed and analyzed.ai_analysis:
        ...     print(f"AI confidence: {analyzed.ai_analysis.markets[0].confidence}")
    """
    # Validate fixture
    if not fixture or not fixture.fixture_id:
        logger.warning("Cannot analyze fixture without fixture_id")
        return None

    try:
        # Log analysis start
        fixture_key = f"{fixture.home_team.name} vs {fixture.away_team.name}" if fixture.home_team and fixture.away_team else fixture.fixture_id
        logger.info(f"Analyzing fixture: {fixture_key} ({fixture.fixture_id})")

        # Get OpenAI client
        client = await get_openai_client()

        # Generate prompt using Story 4.1
        try:
            prompt_data = await export_prompt_for_api(fixture)
        except Exception as e:
            logger.error(f"Failed to generate prompt for fixture {fixture.fixture_id}: {str(e)}")
            fixture.error_message = f"Prompt generation failed: {str(e)}"
            return fixture

        system_prompt = prompt_data.get("system_prompt", "")
        user_message = prompt_data.get("user_message", "")

        if not system_prompt or not user_message:
            logger.error(f"Empty prompt for fixture {fixture.fixture_id}")
            fixture.error_message = "Empty prompt generated"
            return fixture

        # Log prompt (first 300 chars for debugging)
        logger.debug(f"Prompt (first 300 chars): {user_message[:300]}...")

        # Call OpenAI with retry
        response_json = await _call_openai_with_retry(
            client,
            system_prompt,
            user_message,
            fixture.fixture_id
        )

        if not response_json:
            logger.error(f"Failed to get response from OpenAI for fixture {fixture.fixture_id}")
            fixture.error_message = "OpenAI API call failed"
            return fixture

        # Parse response to MarketAnalysis objects
        markets = _parse_openai_response(response_json)

        if not markets:
            logger.error(f"No markets parsed for fixture {fixture.fixture_id}")
            fixture.error_message = "Failed to parse OpenAI response"
            return fixture

        # Attach analysis to fixture
        fixture = _attach_analysis_to_fixture(fixture, markets)

        # Log success
        logger.info(
            f"Successfully analyzed fixture {fixture.fixture_id}: "
            f"{len(markets)} markets"
        )

        return fixture

    except Exception as e:
        logger.exception(f"Unexpected error analyzing fixture {fixture.fixture_id if fixture else 'unknown'}")
        if fixture:
            fixture.error_message = f"Analysis failed: {str(e)}"
        return fixture


async def analyze_all_fixtures(fixtures: list[Fixture] | None) -> list[Fixture]:
    """
    Batch analyze multiple fixtures sequentially.

    Orchestrator for analyzing multiple fixtures from Story 3.3.
    Processes fixtures sequentially (respects rate limiting) and
    collects results. Continues processing even if individual fixtures fail.

    Each fixture is analyzed with:
    - Timeout enforcement (30s)
    - Retry logic (max 3 attempts on transient errors)
    - Rate limiting (500 req/min)
    - Error handling (marked on fixture, not raised)

    Args:
        fixtures: List of consolidated fixtures from Story 3.3

    Returns:
        List of fixtures with ai_analysis attached (or error_message if failed)

    Side Effects:
        - Logs progress: "Analyzing fixture X of Y"
        - Logs summary: "Analyzed X of Y fixtures, Y failures"
        - Updates global token/cost counters
        - May wait for rate limiting

    Example:
        >>> fixtures = await fetch_all_fixtures()
        >>> analyzed = await analyze_all_fixtures(fixtures)
        >>> successful = [f for f in analyzed if f.ai_analysis]
        >>> print(f"Success rate: {len(successful)}/{len(fixtures)}")
    """
    if not fixtures:
        logger.info("No fixtures to analyze")
        return []

    logger.info(f"Starting batch analysis of {len(fixtures)} fixtures")

    results = []
    failures = 0

    for idx, fixture in enumerate(fixtures, 1):
        try:
            # Log progress
            fixture_key = f"{fixture.home_team.name} vs {fixture.away_team.name}" if fixture.home_team and fixture.away_team else fixture.fixture_id
            logger.info(f"Analyzing fixture {idx} of {len(fixtures)}: {fixture_key}")

            # Analyze fixture
            result = await analyze_fixture(fixture)

            if result:
                results.append(result)

                # Check for error
                if hasattr(result, 'error_message') and result.error_message:
                    failures += 1
                elif not hasattr(result, 'ai_analysis') or not result.ai_analysis:
                    failures += 1

            else:
                failures += 1
                results.append(fixture)  # Add original to keep list in sync

        except Exception as e:
            logger.error(f"Error analyzing fixture {idx}: {str(e)}")
            failures += 1
            results.append(fixture)  # Add original to keep list in sync

    # Log summary
    successes = len(results) - failures
    logger.info(
        f"Batch analysis complete: {successes}/{len(fixtures)} successful, "
        f"{failures} failures"
    )

    return results
