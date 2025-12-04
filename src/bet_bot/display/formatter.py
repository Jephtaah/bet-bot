"""
Terminal formatter for betting picks.

This module transforms Pick objects from the edge detection pipeline into
beautifully formatted terminal output using the Rich library.

Features:
- Rich-formatted table with color-coded EV and confidence levels
- Summary footer with statistics (average EV, confidence, total stake)
- Graceful handling of empty picks with user-friendly messages
- Proper alignment and formatting for currency, percentages, and badges

Functions:
    format_picks_for_display: Main function to format picks for terminal display
    _format_fixture_cell: Helper to format fixture information
    _format_ev_cell: Helper to format EV with color
    _format_confidence_cell: Helper to format confidence as colored badge
    _format_stake_cell: Helper to format stake as currency
    _calculate_statistics: Helper to compute summary statistics

Usage:
    from bet_bot.display import format_picks_for_display

    picks = [pick1, pick2, pick3]
    formatted_output = format_picks_for_display(picks)
    print(formatted_output)
"""

import logging
from datetime import datetime, timezone
from typing import Any

from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from bet_bot.models.analysis import Pick

logger = logging.getLogger(__name__)

# No picks message constant
NO_PICKS_MESSAGE = "ℹ️ No profitable picks found meeting your criteria"


def _format_fixture_cell(pick: Pick, fixtures_map: dict[str, Any] | None = None) -> str:
    """
    Format fixture information for display.

    Args:
        pick: Pick object containing fixture_id
        fixtures_map: Optional mapping of fixture_id to Fixture objects for team/league info

    Returns:
        Formatted fixture string (e.g., "Arsenal vs City\n(Premier League)")
    """
    fixture_id = pick.fixture_id

    # Try to get fixture details from map
    if fixtures_map and fixture_id in fixtures_map:
        fixture = fixtures_map[fixture_id]
        home_name = fixture.home_team.name
        away_name = fixture.away_team.name
        league_name = fixture.league.league_name
        kickoff_time = fixture.kickoff_time

        # Format team names (abbreviate if very long)
        if len(home_name) > 12:
            home_name = home_name[:10] + "."
        if len(away_name) > 12:
            away_name = away_name[:10] + "."

        # Format time
        if kickoff_time:
            now = datetime.now(timezone.utc)
            if kickoff_time.date() == now.date():
                time_str = kickoff_time.strftime("Today %H:%M")
            else:
                time_str = kickoff_time.strftime("%a %H:%M")
            return f"{home_name} vs {away_name}\n({league_name}, {time_str})"

        return f"{home_name} vs {away_name}\n({league_name})"

    # Fallback to fixture_id if no fixture data available
    return f"Fixture {fixture_id}"


def _format_ev_cell(ev_percentage: float) -> str:
    """
    Format EV as percentage with color coding.

    Args:
        ev_percentage: EV as percentage (can be negative)

    Returns:
        Rich-formatted string with color (green for positive, red for negative)
    """
    sign = "+" if ev_percentage >= 0 else ""
    formatted = f"{sign}{ev_percentage:.1f}%"

    if ev_percentage > 0:
        return f"[green]{formatted}[/green]"
    elif ev_percentage < 0:
        return f"[red]{formatted}[/red]"
    else:
        return f"[yellow]{formatted}[/yellow]"


def _format_confidence_cell(confidence: int) -> str:
    """
    Format confidence as colored badge.

    Args:
        confidence: Confidence score (0-100)

    Returns:
        Rich-formatted badge string with color
    """
    if confidence > 80:
        return "[green]● HIGH[/green]"
    elif confidence >= 60:
        return "[yellow]● MED[/yellow]"
    else:
        return "[red]● LOW[/red]"


def _format_stake_cell(stake: float) -> str:
    """
    Format stake as currency with thousands separator.

    Args:
        stake: Stake amount in USD

    Returns:
        Formatted currency string (e.g., "$4.50" or "$1,234.56")
    """
    return f"[green]${stake:,.2f}[/green]"


def _format_probability_cell(probability: float) -> str:
    """
    Format probability as percentage.

    Args:
        probability: Probability as decimal (0.0-1.0)

    Returns:
        Formatted percentage string (e.g., "65.2%")
    """
    return f"{probability * 100:.1f}%"


