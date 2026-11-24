"""Strict in-sample versus out-of-sample model audit."""

import pandas as pd

from sofr_hw.interfaces import CalibrationTestSplit, HullWhiteParams, YieldCurve


def evaluate_hw_split(
    split: CalibrationTestSplit, curve: YieldCurve, params: HullWhiteParams
) -> pd.DataFrame:
    """Evaluate calibration fit and distinct term-structure/moneyness OOS errors.

    The function reports each bucket independently and does not refit parameters
    on either OOS set. Prices and errors are per $1 notional or decimal-vol units.
    """
    raise NotImplementedError("TODO (Sean): implement in-sample/OOS evaluation audit")
