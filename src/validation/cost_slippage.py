from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.backtest.engine import run_backtest
from src.strategy.backtest_strategy import create_signal_function


REQUIRED_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
)


@dataclass(frozen=True)
class CostSlippageScenario:
    """Execution-friction result for one scenario."""

    transaction_cost_rate: float
    slippage_rate: float
    trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    gross_pnl: float
    transaction_cost: float
    slippage_cost: float
    net_pnl: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_pct: float


@dataclass(frozen=True)
class CostSlippageResult:
    """Result of transaction-cost and slippage validation."""

    passed: bool
    total_candles: int
    scenarios_checked: int
    baseline_trades: int
    baseline_net_pnl: float
    selected_scenario: CostSlippageScenario | None
    scenarios: tuple[CostSlippageScenario, ...]
    issues: tuple[str, ...]

    @property
    def has_evidence(self) -> bool:
        """Return True when at least one scenario was evaluated."""
        return self.scenarios_checked > 0

    @property
    def friction_resistant(self) -> bool:
        """Return True when the selected scenario remains profitable."""
        return (
            self.selected_scenario is not None
            and self.selected_scenario.net_pnl > 0.0
        )


class CostSlippageValidator:
    """
    Validate strategy viability after execution friction.

    Transaction costs are passed into the authoritative backtest engine.
    Slippage is applied as a post-backtest execution overlay and does not
    alter strategy signals or trade generation.
    """

    def __init__(
        self,
        transaction_cost_rates: tuple[float, ...] = (
            0.0,
            0.0001,
            0.0002,
        ),
        slippage_rates: tuple[float, ...] = (
            0.0,
            0.0001,
            0.0002,
        ),
        initial_capital: float = 100_000.0,
        quantity: int = 1,
        minimum_trades_required: int = 1,
        selected_transaction_cost_rate: float = 0.0001,
        selected_slippage_rate: float = 0.0001,
    ) -> None:

        if not transaction_cost_rates:
            raise ValueError(
                "transaction_cost_rates must not be empty"
            )

        if not slippage_rates:
            raise ValueError(
                "slippage_rates must not be empty"
            )

        if any(rate < 0.0 for rate in transaction_cost_rates):
            raise ValueError(
                "transaction_cost_rates cannot contain negative values"
            )

        if any(rate < 0.0 for rate in slippage_rates):
            raise ValueError(
                "slippage_rates cannot contain negative values"
            )

        if initial_capital <= 0.0:
            raise ValueError(
                "initial_capital must be greater than zero"
            )

        if not isinstance(quantity, int):
            raise ValueError(
                "quantity must be an integer"
            )

        if quantity <= 0:
            raise ValueError(
                "quantity must be greater than zero"
            )

        if minimum_trades_required < 1:
            raise ValueError(
                "minimum_trades_required must be at least 1"
            )

        if selected_transaction_cost_rate < 0.0:
            raise ValueError(
                "selected_transaction_cost_rate cannot be negative"
            )

        if selected_slippage_rate < 0.0:
            raise ValueError(
                "selected_slippage_rate cannot be negative"
            )

        if (
            selected_transaction_cost_rate
            not in transaction_cost_rates
        ):
            raise ValueError(
                "selected_transaction_cost_rate must be included "
                "in transaction_cost_rates"
            )

        if selected_slippage_rate not in slippage_rates:
            raise ValueError(
                "selected_slippage_rate must be included "
                "in slippage_rates"
            )

        self.transaction_cost_rates = tuple(
            transaction_cost_rates
        )
        self.slippage_rates = tuple(
            slippage_rates
        )
        self.initial_capital = initial_capital
        self.quantity = quantity
        self.minimum_trades_required = (
            minimum_trades_required
        )
        self.selected_transaction_cost_rate = (
            selected_transaction_cost_rate
        )
        self.selected_slippage_rate = (
            selected_slippage_rate
        )

    def check(
        self,
        data: pd.DataFrame,
    ) -> CostSlippageResult:
        """Run transaction-cost and slippage validation."""

        validation_error = self._validate_data(data)

        if validation_error is not None:
            return CostSlippageResult(
                passed=False,
                total_candles=(
                    len(data)
                    if isinstance(data, pd.DataFrame)
                    else 0
                ),
                scenarios_checked=0,
                baseline_trades=0,
                baseline_net_pnl=0.0,
                selected_scenario=None,
                scenarios=(),
                issues=(validation_error,),
            )

        working_data = data.copy()

        scenarios: list[CostSlippageScenario] = []

        baseline_trades = 0
        baseline_net_pnl = 0.0

        baseline_result = None

        backtest_results = {}

        for transaction_cost_rate in (
            self.transaction_cost_rates
        ):
            try:
                signal_function = create_signal_function(
                    working_data
                )

                result = run_backtest(
                    data=working_data,
                    signal_function=signal_function,
                    initial_capital=self.initial_capital,
                    quantity=self.quantity,
                    transaction_cost_rate=(
                        transaction_cost_rate
                    ),
                )

            except Exception as exc:
                return CostSlippageResult(
                    passed=False,
                    total_candles=len(working_data),
                    scenarios_checked=len(scenarios),
                    baseline_trades=baseline_trades,
                    baseline_net_pnl=baseline_net_pnl,
                    selected_scenario=None,
                    scenarios=tuple(scenarios),
                    issues=(
                        "backtest evaluation failed: "
                        f"{exc}",
                    ),
                )

            backtest_results[transaction_cost_rate] = result

            if transaction_cost_rate == 0.0:
                baseline_result = result
                baseline_trades = len(result.trades)

                baseline_net_pnl = sum(
                    float(trade.net_pnl)
                    for trade in result.trades
                )

        if baseline_result is None:
            return CostSlippageResult(
                passed=False,
                total_candles=len(working_data),
                scenarios_checked=0,
                baseline_trades=0,
                baseline_net_pnl=0.0,
                selected_scenario=None,
                scenarios=(),
                issues=(
                    "transaction_cost_rates must include "
                    "0.0 for baseline validation",
                ),
            )

        for transaction_cost_rate, result in (
            backtest_results.items()
        ):
            trades = result.trades

            for slippage_rate in self.slippage_rates:

                scenario = self._build_scenario(
                    trades=trades,
                    transaction_cost_rate=(
                        transaction_cost_rate
                    ),
                    slippage_rate=slippage_rate,
                )

                scenarios.append(scenario)

        selected_scenario = next(
            (
                scenario
                for scenario in scenarios
                if (
                    scenario.transaction_cost_rate
                    == self.selected_transaction_cost_rate
                    and scenario.slippage_rate
                    == self.selected_slippage_rate
                )
            ),
            None,
        )

        issues: list[str] = []

        if baseline_trades < self.minimum_trades_required:
            issues.append(
                "insufficient baseline trades: "
                f"{baseline_trades} < "
                f"{self.minimum_trades_required}"
            )

        if selected_scenario is None:
            issues.append(
                "selected execution scenario was not evaluated"
            )
        else:
            if (
                selected_scenario.trades
                != baseline_trades
            ):
                issues.append(
                    "trade count changed across execution-cost "
                    "scenarios"
                )

            if selected_scenario.net_pnl <= 0.0:
                issues.append(
                    "strategy is not profitable under the "
                    "selected execution scenario"
                )

        for scenario in scenarios:
            if scenario.trades != baseline_trades:
                issues.append(
                    "trade count changed across execution-friction "
                    "scenarios"
                )
                break

        passed = (
            baseline_trades >= self.minimum_trades_required
            and selected_scenario is not None
            and selected_scenario.net_pnl > 0.0
            and all(
                scenario.trades == baseline_trades
                for scenario in scenarios
            )
        )

        return CostSlippageResult(
            passed=passed,
            total_candles=len(working_data),
            scenarios_checked=len(scenarios),
            baseline_trades=baseline_trades,
            baseline_net_pnl=baseline_net_pnl,
            selected_scenario=selected_scenario,
            scenarios=tuple(scenarios),
            issues=tuple(dict.fromkeys(issues)),
        )

    @staticmethod
    def _validate_data(
        data: pd.DataFrame,
    ) -> str | None:
        """Validate the minimum input structure."""

        if not isinstance(data, pd.DataFrame):
            return (
                "market data must be a pandas DataFrame"
            )

        missing_columns = [
            column
            for column in REQUIRED_COLUMNS
            if column not in data.columns
        ]

        if missing_columns:
            return (
                "missing required columns: "
                + ", ".join(missing_columns)
            )

        if not isinstance(
            data.index,
            pd.DatetimeIndex,
        ):
            return (
                "market data must use a DatetimeIndex"
            )

        if data.empty:
            return "market data is empty"

        if data.index.has_duplicates:
            return (
                "market data contains duplicate timestamps"
            )

        if not data.index.is_monotonic_increasing:
            return (
                "market data timestamps are not chronological"
            )

        required_data = data[
            list(REQUIRED_COLUMNS)
        ]

        if required_data.isna().any().any():
            return (
                "market data contains missing values"
            )

        return None

    def _build_scenario(
        self,
        trades,
        transaction_cost_rate: float,
        slippage_rate: float,
    ) -> CostSlippageScenario:
        """Build metrics for one execution-friction scenario."""

        if not trades:
            return CostSlippageScenario(
                transaction_cost_rate=(
                    transaction_cost_rate
                ),
                slippage_rate=slippage_rate,
                trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                gross_pnl=0.0,
                transaction_cost=0.0,
                slippage_cost=0.0,
                net_pnl=0.0,
                profit_factor=0.0,
                max_drawdown=0.0,
                max_drawdown_pct=0.0,
            )

        adjusted_pnls: list[float] = []
        transaction_costs: list[float] = []
        slippages: list[float] = []

        for trade in trades:
            entry_price = float(
                trade.entry_price
            )
            exit_price = float(
                trade.exit_price
            )
            quantity = float(
                trade.quantity
            )

            notional = (
                entry_price + exit_price
            ) * quantity

            transaction_cost = (
                notional
                * transaction_cost_rate
            )

            slippage = (
                notional
                * slippage_rate
            )

            adjusted_pnl = (
                float(trade.net_pnl)
                - slippage
            )

            adjusted_pnls.append(
                adjusted_pnl
            )

            transaction_costs.append(
                transaction_cost
            )

            slippages.append(
                slippage
            )

        wins = [
            pnl
            for pnl in adjusted_pnls
            if pnl > 0.0
        ]

        losses = [
            pnl
            for pnl in adjusted_pnls
            if pnl < 0.0
        ]

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0.0
            else float("inf")
        )

        net_pnl = sum(adjusted_pnls)

        win_rate = (
            len(wins)
            / len(adjusted_pnls)
            * 100.0
        )

        max_drawdown, max_drawdown_pct = (
            CostSlippageValidator._calculate_drawdown(
                adjusted_pnls,
                self.initial_capital,
            )
        )

        return CostSlippageScenario(
            transaction_cost_rate=(
                transaction_cost_rate
            ),
            slippage_rate=slippage_rate,
            trades=len(adjusted_pnls),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=win_rate,
            gross_pnl=sum(
                float(trade.net_pnl)
                for trade in trades
            ),
            transaction_cost=sum(
                transaction_costs
            ),
            slippage_cost=sum(
                slippages
            ),
            net_pnl=net_pnl,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
        )

    @staticmethod
    def _calculate_drawdown(
        pnls: list[float],
        initial_capital: float,
    ) -> tuple[float, float]:
        """Calculate sequential equity drawdown."""

        equity = initial_capital
        peak_equity = equity

        max_drawdown = 0.0
        max_drawdown_pct = 0.0

        for pnl in pnls:
            equity += pnl

            if equity > peak_equity:
                peak_equity = equity

            drawdown = (
                peak_equity - equity
            )

            drawdown_pct = (
                drawdown
                / peak_equity
                * 100.0
                if peak_equity > 0.0
                else 0.0
            )

            max_drawdown = max(
                max_drawdown,
                drawdown,
            )

            max_drawdown_pct = max(
                max_drawdown_pct,
                drawdown_pct,
            )

        return (
            max_drawdown,
            max_drawdown_pct,
        )
