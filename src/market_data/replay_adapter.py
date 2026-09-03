from __future__ import annotations

import pandas as pd

from .adapter import MarketDataAdapter, MarketDataValidationError, validate_market_data


class ReplayMarketDataAdapter(MarketDataAdapter):
    """
    Deterministic market-data adapter that replays historical 1-minute candles.

    This adapter is intended for development and paper-trading simulation only.
    It does not connect to a broker or place orders.
    """

    def __init__(self, data: pd.DataFrame) -> None:
        self._data = validate_market_data(data)
        self._cursor = 0

    def get_latest_candle(self) -> pd.Series:
        if self._cursor == 0:
            raise MarketDataValidationError(
                "No candle has been consumed yet."
            )

        return self._data.iloc[self._cursor - 1].copy()

    def get_recent_candles(self, limit: int) -> pd.DataFrame:
        if not isinstance(limit, int):
            raise TypeError("limit must be an integer.")

        if limit <= 0:
            raise ValueError("limit must be positive.")

        if self._cursor == 0:
            return self._data.iloc[0:0].copy()

        start = max(0, self._cursor - limit)
        return self._data.iloc[start:self._cursor].copy()

    def has_next(self) -> bool:
        return self._cursor < len(self._data)

    def next_candle(self) -> pd.Series:
        if not self.has_next():
            raise StopIteration("No more market data available.")

        candle = self._data.iloc[self._cursor].copy()
        self._cursor += 1
        return candle

    @property
    def current_timestamp(self) -> pd.Timestamp | None:
        if self._cursor == 0:
            return None

        return self._data.index[self._cursor - 1]

    @property
    def remaining_candles(self) -> int:
        return len(self._data) - self._cursor

    def reset(self) -> None:
        self._cursor = 0