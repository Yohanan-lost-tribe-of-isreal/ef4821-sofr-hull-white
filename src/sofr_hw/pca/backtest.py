"""Out-of-sample historical evaluation of factor hedge performance."""

import pandas as pd


def backtest_hedge(
    target_pnl: pd.Series, hedge_pnl: pd.DataFrame, hedge_ratios: pd.Series
) -> pd.DataFrame:
    """Return date-aligned residual P&L and hedged/unhedged risk statistics.

    The backtest uses only observations after hedge ratios are established; no
    future return may enter ratio estimation.
    """
    raise NotImplementedError("TODO (Nicholas): implement hedge backtest")
