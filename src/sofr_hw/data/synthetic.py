"""Synthetic SOFR market data with a known ground truth.

This module produces stand-in data that has the *same layout* as the real
Bloomberg exports, so downstream code can be developed now and switched to the
real files later by changing only the input path:

* ``usosfr_history.csv`` -- daily SOFR OIS par swap rates (percent), 1M..30Y,
  3 Jul 2023 .. 30 Sep 2026 (US business days), mimicking ``USOSFR*`` Curncy.
* ``vcub_<date>.csv`` -- a cap/floor normal-vol surface on the valuation date,
  mimicking a ``VCUB`` export (maturity x strike, caps and floors).

Unlike the real data, the generating parameters are known and written to
``truth.yaml`` / ``truth_*.csv`` so each stage can be checked against them:

* Curve history: daily Nelson-Siegel factors follow a mean-reverting process
  around a drift path, plus small per-tenor zero-yield noise (so PCA finds
  three dominant factors but not 100% of variance). The valuation date is
  noise-free, so a correct bootstrap reproduces the truth curve.
* Vol surface: ATM cap vols are generated *exactly* from a one-factor
  Hull-White model with known (kappa, sigma), so a correct calibration on the
  ATM caps recovers them. Off-ATM vols add a smile that Hull-White cannot
  produce, so out-of-sample strike errors behave like they would on real data.
* Caps and floors at the same strike share one vol (as in VCUB), so
  cap-floor parity holds exactly by construction.

Conventions (simplified, matching the course single-curve setup): annual
fixed/floating OIS for tenors >= 1Y, single-period simple rate below 1Y,
year fractions instead of day counts, quarterly forward-looking caplets with
the first (already-fixed) caplet excluded. All internal values are decimals.

Nothing produced here may be used for results in the report.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay
from scipy.optimize import brentq
from scipy.stats import norm

from sofr_hw.interfaces import CapFloorQuote, Moneyness, OptionType

# ---------------------------------------------------------------------------
# Tenor grids (labels are the column names of the real export after renaming
# Bloomberg tickers, e.g. USOSFRC Curncy -> "3M", USOSFR10 Curncy -> "10Y").
# ---------------------------------------------------------------------------

SWAP_TENORS: dict[str, float] = {
    "1M": 1 / 12,
    "3M": 0.25,
    "6M": 0.5,
    "9M": 0.75,
    "1Y": 1.0,
    "2Y": 2.0,
    "3Y": 3.0,
    "4Y": 4.0,
    "5Y": 5.0,
    "6Y": 6.0,
    "7Y": 7.0,
    "8Y": 8.0,
    "9Y": 9.0,
    "10Y": 10.0,
    "12Y": 12.0,
    "15Y": 15.0,
    "20Y": 20.0,
    "25Y": 25.0,
    "30Y": 30.0,
}

VCUB_MATURITIES: tuple[float, ...] = (
    1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 15.0, 20.0, 25.0, 30.0,
)
VCUB_STRIKE_OFFSETS_BP: tuple[int, ...] = (-100, -50, 0, 50, 100)

# Knots for per-tenor zero-yield noise (piecewise-linear in maturity).
_NOISE_KNOTS = np.array([1 / 12, 0.25, 0.5, 0.75] + [float(y) for y in range(1, 31)])


# ---------------------------------------------------------------------------
# Ground-truth configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SyntheticConfig:
    """All knobs of the synthetic market; written verbatim to ``truth.yaml``."""

    seed: int = 4821
    history_start: str = "2023-07-03"
    valuation_date: str = "2026-09-30"
    # Nelson-Siegel (beta0=long, beta1=short-long, beta2=hump), decimals.
    ns_tau: float = 2.0
    ns_start: tuple[float, float, float] = (0.036, 0.017, -0.012)  # short ~5.3%
    ns_end: tuple[float, float, float] = (0.041, -0.007, -0.004)  # short ~3.4%
    ns_daily_vol: tuple[float, float, float] = (0.0003, 0.0004, 0.0007)
    ns_corr: tuple[float, float, float] = (-0.4, 0.0, 0.2)  # (b0,b1), (b0,b2), (b1,b2)
    ns_reversion_days: float = 60.0
    zero_noise_bp: float = 0.4
    # Hull-White ground truth for the vol surface.
    hw_kappa: float = 0.03
    hw_sigma: float = 0.0085
    capfloor_accrual_dt: float = 0.25
    # Smile added to off-ATM vols: a*|K-ATM| + b*(K-ATM)  (vol in decimals).
    smile_convexity: float = 0.10
    smile_skew: float = -0.04
    # Optional realism for ATM vols (0 => ATM vols are exactly Hull-White).
    atm_hump_bp: float = 0.0
    vol_noise_bp: float = 0.0
    maturities: tuple[float, ...] = field(default=VCUB_MATURITIES)
    strike_offsets_bp: tuple[int, ...] = field(default=VCUB_STRIKE_OFFSETS_BP)


# ---------------------------------------------------------------------------
# Nelson-Siegel curve helpers
# ---------------------------------------------------------------------------


def ns_zero(t: np.ndarray | float, b0: float, b1: float, b2: float, tau: float) -> np.ndarray:
    """Continuously compounded Nelson-Siegel zero rate (vectorised, t>=0)."""
    t = np.asarray(t, dtype=float)
    x = np.where(t > 0, t / tau, 1e-12)
    factor = -np.expm1(-x) / x
    return b0 + b1 * factor + b2 * (factor - np.exp(-x))


def ns_inst_forward(
    t: np.ndarray | float, b0: float, b1: float, b2: float, tau: float
) -> np.ndarray:
    """Instantaneous forward of the Nelson-Siegel curve."""
    x = np.asarray(t, dtype=float) / tau
    return b0 + b1 * np.exp(-x) + b2 * x * np.exp(-x)


class TruthCurve:
    """Smooth Nelson-Siegel curve satisfying the ``YieldCurve`` protocol."""

    def __init__(
        self,
        valuation_date: date,
        betas: Sequence[float],
        tau: float,
        max_maturity: float = 30.0,
    ) -> None:
        self._valuation_date = valuation_date
        self._betas = tuple(float(b) for b in betas)
        self._tau = float(tau)
        self._max_maturity = float(max_maturity)

    @property
    def valuation_date(self) -> date:
        return self._valuation_date

    @property
    def max_maturity(self) -> float:
        return self._max_maturity

    def _check(self, t: float) -> None:
        if not 0.0 <= t <= self._max_maturity + 1e-12:
            raise ValueError(f"maturity must be in [0, {self._max_maturity}]")

    def zero_rate(self, t: float) -> float:
        self._check(t)
        return float(ns_zero(t, *self._betas, self._tau))

    def df(self, t: float) -> float:
        self._check(t)
        return 1.0 if t == 0.0 else math.exp(-self.zero_rate(t) * t)

    def inst_forward(self, t: float) -> float:
        self._check(t)
        return float(ns_inst_forward(t, *self._betas, self._tau))

    def simple_forward(self, t1: float, t2: float) -> float:
        if t2 <= t1:
            raise ValueError("t2 must be greater than t1")
        return (self.df(t1) / self.df(t2) - 1.0) / (t2 - t1)


# ---------------------------------------------------------------------------
# Curve history simulation
# ---------------------------------------------------------------------------


def business_days(start: str, end: str) -> pd.DatetimeIndex:
    """US business days (federal holidays removed), roughly the SOFR calendar."""
    cbd = CustomBusinessDay(calendar=USFederalHolidayCalendar())
    return pd.date_range(start=start, end=end, freq=cbd, name="date")


def simulate_ns_factors(cfg: SyntheticConfig, rng: np.random.Generator) -> pd.DataFrame:
    """Daily (beta0, beta1, beta2): mean-reverting around a linear drift path."""
    dates = business_days(cfg.history_start, cfg.valuation_date)
    n = len(dates)
    start, end = np.array(cfg.ns_start), np.array(cfg.ns_end)
    target = start + np.linspace(0.0, 1.0, n)[:, None] * (end - start)
    vols = np.array(cfg.ns_daily_vol)
    r01, r02, r12 = cfg.ns_corr
    corr = np.array([[1.0, r01, r02], [r01, 1.0, r12], [r02, r12, 1.0]])
    chol = np.linalg.cholesky(corr * np.outer(vols, vols))
    speed = 1.0 / cfg.ns_reversion_days
    betas = np.empty((n, 3))
    betas[0] = start
    shocks = rng.standard_normal((n, 3)) @ chol.T
    for i in range(1, n):
        betas[i] = betas[i - 1] + speed * (target[i] - betas[i - 1]) + shocks[i]
    # Land exactly on the configured end curve so the valuation date is known.
    drift_fix = np.linspace(0.0, 1.0, n)[:, None] * (end - betas[-1])
    betas = betas + drift_fix
    return pd.DataFrame(betas, index=dates, columns=["beta0", "beta1", "beta2"])


def _zero_curve_matrix(
    factors: pd.DataFrame, noise: np.ndarray, tau: float, maturities: np.ndarray
) -> np.ndarray:
    """Zero yields (rows=dates, cols=maturities) = NS + interpolated noise."""
    b = factors.to_numpy()
    base = np.stack([ns_zero(maturities, *row, tau) for row in b])
    noise_at = np.stack([np.interp(maturities, _NOISE_KNOTS, row) for row in noise])
    return base + noise_at


def par_swap_rates_from_zero(zero_fn, tenors: Sequence[float]) -> np.ndarray:
    """Par OIS rates for one date. ``zero_fn(t_array)`` returns zero rates.

    Below 1Y: single-period simple rate (1/P - 1)/T.
    1Y and above: annual fixed vs annual floating, S = (1-P(T)) / sum_i P(i).
    """
    out = []
    for t in tenors:
        if t < 1.0 - 1e-12:
            p = math.exp(-float(zero_fn(np.array([t]))[0]) * t)
            out.append((1.0 / p - 1.0) / t)
        else:
            n = int(round(t))
            grid = np.arange(1, n + 1, dtype=float)
            dfs = np.exp(-zero_fn(grid) * grid)
            out.append((1.0 - dfs[-1]) / dfs.sum())
    return np.array(out)


def simulate_curve_history(
    cfg: SyntheticConfig, rng: np.random.Generator
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (swap_rates_pct, truth_zero_yields_decimal, ns_factors)."""
    factors = simulate_ns_factors(cfg, rng)
    n = len(factors)
    noise = rng.standard_normal((n, len(_NOISE_KNOTS))) * cfg.zero_noise_bp * 1e-4
    noise[-1] = 0.0  # valuation date is noise-free => equals TruthCurve exactly
    tenors = np.array(list(SWAP_TENORS.values()))

    swap_rows = []
    for i, row in enumerate(factors.to_numpy()):
        noise_row = noise[i]

        def zero_fn(t: np.ndarray, row=row, noise_row=noise_row) -> np.ndarray:
            return ns_zero(t, *row, cfg.ns_tau) + np.interp(t, _NOISE_KNOTS, noise_row)

        swap_rows.append(par_swap_rates_from_zero(zero_fn, tenors))
    swaps = pd.DataFrame(
        np.round(np.array(swap_rows) * 100.0, 5), index=factors.index, columns=list(SWAP_TENORS)
    )
    zeros = pd.DataFrame(
        _zero_curve_matrix(factors, noise, cfg.ns_tau, tenors),
        index=factors.index,
        columns=list(SWAP_TENORS),
    )
    return swaps, zeros, factors


