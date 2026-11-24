"""SOFR caplet, cap, and floor instrument definitions."""

from collections.abc import Sequence
from dataclasses import dataclass

from sofr_hw.interfaces import YieldCurve


@dataclass(frozen=True)
class CapFloorSchedule:
    """Reset/payment schedule with decimal strike and year-fraction accruals."""

    reset_times: tuple[float, ...]
    payment_times: tuple[float, ...]
    accrual_fractions: tuple[float, ...]
    strike: float
    option_type: str


def capfloor_cashflows(
    schedule: CapFloorSchedule, curve: YieldCurve, forwards: Sequence[float]
) -> tuple[float, ...]:
    """Return discounted expected floating-leg option cashflows per $1 notional.

    A caplet amount is ``delta * max(L-K,0)``; a floorlet is
    ``delta * max(K-L,0)``. All rates and strikes are decimal-valued.
    """
    raise NotImplementedError("TODO (Oliver): implement cap/floor cashflows")
