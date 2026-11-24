"""Shared deterministic fixtures."""

import pytest

from tests.fixtures.mock_market import (
    NelsonSiegelMockCurve,
    generate_synthetic_2d_vcub_quotes,
    generate_synthetic_zero_panel,
)


@pytest.fixture
def mock_curve() -> NelsonSiegelMockCurve:
    """Provide an analytic curve conforming to the YieldCurve protocol."""
    return NelsonSiegelMockCurve()


@pytest.fixture
def mock_quotes(mock_curve: NelsonSiegelMockCurve):
    """Provide a synthetic, matched cap/floor volatility surface."""
    return generate_synthetic_2d_vcub_quotes(mock_curve)


@pytest.fixture
def zero_yield_panel():
    """Provide deterministic daily Level/Slope/Curvature yield observations."""
    return generate_synthetic_zero_panel()
