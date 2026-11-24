"""Reusable figures for curves, PCA factors, and option evaluation."""

from pathlib import Path

import pandas as pd


def plot_curve(discount_curve: pd.Series, zero_curve: pd.Series, output_path: Path) -> None:
    """Plot discount factors and zero rates with year-fraction tenor axes."""
    raise NotImplementedError("TODO (Nicholas): implement market curve plot")


def plot_pca_loadings(loadings: pd.DataFrame, output_path: Path) -> None:
    """Plot the leading Level, Slope, and Curvature loading vectors."""
    raise NotImplementedError("TODO (Nicholas): implement PCA loading plot")


def plot_model_evaluation(results: pd.DataFrame, output_path: Path) -> None:
    """Plot in-sample and OOS errors without mixing their labels or observations."""
    raise NotImplementedError("TODO (Nicholas): implement model evaluation plot")
