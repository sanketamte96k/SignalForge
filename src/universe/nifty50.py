from pathlib import Path

import pandas as pd

from src.universe.models import Instrument


_NIFTY50_FILE = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "universe"
    / "nifty50_2026-08-30.csv"
)

_REQUIRED_COLUMNS = (
    "symbol",
    "name",
    "exchange",
    "instrument_type",
    "index_name",
    "valid_from",
)


def load_nifty50() -> tuple[Instrument, ...]:
    """Load the versioned NIFTY 50 constituent universe."""

    if not _NIFTY50_FILE.exists():
        raise FileNotFoundError(
            f"NIFTY 50 constituent file not found: {_NIFTY50_FILE}"
        )

    data = pd.read_csv(_NIFTY50_FILE)

    missing_columns = [
        column for column in _REQUIRED_COLUMNS if column not in data.columns
    ]

    if missing_columns:
        raise ValueError(
            f"NIFTY 50 constituent file is missing columns: {missing_columns}"
        )

    if len(data) != 50:
        raise ValueError(
            f"NIFTY 50 constituent file must contain exactly 50 rows; "
            f"found {len(data)}"
        )

    if data["symbol"].duplicated().any():
        duplicates = sorted(
            data.loc[data["symbol"].duplicated(), "symbol"].tolist()
        )
        raise ValueError(
            f"NIFTY 50 constituent file contains duplicate symbols: {duplicates}"
        )

    if not (data["index_name"] == "NIFTY 50").all():
        raise ValueError("All constituents must belong to NIFTY 50")

    if not (data["exchange"] == "NSE").all():
        raise ValueError("All NIFTY 50 constituents must use NSE")

    if not (data["instrument_type"] == "EQUITY").all():
        raise ValueError("All NIFTY 50 constituents must be EQUITY instruments")

    if data["symbol"].isna().any() or data["name"].isna().any():
        raise ValueError("NIFTY 50 constituents must have symbols and names")

    instruments = tuple(
        Instrument(
            symbol=row.symbol,
            name=row.name,
            exchange=row.exchange,
            instrument_type=row.instrument_type,
        )
        for row in data.itertuples(index=False)
    )

    return instruments


def nifty50_symbols() -> tuple[str, ...]:
    """Return NIFTY 50 symbols in database order."""

    return tuple(instrument.symbol for instrument in load_nifty50())
