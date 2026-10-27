from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.backtest.engine import run_backtest
from src.backtest.simulator import Trade
from src.strategy.backtest_strategy import (
    StrategyConfig,
    create_signal_function,
)


@dataclass(frozen=True)
class HistoricalBacktestResult:
    """Result of historical strategy validation."""

    passed: bool
    total_candles: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    net_pnl: float
    profit_factor: float
    max_drawdown: float
    max_losing_streak: int
    minimum_trades_required: int
    minimum_net_pnl_required: float
    issues: tuple[str, ...]
    execution_model: str = "same_close"
    trades: tuple[Trade, ...] = ()

    @property
    def has_trade_evidence(self) -> bool:
        """Return whether enough trades were generated."""

        return (
            self.total_trades
            >= self.minimum_trades_required
        )

    @property
    def profitable(self) -> bool:
        """Return whether historical net P&L is positive."""

        return (
            self.net_pnl
            > self.minimum_net_pnl_required
        )


class HistoricalBacktestValidator:
    """
    Validate historical strategy behavior for an instrument.

    This validator reuses the authoritative SignalForge strategy
    and backtest engine. It does not modify strategy rules and does
    not make the final instrument approval decision.
    """

    def __init__(
        self,
        *,
        initial_capital: float = 100_000.0,
        quantity: int = 1,
        transaction_cost_rate: float = 0.0,
        minimum_trades_required: int = 1,
        minimum_net_pnl_required: float = 0.0,
        strategy_config: StrategyConfig | None = None,
        execution_model: str = "same_close",
    ) -> None:
        if execution_model not in ("same_close", "next_open"):
            raise ValueError(
                f"Unsupported execution_model: {execution_model}. "
                "Supported models: 'same_close', 'next_open'"
            )
        self._validate_configuration(
            initial_capital=initial_capital,
            quantity=quantity,
            transaction_cost_rate=transaction_cost_rate,
            minimum_trades_required=(
                minimum_trades_required
            ),
            minimum_net_pnl_required=(
                minimum_net_pnl_required
            ),
        )

        if strategy_config is None:
            strategy_config = StrategyConfig()

        if not isinstance(
            strategy_config,
            StrategyConfig,
        ):
            raise TypeError(
                "strategy_config must be a StrategyConfig."
            )

        self._initial_capital = initial_capital
        self._quantity = quantity
        self._transaction_cost_rate = (
            transaction_cost_rate
        )
        self._minimum_trades_required = (
            minimum_trades_required
        )
        self._minimum_net_pnl_required = (
            minimum_net_pnl_required
        )
        self._strategy_config = strategy_config
        self._execution_model = execution_model

    def check(
        self,
        data: pd.DataFrame,
    ) -> HistoricalBacktestResult:
        """Run the authoritative historical backtest."""

        if not isinstance(
            data,
            pd.DataFrame,
        ):
            return self._failed_result(
                "Market data must be a pandas DataFrame."
            )

        if data.empty:
            return self._failed_result(
                "Market data cannot be empty."
            )

        if not isinstance(
            data.index,
            pd.DatetimeIndex,
        ):
            return self._failed_result(
                "Market data index must be a DatetimeIndex."
            )

        required_columns = {
            "open",
            "high",
            "low",
            "close",
            "volume",
        }

        missing = sorted(
            required_columns.difference(
                data.columns
            )
        )

        if missing:
            return self._failed_result(
                "Missing required columns: "
                f"{missing}"
            )

        working = data.copy()

        try:
            signal_function = create_signal_function(
                working,
                self._strategy_config,
            )

            result = run_backtest(
                data=working,
                signal_function=signal_function,
                initial_capital=self._initial_capital,
                quantity=self._quantity,
                transaction_cost_rate=(
                    self._transaction_cost_rate
                ),
                execution_model=self._execution_model,
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            return self._failed_result(
                f"Historical backtest failed: {exc}"
            )

        total_trades = len(result.trades)

        winning_trades = sum(
            1
            for trade in result.trades
            if trade.net_pnl > 0
        )

        losing_trades = sum(
            1
            for trade in result.trades
            if trade.net_pnl < 0
        )

        if total_trades > 0:
            win_rate = round(
                winning_trades
                / total_trades
                * 100.0,
                2,
            )
        else:
            win_rate = 0.0

        net_pnl = round(
            sum(
                trade.net_pnl
                for trade in result.trades
            ),
            2,
        )

        gross_profit = sum(
            trade.net_pnl
            for trade in result.trades
            if trade.net_pnl > 0
        )

        gross_loss = abs(
            sum(
                trade.net_pnl
                for trade in result.trades
                if trade.net_pnl < 0
            )
        )

        if gross_loss == 0:
            if gross_profit > 0:
                profit_factor = float("inf")
            else:
                profit_factor = 0.0
        else:
            profit_factor = round(
                gross_profit / gross_loss,
                4,
            )

        # The authoritative backtest metrics expose
        # max_drawdown_pct. Preserve the validator's public
        # max_drawdown field as the percentage value.
        max_drawdown = round(
            float(
                result.metrics.max_drawdown_pct
            ),
            2,
        )

        max_losing_streak = (
            self._calculate_max_losing_streak(
                result.trades
            )
        )

        issues: list[str] = []

        if (
            total_trades
            < self._minimum_trades_required
        ):
            issues.append(
                "Historical backtest did not generate "
                "enough trades: "
                f"{total_trades} < "
                f"{self._minimum_trades_required}."
            )

        if (
            net_pnl
            <= self._minimum_net_pnl_required
        ):
            issues.append(
                "Historical net P&L did not exceed "
                "the required minimum: "
                f"{net_pnl:.2f} <= "
                f"{self._minimum_net_pnl_required:.2f}."
            )

        return HistoricalBacktestResult(
            passed=not issues,
            total_candles=len(working),
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            net_pnl=net_pnl,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            max_losing_streak=max_losing_streak,
            minimum_trades_required=(
                self._minimum_trades_required
            ),
            minimum_net_pnl_required=(
                self._minimum_net_pnl_required
            ),
            issues=tuple(issues),
            execution_model=self._execution_model,
            trades=tuple(result.trades),
        )

    @staticmethod
    def _calculate_max_losing_streak(
        trades,
    ) -> int:
        """Calculate the longest consecutive losing streak."""

        current_streak = 0
        maximum_streak = 0

        for trade in trades:
            if trade.net_pnl < 0:
                current_streak += 1
                maximum_streak = max(
                    maximum_streak,
                    current_streak,
                )
            else:
                current_streak = 0

        return maximum_streak

    @staticmethod
    def _validate_configuration(
        *,
        initial_capital: float,
        quantity: int,
        transaction_cost_rate: float,
        minimum_trades_required: int,
        minimum_net_pnl_required: float,
    ) -> None:
        """Validate validator configuration."""

        if not isinstance(
            initial_capital,
            (int, float),
        ) or isinstance(
            initial_capital,
            bool,
        ):
            raise TypeError(
                "initial_capital must be numeric."
            )

        if initial_capital <= 0:
            raise ValueError(
                "initial_capital must be greater than zero."
            )

        if not isinstance(
            quantity,
            int,
        ) or isinstance(
            quantity,
            bool,
        ):
            raise TypeError(
                "quantity must be an integer."
            )

        if quantity <= 0:
            raise ValueError(
                "quantity must be greater than zero."
            )

        if not isinstance(
            transaction_cost_rate,
            (int, float),
        ) or isinstance(
            transaction_cost_rate,
            bool,
        ):
            raise TypeError(
                "transaction_cost_rate must be numeric."
            )

        if transaction_cost_rate < 0:
            raise ValueError(
                "transaction_cost_rate cannot be negative."
            )

        if not isinstance(
            minimum_trades_required,
            int,
        ) or isinstance(
            minimum_trades_required,
            bool,
        ):
            raise TypeError(
                "minimum_trades_required must be an integer."
            )

        if minimum_trades_required <= 0:
            raise ValueError(
                "minimum_trades_required must be greater than zero."
            )

        if not isinstance(
            minimum_net_pnl_required,
            (int, float),
        ) or isinstance(
            minimum_net_pnl_required,
            bool,
        ):
            raise TypeError(
                "minimum_net_pnl_required must be numeric."
            )

    @staticmethod
    def _failed_result(
        issue: str,
    ) -> HistoricalBacktestResult:
        """Build a failed result for invalid input."""

        return HistoricalBacktestResult(
            passed=False,
            total_candles=0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            net_pnl=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            max_losing_streak=0,
            minimum_trades_required=0,
            minimum_net_pnl_required=0.0,
            issues=(issue,),
        )
