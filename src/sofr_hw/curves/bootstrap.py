"""Bootstrap a market discount curve from SOFR instruments."""

import pandas as pd

from sofr_hw.interfaces import YieldCurve


def bootstrap_sofr_curve(
    deposits: pd.DataFrame,
    futures: pd.DataFrame,
    swaps: pd.DataFrame,
    valuation_date: str,
) -> YieldCurve:
    """Bootstrap discount factors by sequentially solving instrument par equations.

    Preconditions: instruments are date-ordered with complete accrual conventions.
    Postconditions: the curve reprices input instruments within configured tolerance.
    """
    raise NotImplementedError("TODO (Oliver): implement SOFR curve bootstrapping")
