# EF4821 Group 9 — TODO: Paste finalized README.md

# EF4821 Group 9 — Empirical Calibration of the One-Factor Hull–White Model for SOFR Interest Rate Options

Empirical term-structure bootstrapping, historical Principal Component Analysis (PCA), one-factor Hull–White calibration with **strict out-of-sample (OOS) evaluation**, and model-free Cap–Floor parity testing on USD SOFR markets.

**Team (EF4821 — Group 9):**
- **Oliver** — DATASOURCE Ingestion, SOFR Curve Bootstrapping & $C^2$ Cubic Splines (Sec. 3.1) + Shared Swap Kernel
- **Nicholas** — Historical PCA & 3-Factor Hedging (Sec. 3.2) + OOS Split Firewall & Reporting
- **Sean** — `VCUB` Quote Pricing, Hull–White Calibration/Tree/OOS Audit (Sec. 3.3) & Cap–Floor Parity (Sec. 4.3)

---

## 1. Architecture & Software Engineering Design

This repository implements a **fan-out / fan-in quantitative pipeline** governed by four canonical software engineering patterns:

1. **Hexagonal Architecture & Dependency Inversion** *(Cockburn, 2005; Martin, 2017)*: Pure mathematical modules (`curves/`, `pca/`, `models/`) depend inward on the abstract `YieldCurve` protocol in `interfaces.py`, never on raw DATASOURCE CSV layouts or concrete SciPy spline internals.
2. **Domain-Driven Bounded Contexts & Shared Kernel** *(Evans, 2003)*: Each developer owns an isolated subpackage; cross-cutting financial primitives (off-market payer swap PV, forward swap rates, day-count conventions) live once in `pricing/instruments.py` and `configs/conventions.yaml`.
3. **Design by Contract & Type-Driven Anti-Leakage** *(Meyer, 1992; King, 2019)*: All mathematical preconditions ($\kappa>0, \sigma>0, P(0,0)=1$) are validated on construction. To enforce strict out-of-sample testing, `hw_calibration.py` accepts **only** a dedicated `CalibrationSet` type produced by `dataset_split.py`.
4. **Consumer-Driven Contracts & Test Doubles** *(Fowler, 2006; Meszaros, 2007)*: Downstream modules develop and test from Day 2 against `tests/fixtures/mock_market.py` (`NelsonSiegelMockCurve` + 2D skewed synthetic `VCUB` surface) and enforce automated acceptance gates on upstream providers.

### Component Dependency Graph (Arrows Point Inward to Contracts)

```text
                       ┌────────────────────────────────────────────────────┐
                       │             configs/conventions.yaml               │
                       │  val_date=2026-09-30 | dt | (κ,σ) lock | OOS rules │
                       └─────────────────────────┬──────────────────────────┘
                                                 │ read-only config
                                                 ▼
┌──────────────────────────────┐     ┌────────────────────────────────┐     ┌──────────────────────────────┐
│ [Oliver] data/ & curves/     │     │     SHARED CONTRACT LAYER      │     │ [Oliver] pricing/instruments │
│ • loaders.py (USOSFR + VCUB) │────▶│         interfaces.py          │◀────│ • build_schedule()           │
│ • bootstrap.py (single/batch)│impl │ • YieldCurve (Protocol, C²)    │uses │ • forward_swap_rate()        │
│ • spline.py (C² CubicSpline) │     │ • CapFloorQuote / SwaptionQuote│     │ • price_off_market_swap()    │
│ • SOFRCurve                  │     │ • CalibrationSet (Anti-Leak)   │     └──────────────┬───────────────┘
└──────────────────────────────┘     │ • CalibrationTestSplit         │                    │ shared kernel
                                     │ • HullWhiteParams (const κ,σ)  │                    │
                                     └───────▲────────────────▲───────┘                    │
                          injectable         │                │          injectable        │
              ┌──────────────────────────────┘                └────────────────────────────┤
              │                                                                            │
┌─────────────┴────────────────┐     ┌────────────────────────────────┐     ┌──────────────▼───────────────┐
│ [Nicholas] pca/ & firewall   │     │ [Phase 0] tests/fixtures/      │     │ [Sean] pricing/ & models/    │
│ • pca/factor_model.py (3 PCs)│     │ • NelsonSiegelMockCurve        │     │ • pricing/market_quotes.py   │
│ • pca/hedging.py (3F neutral)│     │ • synthetic_2d_vcub_surface()  │     │ • pricing/parity.py (Sec 4.3)│
│ • pricing/dataset_split.py   │     │   (Enables Day-2 parallelism)  │     │ • models/hw_affine.py        │
│   [OOS SPLIT FIREWALL]       │     └────────────────────────────────┘     │ • models/hw_calibration.py   │
│ • reporting/plots.py         │                                            │ • models/hw_tree.py          │
└─────────────┬────────────────┘                                            │ • models/hw_evaluation.py    │
              │                                                             └──────────────┬───────────────┘
              └──────────────────────────────┐                ┌────────────────────────────┘
                                             ▼                ▼
                                     ┌────────────────────────────────┐
                                     │   [All 3] pipelines/run_all.py │
                                     │   Functional Core / Imp. Shell │
                                     └────────────────────────────────┘
```