# ---------------------------------------------------------------------------
# Hull-White and Bachelier cap/floor pricing
# ---------------------------------------------------------------------------


def capfloor_schedule(maturity: float, dt: float) -> tuple[np.ndarray, np.ndarray]:
    """Reset and payment times, first caplet (fixed at t=0) excluded."""
    n = int(round(maturity / dt))
    pay = dt * np.arange(2, n + 1, dtype=float)
    return pay - dt, pay


def atm_strike(curve, maturity: float, dt: float) -> float:
    """Forward swap rate over the cap's caplet periods (the ATM strike)."""
    resets, pays = capfloor_schedule(maturity, dt)
    dfs = np.array([curve.df(t) for t in pays])
    return (curve.df(resets[0]) - dfs[-1]) / (dt * dfs.sum())


def hw_capfloor_price(
    curve, kappa: float, sigma: float, strike: float, maturity: float, dt: float, option_type: str
) -> float:
    """One-factor Hull-White cap/floor price per $1 notional (ZCB-option formula).

    caplet = (1+K dt) * ZBP(0, S, T, X=1/(1+K dt)); floorlet uses ZBC.
    sigma_p = sigma * sqrt((1-exp(-2 kappa S)) / (2 kappa)) * B(S, T).
    """
    resets, pays = capfloor_schedule(maturity, dt)
    x = 1.0 / (1.0 + strike * dt)
    total = 0.0
    for s, t in zip(resets, pays):
        p_s, p_t = curve.df(s), curve.df(t)
        b = (1.0 - math.exp(-kappa * (t - s))) / kappa
        sig_p = sigma * math.sqrt((1.0 - math.exp(-2.0 * kappa * s)) / (2.0 * kappa)) * b
        h = math.log(p_t / (p_s * x)) / sig_p + 0.5 * sig_p
        if option_type == "cap":
            zb = x * p_s * norm.cdf(-h + sig_p) - p_t * norm.cdf(-h)
        else:
            zb = p_t * norm.cdf(h) - x * p_s * norm.cdf(h - sig_p)
        total += (1.0 + strike * dt) * zb
    return total


