from __future__ import annotations

from datetime import time

import pandas as pd

from src.backtest.simulator import Position
from src.market_data.replay_adapter import ReplayMarketDataAdapter
from src.paper_trading.engine import PaperTradingEngine
from src.paper_trading.reporting import (
    PaperTradingReport,
    create_paper_trading_report,
)
from src.strategy.backtest_strategy import (
    StrategyConfig,
    create_signal_function,
)


class PaperTradingReplayRunner:
    """
    Connects a replay market-data adapter to the frozen SignalForge
    strategy and paper-trading engine.

    Flow:

        ReplayMarketDataAdapter
                ↓
        1-minute candle
                ↓
        Frozen SignalForge strategy
                ↓
        LONG / SHORT / None
                ↓
        PaperTradingEngine
                ↓
        Paper trades + P&L

    This class is for deterministic paper-trading simulation only.
    It does not place broker orders.
    """

    SESSION_START = time(9, 15)
    SESSION_END = time(15, 30)

    def __init__(
        self,
        adapter: ReplayMarketDataAdapter,
        starting_capital: float = 100000.0,
        quantity: int = 1,
        transaction_cost_rate: float = 0.0001,
        strategy_config: StrategyConfig | None = None,
    ) -> None:
        if not isinstance(
            adapter,
            ReplayMarketDataAdapter,
        ):
            raise TypeError(
                "adapter must be a ReplayMarketDataAdapter."
            )

        self.adapter = adapter

        self.engine = PaperTradingEngine(
            starting_capital=starting_capital,
            quantity=quantity,
            transaction_cost_rate=transaction_cost_rate,
        )

        self.strategy_config = strategy_config

        self._previous_candle: pd.Series | None = None
        self._previous_timestamp: pd.Timestamp | None = None

    @property
    def report(self) -> PaperTradingReport:
        """Return the current paper-trading report."""
        return create_paper_trading_report(
            self.engine.state
        )

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

    @staticmethod
    def _validate_signal(
        signal: Position | None,
    ) -> None:
        if signal not in (
            None,
            Position.LONG,
            Position.SHORT,
        ):
            raise ValueError(
                f"Unexpected strategy position: {signal}"
            )

    def run(self) -> PaperTradingEngine:
        """
        Consume every replay candle sequentially.

        The complete replay dataset is used to initialize the frozen
        strategy's indicator context. The adapter controls which
        candle is actually processed at each step.

        No future candle is passed to the strategy as the current
        market observation.
        """

        if self.adapter.remaining_candles == 0:
            return self.engine

        strategy_data = self.adapter.data

        signal_function = create_signal_function(
            strategy_data,
            self.strategy_config,
        )

        while self.adapter.has_next():
            candle = self.adapter.next_candle()
            timestamp = self.adapter.current_timestamp

            if timestamp is None:
                raise RuntimeError(
                    "Replay adapter returned a candle "
                    "without a timestamp."
                )

            # Close anything left from the previous
            # calendar day.
            if (
                self._previous_timestamp is not None
                and timestamp.date()
                != self._previous_timestamp.date()
            ):
                if self._previous_candle is not None:
                    self._close_position_if_open(
                        engine=self.engine,
                        timestamp=self._previous_timestamp,
                        price=float(
                            self._previous_candle["close"]
                        ),
                        reason="Session end",
                    )

            # Ignore pre-market and post-market candles.
            if not self._is_session_timestamp(
                timestamp
            ):
                if self._is_session_end(timestamp):
                    self._close_position_if_open(
                        engine=self.engine,
                        timestamp=timestamp,
                        price=float(candle["close"]),
                        reason="Session end",
                    )

                self._previous_candle = candle
                self._previous_timestamp = timestamp

                continue

            # The first candle has no previous candle.
            if self._previous_candle is None:
                self._previous_candle = candle
                self._previous_timestamp = timestamp

                continue

            signal = signal_function(
                candle,
                self._previous_candle,
            )

            self._validate_signal(signal)

            self.engine.process_signal(
                timestamp=timestamp.to_pydatetime(),
                signal=signal,
                price=float(candle["close"]),
            )

            # Never carry a position beyond the session.
            if self._is_session_end(timestamp):
                self._close_position_if_open(
                    engine=self.engine,
                    timestamp=timestamp,
                    price=float(candle["close"]),
                    reason="Session end",
                )

            self._previous_candle = candle
            self._previous_timestamp = timestamp

        # Final safety closure.
        if (
            self._previous_candle is not None
            and self._previous_timestamp is not None
        ):
            self._close_position_if_open(
                engine=self.engine,
                timestamp=self._previous_timestamp,
                price=float(
                    self._previous_candle["close"]
                ),
                reason="End of data",
            )

        return self.engine