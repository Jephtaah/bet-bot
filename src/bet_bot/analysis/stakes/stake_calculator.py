"""Stake calculation for recommended bet sizing based on edge and confidence."""

import logging

logger = logging.getLogger(__name__)


def calculate_stake(
    bankroll: float,
    ev_percentage: float,
    confidence: int,
) -> dict[str, float]:
    """
    Calculate recommended stake using Kelly Criterion-inspired formula.

    Implements conservative stake sizing to prevent overexposure on marginal picks.
    Uses formula: stake = bankroll × (EV_pct × 0.01 × 0.1) × (confidence / 100)

    The 0.1 multiplier acts as a conservative scaling factor:
    - EV_pct × 0.01 converts percentage (0-100) to decimal (0-1)
    - × 0.1 applies conservative edge multiplier to prevent overbetting
    - × (confidence / 100) scales by confidence (0-1 range)

    Args:
        bankroll: Total betting bankroll in currency units (must be > 0)
        ev_percentage: Expected value as percentage (0-100, e.g., 5.2 for 5.2% EV)
        confidence: Confidence score (0-100, e.g., 72 for 72% confidence)

    Returns:
        Dictionary with three float values:
        - suggested_stake: Recommended bet amount in currency units
        - stake_in_units: Stake expressed in units (1 unit = bankroll / 200)
        - bankroll_percentage: Stake as percentage of bankroll

    Raises:
        ValueError: If bankroll <= 0, ev_percentage < 0, or confidence not in [0, 100]

    Examples:
        >>> stake_info = calculate_stake(1000.0, 5.0, 80)
        >>> stake_info["suggested_stake"]
        4.0
        >>> stake_info["stake_in_units"]
        0.4

        >>> stake_info = calculate_stake(1000.0, 10.0, 90)
        >>> stake_info["suggested_stake"]
        9.0

        >>> stake_info = calculate_stake(500.0, 5.0, 80)
        >>> stake_info["suggested_stake"]
        2.0

    Note:
        Stake is clamped to maximum 5% of bankroll as a safety measure to prevent
        excessive exposure on single picks. Ensures variance can be absorbed.

        Unit sizing standard: 1 unit = bankroll / 200. This conservative sizing
        allows approximately 200 picks at full stake before bankruptcy.

        Minimum stake: $0.01 to prevent zero-dollar suggestions.
    """
    # Input validation
    if bankroll <= 0:
        raise ValueError(f"Bankroll must be positive, got {bankroll}")
    if ev_percentage < 0:
        raise ValueError(f"EV percentage must be non-negative, got {ev_percentage}")
    if not 0 <= confidence <= 100:
        raise ValueError(f"Confidence must be in [0, 100], got {confidence}")

    # Calculate base stake using formula: bankroll × (EV_pct × 0.01 × 0.1) × (confidence / 100)
    stake = bankroll * (ev_percentage * 0.01 * 0.1) * (confidence / 100)

    # Log calculation details
    logger.debug(
        f"Stake calculation: bankroll={bankroll}, EV={ev_percentage}%, confidence={confidence}%",
        extra={
            "bankroll": bankroll,
            "ev_percentage": ev_percentage,
            "confidence": confidence,
            "calculated_stake": stake,
        },
    )

    # Apply clamping: max stake = 5% of bankroll
    max_stake = bankroll * 0.05
    if stake > max_stake:
        logger.debug(
            f"Stake {stake:.2f} exceeds max 5% ({max_stake:.2f}), clamping",
            extra={"ev": ev_percentage, "confidence": confidence, "bankroll": bankroll},
        )
        stake = max_stake

    # Log warnings for edge cases
    if confidence < 50:
        logger.warning(
            f"Low confidence pick (confidence={confidence}%)",
            extra={"confidence": confidence, "stake": stake},
        )
    if ev_percentage < 2:
        logger.warning(
            f"Minimal edge detected (EV={ev_percentage}%)",
            extra={"ev_percentage": ev_percentage, "stake": stake},
        )

    # Ensure minimum stake of $0.01
    stake = max(stake, 0.01)

    # Calculate unit sizing: 1 unit = bankroll / 200
    unit_size = bankroll / 200
    stake_in_units = stake / unit_size

    # Calculate bankroll percentage
    bankroll_percentage = (stake / bankroll) * 100

    # Log final result
    logger.info(
        f"Stake calculated: {stake:.2f} ({stake_in_units:.3f} units, {bankroll_percentage:.2f}% of bankroll)",
        extra={
            "stake": stake,
            "stake_in_units": stake_in_units,
            "bankroll_percentage": bankroll_percentage,
        },
    )

    return {
        "suggested_stake": stake,
        "stake_in_units": stake_in_units,
        "bankroll_percentage": bankroll_percentage,
    }
