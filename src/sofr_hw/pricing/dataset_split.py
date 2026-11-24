"""Declarative, deterministic firewall between calibration and evaluation quotes."""

from collections.abc import Mapping, Sequence
from typing import Any

from sofr_hw.interfaces import (
    CalibrationSet,
    CalibrationTestSplit,
    CapFloorQuote,
    QuotePair,
)


def build_calibration_test_split(
    quotes: Sequence[CapFloorQuote], split_cfg: Mapping[str, Any]
) -> CalibrationTestSplit:
    """Partition quotes using the ``option_split`` section of conventions.yaml.

    Calibration contains only configured ATM caps. OOS term-structure contains
    only held-out ATM caps, while OOS moneyness contains configured non-ATM caps
    and floors. Unconfigured quotes are excluded from these three buckets.
    Matched parity pairs are constructed by exact maturity/strike matches and
    are not fed into model calibration.
    """
    rules = split_cfg.get("option_split", split_cfg)
    calibration_rule = rules["calibration"]
    term_rule = rules["oos_term_structure"]
    moneyness_rule = rules["oos_moneyness"]
    calibration_maturities = {float(value) for value in calibration_rule["maturities"]}
    term_maturities = {float(value) for value in term_rule["maturities"]}
    moneyness_maturities = {float(value) for value in moneyness_rule["maturities"]}
    if calibration_maturities & term_maturities:
        raise ValueError("calibration and OOS term-structure maturities must be disjoint")
    calibration_type = calibration_rule.get("option_type", "cap")
    term_type = term_rule.get("option_type", "cap")
    calibration_moneyness = calibration_rule.get("moneyness", "ATM")
    term_moneyness = term_rule.get("moneyness", "ATM")
    allowed_types = set(moneyness_rule.get("option_types", ("cap", "floor")))
    allowed_moneyness = set(moneyness_rule.get("moneyness", ("ITM", "OTM")))

    calibration: list[CapFloorQuote] = []
    term_structure: list[CapFloorQuote] = []
    moneyness: list[CapFloorQuote] = []
    seen_ids: set[str] = set()
    for quote in quotes:
        if quote.quote_id in seen_ids:
            raise ValueError(f"duplicate quote_id: {quote.quote_id}")
        seen_ids.add(quote.quote_id)
        maturity = float(quote.maturity)
        if quote.moneyness == calibration_moneyness and quote.option_type == calibration_type:
            if maturity in calibration_maturities:
                calibration.append(quote)
                continue
        if quote.moneyness == term_moneyness and quote.option_type == term_type:
            if maturity in term_maturities:
                term_structure.append(quote)
                continue
        if (
            quote.moneyness in allowed_moneyness
            and quote.option_type in allowed_types
            and maturity in moneyness_maturities
        ):
            moneyness.append(quote)

    parity_pairs = _matched_parity_pairs(quotes)
    parity_rule = rules.get("parity", {})
    if parity_rule.get("require_matched_cap_floor_pairs", False) and not parity_pairs:
        raise ValueError("parity configuration requires at least one matched cap/floor pair")
    return CalibrationTestSplit(
        calibration=CalibrationSet(tuple(calibration)),
        oos_term_structure=tuple(term_structure),
        oos_moneyness=tuple(moneyness),
        parity_pairs=parity_pairs,
    )


def _matched_parity_pairs(quotes: Sequence[CapFloorQuote]) -> tuple[QuotePair, ...]:
    """Return sorted exact cap/floor matches by maturity and strike."""
    indexed: dict[tuple[float, float], dict[str, CapFloorQuote]] = {}
    for quote in quotes:
        matching_quotes = indexed.setdefault((quote.maturity, quote.strike), {})
        if quote.option_type in matching_quotes:
            raise ValueError(
                "duplicate option type at parity maturity/strike: "
                f"{quote.option_type}, {quote.maturity}, {quote.strike}"
            )
        matching_quotes[quote.option_type] = quote
    pairs: list[QuotePair] = []
    for key in sorted(indexed):
        matched = indexed[key]
        if "cap" in matched and "floor" in matched:
            pairs.append((matched["cap"], matched["floor"]))
    return tuple(pairs)
