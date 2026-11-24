"""Affine zero-coupon bond pricing in the one-factor Hull-White model."""

from sofr_hw.interfaces import HullWhiteParams, YieldCurve


def hw_bond_price(
    curve: YieldCurve, params: HullWhiteParams, t: float, maturity: float, short_rate: float
) -> float:
    """Return P(t,T)=A(t,T)exp(-B(t,T)r_t) calibrated to the initial curve.

    ``B(t,T)=(1-exp(-kappa*(T-t)))/kappa``; the deterministic ``A`` term is
    chosen so model bond prices reproduce the market discount curve at t=0.
    """
    raise NotImplementedError("TODO (Sean): implement Hull-White affine bond price")


def hw_theta(curve: YieldCurve, params: HullWhiteParams, t: float) -> float:
    """Return theta(t)=f'(0,t)+kappa*f(0,t)+sigma²/(2*kappa)*(1-exp(-2*kappa*t))."""
    raise NotImplementedError("TODO (Sean): implement time-varying Hull-White drift")
