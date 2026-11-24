"""File I/O boundary for raw exports, processed datasets, and pipeline outputs."""

from pathlib import Path
from typing import Any

import pandas as pd


def load_bloomberg_csv(path: Path) -> pd.DataFrame:
    """Load a manually exported Bloomberg CSV after validating its schema.

    Preconditions: ``path`` points to an authorized CSV export. Postconditions:
    the returned frame uses normalized column names and decimal rate units.
    """
    raise NotImplementedError("TODO (Oliver): implement Bloomberg CSV ingestion")


def load_processed_parquet(path: Path) -> pd.DataFrame:
    """Read a processed Parquet dataset from the data boundary."""
    raise NotImplementedError("TODO (Oliver): implement processed data loading")


def write_processed_parquet(frame: pd.DataFrame, path: Path) -> None:
    """Persist validated processed data beneath ``data/processed/``."""
    raise NotImplementedError("TODO (Oliver): implement processed Parquet writing")


def load_conventions(path: Path) -> dict[str, Any]:
    """Load and structurally validate the shared YAML project conventions."""
    raise NotImplementedError("TODO (Oliver): implement convention loading")
