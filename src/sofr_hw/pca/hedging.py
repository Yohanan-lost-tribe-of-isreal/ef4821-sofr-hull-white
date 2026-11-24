"""Three-factor Level/Slope/Curvature hedge ratio construction."""

import numpy as np
import pandas as pd

from sofr_hw.pca.factor_model import YieldPCAResult


def factor_hedge_ratios(
    instrument_dv01: pd.Series,
    hedge_dv01: pd.DataFrame,
    pca: YieldPCAResult,
    n_factors: int = 3,
) -> pd.Series:
    """Solve minimum-norm hedge notionals neutralizing the selected PCA factors."""
    raise NotImplementedError("TODO (Nicholas): implement three-factor hedge ratios")


def factor_exposures(
    position_dv01: pd.Series, pca: YieldPCAResult, n_factors: int = 3
) -> np.ndarray:
    """Project tenor DV01 exposure onto the leading orthonormal PCA loadings."""
    raise NotImplementedError("TODO (Nicholas): compute PCA factor exposures")
