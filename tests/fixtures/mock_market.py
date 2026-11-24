"""Deterministic market double fixtures for parallel development."""

import math
from datetime import date

import numpy as np
import pandas as pd

from sofr_hw.interfaces import CapFloorQuote, YieldCurve


class NelsonSiegelMockCurve:
    """Nelson-Siegel mock curve with a closed-form instantaneous forward."""

    def __init__(
        self,
        valuation_date: date = date(2026, 9, 30),
        max_maturity: float = 30.0,
        beta0: float = 0.035,
        beta1: float = -0.012,
        beta2: float = 0.018,
        tau: float = 2.5,
    ) -> None:
        """Initialize fixed Nelson-Siegel parameters in decimal-rate units."""
        self._valuation_date = valuation_date
        self._max_maturity = max_maturity
        self.beta0 = beta0
        self.beta1 = beta1
        self.beta2 = beta2
        self.tau = tau

    @property
    def valuation_date(self) -> date:
        """Return the mock valuation date."""
        return self._valuation_date

    @property
    def max_maturity(self) -> float:
        """Return the mock curve's maximum supported maturity."""
        return self._max_maturity

    def _validate_time(self, t: float) -> None:
        if not 0.0 <= t <= self.max_maturity:
            raise ValueError(f"maturity must be in [0, {self.max_maturity}]")

    def zero_rate(self, t: float) -> float:
        """Return the Nelson-Siegel continuously compounded zero rate."""
        self._validate_time(t)
        if t == 0.0:
            return self.beta0 + self.beta1
        x = t / self.tau
        decay = math.exp(-x)
        factor = -math.expm1(-x) / x
        return self.beta0 + self.beta1 * factor + self.beta2 * (factor - decay)

    def df(self, t: float) -> float:
        """Return exp(-zero_rate(t)*t), with P(0,0)=1."""
        self._validate_time(t)
        return math.exp(-self.zero_rate(t) * t)

    def inst_forward(self, t: float) -> float:
        """Return the exact Nelson-Siegel instantaneous forward."""
        self._validate_time(t)
        x = t / self.tau
        decay = math.exp(-x)
        return self.beta0 + self.beta1 * decay + self.beta2 * x * decay

    def simple_forward(self, t1: float, t2: float) -> float:
        """Return the simple-compounded forward derived from discount factors."""
        self._validate_time(t1)
        self._validate_time(t2)
        if t2 <= t1:
            raise ValueError("t2 must be greater than t1")
        return (self.df(t1) / self.df(t2) - 1.0) / (t2 - t1)


def generate_synthetic_zero_panel(n_days: int = 820) -> pd.DataFrame:
    """Return a deterministic three-factor daily zero-yield panel in decimals."""
    if n_days < 2:
        raise ValueError("n_days must be at least 2")
    maturities = np.array([0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0])
    dates = pd.bdate_range(end="2026-09-30", periods=n_days, name="date")
    time = np.arange(n_days, dtype=float)
    level = 0.0008 * np.sin(time * 0.071) + 0.00025 * np.cos(time * 0.019)
    slope = 0.00055 * np.sin(time * 0.037 + 0.8)
    curvature = 0.00035 * np.cos(time * 0.053 - 0.4)
    normalized = maturities / 5.0
    level_loading = np.ones_like(maturities)
    slope_loading = np.exp(-normalized / 3.0) - 0.35
    curvature_loading = normalized * np.exp(-normalized / 1.5) - 0.18
    baseline = 0.032 + 0.002 * np.log1p(maturities)
    panel = (
        baseline[None, :]
        + level[:, None] * level_loading[None, :]
        + slope[:, None] * slope_loading[None, :]
        + curvature[:, None] * curvature_loading[None, :]
    )
    return pd.DataFrame(panel, index=dates, columns=maturities)


def generate_synthetic_2d_vcub_quotes(
    curve: YieldCurve,
) -> list[CapFloorQuote]:
    """Return a deterministic maturity/strike surface with skew and a vol hump."""
    maturities = (1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0, 15.0, 20.0)
    quotes: list[CapFloorQuote] = []
    for maturity in maturities:
        atm = curve.simple_forward(0.0, maturity)
        hump = math.exp(-((maturity - 7.0) / 5.0) ** 2)
        base_vol = 0.0065 + 0.0035 * hump + 0.000025 * maturity
        strikes = (
            ("ATM", atm, 0.0),
            ("ITM", atm - 0.005, -0.0006),
            ("OTM", atm + 0.005, 0.0009),
        )
        for moneyness, strike, skew in strikes:
            for option_type in ("cap", "floor"):
                option_skew = skew if option_type == "cap" else -skew * 0.7
                volatility = base_vol + abs(strike - atm) * 0.16 + option_skew
                quote_id = f"{option_type}-{moneyness}-{maturity:g}"
                quotes.append(
                    CapFloorQuote(
                        maturity=maturity,
                        strike=strike,
                        volatility=volatility,
                        option_type=option_type,
                        is_atm=moneyness == "ATM",
                        quote_id=quote_id,
                        moneyness=moneyness,
                    )
                )
    return quotes