def _calculate_statistics(picks: list[Pick]) -> dict[str, Any]:
    """
    Calculate summary statistics from picks.

    Args:
        picks: List of Pick objects

    Returns:
        Dictionary with statistics: total_picks, avg_ev, avg_confidence, total_stake, min_ev, max_ev
    """
    if not picks:
        return {
            "total_picks": 0,
            "avg_ev": 0.0,
            "avg_confidence": 0,
            "total_stake": 0.0,
            "min_ev": 0.0,
            "max_ev": 0.0,
        }

    total_picks = len(picks)
    total_ev = sum(pick.ev_percentage for pick in picks)
    total_confidence = sum(pick.confidence for pick in picks)
    total_stake = sum(pick.recommended_stake for pick in picks)

    avg_ev = total_ev / total_picks
    avg_confidence = int(total_confidence / total_picks)
    min_ev = min(pick.ev_percentage for pick in picks)
    max_ev = max(pick.ev_percentage for pick in picks)

    return {
        "total_picks": total_picks,
        "avg_ev": avg_ev,
        "avg_confidence": avg_confidence,
        "total_stake": total_stake,
        "min_ev": min_ev,
        "max_ev": max_ev,
    }


def format_picks_for_display(
    picks: list[Pick] | None = None,
    fixtures_map: dict[str, Any] | None = None,
) -> str:
    """
    Format picks for terminal display with Rich library.

    Transforms a list of Pick objects into a beautifully formatted table
    with color-coded EV, confidence badges, and summary statistics.

    Args:
        picks: List of Pick objects from edge detection pipeline, or None/empty
        fixtures_map: Optional mapping of fixture_id to Fixture objects for enhanced formatting

    Returns:
        Formatted table string ready for terminal display

    Example:
        >>> picks = [pick1, pick2, pick3]
        >>> output = format_picks_for_display(picks)
        >>> print(output)
        # Displays formatted table with picks, colors, and summary

        >>> output = format_picks_for_display([])
        >>> print(output)
        # Displays "No profitable picks" message
    """
    # Handle empty or None input
    if not picks:
        message = f"{NO_PICKS_MESSAGE}\n\nAll analyzed fixtures had EV below your threshold or insufficient data quality"
        panel = Panel(
            message,
            border_style="blue",
            padding=(1, 2),
        )
        # Render to string using console
        console = Console()
        with console.capture() as capture:
            console.print(panel)
        return capture.get()

    # Create Rich table
    table = Table(
        title="🎯 Betting Picks Summary",
        box=ROUNDED,
        padding=(0, 1),
        show_header=True,
        header_style="bold cyan",
    )

    # Add columns with proper alignment
    table.add_column("Fixture", style="white", no_wrap=False)
    table.add_column("Market", style="cyan", no_wrap=True)
    table.add_column("AI Prob", justify="right", style="white")
    table.add_column("Implied Prob", justify="right", style="white")
    table.add_column("EV", justify="right", no_wrap=True)
    table.add_column("Confidence", justify="center", no_wrap=True)
    table.add_column("Stake", justify="right", no_wrap=True)

    # Add rows for each pick
    for pick in picks:
        fixture_cell = _format_fixture_cell(pick, fixtures_map)
        market_cell = pick.market
        ai_prob_cell = _format_probability_cell(pick.ai_probability)
        implied_prob_cell = _format_probability_cell(pick.implied_probability)
        ev_cell = _format_ev_cell(pick.ev_percentage)
        confidence_cell = _format_confidence_cell(pick.confidence)
        stake_cell = _format_stake_cell(pick.recommended_stake)

        table.add_row(
            fixture_cell,
            market_cell,
            ai_prob_cell,
            implied_prob_cell,
            ev_cell,
            confidence_cell,
            stake_cell,
        )

    # Calculate statistics
    stats = _calculate_statistics(picks)

    # Build summary footer
    summary_text = (
        f"📊 Summary: {stats['total_picks']} picks | "
        f"Avg EV: [green]+{stats['avg_ev']:.1f}%[/green] | "
        f"Avg Confidence: {stats['avg_confidence']}% | "
        f"Total Stake: [green]${stats['total_stake']:,.2f}[/green]\n"
        f"EV Range: +{stats['min_ev']:.1f}% to +{stats['max_ev']:.1f}%"
    )

    # Render table and footer using Rich console
    console = Console()
    with console.capture() as capture:
        console.print(table)
        console.print()  # Blank line
        console.print(summary_text)

    return capture.get()
