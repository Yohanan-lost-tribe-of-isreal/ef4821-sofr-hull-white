"""Layer 3 type-driven anti-leakage gates for strict OOS evaluation."""

from pathlib import Path

import pytest
import yaml

from sofr_hw.interfaces import CalibrationSet
from sofr_hw.pricing.dataset_split import build_calibration_test_split


@pytest.fixture
def split_config() -> dict:
    config_path = Path(__file__).resolve().parents[1] / "configs" / "conventions.yaml"
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_calibration_and_oos_buckets_are_nonempty_and_disjoint(
    mock_quotes, split_config: dict
) -> None:
    split = build_calibration_test_split(mock_quotes, split_config)
    calibration_ids = {quote.quote_id for quote in split.calibration.quotes}
    term_ids = {quote.quote_id for quote in split.oos_term_structure}
    moneyness_ids = {quote.quote_id for quote in split.oos_moneyness}
    assert calibration_ids
    assert term_ids
    assert moneyness_ids
    assert calibration_ids.isdisjoint(term_ids)
    assert calibration_ids.isdisjoint(moneyness_ids)
    assert term_ids.isdisjoint(moneyness_ids)
    assert len(split.parity_pairs) > 0


def test_calibration_set_requires_two_quotes(mock_quotes) -> None:
    with pytest.raises(ValueError, match="at least two"):
        CalibrationSet((mock_quotes[0],))
