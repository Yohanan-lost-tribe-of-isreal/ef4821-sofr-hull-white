"""C² interpolation and derivatives for market discount and forward curves."""

import numpy as np


def fit_log_discount_spline(times: np.ndarray, discount_factors: np.ndarray) -> object:
    """Fit a C² cubic spline to log discount factors.

    The interpolant is ``g(t)=ln(P^mkt(0,t))``; its instantaneous forward is
    ``f(0,t)=-g'(t)``. Preconditions: increasing nonnegative times and positive
    discount factors with ``P(0)=1``.
    """
    raise NotImplementedError("TODO (Oliver): implement C² log-discount spline")
