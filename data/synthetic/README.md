# Synthetic market data (development only)

> **Do not use anything in this folder for results in the report.** It is made-up data with a known
> answer, so we can build and test the pipeline before the Bloomberg export is ready.

Regenerate with `python pipelines/make_synthetic_data.py` (deterministic, seed 4821).
Generator: `src/sofr_hw/data/synthetic.py`. Checks: `tests/test_synthetic_data.py`.

## Files

| File | Mimics | Layout | Units |
|---|---|---|---|
| `usosfr_history.csv` | Bloomberg `USOSFR*` Curncy daily history | `date` + 19 tenor columns `1M … 30Y`, 813 US business days, 2023-07-03 → 2026-09-30 | **percent** (like Bloomberg) |
| `vcub_2026-09-30.csv` | Bloomberg `VCUB` (SOFR, normal vol) | one row per cap/floor × maturity (1–30Y) × strike (ATM, ±50bp, ±100bp) = 150 rows | `*_pct` percent, `*_bp` basis points |
| `truth_zero_yields.csv` | — (answer key) | true continuously-compounded zero yields at the same tenors | decimals |
| `truth_ns_factors.csv` | — (answer key) | true daily Nelson–Siegel factors | decimals |
| `truth.yaml` | — (answer key) | every generating parameter, incl. Hull–White κ = 0.03, σ = 0.0085 | decimals |

The real exports should be saved to `data/raw/` **in the same layout** (rename Bloomberg ticker columns
to tenor labels, e.g. `USOSFRC Curncy → 3M`, `USOSFR10 Curncy → 10Y`). Then switching from synthetic
to real data means changing only the input path.

`vcub` columns: `quote_id, option_type, maturity_years, strike_offset_bp, strike_pct, atm_strike_pct,
moneyness, normal_vol_bp, premium_bp, hw_model_vol_bp`. `hw_model_vol_bp` is the answer key (the vol
Hull–White would give at that strike) and will **not** exist in the real export. `premium_bp` is per
unit notional, ×10⁴.

## How it was generated (what each person can check against)

- **Oliver (bootstrap):** par rates are computed from a smooth Nelson–Siegel curve with annual
  fixed/floating OIS (≥1Y) and single-period simple rates (<1Y), year fractions, single curve. Every
  day except the valuation date has ~0.4bp per-tenor noise. **On 2026-09-30 there is no noise**, so a
  correct bootstrap + spline should reproduce `truth_valuation_curve()` closely, and must reprice the
  input swaps.
- **Nicholas (PCA):** use `truth_zero_yields.csv` now (Oliver's bootstrapped history replaces it
  later). Daily changes: PC1 ≈ 83%, PC1–2 ≈ 96%, PC1–3 ≈ 98%, which is realistic, not a perfect 100%.
- **Sean (HW / parity):** ATM cap vols are generated **exactly** from Hull–White (κ = 0.03,
  σ = 0.0085) on the valuation-date truth curve, using quarterly forward-looking caplets with the
  first caplet excluded and the ATM strike = forward swap rate. Calibrating on the ATM 2/5/10Y caps
  should recover κ and σ (the test suite does this with a 10-line least-squares fit). Off-ATM vols
  add a smile `0.10·|K−ATM| − 0.04·(K−ATM)` that Hull–White can't produce, so OOS-strike errors are
  non-zero by design. `quotes_from_vcub_csv()` returns `CapFloorQuote` objects ready for
  `build_calibration_test_split()`.
- **Parity:** cap and floor at the same strike share one vol (as VCUB does), so parity holds exactly
  (ε ≈ 0, rounding only). Real VCUB data will behave the same way. A meaningful parity test needs
  independently quoted cap and floor premiums.

Optional realism: `--vol-noise-bp 0.5` adds quote noise; `--atm-hump-bp 8` adds a vol hump around 5Y
that constant-parameter Hull–White can't fit (so OOS-maturity errors become non-zero too).
