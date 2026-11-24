"""Command-line orchestration for the SOFR Hull-White project."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def run_mock() -> int:
    """Run the deterministic mock-data split and report its invariants."""
    import sys

    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))
    from sofr_hw.pricing.dataset_split import build_calibration_test_split
    from tests.fixtures.mock_market import (
        NelsonSiegelMockCurve,
        generate_synthetic_2d_vcub_quotes,
    )

    with (ROOT / "configs" / "conventions.yaml").open(encoding="utf-8") as handle:
        conventions = yaml.safe_load(handle)
    curve = NelsonSiegelMockCurve()
    quotes = generate_synthetic_2d_vcub_quotes(curve)
    split = build_calibration_test_split(quotes, conventions)
    calibration_ids = {quote.quote_id for quote in split.calibration.quotes}
    term_ids = {quote.quote_id for quote in split.oos_term_structure}
    moneyness_ids = {quote.quote_id for quote in split.oos_moneyness}
    disjoint = not (calibration_ids & term_ids or calibration_ids & moneyness_ids)
    print(f"Calibration quotes: {len(split.calibration.quotes)}")
    print(f"OOS term-structure quotes: {len(split.oos_term_structure)}")
    print(f"OOS moneyness quotes: {len(split.oos_moneyness)}")
    print(f"Matched parity pairs: {len(split.parity_pairs)}")
    print(f"Calibration/OOS disjoint: {disjoint}")
    if not disjoint:
        raise RuntimeError("Anti-leakage invariant failed")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch the requested data mode."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("mock", "bloomberg"), required=True)
    args = parser.parse_args(argv)
    if args.mode == "mock":
        return run_mock()
    raise NotImplementedError(
        "Bloomberg mode is not implemented; add validated loaders in "
        "src/sofr_hw/data/loaders.py and curve/quote adapters before enabling it."
    )


if __name__ == "__main__":
    raise SystemExit(main())
