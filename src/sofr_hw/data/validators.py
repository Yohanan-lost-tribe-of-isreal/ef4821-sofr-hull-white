"""Schema and domain validation for externally sourced market data."""

from collections.abc import Mapping
from typing import Any

import pandas as pd


def validate_discount_curve_quotes(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate positive discount factors and strictly increasing year fractions."""
    raise NotImplementedError("TODO (Oliver): validate discount-curve source data")


def validate_capfloor_quotes(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate cap/floor quote schema, decimal units, and positive volatilities."""
    raise NotImplementedError("TODO (Oliver): validate cap/floor source data")


def validate_conventions(config: Mapping[str, Any]) -> None:
    """Validate required keys, date ordering, decimal units, and split conventions."""
    raise NotImplementedError("TODO (Oliver): validate project conventions")
