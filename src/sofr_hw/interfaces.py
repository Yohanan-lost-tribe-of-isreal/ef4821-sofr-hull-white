"""Stable contracts shared across curve, pricing, and model implementations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol, TypeAlias, runtime_checkable


@runtime_checkable
class YieldCurve(Protocol):
    """Market discount curve exposed through discount and C²-forward tiers.

    All time arguments are year fractions from ``valuation_date``. Discount
    factors are ``P^mkt(0, t)``; the instantaneous forward is
    ``-d/dt ln(P^mkt(0, t))`` and must be C²-smooth over the supported domain.
    """

    @property
    def valuation_date(self) -> date:
        """Date on which the curve is valued."""

    @property
    def max_maturity(self) -> float:
        """Largest supported year-fraction maturity."""

    def df(self, t: float) -> float:
        """Return the market discount factor P^mkt(0, t)."""

    def zero_rate(self, t: float) -> float:
        """Return the continuously compounded zero rate in decimal units."""

    def inst_forward(self, t: float) -> float:
        """Return the C²-smooth instantaneous forward in decimal units."""

    def simple_forward(self, t1: float, t2: float) -> float:
        """Return the simple-compounded forward over [t1, t2] in decimal units."""


OptionType: TypeAlias = Literal["cap", "floor"]
Moneyness: TypeAlias = Literal["ATM", "ITM", "OTM"]


@dataclass(frozen=True)
class HullWhiteParams:
    """Constant-parameter Hull-White model with time-varying drift theta(t)."""

    kappa: float
    sigma: float

    def __post_init__(self) -> None:
        """Require strictly positive finite mean reversion and volatility."""
        if not math.isfinite(self.kappa) or self.kappa <= 0.0:
            raise ValueError("kappa must be finite and strictly positive")
        if not math.isfinite(self.sigma) or self.sigma <= 0.0:
            raise ValueError("sigma must be finite and strictly positive")


@dataclass(frozen=True)
class CapFloorQuote:
    """A cap/floor volatility quote; rates, strikes, and volatilities are decimals."""

    maturity: float
    strike: float
    volatility: float
    option_type: OptionType
    is_atm: bool
    quote_id: str
    moneyness: Moneyness = "ATM"

    def __post_init__(self) -> None:
        """Validate the quote's units, domain, and option identity."""
        if not math.isfinite(self.maturity) or self.maturity <= 0.0:
            raise ValueError("maturity must be finite and strictly positive")
        if not math.isfinite(self.strike):
            raise ValueError("strike must be finite")
        if not math.isfinite(self.volatility) or self.volatility <= 0.0:
            raise ValueError("volatility must be finite and strictly positive")
        if self.option_type not in ("cap", "floor"):
            raise ValueError("option_type must be 'cap' or 'floor'")
        if self.moneyness not in ("ATM", "ITM", "OTM"):
            raise ValueError("moneyness must be 'ATM', 'ITM', or 'OTM'")
        if self.is_atm != (self.moneyness == "ATM"):
            raise ValueError("is_atm must agree with the moneyness label")
        if not self.quote_id:
            raise ValueError("quote_id must be non-empty")


@dataclass(frozen=True)
class CalibrationSet:
    """The only quote container accepted by the in-sample calibration API."""

    quotes: tuple[CapFloorQuote, ...]

    def __post_init__(self) -> None:
        """Freeze quote sequences and enforce the minimum calibration sample size."""
        frozen_quotes = tuple(self.quotes)
        if len(frozen_quotes) < 2:
            raise ValueError("CalibrationSet requires at least two quotes")
        if len({quote.quote_id for quote in frozen_quotes}) != len(frozen_quotes):
            raise ValueError("CalibrationSet quote_id values must be unique")
        object.__setattr__(self, "quotes", frozen_quotes)


QuotePair: TypeAlias = tuple[CapFloorQuote, CapFloorQuote]


@dataclass(frozen=True)
class CalibrationTestSplit:
    """Disjoint calibration and out-of-sample quote buckets plus parity pairs."""

    calibration: CalibrationSet
    oos_term_structure: tuple[CapFloorQuote, ...]
    oos_moneyness: tuple[CapFloorQuote, ...]
    parity_pairs: tuple[QuotePair, ...]

    def __post_init__(self) -> None:
        """Freeze buckets and reject any quote leakage between primary buckets."""
        term_structure = tuple(self.oos_term_structure)
        moneyness = tuple(self.oos_moneyness)
        pairs = tuple(tuple(pair) for pair in self.parity_pairs)
        calibration_ids = {quote.quote_id for quote in self.calibration.quotes}
        term_ids = {quote.quote_id for quote in term_structure}
        moneyness_ids = {quote.quote_id for quote in moneyness}
        if calibration_ids & term_ids or calibration_ids & moneyness_ids:
            raise ValueError("Calibration quotes must be disjoint from OOS buckets")
        if term_ids & moneyness_ids:
            raise ValueError("OOS term-structure and moneyness buckets must be disjoint")
        if any(len(pair) != 2 for pair in pairs):
            raise ValueError("Each parity pair must contain exactly two quotes")
        for pair in pairs:
            if {quote.option_type for quote in pair} != {"cap", "floor"}:
                raise ValueError("Each parity pair must contain one cap and one floor")
            if pair[0].maturity != pair[1].maturity or pair[0].strike != pair[1].strike:
                raise ValueError("Parity pair quotes must have matching maturity and strike")
        object.__setattr__(self, "oos_term_structure", term_structure)
        object.__setattr__(self, "oos_moneyness", moneyness)
        object.__setattr__(self, "parity_pairs", pairs)
