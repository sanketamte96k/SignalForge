"""Causal historical replay runner for SignalForge."""

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
from src.strategy.backtest_strategy import StrategyConfig
from src.strategy.context import CausalStrategyContext


class PaperTradingReplayRunner:
    """
    Connect a replay market-data stream to the causal SignalForge
    strategy context and paper-trading engine.

    Replay architecture:

        Historical warm-up
                ↓
        CausalStrategyContext
                ↓
        Replay boundary
                ↓
        One candle at a time
                ↓
        Frozen SignalForge strategy
                ↓
        PaperTradingEngine

    Candles before replay_start are used only to warm the causal
    indicator state.

    Candles at or after replay_start are tradeable observations.

    No future replay candle is supplied to the strategy before it
    arrives through the replay adapter.
    """

    SESSION_START = time(9, 15)
    SESSION_END = time(15, 30)

    def __init__(
        self,
        adapter: ReplayMarketDataAdapter | None = None,
        starting_capital: float = 100000.0,
        quantity: int = 1,
        transaction_cost_rate: float = 0.0001,
        strategy_config: StrategyConfig | None = None,
        adapter_data: pd.DataFrame | None = None,
        replay_start: pd.Timestamp | str | None = None,
    ) -> None:
        if adapter is None and adapter_data is not None:
            adapter = ReplayMarketDataAdapter(
                adapter_data
            )

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

        if replay_start is None:
            self._replay_start = None
        else:
            self._replay_start = pd.Timestamp(
                replay_start
            )

            if pd.isna(self._replay_start):
                raise ValueError(
                    "replay_start must not be NaT."
                )

        self._strategy_context: (
            CausalStrategyContext | None
        ) = None

        self._previous_candle: pd.Series | None = None
        self._previous_timestamp: pd.Timestamp | None = None

    @property
    def replay_start(
        self,
    ) -> pd.Timestamp | None:
        """Return the configured replay boundary."""

        return self._replay_start

    @property
    def report(self) -> PaperTradingReport:
        """Return the current paper-trading report."""

        return create_paper_trading_report(
            self.engine.state
        )

    @property
    def strategy_context(
        self,
    ) -> CausalStrategyContext | None:
        """
        Return the causal strategy context created by the run.

        Returns None before run() starts.
        """

        return self._strategy_context

    @classmethod
    def _is_session_timestamp(
        cls,
        timestamp: pd.Timestamp,
    ) -> bool:
        """Return True when timestamp is inside the session."""

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
        """Return True when timestamp is at or after session end."""

        return timestamp.time() >= cls.SESSION_END

    @staticmethod
    def _close_position_if_open(
        engine: PaperTradingEngine,
        timestamp: pd.Timestamp,
        price: float,
        reason: str,
    ) -> None:
        """Close the current position if one is open."""

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
        """Validate the strategy position."""

        if signal not in (
            None,
            Position.LONG,
            Position.SHORT,
        ):
            raise ValueError(
                f"Unexpected strategy position: {signal}"
            )

    def _resolve_replay_start(
        self,
    ) -> pd.Timestamp:
        """
        Resolve the replay boundary.

        An explicit replay_start is preferred.

        When omitted, the first candle remains the replay boundary,
        preserving backward compatibility with existing callers.
        """

        if self._replay_start is not None:
            return self._replay_start

        data = self.adapter.data

        if data.empty:
            raise ValueError(
                "Cannot resolve replay_start from empty data."
            )

        return pd.Timestamp(
            data.index[0]
        )

    @staticmethod
    def _make_candle(
        timestamp: pd.Timestamp,
        row: pd.Series,
    ) -> pd.Series:
        """Create a defensive candle Series with timestamp as name."""

        candle = row.copy()
        candle.name = pd.Timestamp(timestamp)

        return candle

    def _create_empty_context(
        self,
    ) -> CausalStrategyContext:
        """Create a fresh causal strategy context."""

        return CausalStrategyContext(
            strategy_config=self.strategy_config,
        )

    def _warm_up_context(
        self,
        context: CausalStrategyContext,
        replay_start: pd.Timestamp,
    ) -> None:
        """
        Warm the causal context using only historical candles.

        Every warm-up candle is processed sequentially.

        No candle at or after replay_start is supplied here.
        """

        data = self.adapter.data

        warmup = data.loc[
            data.index < replay_start
        ]

        for timestamp, row in warmup.iterrows():
            candle = self._make_candle(
                timestamp,
                row,
            )

            context.process_candle(
                candle
            )

    def run(self) -> PaperTradingEngine:
        """
        Consume every replay candle sequentially.

        Historical candles before replay_start are used for causal
        indicator warm-up.

        Candles at or after replay_start are processed as the
        tradeable replay stream.
        """

        if self.adapter.remaining_candles == 0:
            return self.engine

        replay_start = self._resolve_replay_start()

        self._strategy_context = (
            self._create_empty_context()
        )

        # ---------------------------------------------------------
        # Historical causal warm-up.
        #
        # Only candles strictly before replay_start are supplied.
        # ---------------------------------------------------------
        self._warm_up_context(
            context=self._strategy_context,
            replay_start=replay_start,
        )

        while self.adapter.has_next():
            candle = self.adapter.next_candle()

            timestamp = self.adapter.current_timestamp

            if timestamp is None:
                raise RuntimeError(
                    "Replay adapter returned a candle "
                    "without a timestamp."
                )

            # -----------------------------------------------------
            # Candles before replay_start were already used for
            # warm-up. The adapter still consumes them sequentially
            # to preserve the existing replay contract.
            # -----------------------------------------------------
            if timestamp < replay_start:
                self._previous_candle = candle
                self._previous_timestamp = timestamp
                continue

            # -----------------------------------------------------
            # Calendar-day boundary.
            # -----------------------------------------------------
            if (
                self._previous_timestamp is not None
                and timestamp.date()
                != self._previous_timestamp.date()
            ):
                if self._previous_candle is not None:
                    self._close_position_if_open(
                        engine=self.engine,
                        timestamp=(
                            self._previous_timestamp
                        ),
                        price=float(
                            self._previous_candle[
                                "close"
                            ]
                        ),
                        reason="Session end",
                    )

            # -----------------------------------------------------
            # Ignore candles outside the trading session.
            # -----------------------------------------------------
            if not self._is_session_timestamp(
                timestamp
            ):
                if self._is_session_end(timestamp):
                    self._close_position_if_open(
                        engine=self.engine,
                        timestamp=timestamp,
                        price=float(
                            candle["close"]
                        ),
                        reason="Session end",
                    )

                self._previous_candle = candle
                self._previous_timestamp = timestamp

                continue

            # -----------------------------------------------------
            # Causal strategy processing.
            #
            # The strategy sees this candle only now.
            # -----------------------------------------------------
            context_result = (
                self._strategy_context.process_candle(
                    candle
                )
            )

            signal = context_result.position

            self._validate_signal(
                signal
            )

            self.engine.process_signal(
                timestamp=timestamp.to_pydatetime(),
                signal=signal,
                price=float(
                    candle["close"]
                ),
            )

            # -----------------------------------------------------
            # Never carry a position beyond session end.
            # -----------------------------------------------------
            if self._is_session_end(
                timestamp
            ):
                self._close_position_if_open(
                    engine=self.engine,
                    timestamp=timestamp,
                    price=float(
                        candle["close"]
                    ),
                    reason="Session end",
                )

            self._previous_candle = candle
            self._previous_timestamp = timestamp

        # ---------------------------------------------------------
        # Final safety closure.
        # ---------------------------------------------------------
        if (
            self._previous_candle is not None
            and self._previous_timestamp is not None
        ):
            self._close_position_if_open(
                engine=self.engine,
                timestamp=self._previous_timestamp,
                price=float(
                    self._previous_candle[
                        "close"
                    ]
                ),
                reason="End of data",
            )

        return self.engine