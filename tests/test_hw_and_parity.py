"""Layer 2 Hull-White and Layer 4 model-free parity tests, implemented by Sean."""

import pytest

pytestmark = pytest.mark.skip(reason="TODO (Sean): implement Layer 2/4 tests")


def test_tree_prices_reproduce_curve_and_cap_floor_parity() -> None:
    """Verify tree repricing and matched cap-floor parity."""
    raise NotImplementedError
