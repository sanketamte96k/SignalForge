"""Indian market-session utilities for SignalForge."""

from datetime import time

import pandas as pd


MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


def validate_session_parameters(
    market_open: time = MARKET_OPEN,
    market_close: time = MARKET_CLOSE,
) -> None:
    """Validate market-session boundaries."""

    if not isinstance(market_open, time):
        raise TypeError(
            "market_open must be a datetime.time."
        )

    if not isinstance(market_close, time):
        raise TypeError(
            "market_close must be a datetime.time."
        )

    if market_open >= market_close:
        raise ValueError(
            "market_open must be earlier than "
            "market_close."
        )


def filter_market_session(
    data: pd.DataFrame,
    market_open: time = MARKET_OPEN,
    market_close: time = MARKET_CLOSE,
) -> pd.DataFrame:
    """
    Keep only candles inside the regular Indian market session.

    The default session is 09:15 through 15:30.

    Parameters
    ----------
    data:
        DataFrame indexed by DatetimeIndex.

    market_open:
        Session opening time.

    market_close:
        Session closing time.

    Returns
    -------
    pd.DataFrame
        DataFrame containing only regular-session rows.

    Notes
    -----
    The market close boundary is inclusive so a legitimate
    15:30 candle is retained.
    """

    if not isinstance(
        data,
        pd.DataFrame,
    ):
        raise TypeError(
            "data must be a pandas DataFrame."
        )

    if not isinstance(
        data.index,
        pd.DatetimeIndex,
    ):
        raise TypeError(
            "data index must be a pandas DatetimeIndex."
        )

    validate_session_parameters(
        market_open=market_open,
        market_close=market_close,
    )

    if data.empty:
        return data.copy()

    result = data.copy()

    timestamps = result.index.time

    mask = (
        (timestamps >= market_open)
        & (timestamps <= market_close)
    )

    return result.loc[mask].copy()


def is_market_session_timestamp(
    timestamp: pd.Timestamp,
    market_open: time = MARKET_OPEN,
    market_close: time = MARKET_CLOSE,
) -> bool:
    """Return whether a timestamp falls inside the regular session."""

    if not isinstance(
        timestamp,
        pd.Timestamp,
    ):
        raise TypeError(
            "timestamp must be a pandas Timestamp."
        )

    validate_session_parameters(
        market_open=market_open,
        market_close=market_close,
    )

    current_time = timestamp.time()

    return (
        market_open
        <= current_time
        <= market_close
    )


def remove_duplicate_timestamps(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Remove duplicate timestamps while preserving the first occurrence."""

    if not isinstance(
        data,
        pd.DataFrame,
    ):
        raise TypeError(
            "data must be a pandas DataFrame."
        )

    if not isinstance(
        data.index,
        pd.DatetimeIndex,
    ):
        raise TypeError(
            "data index must be a pandas DatetimeIndex."
        )

    return data.loc[
        ~data.index.duplicated(
            keep="first"
        )
    ].copy()


def prepare_market_session(
    data: pd.DataFrame,
    market_open: time = MARKET_OPEN,
    market_close: time = MARKET_CLOSE,
) -> pd.DataFrame:
    """
    Prepare market data for SignalForge processing.

    Operations:

    1. Validate the index.
    2. Sort timestamps.
    3. Remove duplicate timestamps.
    4. Keep regular-session candles only.
    """

    if not isinstance(
        data,
        pd.DataFrame,
    ):
        raise TypeError(
            "data must be a pandas DataFrame."
        )

    if not isinstance(
        data.index,
        pd.DatetimeIndex,
    ):
        raise TypeError(
            "data index must be a pandas DatetimeIndex."
        )

    validate_session_parameters(
        market_open=market_open,
        market_close=market_close,
    )

    result = data.copy()

    result = result.sort_index()

    result = remove_duplicate_timestamps(
        result
    )

    result = filter_market_session(
        result,
        market_open=market_open,
        market_close=market_close,
    )

    return result