def bachelier_capfloor_price(
    curve, normal_vol: float, strike: float, maturity: float, dt: float, option_type: str
) -> float:
    """Cap/floor price per $1 notional using one flat normal (bp) vol."""
    resets, pays = capfloor_schedule(maturity, dt)
    total = 0.0
    for s, t in zip(resets, pays):
        p_t = curve.df(t)
        fwd = (curve.df(s) / p_t - 1.0) / dt
        sd = normal_vol * math.sqrt(s)
        d = (fwd - strike) / sd
        if option_type == "cap":
            payoff = (fwd - strike) * norm.cdf(d) + sd * norm.pdf(d)
        else:
            payoff = (strike - fwd) * norm.cdf(-d) + sd * norm.pdf(d)
        total += dt * p_t * payoff
    return total


def implied_flat_normal_vol(
    curve, price: float, strike: float, maturity: float, dt: float, option_type: str
) -> float:
    """Invert a cap/floor price to a flat normal vol (decimal)."""

    def objective(v: float) -> float:
        return bachelier_capfloor_price(curve, v, strike, maturity, dt, option_type) - price

    return brentq(objective, 1e-6, 0.2, xtol=1e-14, maxiter=200)


# ---------------------------------------------------------------------------
# VCUB surface
# ---------------------------------------------------------------------------


