from __future__ import annotations

from datetime import time

import pandas as pd

from src.backtest.simulator import Position
from src.paper_trading.engine import PaperTradingEngine
from src.strategy.backtest_strategy import (
    StrategyConfig,
    create_signal_function,
)


class PaperTradingRunner:
    """
    Connects the frozen SignalForge strategy to the
    paper-trading engine.

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

    Safety rules:
    - NO_TRADE (None) means HOLD.
    - Positions are closed at session boundaries.
    - Positions are closed at the final supplied candle.
    - Positions must not carry overnight.
    """

    SESSION_START = time(9, 15)
    SESSION_END = time(15, 30)

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
            raise ValueError(
                "Market data cannot be empty"
            )

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

    @classmethod
    def _is_session_timestamp(
        cls,
        timestamp: pd.Timestamp,
    ) -> bool:
        current_time = timestamp.time()

        return (
            cls.SESSION_START
            <= current_time
            <= cls.SESSION_END
        )

    @classmethod
    def _is_session_end(
        cls,
        timestamp: pd.Timestamp,
    ) -> bool:
        return timestamp.time() >= cls.SESSION_END

    @staticmethod
    def _close_position_if_open(
        engine: PaperTradingEngine,
        timestamp: pd.Timestamp,
        price: float,
        reason: str,
    ) -> None:
        if not engine.state.has_position:
            return

        engine.close_position(
            timestamp=timestamp.to_pydatetime(),
            price=float(price),
            reason=reason,
        )

    def run(
        self,
        data: pd.DataFrame,
    ) -> PaperTradingEngine:
        """
        Run paper trading over chronological 1-minute market data.

        Strategy signals are processed sequentially.

        Positions are explicitly closed:
        - At the end of each trading session.
        - At the final supplied candle.

        NO_TRADE signals are passed through as HOLD behavior
        and do not close positions.
        """

        self._validate_market_data(data)

        data = self._prepare_data(data)

        signal_function = create_signal_function(
            data,
            self.strategy_config,
        )

        if len(data) < 2:
            if len(data) == 1:
                final_row = data.iloc[0]

                self._close_position_if_open(
                    engine=self.engine,
                    timestamp=data.index[0],
                    price=float(final_row["close"]),
                    reason="End of data",
                )

            return self.engine

        previous_row = data.iloc[0]
        previous_timestamp = data.index[0]

        for timestamp, row in data.iloc[1:].iterrows():
            current_timestamp = timestamp

            # If a new calendar day begins, make sure any
            # position from the previous session is closed.
            if (
                current_timestamp.date()
                != previous_timestamp.date()
            ):
                self._close_position_if_open(
                    engine=self.engine,
                    timestamp=previous_timestamp,
                    price=float(previous_row["close"]),
                    reason="Session end",
                )

            # Ignore timestamps outside the defined market
            # session. Any open position is closed safely.
            if not self._is_session_timestamp(
                current_timestamp
            ):
                if self._is_session_end(
                    current_timestamp
                ):
                    self._close_position_if_open(
                        engine=self.engine,
                        timestamp=current_timestamp,
                        price=float(row["close"]),
                        reason="Session end",
                    )

                previous_row = row
                previous_timestamp = current_timestamp
                continue

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
                timestamp=current_timestamp.to_pydatetime(),
                signal=signal,
                price=price,
            )

            # Never carry a position beyond the session.
            if self._is_session_end(
                current_timestamp
            ):
                self._close_position_if_open(
                    engine=self.engine,
                    timestamp=current_timestamp,
                    price=price,
                    reason="Session end",
                )

            previous_row = row
            previous_timestamp = current_timestamp

        # Final safety closure. Even if the dataset ends before
        # 15:30, no position may remain open after run().
        final_timestamp = data.index[-1]
        final_row = data.iloc[-1]

        self._close_position_if_open(
            engine=self.engine,
            timestamp=final_timestamp,
            price=float(final_row["close"]),
            reason="End of data",
        )

        return self.engine