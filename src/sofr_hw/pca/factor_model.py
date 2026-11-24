"""Historical principal-component analysis of zero-yield changes."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sofr_hw.interfaces import YieldCurve


@dataclass(frozen=True)
class YieldPCAResult:
    """PCA loadings, explained-variance ratios, and factor score time series."""

    loadings: pd.DataFrame
    explained_variance_ratio: np.ndarray
    scores: pd.DataFrame


def fit_yield_pca(zero_yield_panel: pd.DataFrame, n_factors: int = 3) -> YieldPCAResult:
    """Fit PCA to demeaned historical zero-yield changes.

    Columns represent maturities and rows dates. Loadings are orthonormal in
    Euclidean tenor space; factors are ordered by descending explained variance.
    """
    raise NotImplementedError("TODO (Nicholas): implement historical yield PCA")


def curve_zero_vector(curve: YieldCurve, maturities: tuple[float, ...]) -> np.ndarray:
    """Sample decimal zero rates from the abstract YieldCurve at given tenors."""
    raise NotImplementedError("TODO (Nicholas): sample curve zero-rate vector")
