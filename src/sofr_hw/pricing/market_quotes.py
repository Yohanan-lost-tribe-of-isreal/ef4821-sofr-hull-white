"""Normalize market cap/floor quotes into domain types."""

import pandas as pd

from sofr_hw.interfaces import CapFloorQuote


def quotes_from_frame(frame: pd.DataFrame) -> tuple[CapFloorQuote, ...]:
    """Convert normalized rows to immutable quotes, preserving decimal units.

    Preconditions: required quote columns are present and validated. Postconditions:
    quote identifiers are unique and option/moneyness labels are canonical.
    """
    raise NotImplementedError("TODO (Sean): convert normalized quote rows")
