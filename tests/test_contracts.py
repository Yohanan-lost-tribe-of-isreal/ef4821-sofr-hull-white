"""Layer 1 design-by-contract gates for market curves."""

import numpy as np

from sofr_hw.interfaces import YieldCurve


def test_mock_curve_satisfies_protocol(mock_curve: YieldCurve) -> None:
    assert isinstance(mock_curve, YieldCurve)


def test_discount_factor_domain_and_origin(mock_curve: YieldCurve) -> None:
    assert mock_curve.df(0.0) == 1.0
    for maturity in (0.25, 1.0, 5.0, 20.0, mock_curve.max_maturity):
        assert mock_curve.df(maturity) > 0.0


def test_instantaneous_forward_matches_discount_derivative(mock_curve: YieldCurve) -> None:
    for maturity in np.linspace(0.1, mock_curve.max_maturity - 0.1, 25):
        step = 1e-5
        finite_difference = -(
            np.log(mock_curve.df(maturity + step))
            - np.log(mock_curve.df(maturity - step))
        ) / (2.0 * step)
        assert abs(mock_curve.inst_forward(float(maturity)) - finite_difference) < 1e-6