---

## 2. Mathematical Dataflow & Tiered Coupling

Every stage maps directly to the EF4821 lecture derivations (Chapters 1–3). Note the **two-tier coupling** between Oliver's curve and Sean's Hull–White engine:
- **Tier 1 (`P^mkt(0,u)` only)**: Analytical Hull–White caplet pricing plugs market discount factors directly into the ZCB-put formula with $\sigma_{\text{avg}}(\kappa,\sigma)$ (Ch 2, Slides 18–20). The $(\kappa,\sigma)$ calibration loop never differentiates $\theta(t)$.
- **Tier 2 (`f^mkt(0,u) = -d/du ln P^mkt(0,u)`)**: Requires $C^2$ cubic spline smoothness (Ch 1, Slide 3; Ch 2, Slide 17) and is invoked *after* $(\hat{\kappa},\hat{\sigma})$ is frozen—for $\phi(t)/\theta(t)$ extraction, Hull–White tree calibration (Ch 3, Slide 5), and optional swaption pricing (Ch 2, Slides 22–23).

```text
[DATASOURCE Raw: USOSFR 1Y–30Y (2023-07-03..2026-09-30)]   [DATASOURCE Raw: VCUB 2D Grid (2026-09-30)]
                        │                                  Maturities × Strikes (ATM/ITM/OTM)
                        ▼                                                         │
            [Oliver] loaders.py + validators.py                                   │
                        │                                                         │
          ┌─────────────┴──────────────────────┐                                  │
          ▼ (batch ~820 trading days)          ▼ (val_date: 2026-09-30)           │
   bootstrap_discount_factors()         bootstrap + C² CubicSpline                │
          │                                    │                                  │
          ▼                                    ▼                                  │
 [zero_yields_history.parquet]        SOFRCurve (YieldCurve Protocol)             │
   y(t_i, τ_j)  [Ch 1, S12]           • Tier 1: P^mkt(0,u)                        │
          │                           • Tier 2: f^mkt(0,u)                        │
          ▼                                │       │          │                   │
 [Nicholas] factor_model.py                │       │          │                   ▼
   Δ_ij → V = CDCᵀ (L, S, C >98%)          │       │          └───▶ [Sean] market_quotes.py
   [Ch 1, S12–14]                          │       │                • ATM R_swap (instruments.py)
          │                                │       │                • Vol → $ Price + Vega [Ch 1, S20–21]
          ▼                                │       │                              │
 [Nicholas] hedging.py                     │       │                              ▼
   3-Factor Neutral Weights                │       │       ╔═══════════════════════════════════════════╗
   [Ch 1, S14–15]                          │       │       ║ [Nicholas] OOS SPLIT FIREWALL             ║
          │                                │       │       ║ dataset_split.py (per conventions.yaml)   ║
          │                                │       │       ╚═════╤═══════════════╤═══════════════╤═════╝
          │                                │       │             │               │               │
          │                                │       │    ┌────────┘               │               └────────┐
          │                                │       │    ▼ (In-Sample ONLY)       ▼ (Held-Out OOS)         ▼ (Matched K,T)
          │                                │       │ [CalibrationSet]     [OOS Test Buckets]       [Parity Pairs]
          │                                │       │  ATM Benchmark Caps   • OOS-Maturity (ATM)           │
          │                                │       │    │                  • OOS-Strike (ITM/OTM)         ▼
          │                                │       │    │                  • (Opt) OOS-Swaptions   [Sean] parity.py
          │                                ├───────┼──▶ [Sean] hw_calibration.py │                 PayerSwap(K) PV
          │                                │(Tier 1│    Vega-WLS → (κ̂, σ̂)        │                 Residual ε [Ch 1, S22]
          │                                │ only!)│    [Ch 2, S18–20, S26]      │                        │
          │                                │       │    │                        │                        │
          │                                │       │    ▼ Frozen (κ̂, σ̂)          │                        │
          │                                └───────┼──▶ [Sean] hw_affine.py (φ/θ)│                        │
          │                                 (Tier 2│    & hw_tree.py             │                        │
          │                                 f^mkt!)│    [Ch 2, S16–17; Ch 3, S5] │                        │
          │                                        │    │                        │                        │
          │                                        │    ▼                        │                        │
          │                                        └──▶ [Sean] hw_evaluation.py ◀┘                        │
          │                                             • In-Sample vs. OOS Pricing (Analytical + Tree)   │
          │                                             • Invert Model Price → Model Implied Vol          │
          │                                             • Export oos_error_matrix.parquet                 │
          └──────────────────────────────┬──────────────┴────────────────────────┴────────────────────────┘
                                         ▼
                  [All 3] Section 4.4 Synthesis (04_final_synthesis.ipynb)
                  • PC2/PC3 empirical variance vs. OOS-Maturity & OOS-Strike errors
                  • 2-param fit ceiling [Ch 2, S26] | Negative rates [Ch 2, S4] | LMM inconsistency [Ch 2, S21]
```

