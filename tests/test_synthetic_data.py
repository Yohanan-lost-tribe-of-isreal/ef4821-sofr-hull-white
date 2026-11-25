"""Checks that the synthetic dataset is internally consistent and has a known truth."""

from pathlib import Path

import numpy as np
import pytest
import yaml
from scipy.optimize import least_squares

from sofr_hw.data.synthetic import (
    SWAP_TENORS,
    SyntheticConfig,
    atm_strike,
    bachelier_capfloor_price,
    capfloor_schedule,
    generate_synthetic_market,
    hw_capfloor_price,
    load_swap_history_pct,
    par_swap_rates_from_zero,
    quotes_from_vcub_csv,
    truth_valuation_curve,
    write_synthetic_market,
)
from sofr_hw.pricing.dataset_split import build_calibration_test_split

CFG = SyntheticConfig()
DT = CFG.capfloor_accrual_dt


@pytest.fixture(scope="module")
def market() -> dict:
    return generate_synthetic_market(CFG)


@pytest.fixture(scope="module")
def curve():
    return truth_valuation_curve(CFG)


def test_generation_is_deterministic(market) -> None:
    again = generate_synthetic_market(CFG)
    assert again["usosfr_history"].equals(market["usosfr_history"])
    assert again["vcub"].equals(market["vcub"])


def test_history_shape_and_dates(market) -> None:
    swaps = market["usosfr_history"]
    assert list(swaps.columns) == list(SWAP_TENORS)
    assert str(swaps.index[0].date()) == CFG.history_start
    assert str(swaps.index[-1].date()) == CFG.valuation_date
    assert 790 <= len(swaps) <= 830
    assert swaps.notna().all().all()
    assert (swaps > 0).all().all()


def test_valuation_date_swaps_reprice_on_truth_curve(market, curve) -> None:
    quoted = market["usosfr_history"].iloc[-1].to_numpy() / 100.0
    model = par_swap_rates_from_zero(
        lambda t: np.array([curve.zero_rate(float(x)) for x in t]), list(SWAP_TENORS.values())
    )
    assert np.max(np.abs(quoted - model)) < 1e-7  # quotes are rounded to 1e-5 percent


def test_zero_yield_pca_has_three_dominant_but_imperfect_factors(market) -> None:
    changes = market["truth_zero_yields"].diff().dropna().to_numpy()
    changes = changes - changes.mean(axis=0)
    singular = np.linalg.svd(changes, compute_uv=False) ** 2
    explained = np.cumsum(singular) / singular.sum()
    assert explained[2] > 0.95
    assert explained[2] < 0.9999


def test_atm_vols_are_exact_hull_white(market, curve) -> None:
    atm = market["vcub"].query("strike_offset_bp == 0 and option_type == 'cap'")
    for row in atm.itertuples():
        strike = row.strike_pct / 100.0
        hw = hw_capfloor_price(curve, CFG.hw_kappa, CFG.hw_sigma, strike, row.maturity_years,
                               DT, "cap")
        quoted = bachelier_capfloor_price(curve, row.normal_vol_bp / 1e4, strike,
                                          row.maturity_years, DT, "cap")
        assert abs(hw - quoted) < 1e-7  # vol rounded to 1e-4 bp


def test_atm_strike_is_forward_swap_rate(market, curve) -> None:
    for row in market["vcub"].query("strike_offset_bp == 0").itertuples():
        assert abs(row.atm_strike_pct / 100 - atm_strike(curve, row.maturity_years, DT)) < 1e-8


def test_cap_floor_parity_holds_exactly(market, curve) -> None:
    vcub = market["vcub"]
    caps = vcub[vcub.option_type == "cap"].set_index(["maturity_years", "strike_offset_bp"])
    floors = vcub[vcub.option_type == "floor"].set_index(["maturity_years", "strike_offset_bp"])
    for key, cap in caps.iterrows():
        resets, pays = capfloor_schedule(key[0], DT)
        annuity = DT * sum(curve.df(t) for t in pays)
        strike = cap.strike_pct / 100.0
        swap = annuity * (cap.atm_strike_pct / 100.0 - strike)
        residual = (cap.premium_bp - floors.loc[key].premium_bp) / 1e4 - swap
        assert abs(residual) < 2e-8  # premium rounding only


def test_moneyness_labels(market) -> None:
    vcub = market["vcub"]
    below = vcub[vcub.strike_offset_bp < 0]
    above = vcub[vcub.strike_offset_bp > 0]
    assert set(below[below.option_type == "cap"].moneyness) == {"ITM"}
    assert set(below[below.option_type == "floor"].moneyness) == {"OTM"}
    assert set(above[above.option_type == "cap"].moneyness) == {"OTM"}
    assert set(above[above.option_type == "floor"].moneyness) == {"ITM"}


def test_csv_roundtrip_feeds_split_and_recovers_hw_params(tmp_path: Path) -> None:
    paths = write_synthetic_market(tmp_path, CFG)
    swaps = load_swap_history_pct(paths["usosfr_history"])
    assert swaps.max().max() < 0.1  # converted to decimals
    truth = yaml.safe_load(paths["truth"].read_text())
    assert truth["hw_kappa"] == CFG.hw_kappa

    quotes = quotes_from_vcub_csv(paths["vcub"])
    conventions = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "configs" / "conventions.yaml").read_text()
    )
    split = build_calibration_test_split(quotes, conventions)
    assert len(split.calibration.quotes) == 3
    assert len(split.oos_term_structure) == 6
    assert len(split.oos_moneyness) > 0
    assert len(split.parity_pairs) == len(quotes) // 2

    # A minimal calibration on the in-sample ATM caps must recover the truth.
    curve = truth_valuation_curve(CFG)
    targets = [
        bachelier_capfloor_price(curve, q.volatility, q.strike, q.maturity, DT, "cap")
        for q in split.calibration.quotes
    ]

    def residuals(x: np.ndarray) -> np.ndarray:
        return np.array([
            hw_capfloor_price(curve, x[0], x[1], q.strike, q.maturity, DT, "cap") - p
            for q, p in zip(split.calibration.quotes, targets)
        ]) * 1e4

    fit = least_squares(residuals, x0=[0.1, 0.01], bounds=([1e-3, 1e-5], [2.0, 0.05]),
                        xtol=1e-14, ftol=1e-14, gtol=1e-14)
    assert abs(fit.x[0] - CFG.hw_kappa) < 2e-3
    assert abs(fit.x[1] - CFG.hw_sigma) < 2e-5
