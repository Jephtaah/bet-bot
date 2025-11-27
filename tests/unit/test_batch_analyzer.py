"""
Unit tests for batch analyzer module (Story 4.4).

Tests cover:
- Batch analysis orchestration with multiple fixtures
- Single fixture pipeline orchestration (4.1 → 4.2 → 4.3)
- Progress tracking and logging
- Error handling and graceful degradation
- Pipeline summary generation
- Input validation

Uses pytest with async support (@pytest.mark.asyncio).
Mocking uses unittest.mock.patch and pytest-mock.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bet_bot.analysis.ai.batch_analyzer import (
    _analyze_single_fixture,
    _create_pipeline_summary,
    _format_error_summary,
    _format_error_summary_from_dict,
    _validate_fixtures_for_analysis,
    batch_analyze_all_fixtures,
)
from bet_bot.models import AIAnalysis, Fixture, League, MarketAnalysis, Team


@pytest.fixture
def sample_fixture():
    """Create a sample fixture for testing."""
    return Fixture(
        fixture_id="123456",
        home_team=Team(id="1", name="Team A"),
        away_team=Team(id="2", name="Team B"),
        league=League(league_id="39", league_name="Championship", league_country="England", league_season=2025),
        kickoff_time="2025-12-01T15:00:00Z",
        odds={"match_result": {"home": 2.0, "draw": 3.5, "away": 3.2}},
    )


@pytest.fixture
def sample_fixtures_list(sample_fixture):
    """Create a list of sample fixtures."""
    fixtures = []
    for i in range(3):
        fixture = Fixture(
            fixture_id=f"fixture_{i}",
            home_team=Team(id=str(i * 2), name=f"Team {i*2}"),
            away_team=Team(id=str(i * 2 + 1), name=f"Team {i*2+1}"),
            league=League(league_id="39", league_name="Championship", league_country="England", league_season=2025),
            kickoff_time="2025-12-01T15:00:00Z",
            odds={"match_result": {"home": 2.0, "draw": 3.5, "away": 3.2}},
        )
        fixtures.append(fixture)
    return fixtures


class TestValidateFixtures:
    """Test input validation for fixture lists."""

    def test_validate_fixtures_with_none(self):
        """Test validation rejects None input."""
        assert not _validate_fixtures_for_analysis(None)

    def test_validate_fixtures_with_empty_list(self):
        """Test validation rejects empty list."""
        assert not _validate_fixtures_for_analysis([])

    def test_validate_fixtures_with_non_list(self):
        """Test validation rejects non-list input."""
        assert not _validate_fixtures_for_analysis("not a list")

    def test_validate_fixtures_with_valid_list(self, sample_fixtures_list):
        """Test validation accepts valid fixture list."""
        assert _validate_fixtures_for_analysis(sample_fixtures_list)


class TestFormatErrorSummary:
    """Test error formatting utilities."""

    def test_format_error_summary_with_fixture(self, sample_fixture):
        """Test formatting error from fixture object."""
        sample_fixture.error_message = "Test error"
        result = _format_error_summary(sample_fixture)
        assert "fixture_" in result or "123456" in result
        assert "Test error" in result

    def test_format_error_summary_from_dict(self):
        """Test formatting error from dict."""
        error_detail = {"fixture_id": "fix_123", "error": "Analysis failed"}
        result = _format_error_summary_from_dict(error_detail)
        assert "fix_123" in result
        assert "Analysis failed" in result

    def test_format_error_summary_with_none_fixture(self):
        """Test formatting with None fixture returns sensible message."""
        result = _format_error_summary(None)
        assert "unknown" in result or "error" in result.lower()


class TestCreatePipelineSummary:
    """Test pipeline summary generation."""

    def test_summary_with_empty_list(self):
        """Test summary generation with empty results."""
        summary = _create_pipeline_summary([])
        assert summary["total"] == 0
        assert summary["successful"] == 0
        assert summary["failed"] == 0
        assert summary["success_rate"] == 0.0
        assert summary["error_list"] == []

    def test_summary_with_successful_fixtures(self, sample_fixtures_list):
        """Test summary with all successful analyses."""
        # Attach ai_analysis to all fixtures
        for fixture in sample_fixtures_list:
            fixture.ai_analysis = AIAnalysis(
                fixture_id=fixture.fixture_id,
                markets=[
                    MarketAnalysis(
                        market_type="match_result",
                        ai_probability=0.6,
                        reasoning="Test",
                        confidence=80,
                    )
                ],
                analysis_timestamp="2025-12-01T10:00:00Z",
                model_used="gpt-4",
            )

        summary = _create_pipeline_summary(sample_fixtures_list)
        assert summary["total"] == 3
        assert summary["successful"] == 3
        assert summary["failed"] == 0
        assert summary["success_rate"] == 1.0

    def test_summary_with_failed_fixtures(self, sample_fixtures_list):
        """Test summary with failed analyses."""
        # Mark all as failed
        for fixture in sample_fixtures_list:
            fixture.error_message = "Analysis failed"

        summary = _create_pipeline_summary(sample_fixtures_list)
        assert summary["total"] == 3
        assert summary["successful"] == 0
        assert summary["failed"] == 3
        assert summary["success_rate"] == 0.0
        assert len(summary["error_list"]) == 3

    def test_summary_with_mixed_success_failure(self, sample_fixtures_list):
        """Test summary with mixed success and failure."""
        # First fixture succeeds
        sample_fixtures_list[0].ai_analysis = AIAnalysis(
            fixture_id=sample_fixtures_list[0].fixture_id,
            markets=[
                MarketAnalysis(
                    market_type="match_result",
                    ai_probability=0.6,
                    reasoning="Test",
                    confidence=80,
                )
            ],
            analysis_timestamp="2025-12-01T10:00:00Z",
            model_used="gpt-4",
        )

        # Others fail
        sample_fixtures_list[1].error_message = "Error 1"
        sample_fixtures_list[2].error_message = "Error 2"

        summary = _create_pipeline_summary(sample_fixtures_list)
        assert summary["total"] == 3
        assert summary["successful"] == 1
        assert summary["failed"] == 2
        assert summary["success_rate"] == pytest.approx(1 / 3)


class TestAnalyzeSingleFixture:
    """Test single fixture orchestration through pipeline."""

    @pytest.mark.asyncio
    async def test_analyze_single_fixture_success(self, sample_fixture):
        """Test successful single fixture analysis."""
        with patch(
            "bet_bot.analysis.ai.batch_analyzer.export_prompt_for_api"
        ) as mock_prompt, patch(
            "bet_bot.analysis.ai.batch_analyzer.analyze_fixture"
        ) as mock_analyze, patch(
            "bet_bot.analysis.ai.batch_analyzer.parse_openai_response"
        ) as mock_parse, patch(
            "bet_bot.analysis.ai.batch_analyzer.attach_parsed_analysis_to_fixture"
        ) as mock_attach:

            # Setup mocks - export_prompt_for_api returns dict
            mock_prompt.return_value = {
                "system_prompt": "You are an expert...",
                "user_message": "Analyze this"
            }

            analyzed_fixture = sample_fixture
            analyzed_fixture.ai_analysis = {"markets": [{"type": "match_result"}]}
            mock_analyze.return_value = analyzed_fixture

            mock_parse.return_value = [
                MarketAnalysis(
                    market_type="match_result",
                    ai_probability=0.6,
                    reasoning="Test",
                    confidence=80,
                )
            ]

            final_fixture = sample_fixture
            final_fixture.ai_analysis = AIAnalysis(
                fixture_id=sample_fixture.fixture_id,
                markets=[
                    MarketAnalysis(
                        market_type="match_result",
                        ai_probability=0.6,
                        reasoning="Test",
                        confidence=80,
                    )
                ],
                analysis_timestamp="2025-12-01T10:00:00Z",
                model_used="gpt-4",
            )
            mock_attach.return_value = final_fixture

            # Execute
            result = await _analyze_single_fixture(sample_fixture)

            # Verify
            assert result is not None
            assert result.ai_analysis is not None
            assert not result.error_message

    @pytest.mark.asyncio
    async def test_analyze_single_fixture_with_none(self):
        """Test handling of None fixture."""
        result = await _analyze_single_fixture(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_single_fixture_missing_teams(self, sample_fixture):
        """Test handling fixture with missing teams."""
        sample_fixture.home_team = None
        result = await _analyze_single_fixture(sample_fixture)
        assert result is not None
        assert result.error_message is not None
        assert "team" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_analyze_single_fixture_prompt_failure(self, sample_fixture):
        """Test error handling when prompt generation fails."""
        with patch(
            "bet_bot.analysis.ai.batch_analyzer.export_prompt_for_api"
        ) as mock_prompt:
            mock_prompt.side_effect = Exception("Prompt error")

            result = await _analyze_single_fixture(sample_fixture)

            assert result is not None
            assert result.error_message is not None
            assert "Prompt generation" in result.error_message

    @pytest.mark.asyncio
    async def test_analyze_single_fixture_openai_failure(self, sample_fixture):
        """Test error handling when OpenAI call fails."""
        with patch(
            "bet_bot.analysis.ai.batch_analyzer.export_prompt_for_api"
        ) as mock_prompt, patch(
            "bet_bot.analysis.ai.batch_analyzer.analyze_fixture"
        ) as mock_analyze:

            mock_prompt.return_value = {
                "system_prompt": "You are an expert...",
                "user_message": "Analyze"
            }
            mock_analyze.side_effect = Exception("OpenAI error")

            result = await _analyze_single_fixture(sample_fixture)

            assert result is not None
            assert result.error_message is not None
            assert "OpenAI API" in result.error_message or "OpenAI" in result.error_message

    @pytest.mark.asyncio
    async def test_analyze_single_fixture_parse_failure(self, sample_fixture):
        """Test error handling when response parsing fails."""
        with patch(
            "bet_bot.analysis.ai.batch_analyzer.export_prompt_for_api"
        ) as mock_prompt, patch(
            "bet_bot.analysis.ai.batch_analyzer.analyze_fixture"
        ) as mock_analyze, patch(
            "bet_bot.analysis.ai.batch_analyzer.parse_openai_response"
        ) as mock_parse:

            mock_prompt.return_value = {
                "system_prompt": "You are an expert...",
                "user_message": "Analyze"
            }

            analyzed_fixture = sample_fixture
            analyzed_fixture.ai_analysis = {"markets": []}
            mock_analyze.return_value = analyzed_fixture

            async def async_parse_error(*args, **kwargs):
                raise Exception("Parse error")
            mock_parse.side_effect = async_parse_error

            result = await _analyze_single_fixture(sample_fixture)

            assert result is not None
            assert result.error_message is not None
            assert "parsing" in result.error_message.lower()


class TestBatchAnalyzeAllFixtures:
    """Test batch analysis orchestration."""

    @pytest.mark.asyncio
    async def test_batch_analyze_empty_list(self):
        """Test batch analysis with empty fixture list."""
        result = await batch_analyze_all_fixtures([])
        assert result == []

    @pytest.mark.asyncio
    async def test_batch_analyze_none(self):
        """Test batch analysis with None input."""
        result = await batch_analyze_all_fixtures(None)
        assert result == []

    @pytest.mark.asyncio
    async def test_batch_analyze_single_fixture_success(self, sample_fixture):
        """Test batch analysis with single successful fixture."""
        with patch(
            "bet_bot.analysis.ai.batch_analyzer._analyze_single_fixture"
        ) as mock_analyze:

            sample_fixture.ai_analysis = AIAnalysis(
                fixture_id=sample_fixture.fixture_id,
                markets=[
                    MarketAnalysis(
                        market_type="match_result",
                        ai_probability=0.6,
                        reasoning="Test",
                        confidence=80,
                    )
                ],
                analysis_timestamp="2025-12-01T10:00:00Z",
                model_used="gpt-4",
            )
            mock_analyze.return_value = sample_fixture

            result = await batch_analyze_all_fixtures([sample_fixture])

            assert len(result) == 1
            assert result[0].ai_analysis is not None
            assert not result[0].error_message

    @pytest.mark.asyncio
    async def test_batch_analyze_multiple_fixtures_success(self, sample_fixtures_list):
        """Test batch analysis with multiple successful fixtures."""
        # Mark all as successful
        for fixture in sample_fixtures_list:
            fixture.ai_analysis = AIAnalysis(
                fixture_id=fixture.fixture_id,
                markets=[
                    MarketAnalysis(
                        market_type="match_result",
                        ai_probability=0.6,
                        reasoning="Test",
                        confidence=80,
                    )
                ],
                analysis_timestamp="2025-12-01T10:00:00Z",
                model_used="gpt-4",
            )

        with patch(
            "bet_bot.analysis.ai.batch_analyzer._analyze_single_fixture"
        ) as mock_analyze:
            mock_analyze.side_effect = sample_fixtures_list

            result = await batch_analyze_all_fixtures(sample_fixtures_list)

            assert len(result) == 3
            for fixture in result:
                assert fixture.ai_analysis is not None

    @pytest.mark.asyncio
    async def test_batch_analyze_mixed_success_failure(self, sample_fixtures_list):
        """Test batch analysis with mixed success and failure."""
        # First succeeds
        sample_fixtures_list[0].ai_analysis = AIAnalysis(
            fixture_id=sample_fixtures_list[0].fixture_id,
            markets=[
                MarketAnalysis(
                    market_type="match_result",
                    ai_probability=0.6,
                    reasoning="Test",
                    confidence=80,
                )
            ],
            analysis_timestamp="2025-12-01T10:00:00Z",
            model_used="gpt-4",
        )

        # Others fail
        sample_fixtures_list[1].error_message = "Error 1"
        sample_fixtures_list[2].error_message = "Error 2"

        with patch(
            "bet_bot.analysis.ai.batch_analyzer._analyze_single_fixture"
        ) as mock_analyze:
            mock_analyze.side_effect = sample_fixtures_list

            result = await batch_analyze_all_fixtures(sample_fixtures_list)

            assert len(result) == 3
            # All fixtures returned
            assert result[0].ai_analysis is not None
            assert result[1].error_message is not None
            assert result[2].error_message is not None

    @pytest.mark.asyncio
    async def test_batch_analyze_all_failures(self, sample_fixtures_list):
        """Test batch analysis where all fixtures fail."""
        for fixture in sample_fixtures_list:
            fixture.error_message = "Analysis failed"

        with patch(
            "bet_bot.analysis.ai.batch_analyzer._analyze_single_fixture"
        ) as mock_analyze:
            mock_analyze.side_effect = sample_fixtures_list

            result = await batch_analyze_all_fixtures(sample_fixtures_list)

            assert len(result) == 3
            for fixture in result:
                assert fixture.error_message is not None
