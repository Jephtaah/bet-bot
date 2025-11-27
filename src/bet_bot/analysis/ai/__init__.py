"""AI analysis module for bet-bot.

This package contains modules for OpenAI-based analysis:
- prompt_builder: Constructs rich context prompts for AI analysis
- client: Manages OpenAI API calls
- response_parser: Parses AI responses
"""

from bet_bot.analysis.ai.batch_analyzer import batch_analyze_all_fixtures
from bet_bot.analysis.ai.client import (
    analyze_all_fixtures,
    analyze_fixture,
)
from bet_bot.analysis.ai.prompt_builder import (
    build_analysis_prompt,
    export_prompt_for_api,
)
from bet_bot.analysis.ai.response_parser import (
    attach_parsed_analysis_to_fixture,
    get_probability_summary,
    parse_all_fixture_responses,
    parse_openai_response,
)

__all__ = [
    "build_analysis_prompt",
    "export_prompt_for_api",
    "analyze_fixture",
    "analyze_all_fixtures",
    "batch_analyze_all_fixtures",
    "parse_openai_response",
    "attach_parsed_analysis_to_fixture",
    "parse_all_fixture_responses",
    "get_probability_summary",
]