---

## 3. Calibration vs. Out-of-Sample (OOS) Evaluation Protocol

To rigorously evaluate out-of-sample pricing capability (rather than relying on in-sample fitting error alone), all `VCUB` quotes on `2026-09-30` are partitioned declaratively in `configs/conventions.yaml`:

| Dataset Bucket | Quotes Included | Enters Optimizer? | Evaluation Purpose |
| :--- | :--- | :---: | :--- |
| **In-Sample Calibration (`CalibrationSet`)** | Benchmark ATM Caps (`2Y, 5Y, 10Y`), $K = R_{\text{swap}}(T_0, T_N)$ | **Yes** | Identifies scalar $(\hat{\kappa}, \hat{\sigma})$ via Vega-weighted least squares. |
| **OOS-Maturity (Term-Structure Test)** | Held-out ATM Caps (`1Y, 3Y, 4Y, 7Y, 15Y, 20Y`) | **No** | Tests whether 2 constant parameters generalize across the volatility term structure. |
| **OOS-Strike (Moneyness / Smile Test)** | ITM & OTM Caps and Floors across maturities | **No** | Tests Gaussian short-rate dynamics against market volatility skew/smile. |
| **OOS-Instrument *(Optional)*** | European SOFR Swaptions (if exported from `VCUB`) | **No** | Tests cross-instrument generalization (Jamshidian $r^*$ / tree vs. Market Model). |
| **Model-Free Parity Set (Sec. 4.3)** | Matched $(K, T_N)$ Cap–Floor pairs | **No** | Computes $\varepsilon$, $\text{Cap}(K_{\text{mkt}})$, $\text{Floor}(K_{\text{mkt}})$, and $\text{PayerSwap}(K_{\text{mkt}})$
  *(ATM Floors are not used alone as an OOS test because parity algebraically links them to ATM Caps.)* |

---

## 4. Ubiquitous Language & Core Interface Definitions

All modules enforce the following conventions and contracts (`src/sofr_hw/interfaces.py` and `configs/conventions.yaml`):

- **Units**: All rates, strikes, and volatilities inside `src/` are **decimals** (e.g., `0.0425` for `4.25%`); all prices are per `$1` notional.
- **Hull–White Specification (Ch 2, Slides 12–20)**: Scalar constants $\kappa > 0, \sigma > 0$ with time-dependent curve-fitting drift $\theta(t)$:
  $$dr(t) = \theta(t)\,dt - \kappa r(t)\,dt + \sigma\,dB(t), \qquad r(s) = \phi(s) + \hat{r}(s)$$
  $$P(t,u) = \exp\!\left(-\int_t^u \phi(s)\,ds - a(\tau) - b(\tau)\hat{r}(t)\right), \quad b(\tau)=\frac{1-e^{-\kappa\tau}}{\kappa}$$
- **Core Python Contracts**:
  - `YieldCurve` (`Protocol`): `.df(t)` (Tier 1), `.zero_rate(t)`, `.inst_forward(t)` (Tier 2, $C^2$-smooth), `.simple_forward(t1, t2)`.
  - `CapFloorQuote` (frozen dataclass): `quote_id`, `option_type`, `maturity_years`, `accrual_dt`, `strike`, `atm_forward_swap_rate`, `moneyness`, `implied_vol`, `vol_type`, `market_price`, `vega`.
  - `CalibrationSet` (frozen dataclass): enforces `len(quotes) >= 2`; sole accepted input to `calibrate_hw_params()`.
  - `CalibrationTestSplit` (frozen dataclass): immutable bundle of `calibration`, `oos_term_structure`, `oos_moneyness`, and `parity_pairs`.
  - `HullWhiteParams` (frozen dataclass): enforces finite $\kappa > 0$ and $\sigma > 0$.

---

## 5. Team Co-Working Workflow & Progress Milestones

