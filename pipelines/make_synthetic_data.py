"""Generate the synthetic (Bloomberg-shaped) market dataset into data/synthetic/.

Usage:
    python pipelines/make_synthetic_data.py                 # default seed 4821
    python pipelines/make_synthetic_data.py --seed 7 --vol-noise-bp 0.5 --atm-hump-bp 8

Output is deterministic for a given seed and options. See data/synthetic/README.md.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sofr_hw.data.synthetic import SyntheticConfig, write_synthetic_market  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "synthetic")
    parser.add_argument("--seed", type=int, default=SyntheticConfig.seed)
    parser.add_argument("--vol-noise-bp", type=float, default=0.0,
                        help="random noise on every vol quote (0 = exact HW at ATM)")
    parser.add_argument("--atm-hump-bp", type=float, default=0.0,
                        help="vol hump around 5Y that constant-parameter HW cannot fit")
    args = parser.parse_args(argv)
    cfg = replace(
        SyntheticConfig(),
        seed=args.seed,
        vol_noise_bp=args.vol_noise_bp,
        atm_hump_bp=args.atm_hump_bp,
    )
    paths = write_synthetic_market(args.out, cfg)
    for name, path in paths.items():
        print(f"{name:>18}: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