def moneyness_label(option_type: str, offset_bp: int) -> Moneyness:
    """Caps are ITM below ATM; floors are ITM above ATM."""
    if offset_bp == 0:
        return "ATM"
    below = offset_bp < 0
    if option_type == "cap":
        return "ITM" if below else "OTM"
    return "OTM" if below else "ITM"


def quote_id(option_type: str, maturity: float, offset_bp: int) -> str:
    return f"{option_type}-{maturity:g}Y-{offset_bp:+04d}bp"


def build_vcub_surface(
    cfg: SyntheticConfig, curve: TruthCurve, rng: np.random.Generator
) -> pd.DataFrame:
    """VCUB-style rows: one normal vol per (maturity, strike), shared by cap & floor."""
    dt = cfg.capfloor_accrual_dt
    rows = []
    for maturity in cfg.maturities:
        k_atm = atm_strike(curve, maturity, dt)
        hump = cfg.atm_hump_bp * 1e-4 * math.exp(-(((maturity - 5.0) / 4.0) ** 2))
        for offset in cfg.strike_offsets_bp:
            strike = k_atm + offset * 1e-4
            # HW vol at this strike (cap price -> flat normal vol; floor gives same).
            hw_price = hw_capfloor_price(
                curve, cfg.hw_kappa, cfg.hw_sigma, strike, maturity, dt, "cap"
            )
            hw_vol = implied_flat_normal_vol(curve, hw_price, strike, maturity, dt, "cap")
            m = strike - k_atm
            smile = cfg.smile_convexity * abs(m) + cfg.smile_skew * m
            noise = cfg.vol_noise_bp * 1e-4 * rng.standard_normal() if cfg.vol_noise_bp else 0.0
            vol = hw_vol + hump + smile + noise
            for option_type in ("cap", "floor"):
                premium = bachelier_capfloor_price(curve, vol, strike, maturity, dt, option_type)
                rows.append(
                    {
                        "valuation_date": cfg.valuation_date,
                        "quote_id": quote_id(option_type, maturity, offset),
                        "option_type": option_type,
                        "maturity_years": maturity,
                        "strike_offset_bp": offset,
                        "strike_pct": round(strike * 100.0, 6),
                        "atm_strike_pct": round(k_atm * 100.0, 6),
                        "moneyness": moneyness_label(option_type, offset),
                        "normal_vol_bp": round(vol * 1e4, 4),
                        "premium_bp": round(premium * 1e4, 4),
                        "hw_model_vol_bp": round(hw_vol * 1e4, 4),
                    }
                )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Orchestration and loaders
