"""Recombining Hull-White short-rate tree pricing interface."""

from sofr_hw.interfaces import HullWhiteParams, YieldCurve
from sofr_hw.pricing.instruments import CapFloorSchedule


def price_capfloor_tree(
    schedule: CapFloorSchedule,
    curve: YieldCurve,
    params: HullWhiteParams,
    time_steps_per_year: int = 48,
) -> float:
    """Price a cap or floor per $1 notional using a curve-fitted trinomial tree.

    The lattice is calibrated at each time step to reproduce market discount
    factors, with transitions under risk-neutral pricing probabilities.
    """
    raise NotImplementedError("TODO (Sean): implement Hull-White tree pricing")
