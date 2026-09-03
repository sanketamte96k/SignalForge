from __future__ import annotations

import pandas as pd

from src.backtest.simulator import Position
from src.paper_trading.engine import PaperTradingEngine
from src.strategy.backtest_strategy import (
    StrategyConfig,
    create_signal_function,
)


class PaperTradingRunner:
    """
    Connects the frozen SignalForge strategy to the paper-trading engine.

    Flow:

        1-minute market data
                ↓
        Frozen SignalForge strategy
                ↓
        LONG / SHORT / None
                ↓
        Paper Trading Engine
                ↓
        Paper trades + P&L
    """

    def __init__(
        self,
        starting_capital: float = 100000.0,
        quantity: int = 1,
        transaction_cost_rate: float = 0.0001,
        strategy_config: StrategyConfig | None = None,
    ) -> None:
        self.engine = PaperTradingEngine(
            starting_capital=starting_capital,
            quantity=quantity,
            transaction_cost_rate=transaction_cost_rate,
        )

        self.strategy_config = strategy_config

    @staticmethod
    def _validate_market_data(data: pd.DataFrame) -> None:
        if data.empty:
            raise ValueError("Market data cannot be empty")

        required_columns = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        missing_columns = required_columns - set(data.columns)

        if missing_columns:
            raise ValueError(
                f"Missing required columns: {sorted(missing_columns)}"
            )

        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError(
                "Market data index must be a DatetimeIndex"
            )

        if not data.index.is_monotonic_increasing:
            raise ValueError(
                "Market data must be sorted by timestamp"
            )

    @staticmethod
    def _prepare_data(data: pd.DataFrame) -> pd.DataFrame:
        prepared = data.copy()

        prepared = prepared.sort_index()

        prepared = prepared[
            ~prepared.index.duplicated(keep="last")
        ]

        return prepared

    def run(
        self,
        data: pd.DataFrame,
    ) -> PaperTradingEngine:
        """
        Run paper trading over chronological 1-minute market data.

        The frozen SignalForge strategy receives each row
        sequentially and controls all signal generation.
        """

        self._validate_market_data(data)

        data = self._prepare_data(data)

        signal_function = create_signal_function(
            data,
            self.strategy_config,
        )

        if len(data) < 2:
            return self.engine

        previous_row = data.iloc[0]

        for timestamp, row in data.iloc[1:].iterrows():
            signal = signal_function(
                row,
                previous_row,
            )

            if signal not in (
                None,
                Position.LONG,
                Position.SHORT,
            ):
                raise ValueError(
                    f"Unexpected strategy position: {signal}"
                )

            price = float(row["close"])

            self.engine.process_signal(
                timestamp=timestamp,
                signal=signal,
                price=price,
            )

            previous_row = row

        return self.engine