"""In-sample-only calibration API for scalar Hull-White parameters."""

from sofr_hw.interfaces import CalibrationSet, HullWhiteParams, YieldCurve


def calibrate_hw_params(
    calibration: CalibrationSet, curve: YieldCurve
) -> HullWhiteParams:
    """Fit constant kappa and sigma to in-sample benchmark ATM cap quotes.

    The argument type is deliberately restricted to ``CalibrationSet`` to prevent
    full quote tables and held-out observations entering model calibration.
    Parameters satisfy kappa>0 and sigma>0; objective conventions are defined
    in decimal market-volatility units.
    """
    raise NotImplementedError("TODO (Sean): calibrate from CalibrationSet only")
