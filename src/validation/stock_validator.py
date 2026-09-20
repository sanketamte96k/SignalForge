"""Orchestrate the complete SignalForge stock validation pipeline."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.strategy.backtest_strategy import StrategyConfig
from src.universe.validation import ValidationStatus
from src.validation.approval import ApprovalResult, ApprovalValidator
from src.validation.causality import CausalityResult, CausalityValidator
from src.validation.cost_slippage import (
    CostSlippageResult,
    CostSlippageValidator,
)
from src.validation.data_availability import (
    DataAvailabilityChecker,
    DataAvailabilityResult,
)
from src.validation.data_quality import (
    DataQualityChecker,
    DataQualityResult,
)
from src.validation.historical_backtest import (
    HistoricalBacktestResult,
    HistoricalBacktestValidator,
)
from src.validation.indicator_compatibility import (
    IndicatorCompatibilityChecker,
    IndicatorCompatibilityResult,
)
from src.validation.regime_oos import (
    RegimeOOSResult,
    RegimeOOSValidator,
)


@dataclass(frozen=True)
class StockValidationResult:
    """Complete validation result for one stock."""

    symbol: str
    data_availability: DataAvailabilityResult
    data_quality: DataQualityResult
    indicator_compatibility: IndicatorCompatibilityResult
    historical_backtest: HistoricalBacktestResult
    causality: CausalityResult
    cost_slippage: CostSlippageResult
    regime_oos: RegimeOOSResult
    approval: ApprovalResult

    @property
    def status(self) -> ValidationStatus:
        """Return the final validation status."""

        return self.approval.status

    @property
    def signal_eligible(self) -> bool:
        """Return whether the stock may enter the signal engine."""

        return self.approval.signal_eligible

    @property
    def approved(self) -> bool:
        """Return whether every validation gate passed."""

        return self.approval.approved

    @property
    def passed_gates(self) -> tuple[str, ...]:
        """Return validation gates that passed."""

        return self.approval.passed_gates

    @property
    def failed_gates(self) -> tuple[str, ...]:
        """Return validation gates that failed."""

        return self.approval.failed_gates

    @property
    def issues(self) -> tuple[str, ...]:
        """Return all validation issues."""

        return self.approval.issues


class StockValidationRunner:
    """
    Run the complete seven-gate validation pipeline for a stock.

    This class orchestrates existing Phase 9 validators. It does not
    modify the strategy, mutate the supplied market data, or update
    universe state.
    """

    def __init__(
        self,
        *,
        development_start: str | pd.Timestamp,
        development_end: str | pd.Timestamp,
        oos_start: str | pd.Timestamp,
        oos_end: str | pd.Timestamp,
        minimum_availability_candles: int = 1,
        minimum_availability_sessions: int = 1,
        required_timeframes: tuple[str, ...] = (
            "5m",
            "10m",
            "15m",
            "30m",
        ),
        minimum_indicator_observations: int = 1,
        initial_capital: float = 100_000.0,
        quantity: int = 1,
        historical_transaction_cost_rate: float = 0.0001,
        minimum_historical_trades: int = 1,
        minimum_historical_net_pnl: float = 0.0,
        causality_minimum_observations: int = 1,
        causality_observation_step: int = 1,
        causality_minimum_history_candles: int = 50,
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
        selected_transaction_cost_rate: float = 0.0001,
        selected_slippage_rate: float = 0.0001,
        minimum_oos_trades: int = 1,
        minimum_oos_net_pnl: float = 0.0,
        minimum_oos_profit_factor: float = 1.0,
        direction_threshold_pct: float = 0.50,
        volatility_window: int = 60,
        volatility_min_periods: int = 20,
        strategy_config: StrategyConfig | None = None,
    ) -> None:
        self.required_timeframes = required_timeframes
        self.strategy_config = strategy_config

        self.data_availability_checker = DataAvailabilityChecker(
            minimum_candles=minimum_availability_candles,
            minimum_sessions=minimum_availability_sessions,
            required_timeframes=required_timeframes,
        )

        self.data_quality_checker = DataQualityChecker()

        self.indicator_compatibility_checker = (
            IndicatorCompatibilityChecker(
                required_timeframes=required_timeframes,
                minimum_ready_observations=(
                    minimum_indicator_observations
                ),
            )
        )

        self.historical_backtest_validator = (
            HistoricalBacktestValidator(
                initial_capital=initial_capital,
                quantity=quantity,
                transaction_cost_rate=(
                    historical_transaction_cost_rate
                ),
                minimum_trades_required=(
                    minimum_historical_trades
                ),
                minimum_net_pnl_required=(
                    minimum_historical_net_pnl
                ),
                strategy_config=strategy_config,
            )
        )

        self.causality_validator = CausalityValidator(
            minimum_observations=causality_minimum_observations,
            observation_step=causality_observation_step,
            minimum_history_candles=(
                causality_minimum_history_candles
            ),
        )

        self.cost_slippage_validator = CostSlippageValidator(
            transaction_cost_rates=transaction_cost_rates,
            slippage_rates=slippage_rates,
            initial_capital=initial_capital,
            quantity=quantity,
            minimum_trades_required=(
                minimum_historical_trades
            ),
            selected_transaction_cost_rate=(
                selected_transaction_cost_rate
            ),
            selected_slippage_rate=(
                selected_slippage_rate
            ),
        )

        self.regime_oos_validator = RegimeOOSValidator(
            development_start=development_start,
            development_end=development_end,
            oos_start=oos_start,
            oos_end=oos_end,
            initial_capital=initial_capital,
            quantity=quantity,
            transaction_cost_rate=(
                historical_transaction_cost_rate
            ),
            minimum_oos_trades=minimum_oos_trades,
            minimum_oos_net_pnl=minimum_oos_net_pnl,
            minimum_oos_profit_factor=minimum_oos_profit_factor,
            direction_threshold_pct=direction_threshold_pct,
            volatility_window=volatility_window,
            volatility_min_periods=volatility_min_periods,
            strategy_config=strategy_config,
        )

        self.approval_validator = ApprovalValidator()

    def validate(
        self,
        *,
        symbol: str,
        data: pd.DataFrame,
    ) -> StockValidationResult:
        """
        Run all seven validation gates for one stock.

        Parameters
        ----------
        symbol:
            Stock symbol used only as result metadata.
        data:
            Historical 1-minute OHLCV data.

        Returns
        -------
        StockValidationResult
            Complete seven-gate validation result.
        """

        normalized_symbol = self._normalize_symbol(symbol)

        if not isinstance(data, pd.DataFrame):
            raise TypeError(
                "data must be a pandas DataFrame."
            )

        data_availability = self.data_availability_checker.check(
            data
        )

        data_quality = self.data_quality_checker.check(data)

        indicator_compatibility = (
            self.indicator_compatibility_checker.check(data)
        )

        historical_backtest = (
            self.historical_backtest_validator.check(data)
        )

        causality = self.causality_validator.check(data)

        cost_slippage = self.cost_slippage_validator.check(data)

        regime_oos = self.regime_oos_validator.check(data)

        approval = self.approval_validator.evaluate(
            data_availability=data_availability,
            data_quality=data_quality,
            indicator_compatibility=indicator_compatibility,
            historical_backtest=historical_backtest,
            causality=causality,
            cost_slippage=cost_slippage,
            regime_oos=regime_oos,
        )

        return StockValidationResult(
            symbol=normalized_symbol,
            data_availability=data_availability,
            data_quality=data_quality,
            indicator_compatibility=indicator_compatibility,
            historical_backtest=historical_backtest,
            causality=causality,
            cost_slippage=cost_slippage,
            regime_oos=regime_oos,
            approval=approval,
        )

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Normalize and validate a stock symbol."""

        if not isinstance(symbol, str):
            raise TypeError("symbol must be a string.")

        normalized = symbol.strip().upper()

        if not normalized:
            raise ValueError("symbol must not be empty.")

        return normalized