### Branching & Code Review Governance (GitHub Flow)
1. **`main` is protected**: Never push directly to `main`. Branch per vertical slice (`feat/oliver-bootstrap`, `feat/nicholas-split-firewall`, `feat/sean-hw-affine`) and merge via PR every 2–3 days.
2. **Consumer-Driven PR Reviews**: Enforced via `.github/CODEOWNERS`—Sean reviews Oliver's `curves/` PR (guarding $f^{\text{mkt}}$ smoothness); Oliver reviews Sean's `parity.py` & `market_quotes.py`; Sean reviews Nicholas's `dataset_split.py`.
3. **Zero Logic in Notebooks**: All math lives in `src/sofr_hw/`. Notebooks under `notebooks/` only call installed library functions and render figures.

### Parallel Execution Sequence & 3 Synchronous Seam Checkpoints

```text
Day   Oliver (Data/Curves/Swaps)     Git main (CI: ruff + pytest)     Nicholas (PCA/Firewall/Plots)  Sean (Quotes/HW/Parity/OOS)
 │
 ├─D1 [============== SEAM 1 (All 3, 60m): Freeze interfaces.py, conventions.yaml, 2D mock_market.py ==============]
 │                                    │ PR #1 merged (Contract + Anti-Leakage Gate Frozen)
 │                                    │
 ├─D2 feat/oliver-curves              │                                feat/nicholas-split            feat/sean-hw-core
 │    • Clean USOSFR + 2D VCUB        │                                • dataset_split.py             • market_quotes.py (Vol↔Price)
 │    • Bootstrap + C² CubicSpline    │                                • test_no_leakage.py           • hw_affine.py + hw_calibration.py
 │    • pricing/instruments.py        │◀── PR #2: Split Firewall ──────┘ (Sean reviews)               • parity.py (on Mock)
 │                                    │                                feat/nicholas-pca              feat/sean-hw-tree-oos
 │                                    │                                • factor_model.py + hedging.py • hw_tree.py + hw_evaluation.py
 │                                    │
 ├─D5 [============== SEAM 2 (Oliver + Sean, 60m): Audit real VCUB vol→price & C² f^mkt(0,u) smoothness ===========]
 │    PR #3: Curves, Swaps & Data ───▶│──(CI: Swap=0, C² pass)
 │    (Sean reviews f^mkt + VCUB)     │────────── git pull ───────────▶│ Switch Mock → Real 820d      │ Switch Mock → Real Curve+VCUB
 │                                    │                                │ Run real PCA & 3F hedge      │ Calibrate (κ̂,σ̂) on Calib ONLY
 ├─D8                                 │◀── PR #4: PCA & Hedge ─────────│ (Oliver reviews)             │ Score OOS-Mat, OOS-Strike & ε
 │                                    │◀── PR #5: HW, Tree, OOS, ε ───────────────────────────────────│ (Oliver+Nicholas review)
 │                                    │
 ├─D10 [============= SEAM 3 (All 3, 60m): Wire pipelines/run_all.py & compile Section 4.4 synthesis ==============]
```

---

## 6. Automated 4-Layer Verification Pyramid (CI Merge Gates)

Every Pull Request must pass `ruff check .` and all four `pytest` layers in `.github/workflows/ci.yml`:

| Gate Layer | Test File | Mathematical / Engineering Invariant Verified |
| :--- | :--- | :--- |
| **Layer 1: Contract Gate (CDC)** | `tests/test_contracts.py` | Both `NelsonSiegelMockCurve` and `SOFRCurve` satisfy `P(0,0)=1`, `P(0,t)>0`, and `inst_forward(t) == -d/dt ln P(0,t)` within `1e-6`. |
| **Layer 2: Domain Invariants** | `test_curves.py`, `test_pca_hedging.py`, `test_hw_and_parity.py` | Input par swaps reprice to `< 1e-10`; spline $C^2$-continuous at knots; PCA $C^\top C = I$; hedged 3-factor net betas $< 1e-10$; HW exact fit matches $P^{\text{mkt}}(0,u) < 1e-8$. |
| **Layer 3: Anti-Leakage Firewall** | `tests/test_no_leakage.py` | `calib_ids` is strictly disjoint from `oos_term_structure` and `oos_moneyness`; all OOS sets non-empty; `CalibrationSet` enforced. |
| **Layer 4: Cross-Model Audit** | `tests/test_hw_and_parity.py` | Analytical HW caplets converge to HW tree prices as $\Delta t \to 0$; model-generated prices satisfy $\varepsilon_{\text{model}} = 0$. |

---

## 7. Quickstart & Reproducibility

```bash
# 1. Create virtual environment and install package in editable mode with dev tools
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 2. Run linting and full 4-layer verification suite
ruff check .
pytest -v

# 3. Run full pipeline end-to-end (use --mode mock before DATASOURCE CSVs are placed in data/raw/)
python pipelines/run_all.py --mode mock
python pipelines/run_all.py --mode [e.g.bloomberg]
```

All generated report tables and plots are written deterministically to `outputs/tables/` and `outputs/figures/`.
