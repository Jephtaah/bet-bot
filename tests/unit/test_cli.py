"""
Unit tests for bet-bot CLI

Tests the command-line interface using Typer's CliRunner to verify:
- Help text and command structure
- Version flag functionality
- Analyze command with various arguments
- Input validation (bankroll, config)
- Error handling and exit codes
"""

import pytest
from typer.testing import CliRunner
from bet_bot.cli.main import app, __version__


# Initialize CLI test runner
runner = CliRunner()


class TestCLIBasics:
    """Test basic CLI functionality (help, version)"""

    def test_cli_help_displays_correctly(self):
        """Test that --help flag shows help text and exits with code 0"""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Positive Expected Value Detection Tool for Football Betting" in result.stdout
        assert "analyze" in result.stdout

    def test_cli_version_displays_correctly(self):
        """Test that --version flag displays version and exits"""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert f"bet-bot version {__version__}" in result.stdout

    def test_cli_version_short_flag(self):
        """Test that -v short flag also displays version"""
        result = runner.invoke(app, ["-v"])
        assert result.exit_code == 0
        assert f"bet-bot version {__version__}" in result.stdout

    def test_cli_invalid_command_shows_error(self):
        """Test that invalid command shows error with helpful message"""
        result = runner.invoke(app, ["invalid-command"])
        assert result.exit_code != 0
        output = result.stdout + result.stderr
        assert "Error" in output or "No such command" in output


class TestAnalyzeCommandHelp:
    """Test analyze command help and structure"""

    def test_analyze_help_displays_correctly(self):
        """Test that analyze --help shows command-specific help"""
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "analyze" in result.stdout
        assert "--bankroll" in result.stdout
        assert "--config" in result.stdout

    def test_analyze_help_includes_examples(self):
        """Test that analyze help includes usage examples"""
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "Example" in result.stdout or "example" in result.stdout


class TestAnalyzeCommandValidInputs:
    """Test analyze command with valid inputs"""

    def test_analyze_accepts_valid_integer_bankroll(self):
        """Test that analyze accepts integer bankroll values"""
        result = runner.invoke(app, ["analyze", "--bankroll", "1000"])
        assert result.exit_code == 0
        assert "Starting analysis with bankroll: $1000.00" in result.stdout

    def test_analyze_accepts_valid_float_bankroll(self):
        """Test that analyze accepts float bankroll values"""
        result = runner.invoke(app, ["analyze", "--bankroll", "500.50"])
        assert result.exit_code == 0
        assert "Starting analysis with bankroll: $500.50" in result.stdout

    def test_analyze_accepts_large_bankroll(self):
        """Test that analyze accepts large bankroll values"""
        result = runner.invoke(app, ["analyze", "--bankroll", "100000"])
        assert result.exit_code == 0
        assert "Starting analysis with bankroll: $100000.00" in result.stdout

    def test_analyze_with_short_bankroll_flag(self):
        """Test that -b short flag works for bankroll"""
        result = runner.invoke(app, ["analyze", "-b", "1000"])
        assert result.exit_code == 0
        assert "Starting analysis with bankroll: $1000.00" in result.stdout

    def test_analyze_with_config_option(self):
        """Test that --config option is accepted and displayed"""
        result = runner.invoke(app, ["analyze", "--bankroll", "1000", "--config", "/path/to/config.yaml"])
        assert result.exit_code == 0
        assert "Starting analysis with bankroll: $1000.00" in result.stdout
        assert "Using config file: /path/to/config.yaml" in result.stdout

    def test_analyze_with_short_config_flag(self):
        """Test that -c short flag works for config"""
        result = runner.invoke(app, ["analyze", "-b", "1000", "-c", "config.yaml"])
        assert result.exit_code == 0
        assert "Using config file: config.yaml" in result.stdout

    def test_analyze_without_config_option(self):
        """Test that config option is truly optional"""
        result = runner.invoke(app, ["analyze", "--bankroll", "1000"])
        assert result.exit_code == 0
        assert "Starting analysis with bankroll: $1000.00" in result.stdout


