"""Concrete market curve adapting spline functions to the YieldCurve contract."""

from datetime import date

from sofr_hw.interfaces import YieldCurve


class CubicSplineYieldCurve:
    """YieldCurve backed by a C² log-discount cubic spline."""

    def __init__(self, valuation_date: date, max_maturity: float, log_discount_spline: object):
        """Store the valuation date, supported horizon, and fitted spline."""
        raise NotImplementedError("TODO (Oliver): initialize the spline-backed curve")

    @property
    def valuation_date(self) -> date:
        """Return the curve valuation date."""
        raise NotImplementedError("TODO (Oliver): expose valuation date")

    @property
    def max_maturity(self) -> float:
        """Return the maximum supported year-fraction maturity."""
        raise NotImplementedError("TODO (Oliver): expose maximum maturity")

    def df(self, t: float) -> float:
        """Return P^mkt(0,t), requiring 0 <= t <= max_maturity."""
        raise NotImplementedError("TODO (Oliver): evaluate discount factor")

    def zero_rate(self, t: float) -> float:
        """Return the continuously compounded zero rate in decimal units."""
        raise NotImplementedError("TODO (Oliver): evaluate zero rate")

    def inst_forward(self, t: float) -> float:
        """Return -d/dt ln P^mkt(0,t), smooth through second order."""
        raise NotImplementedError("TODO (Oliver): evaluate instantaneous forward")

    def simple_forward(self, t1: float, t2: float) -> float:
        """Return (P(0,t1)/P(0,t2)-1)/(t2-t1) for t2 > t1."""
        raise NotImplementedError("TODO (Oliver): evaluate simple forward")


def require_yield_curve(curve: YieldCurve) -> YieldCurve:
    """Validate and return an object conforming to the shared curve protocol."""
    raise NotImplementedError("TODO (Oliver): validate curve implementation")
