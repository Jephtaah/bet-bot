"""
OpenAI response parser for bet-bot application.

This module parses and validates OpenAI JSON responses for betting analysis.
It extracts structured probability data for edge detection calculation from
raw OpenAI responses and validates all fields according to requirements.

Features:
- Parse OpenAI JSON response format (markets array with probabilities, reasoning, confidence)
- Extract probabilities for all markets (match_result, total_goals, corners, cards)
- Validate probability values are floats in range [0.0, 1.0]
- Normalize multi-outcome market probabilities to sum to 1.0
- Handle malformed responses gracefully (missing fields, invalid JSON, type errors)
- Attach parsed analysis to fixture.ai_analysis field
- Create validated MarketAnalysis objects

Architecture:
- parse_openai_response(): Main entry point for parsing raw response
- attach_parsed_analysis_to_fixture(): Attach parsed analysis to fixture
- parse_all_fixture_responses(): Batch orchestrator for multiple fixtures
- _validate_openai_response_structure(): Validate response JSON structure
- _validate_market_probabilities(): Validate probability values and sum
- _normalize_probabilities(): Normalize probabilities to sum to 1.0
- _parse_market(): Parse and validate single market
- _extract_market_probabilities(): Extract probabilities by market type
- get_probability_summary(): Create summary of parsed probabilities

Integration:
- Input: Fixture with raw ai_analysis JSON response (from Story 4.2)
- Output: Fixture with ai_analysis = AIAnalysis (structured MarketAnalysis objects)
- Called by: Story 4.4 (Batch Analyze All Fixtures)

Usage:
    from bet_bot.analysis.ai import parse_openai_response, attach_parsed_analysis_to_fixture

    # Parse raw response
    parsed_markets = await parse_openai_response(raw_json_response, fixture_id)

    # Attach to fixture
    fixture = await attach_parsed_analysis_to_fixture(fixture, parsed_markets)

    # Batch processing
    updated_fixtures = await parse_all_fixture_responses(fixtures)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from bet_bot.models import AIAnalysis, Fixture, MarketAnalysis

# Module-level logger
logger = logging.getLogger(__name__)

# Probability validation thresholds
PROBABILITY_RANGE = (0.0, 1.0)
PROBABILITY_SUM_TOLERANCE = 0.05  # ±5% tolerance for multi-outcome markets
MARKET_TYPES = {"match_result", "total_goals", "corners", "cards"}
MULTI_OUTCOME_MARKETS = {"match_result"}  # Markets with 3+ outcomes
BINARY_MARKETS = {"total_goals", "corners", "cards"}  # Markets with 2 outcomes


def _validate_openai_response_structure(response: dict[str, Any]) -> bool:
    """
    Validate OpenAI response has required structure.

    Checks that response has "markets" key (required array), and each market
    has required fields: "type", "probabilities", "reasoning", "confidence".

    Args:
        response: The OpenAI response dict to validate

    Returns:
        True if structure is valid, False otherwise

    Side Effects:
        Logs validation failures at WARNING level with response summary
    """
    # Check "markets" key exists
    if "markets" not in response:
        logger.warning(f"Response missing required 'markets' key: {list(response.keys())}")
        return False

    markets = response.get("markets")
    if not isinstance(markets, list):
        logger.warning(f"'markets' field is not a list: {type(markets).__name__}")
        return False

    # Validate each market has required fields
    required_fields = {"type", "probabilities", "reasoning", "confidence"}
    for idx, market in enumerate(markets):
        if not isinstance(market, dict):
            logger.warning(f"Market {idx} is not a dict: {type(market).__name__}")
            return False

        missing_fields = required_fields - set(market.keys())
        if missing_fields:
            logger.warning(f"Market {idx} missing fields: {missing_fields}")
            return False

        # Validate field types
        if not isinstance(market.get("probabilities"), dict):
            logger.warning(
                f"Market {idx} 'probabilities' is not dict: "
                f"{type(market.get('probabilities')).__name__}"
            )
            return False

    return True


def _validate_market_probabilities(market_type: str, probabilities_dict: dict[str, float]) -> bool:
    """
    Validate market probability values and sum.

    Checks that:
    - All values are floats in [0.0, 1.0] range
    - For multi-outcome markets (match_result), sum ≈ 1.0 (tolerance ±0.05)
    - For binary markets (total_goals, corners, cards), sum ≈ 1.0 (tolerance ±0.05)

    Args:
        market_type: Type of market (e.g., "match_result")
        probabilities_dict: Dict of {outcome: probability}

    Returns:
        True if probabilities are valid, False otherwise

    Side Effects:
        Logs validation failures at WARNING level with market type and values
    """
    if not probabilities_dict:
        logger.warning(f"Market {market_type} has empty probabilities dict")
        return False

    # Check all values are numeric
    for outcome, prob in probabilities_dict.items():
        if not isinstance(prob, (int, float)):
            logger.warning(
                f"Market {market_type} outcome '{outcome}' probability is not numeric: "
                f"{type(prob).__name__} value={prob}"
            )
            return False

        # Check range [0.0, 1.0]
        if prob < PROBABILITY_RANGE[0] or prob > PROBABILITY_RANGE[1]:
            logger.warning(
                f"Market {market_type} outcome '{outcome}' probability {prob} "
                f"outside range {PROBABILITY_RANGE}"
            )
            return False

    # Check sum for multi-outcome and binary markets
    prob_sum = sum(probabilities_dict.values())
    min_sum = 1.0 - PROBABILITY_SUM_TOLERANCE
    max_sum = 1.0 + PROBABILITY_SUM_TOLERANCE

    if prob_sum < min_sum or prob_sum > max_sum:
        logger.warning(
            f"Market {market_type} probability sum {prob_sum:.3f} "
            f"outside tolerance range [{min_sum:.3f}, {max_sum:.3f}]"
        )
        return False

    return True


def _normalize_probabilities(market_type: str, probabilities_dict: dict[str, float]) -> dict[str, float]:
    """
    Normalize probabilities to sum to 1.0.

    If probabilities sum != 1.0, divides each by sum to renormalize.
    Handles division by zero (all zeros case).
    Clips out-of-range values to [0.0, 1.0].

    Args:
        market_type: Type of market (for logging)
        probabilities_dict: Dict of {outcome: probability}

    Returns:
        Normalized probabilities dict

    Side Effects:
        Logs normalization at DEBUG level if adjustment made
    """
    prob_sum = sum(probabilities_dict.values())

    # Handle division by zero (all zeros)
    if prob_sum == 0:
        logger.debug(f"Market {market_type} has all-zero probabilities, returning original")
        return probabilities_dict

    # Normalize if sum != 1.0
    if abs(prob_sum - 1.0) > 0.001:  # Allow small floating-point tolerance
        logger.debug(
            f"Normalizing market {market_type} probabilities: sum was {prob_sum:.3f}"
        )
        normalized = {}
        for outcome, prob in probabilities_dict.items():
            normalized_prob = prob / prob_sum
            # Clip to valid range after normalization
            normalized_prob = max(PROBABILITY_RANGE[0], min(PROBABILITY_RANGE[1], normalized_prob))
            normalized[outcome] = normalized_prob
        return normalized

    return probabilities_dict


def _extract_market_probabilities(market_type: str, probabilities_dict: dict[str, float]) -> dict[str, float]:
    """
    Extract and normalize probabilities for specific market type.

    Handles market-type-specific probability extraction. Assigns defaults
    for missing outcome keys to ensure consistent structure.

    Args:
        market_type: Type of market (e.g., "match_result", "total_goals")
        probabilities_dict: Raw probabilities dict from response

    Returns:
        Dict with standardized probability keys for market type

    Side Effects:
        Logs at DEBUG if defaults are used for missing keys
    """
    # Define expected keys by market type
    market_key_mapping = {
        "match_result": ["home", "draw", "away"],
        "total_goals": ["over", "under"],
        "corners": ["over", "under"],
        "cards": ["over", "under"],
    }

    expected_keys = market_key_mapping.get(market_type, list(probabilities_dict.keys()))

    # Extract and validate keys
    extracted = {}
    for key in expected_keys:
        if key in probabilities_dict:
            extracted[key] = probabilities_dict[key]
        else:
            # Use default if missing (0.5 for 2-outcome, 0.333 for 3-outcome)
            default_val = 0.5 if market_type in BINARY_MARKETS else (1.0 / len(expected_keys))
            extracted[key] = default_val
            logger.debug(
                f"Market {market_type} missing outcome '{key}', using default {default_val:.3f}"
            )

    return extracted


def _parse_market(market_object: dict[str, Any], fixture_id: str) -> MarketAnalysis | None:
    """
    Parse and validate single market from OpenAI response.

    Extracts market type, probabilities, reasoning, and confidence.
    Validates and normalizes probabilities. Creates MarketAnalysis object.

    Args:
        market_object: Market dict from OpenAI response
        fixture_id: Fixture ID for logging context

    Returns:
        MarketAnalysis object if successful, None if parsing failed

    Side Effects:
        Logs warnings if market validation fails
    """
    try:
        # Extract required fields
        market_type = market_object.get("type", "unknown")
        if not market_type:
            logger.warning(f"Fixture {fixture_id}: Market missing 'type' field")
            return None

        probabilities = market_object.get("probabilities", {})
        if not probabilities or not isinstance(probabilities, dict):
            logger.warning(
                f"Fixture {fixture_id}: Market '{market_type}' missing/invalid probabilities"
            )
            return None

        reasoning = market_object.get("reasoning", "No reasoning provided")
        if not isinstance(reasoning, str):
            reasoning = str(reasoning)
        reasoning = reasoning.strip()[:500]  # Max 500 chars

        confidence = market_object.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)):
            confidence = 0.5
        # Convert [0.0, 1.0] to [0, 100] if needed
        if 0.0 <= confidence <= 1.0:
            confidence = int(confidence * 100)
        # Ensure confidence in [0, 100]
        confidence = max(0, min(100, int(confidence)))

        # Validate probabilities
        if not _validate_market_probabilities(market_type, probabilities):
            logger.warning(
                f"Fixture {fixture_id}: Market '{market_type}' probability validation failed"
            )
            # Continue anyway - normalize will fix issues
            probabilities = _normalize_probabilities(market_type, probabilities)

        # Normalize probabilities
        probabilities = _normalize_probabilities(market_type, probabilities)

        # Extract and standardize outcomes
        probabilities = _extract_market_probabilities(market_type, probabilities)

        # Calculate ai_probability as max probability (primary outcome)
        ai_probability = max(probabilities.values()) if probabilities else 0.5

        # Create MarketAnalysis object
        try:
            market = MarketAnalysis(
                market_type=market_type,
                ai_probability=ai_probability,
                reasoning=reasoning or "No reasoning provided",
                confidence=confidence
            )
            return market
        except ValidationError as e:
            logger.warning(
                f"Fixture {fixture_id}: Failed to create MarketAnalysis for '{market_type}': {str(e)}"
            )
            return None

    except Exception as e:
        logger.warning(f"Fixture {fixture_id}: Error parsing market: {str(e)}")
        return None


async def parse_openai_response(
    response_json: str | dict[str, Any],
    fixture_id: str
) -> list[MarketAnalysis] | None:
    """
    Parse OpenAI JSON response and extract MarketAnalysis objects.

    Main entry point for parsing raw OpenAI responses. Handles:
    - JSON parsing (if string input)
    - Structure validation
    - Per-market parsing and validation
    - Graceful error handling

    Never raises exceptions. Returns None on complete failure, or partial
    results if individual markets fail.

    Args:
        response_json: Raw OpenAI response (JSON string or dict)
        fixture_id: Fixture ID for logging context

    Returns:
        List of MarketAnalysis objects, empty list if no valid markets,
        None if parsing completely fails

    Side Effects:
        Logs at DEBUG level: raw response (first 300 chars)
        Logs at WARNING level: validation failures, missing fields
        Logs at ERROR level: JSON parse errors, complete failures
    """
    try:
        # Parse JSON if string input
        if isinstance(response_json, str):
            logger.debug(f"Fixture {fixture_id}: Parsing JSON response (first 300 chars): {response_json[:300]}")
            try:
                response_data = json.loads(response_json)
            except json.JSONDecodeError as e:
                logger.error(
                    f"Fixture {fixture_id}: Failed to parse response as JSON: {str(e)}"
                )
                return None
        else:
            response_data = response_json
            logger.debug(f"Fixture {fixture_id}: Processing dict response")

        # Validate response structure
        if not _validate_openai_response_structure(response_data):
            logger.warning(
                f"Fixture {fixture_id}: Response structure validation failed"
            )
            # Try to extract markets anyway
            if "markets" not in response_data:
                return None

        # Extract markets array
        markets_data = response_data.get("markets", [])
        if not isinstance(markets_data, list):
            logger.warning(
                f"Fixture {fixture_id}: 'markets' field is not list: "
                f"{type(markets_data).__name__}"
            )
            return None

        if not markets_data:
            logger.warning(f"Fixture {fixture_id}: Response has empty markets array")
            return []

        # Parse each market
        parsed_markets = []
        for idx, market_object in enumerate(markets_data):
            try:
                if not isinstance(market_object, dict):
                    logger.warning(
                        f"Fixture {fixture_id}: Market {idx} is not dict, skipping"
                    )
                    continue

                market = _parse_market(market_object, fixture_id)
                if market:
                    parsed_markets.append(market)
                    logger.debug(
                        f"Fixture {fixture_id}: Parsed market {idx} ({market.market_type})"
                    )

            except Exception as e:
                logger.warning(
                    f"Fixture {fixture_id}: Error parsing market {idx}: {str(e)}"
                )
                continue

        # Log result
        logger.info(
            f"Fixture {fixture_id}: Parsed {len(parsed_markets)} markets from response"
        )

        return parsed_markets if parsed_markets else []

    except Exception:
        logger.exception(f"Fixture {fixture_id}: Unexpected error in parse_openai_response")
        return None


async def attach_parsed_analysis_to_fixture(
    fixture: Fixture,
    parsed_markets: list[MarketAnalysis]
) -> Fixture:
    """
    Attach parsed analysis to fixture object.

    Creates AIAnalysis model with list of MarketAnalysis objects and
    attaches to fixture.ai_analysis field. Adds metadata (analysis_timestamp,
    model_used) for tracking.

    Args:
        fixture: The fixture to augment
        parsed_markets: List of parsed MarketAnalysis objects

    Returns:
        Augmented fixture with ai_analysis field populated

    Side Effects:
        Logs at DEBUG level: attachment success with market count
        Logs at WARNING level: if parsed_markets is empty
    """
    if not fixture or not fixture.fixture_id:
        logger.warning("Cannot attach analysis to invalid fixture")
        return fixture

    try:
        if not parsed_markets:
            logger.warning(
                f"Fixture {fixture.fixture_id}: Attaching empty markets list"
            )

        # Create AIAnalysis object
        analysis = AIAnalysis(
            fixture_id=fixture.fixture_id,
            markets=parsed_markets,
            analysis_timestamp=datetime.now(timezone.utc)
        )

        # Attach to fixture
        fixture.ai_analysis = analysis

        logger.debug(
            f"Fixture {fixture.fixture_id}: Attached AI analysis "
            f"({len(parsed_markets)} markets)"
        )

        return fixture

    except ValidationError as e:
        logger.error(
            f"Fixture {fixture.fixture_id}: Failed to create AIAnalysis: {str(e)}"
        )
        fixture.error_message = f"Analysis attachment failed: {str(e)}"
        return fixture

    except Exception as e:
        logger.exception(
            f"Fixture {fixture.fixture_id}: Unexpected error attaching analysis"
        )
        fixture.error_message = f"Analysis attachment failed: {str(e)}"
        return fixture


async def parse_all_fixture_responses(
    fixtures: list[Fixture]
) -> list[Fixture]:
    """
    Parse responses for multiple fixtures.

    Batch orchestrator for parsing multiple fixtures. Iterates through
    fixtures, parses each response, handles failures gracefully.
    Returns all fixtures (success or failure) in original order.

    Args:
        fixtures: List of fixtures with raw ai_analysis responses

    Returns:
        List of fixtures with parsed ai_analysis (or error_message if failed)

    Side Effects:
        Logs at INFO level: progress updates and summary
        Logs individual fixture parse results at DEBUG level
    """
    if not fixtures:
        logger.info("No fixtures to parse")
        return []

    logger.info(f"Starting response parsing for {len(fixtures)} fixtures")

    results = []
    failures = 0

    for idx, fixture in enumerate(fixtures, 1):
        try:
            fixture_key = (
                f"{fixture.home_team.name} vs {fixture.away_team.name}"
                if fixture.home_team and fixture.away_team
                else fixture.fixture_id
            )
            logger.info(f"Parsing fixture {idx}/{len(fixtures)}: {fixture_key}")

            # Get raw response
            raw_response = fixture.ai_analysis
            if not raw_response:
                logger.warning(f"Fixture {fixture.fixture_id}: No ai_analysis response to parse")
                fixture.error_message = "No ai_analysis response found"
                results.append(fixture)
                failures += 1
                continue

            # Parse response
            parsed_markets = await parse_openai_response(raw_response, fixture.fixture_id)

            if parsed_markets is None:
                logger.error(
                    f"Fixture {fixture.fixture_id}: Response parsing completely failed"
                )
                fixture.error_message = "Response parsing failed"
                results.append(fixture)
                failures += 1
                continue

            # Attach to fixture
            fixture = await attach_parsed_analysis_to_fixture(fixture, parsed_markets)
            results.append(fixture)

            logger.debug(
                f"Fixture {fixture.fixture_id}: Successfully parsed "
                f"({len(parsed_markets)} markets)"
            )

        except Exception as e:
            logger.error(
                f"Error parsing fixture {idx}: {str(e)}"
            )
            if fixture:
                fixture.error_message = f"Parsing failed: {str(e)}"
                results.append(fixture)
            failures += 1

    # Log summary
    successes = len(results) - failures
    logger.info(
        f"Response parsing complete: {successes}/{len(fixtures)} successful, "
        f"{failures} failures"
    )

    return results


def get_probability_summary(markets: list[MarketAnalysis]) -> dict[str, dict[str, float]]:
    """
    Create summary of parsed probabilities by market type.

    Helper function for logging and debugging. Extracts and organizes
    probabilities from MarketAnalysis objects by market type.

    Args:
        markets: List of MarketAnalysis objects

    Returns:
        Dict organized by market type: {market_type: {outcome: probability, ...}, ...}

    Example:
        >>> summary = get_probability_summary(markets)
        >>> print(summary["match_result"])  # {"home": 0.55, "draw": 0.25, "away": 0.20}
    """
    summary: dict[str, dict[str, float]] = {}

    for market in markets:
        market_type = market.market_type
        if market_type not in summary:
            summary[market_type] = {}

        # Create entry with ai_probability as primary outcome
        summary[market_type]["ai_probability"] = market.ai_probability
        summary[market_type]["confidence"] = market.confidence

    return summary
