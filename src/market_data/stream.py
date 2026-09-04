"""Causal streaming market-data interfaces for SignalForge."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class MarketDataStream(ABC):
    """
    Abstract interface for sequential market-data consumption.

    Implementations expose candles sequentially so consumers can process
    market data causally, without depending on future candles.

    This interface is intentionally broker-independent so the same
    architecture can later support both historical replay and live data.
    """

    @abstractmethod
    def has_next(self) -> bool:
        """
        Return True when another candle is available.
        """
        raise NotImplementedError

    @abstractmethod
    def next_candle(self) -> pd.Series:
        """
        Consume and return the next available candle.

        Raises:
            StopIteration: If no candle remains.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def current_timestamp(self) -> pd.Timestamp | None:
        """
        Return the timestamp of the most recently consumed candle.

        Returns:
            None before the first candle has been consumed.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def remaining_candles(self) -> int:
        """
        Return the number of candles remaining.
        """
        raise NotImplementedError