# ---------------------------------------------------------------------------


def truth_valuation_curve(cfg: SyntheticConfig | None = None) -> TruthCurve:
    """The exact curve on the valuation date (what a correct bootstrap recovers)."""
    cfg = cfg or SyntheticConfig()
    return TruthCurve(date.fromisoformat(cfg.valuation_date), cfg.ns_end, cfg.ns_tau)


def generate_synthetic_market(cfg: SyntheticConfig | None = None) -> dict[str, pd.DataFrame]:
    """Build every synthetic table deterministically from ``cfg.seed``."""
    cfg = cfg or SyntheticConfig()
    rng = np.random.default_rng(cfg.seed)
    swaps, zeros, factors = simulate_curve_history(cfg, rng)
    vcub = build_vcub_surface(cfg, truth_valuation_curve(cfg), rng)
    return {
        "usosfr_history": swaps,
        "truth_zero_yields": zeros,
        "truth_ns_factors": factors,
        "vcub": vcub,
    }


def write_synthetic_market(out_dir: Path, cfg: SyntheticConfig | None = None) -> dict[str, Path]:
    """Write the synthetic tables as CSV plus ``truth.yaml`` into ``out_dir``."""
    cfg = cfg or SyntheticConfig()
    out_dir.mkdir(parents=True, exist_ok=True)
    tables = generate_synthetic_market(cfg)
    paths = {
        "usosfr_history": out_dir / "usosfr_history.csv",
        "vcub": out_dir / f"vcub_{cfg.valuation_date}.csv",
        "truth_zero_yields": out_dir / "truth_zero_yields.csv",
        "truth_ns_factors": out_dir / "truth_ns_factors.csv",
        "truth": out_dir / "truth.yaml",
    }
    tables["usosfr_history"].to_csv(paths["usosfr_history"], date_format="%Y-%m-%d")
    tables["vcub"].to_csv(paths["vcub"], index=False)
    tables["truth_zero_yields"].to_csv(
        paths["truth_zero_yields"], date_format="%Y-%m-%d", float_format="%.10f"
    )
    tables["truth_ns_factors"].to_csv(
        paths["truth_ns_factors"], date_format="%Y-%m-%d", float_format="%.10f"
    )
    truth = {
        "WARNING": "SYNTHETIC DATA - for development and testing only, never for report results",
        "units": "decimals unless the column name says pct or bp",
        "n_trading_days": len(tables["usosfr_history"]),
        **{k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(cfg).items()},
    }
    paths["truth"].write_text(yaml.safe_dump(truth, sort_keys=False), encoding="utf-8")
    return paths


def load_swap_history_pct(path: Path) -> pd.DataFrame:
    """Read a USOSFR-style history (percent) -> decimal frame, columns = years."""
    frame = pd.read_csv(path, index_col="date", parse_dates=True)
    frame = frame / 100.0
    frame.columns = [SWAP_TENORS[c] for c in frame.columns]
    return frame


def quotes_from_vcub_csv(path: Path) -> list[CapFloorQuote]:
    """Read a VCUB-style CSV into ``CapFloorQuote`` domain objects (decimals)."""
    frame = pd.read_csv(path)
    quotes = []
    for row in frame.itertuples(index=False):
        option_type: OptionType = row.option_type
        moneyness: Moneyness = row.moneyness
        quotes.append(
            CapFloorQuote(
                maturity=float(row.maturity_years),
                strike=float(row.strike_pct) / 100.0,
                volatility=float(row.normal_vol_bp) / 1e4,
                option_type=option_type,
                is_atm=moneyness == "ATM",
                quote_id=str(row.quote_id),
                moneyness=moneyness,
            )
        )
    return quotes
