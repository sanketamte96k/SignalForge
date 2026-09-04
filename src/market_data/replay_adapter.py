"""Historical replay market-data adapter for SignalForge."""

from __future__ import annotations

import pandas as pd

from .adapter import (
    MarketDataAdapter,
    MarketDataValidationError,
    validate_market_data,
)
from .stream import MarketDataStream


class ReplayMarketDataAdapter(
    MarketDataAdapter,
    MarketDataStream,
):
    """
    Deterministic market-data adapter that replays historical
    1-minute candles sequentially.

    This adapter is intended for development and paper-trading
    simulation only.

    It does not connect to a broker or place orders.

    The stream interface exposes candles sequentially so consumers
    can process market data causally.
    """

    def __init__(self, data: pd.DataFrame) -> None:
        self._data = validate_market_data(data)
        self._cursor = 0

    @property
    def data(self) -> pd.DataFrame:
        """
        Return a copy of the validated replay dataset.

        This property is retained for backward compatibility with
        existing replay and parity functionality.

        A copy is returned so callers cannot accidentally modify
        the adapter's internal market-data state.
        """
        return self._data.copy()

    def get_latest_candle(self) -> pd.Series:
        """
        Return the most recently consumed candle.

        Raises:
            MarketDataValidationError:
                If no candle has been consumed yet.
        """
        if self._cursor == 0:
            raise MarketDataValidationError(
                "No candle has been consumed yet."
            )

        return self._data.iloc[
            self._cursor - 1
        ].copy()

    def get_recent_candles(
        self,
        limit: int,
    ) -> pd.DataFrame:
        """
        Return up to the last `limit` consumed candles.

        Args:
            limit:
                Maximum number of previously consumed candles
                to return.

        Raises:
            TypeError:
                If limit is not an integer.
            ValueError:
                If limit is not positive.
        """
        if not isinstance(limit, int):
            raise TypeError(
                "limit must be an integer."
            )

        if limit <= 0:
            raise ValueError(
                "limit must be positive."
            )

        if self._cursor == 0:
            return self._data.iloc[
                0:0
            ].copy()

        start = max(
            0,
            self._cursor - limit,
        )

        return self._data.iloc[
            start:self._cursor
        ].copy()

    def has_next(self) -> bool:
        """
        Return True if another candle is available
        for replay.
        """
        return self._cursor < len(self._data)

    def next_candle(self) -> pd.Series:
        """
        Consume and return the next candle.

        Raises:
            StopIteration:
                If all candles have already been consumed.
        """
        if not self.has_next():
            raise StopIteration(
                "No more market data available."
            )

        candle = self._data.iloc[
            self._cursor
        ].copy()

        self._cursor += 1

        return candle

    @property
    def current_timestamp(
        self,
    ) -> pd.Timestamp | None:
        """
        Return the timestamp of the most recently
        consumed candle.

        Returns:
            None before the first candle has been consumed.
        """
        if self._cursor == 0:
            return None

        return self._data.index[
            self._cursor - 1
        ]

    @property
    def remaining_candles(self) -> int:
        """
        Return the number of candles remaining
        in the replay.
        """
        return len(self._data) - self._cursor

    def reset(self) -> None:
        """
        Reset the replay cursor to the beginning.
        """
        self._cursor = 0