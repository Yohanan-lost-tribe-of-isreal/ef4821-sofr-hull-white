"""Model-free cap-floor parity calculations."""

from sofr_hw.interfaces import YieldCurve


def cap_floor_parity_value(
    cap_price: float,
    floor_price: float,
    strike: float,
    annuity: float,
    forward_swap_rate: float,
) -> float:
    """Return the parity residual C-F-A(F-K) for unit notional.

    The model-free identity is ``C-F=A(F-K)`` for matched cap/floor terms.
    Prices are per $1 notional, and rates, strikes, and annuity are decimals/year.
    """
    raise NotImplementedError("TODO (Sean): implement model-free parity residual")


def cap_floor_parity_from_curve(
    cap_price: float, floor_price: float, strike: float, curve: YieldCurve
) -> float:
    """Evaluate the cap-floor parity residual using curve-implied forward and annuity."""
    raise NotImplementedError("TODO (Sean): implement curve-based parity check")