class TestAnalyzeCommandValidation:
    """Test analyze command input validation"""

    def test_analyze_rejects_zero_bankroll(self):
        """Test that bankroll of 0 is rejected with error message"""
        result = runner.invoke(app, ["analyze", "--bankroll", "0"])
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Error: Bankroll must be positive" in output

    def test_analyze_rejects_negative_bankroll(self):
        """Test that negative bankroll is rejected"""
        result = runner.invoke(app, ["analyze", "--bankroll", "-100"])
        assert result.exit_code != 0
        # Typer's min validation catches this before our custom validation
        output = result.stdout + result.stderr
        assert "not in the range" in output or "Invalid value" in output

    def test_analyze_rejects_non_numeric_bankroll(self):
        """Test that non-numeric bankroll is rejected"""
        result = runner.invoke(app, ["analyze", "--bankroll", "abc"])
        assert result.exit_code != 0
        output = result.stdout + result.stderr
        assert "not a valid" in output or "Invalid value" in output

    def test_analyze_requires_bankroll_argument(self):
        """Test that bankroll argument is required"""
        result = runner.invoke(app, ["analyze"])
        assert result.exit_code != 0
        output = result.stdout + result.stderr
        assert "Missing option" in output or "required" in output.lower()


class TestAnalyzeCommandEdgeCases:
    """Test analyze command edge cases"""

    def test_analyze_with_very_small_bankroll(self):
        """Test analyze with very small positive bankroll"""
        result = runner.invoke(app, ["analyze", "--bankroll", "0.01"])
        assert result.exit_code == 0
        assert "Starting analysis with bankroll: $0.01" in result.stdout

    def test_analyze_with_decimal_precision(self):
        """Test that decimal precision is handled correctly"""
        result = runner.invoke(app, ["analyze", "--bankroll", "1234.56789"])
        assert result.exit_code == 0
        # Should format to 2 decimal places
        assert "Starting analysis with bankroll: $1234.57" in result.stdout

    def test_analyze_with_scientific_notation_bankroll(self):
        """Test that scientific notation is parsed correctly"""
        result = runner.invoke(app, ["analyze", "--bankroll", "1e3"])
        assert result.exit_code == 0
        assert "Starting analysis with bankroll: $1000.00" in result.stdout


class TestCLIAppMetadata:
    """Test CLI app configuration and metadata"""

    def test_app_has_correct_name(self):
        """Test that app name is configured correctly"""
        result = runner.invoke(app, ["--help"])
        # Check that bet-bot appears in usage or help text
        assert "bet-bot" in result.stdout.lower() or "python -m bet_bot.cli" in result.stdout

    def test_version_constant_is_defined(self):
        """Test that version constant exists and has correct format"""
        assert __version__
        assert isinstance(__version__, str)
        # Version should match semantic versioning pattern (X.Y.Z)
        parts = __version__.split(".")
        assert len(parts) == 3
        assert all(part.isdigit() for part in parts)


class TestCLIErrorHandling:
    """Test CLI error handling and user-friendly messages"""

    def test_error_messages_are_user_friendly(self):
        """Test that error messages don't expose raw Python exceptions"""
        result = runner.invoke(app, ["analyze", "--bankroll", "0"])
        assert result.exit_code != 0
        # Should not contain Python traceback
        assert "Traceback" not in result.stdout
        assert "Exception" not in result.stdout

    def test_validation_error_suggests_help(self):
        """Test that validation errors suggest using --help"""
        result = runner.invoke(app, ["analyze"])
        assert result.exit_code != 0
        output = result.stdout + result.stderr
        assert "--help" in output or "help" in output.lower()


if __name__ == "__main__":
    # Allow running tests directly with: python tests/unit/test_cli.py
    pytest.main([__file__, "-v"])
