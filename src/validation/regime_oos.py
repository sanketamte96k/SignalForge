"""Regime and out-of-sample validation for SignalForge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from src.backtest.engine import run_backtest
from src.backtest.simulator import Trade
from src.strategy.backtest_strategy import (
    StrategyConfig,
    create_signal_function,
)


DIRECTION_REGIMES = (
    "TREND_UP",
    "TREND_DOWN",
    "SIDEWAYS",
)

VOLATILITY_REGIMES = (
    "HIGH_VOL",
    "LOW_VOL",
)


@dataclass(frozen=True)
class RegimeMetrics:
    """Performance metrics for one market regime."""

    regime: str
    trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    net_pnl: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_pct: float


@dataclass(frozen=True)
class OOSMetrics:
    """Performance metrics for one chronological evaluation period."""

    period: str
    start: pd.Timestamp
    end: pd.Timestamp
    candles: int
    trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    net_pnl: float
    profit_factor: float
    max_drawdown: float
    max_drawdown_pct: float


@dataclass(frozen=True)
class RegimeOOSResult:
    """Complete regime and out-of-sample validation result."""

    passed: bool
    total_candles: int
    development_candles: int
    oos_candles: int
    development_trades: int
    oos_trades: int
    development_net_pnl: float
    oos_net_pnl: float
    development_profit_factor: float
    oos_profit_factor: float
    oos_win_rate: float
    pnl_change: float
    profit_factor_change: float
    win_rate_change: float
    direction_regimes: tuple[RegimeMetrics, ...]
    volatility_regimes: tuple[RegimeMetrics, ...]
    oos_metrics: OOSMetrics | None
    minimum_oos_trades: int
    minimum_oos_net_pnl: float
    minimum_oos_profit_factor: float
    issues: tuple[str, ...]

    @property
    def has_evidence(self) -> bool:
        """Return whether both development and OOS have trades."""

        return (
            self.development_trades > 0
            and self.oos_trades > 0
        )

    @property
    def oos_profitable(self) -> bool:
        """Return whether OOS net P&L is positive."""

        return (
            self.oos_metrics is not None
            and self.oos_metrics.net_pnl > 0
        )

    @property
    def oos_profitable_by_threshold(self) -> bool:
        """Return whether OOS P&L exceeds configured threshold."""

        return (
            self.oos_metrics is not None
            and self.oos_metrics.net_pnl
            > self.minimum_oos_net_pnl
        )

    @property
    def oos_profit_factor_passed(self) -> bool:
        """Return whether OOS profit factor exceeds threshold."""

        return (
            self.oos_metrics is not None
            and self.oos_metrics.profit_factor
            > self.minimum_oos_profit_factor
        )

    @property
    def oos_trade_requirement_passed(self) -> bool:
        """Return whether OOS has enough trade evidence."""

        return (
            self.oos_metrics is not None
            and self.oos_metrics.trades
            >= self.minimum_oos_trades
        )

    @property
    def regime_count(self) -> int:
        """Return the total number of regime buckets."""

        return (
            len(self.direction_regimes)
            + len(self.volatility_regimes)
        )


class RegimeOOSValidator:
    """
    Validate a frozen strategy across market regimes and OOS data.

    Regime classification is causal: each trading session is
    classified using only information from the previously completed
    session.

    This validator is diagnostic only. It does not modify the
    strategy and does not make the final stock approval decision.
    """

    def __init__(
        self,
        *,
        development_start: str | pd.Timestamp,
        development_end: str | pd.Timestamp,
        oos_start: str | pd.Timestamp,
        oos_end: str | pd.Timestamp,
        initial_capital: float = 100_000.0,
        quantity: int = 1,
        transaction_cost_rate: float = 0.0001,
        minimum_oos_trades: int = 1,
        minimum_oos_net_pnl: float = 0.0,
        minimum_oos_profit_factor: float = 1.0,
        direction_threshold_pct: float = 0.50,
        volatility_window: int = 60,
        volatility_min_periods: int = 20,
        strategy_config: StrategyConfig | None = None,
    ) -> None:
        self.development_start = pd.Timestamp(
            development_start
        )
        self.development_end = pd.Timestamp(
            development_end
        )
        self.oos_start = pd.Timestamp(oos_start)
        self.oos_end = pd.Timestamp(oos_end)

        self.initial_capital = initial_capital
        self.quantity = quantity
        self.transaction_cost_rate = (
            transaction_cost_rate
        )
        self.minimum_oos_trades = minimum_oos_trades
        self.minimum_oos_net_pnl = minimum_oos_net_pnl
        self.minimum_oos_profit_factor = (
            minimum_oos_profit_factor
        )
        self.direction_threshold_pct = (
            direction_threshold_pct
        )
        self.volatility_window = volatility_window
        self.volatility_min_periods = (
            volatility_min_periods
        )
        self.strategy_config = strategy_config

        self._validate_configuration()

    def _validate_configuration(self) -> None:
        """Validate validator configuration."""

        if self.development_start > self.development_end:
            raise ValueError(
                "development_start must be before "
                "development_end."
            )

        if self.oos_start > self.oos_end:
            raise ValueError(
                "oos_start must be before oos_end."
            )

        if self.development_end >= self.oos_start:
            raise ValueError(
                "development and OOS periods must not overlap."
            )

        if not isinstance(
            self.initial_capital,
            (int, float),
        ) or isinstance(self.initial_capital, bool):
            raise TypeError(
                "initial_capital must be numeric."
            )

        if self.initial_capital <= 0:
            raise ValueError(
                "initial_capital must be greater than zero."
            )

        if (
            not isinstance(self.quantity, int)
            or isinstance(self.quantity, bool)
        ):
            raise TypeError(
                "quantity must be an integer."
            )

        if self.quantity <= 0:
            raise ValueError(
                "quantity must be greater than zero."
            )

        if not isinstance(
            self.transaction_cost_rate,
            (int, float),
        ) or isinstance(
            self.transaction_cost_rate,
            bool,
        ):
            raise TypeError(
                "transaction_cost_rate must be numeric."
            )

        if self.transaction_cost_rate < 0:
            raise ValueError(
                "transaction_cost_rate cannot be negative."
            )

        if (
            not isinstance(
                self.minimum_oos_trades,
                int,
            )
            or isinstance(
                self.minimum_oos_trades,
                bool,
            )
        ):
            raise TypeError(
                "minimum_oos_trades must be an integer."
            )

        if self.minimum_oos_trades < 1:
            raise ValueError(
                "minimum_oos_trades must be at least one."
            )

        if not isinstance(
            self.minimum_oos_net_pnl,
            (int, float),
        ) or isinstance(
            self.minimum_oos_net_pnl,
            bool,
        ):
            raise TypeError(
                "minimum_oos_net_pnl must be numeric."
            )

        if not isinstance(
            self.minimum_oos_profit_factor,
            (int, float),
        ) or isinstance(
            self.minimum_oos_profit_factor,
            bool,
        ):
            raise TypeError(
                "minimum_oos_profit_factor must be numeric."
            )

        if self.minimum_oos_profit_factor < 0:
            raise ValueError(
                "minimum_oos_profit_factor cannot be negative."
            )

        if not isinstance(
            self.direction_threshold_pct,
            (int, float),
        ) or isinstance(
            self.direction_threshold_pct,
            bool,
        ):
            raise TypeError(
                "direction_threshold_pct must be numeric."
            )

        if self.direction_threshold_pct < 0:
            raise ValueError(
                "direction_threshold_pct cannot be negative."
            )

        if (
            not isinstance(
                self.volatility_window,
                int,
            )
            or isinstance(
                self.volatility_window,
                bool,
            )
        ):
            raise TypeError(
                "volatility_window must be an integer."
            )

        if self.volatility_window < 1:
            raise ValueError(
                "volatility_window must be greater than zero."
            )

        if (
            not isinstance(
                self.volatility_min_periods,
                int,
            )
            or isinstance(
                self.volatility_min_periods,
                bool,
            )
        ):
            raise TypeError(
                "volatility_min_periods must be an integer."
            )

        if (
            self.volatility_min_periods < 1
            or self.volatility_min_periods
            > self.volatility_window
        ):
            raise ValueError(
                "volatility_min_periods must be between "
                "1 and volatility_window."
            )

    @staticmethod
    def _validate_data(
        data: pd.DataFrame,
    ) -> None:
        """Validate historical OHLCV input."""

        if not isinstance(data, pd.DataFrame):
            raise TypeError(
                "data must be a pandas DataFrame."
            )

        if data.empty:
            raise ValueError(
                "data cannot be empty."
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
            raise ValueError(
                "data is missing required columns: "
                f"{missing}"
            )

        if not isinstance(
            data.index,
            pd.DatetimeIndex,
        ):
            raise TypeError(
                "data index must be a "
                "pandas DatetimeIndex."
            )

        if data.index.has_duplicates:
            raise ValueError(
                "data index cannot contain duplicates."
            )

        if not data.index.is_monotonic_increasing:
            raise ValueError(
                "data index must be sorted."
            )

        for column in (
            "open",
            "high",
            "low",
            "close",
            "volume",
        ):
            if not pd.api.types.is_numeric_dtype(
                data[column]
            ):
                raise TypeError(
                    f"{column} must be numeric."
                )

            if data[column].isna().any():
                raise ValueError(
                    f"{column} cannot contain "
                    "missing values."
                )

    def _calculate_session_features(
        self,
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Calculate causal session-level regime features.

        Each session's regime is based exclusively on the
        previously completed session. Therefore no candle from the
        current trading session contributes to its regime label.
        """

        rows = []

        grouped = data.groupby(
            data.index.date
        )

        for session_date, session in grouped:
            if session.empty:
                continue

            first_open = float(
                session["open"].iloc[0]
            )

            last_close = float(
                session["close"].iloc[-1]
            )

            if first_open <= 0:
                continue

            minute_returns = (
                session["close"]
                .pct_change()
                .dropna()
            )

            if minute_returns.empty:
                realized_vol = 0.0
            else:
                realized_vol = (
                    minute_returns.std()
                    * (len(minute_returns) ** 0.5)
                    * 100.0
                )

            session_return = (
                last_close / first_open - 1.0
            ) * 100.0

            session_range = (
                (
                    float(session["high"].max())
                    - float(session["low"].min())
                )
                / first_open
                * 100.0
            )

            rows.append(
                {
                    "date": pd.Timestamp(
                        session_date
                    ),
                    "session_return_pct": (
                        session_return
                    ),
                    "session_range_pct": (
                        session_range
                    ),
                    "realized_vol_pct": (
                        realized_vol
                    ),
                }
            )

        if not rows:
            raise ValueError(
                "Unable to calculate session features."
            )

        features = (
            pd.DataFrame(rows)
            .set_index("date")
            .sort_index()
        )

        features["vol_median"] = (
            features["realized_vol_pct"]
            .rolling(
                self.volatility_window,
                min_periods=self.volatility_min_periods,
            )
            .median()
        )

        # Calculate the regime from the PREVIOUS completed
        # session. Shift all features forward by one session.
        features["prior_session_return_pct"] = (
            features["session_return_pct"].shift(1)
        )

        features["prior_session_realized_vol_pct"] = (
            features["realized_vol_pct"].shift(1)
        )

        features["prior_vol_median"] = (
            features["vol_median"].shift(1)
        )

        features["direction"] = "SIDEWAYS"

        features.loc[
            features["prior_session_return_pct"]
            >= self.direction_threshold_pct,
            "direction",
        ] = "TREND_UP"

        features.loc[
            features["prior_session_return_pct"]
            <= -self.direction_threshold_pct,
            "direction",
        ] = "TREND_DOWN"

        features["volatility"] = "LOW_VOL"

        high_vol_mask = (
            features["prior_session_realized_vol_pct"]
            > features["prior_vol_median"]
        )

        features.loc[
            high_vol_mask.fillna(False),
            "volatility",
        ] = "HIGH_VOL"

        return features

    @staticmethod
    def _calculate_trade_metrics(
        trades: Iterable[Trade],
        *,
        regime: str,
        initial_capital: float,
    ) -> RegimeMetrics:
        """Calculate performance metrics for grouped trades."""

        trade_list = list(trades)

        if not trade_list:
            return RegimeMetrics(
                regime=regime,
                trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                net_pnl=0.0,
                profit_factor=0.0,
                max_drawdown=0.0,
                max_drawdown_pct=0.0,
            )

        pnl = [
            float(trade.net_pnl)
            for trade in trade_list
        ]

        wins = [
            value
            for value in pnl
            if value > 0
        ]

        losses = [
            value
            for value in pnl
            if value < 0
        ]

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))

        if gross_loss > 0:
            profit_factor = (
                gross_profit / gross_loss
            )
        elif gross_profit > 0:
            profit_factor = float("inf")
        else:
            profit_factor = 0.0

        equity = initial_capital
        peak_equity = initial_capital
        max_drawdown = 0.0
        max_drawdown_pct = 0.0

        for value in pnl:
            equity += value

            if equity > peak_equity:
                peak_equity = equity

            drawdown = (
                peak_equity - equity
            )

            drawdown_pct = (
                drawdown / peak_equity * 100.0
                if peak_equity > 0
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

        return RegimeMetrics(
            regime=regime,
            trades=len(trade_list),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=(
                len(wins)
                / len(trade_list)
                * 100.0
            ),
            net_pnl=sum(pnl),
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
        )

    def _run_period(
        self,
        data: pd.DataFrame,
    ):
        """Run the frozen strategy on one period."""

        config = self.strategy_config

        if config is None:
            config = StrategyConfig(
                use_rvol=False
            )

        signal_function = create_signal_function(
            data,
            config,
        )

        return run_backtest(
            data=data,
            signal_function=signal_function,
            initial_capital=self.initial_capital,
            quantity=self.quantity,
            transaction_cost_rate=(
                self.transaction_cost_rate
            ),
        )

    @staticmethod
    def _period_metrics(
        result,
        *,
        period: str,
        data: pd.DataFrame,
        initial_capital: float,
    ) -> OOSMetrics:
        """Convert a backtest result into period metrics."""

        metrics = RegimeOOSValidator._calculate_trade_metrics(
            result.trades,
            regime=period,
            initial_capital=initial_capital,
        )

        return OOSMetrics(
            period=period,
            start=data.index.min(),
            end=data.index.max(),
            candles=len(data),
            trades=metrics.trades,
            winning_trades=metrics.winning_trades,
            losing_trades=metrics.losing_trades,
            win_rate=metrics.win_rate,
            net_pnl=metrics.net_pnl,
            profit_factor=metrics.profit_factor,
            max_drawdown=metrics.max_drawdown,
            max_drawdown_pct=metrics.max_drawdown_pct,
        )

    def check(
        self,
        data: pd.DataFrame,
    ) -> RegimeOOSResult:
        """Run regime and OOS validation."""

        try:
            self._validate_data(data)
        except (
            TypeError,
            ValueError,
        ) as exc:
            return RegimeOOSResult(
                passed=False,
                total_candles=(
                    len(data)
                    if isinstance(
                        data,
                        pd.DataFrame,
                    )
                    else 0
                ),
                development_candles=0,
                oos_candles=0,
                development_trades=0,
                oos_trades=0,
                development_net_pnl=0.0,
                oos_net_pnl=0.0,
                development_profit_factor=0.0,
                oos_profit_factor=0.0,
                oos_win_rate=0.0,
                pnl_change=0.0,
                profit_factor_change=0.0,
                win_rate_change=0.0,
                direction_regimes=(),
                volatility_regimes=(),
                oos_metrics=None,
                minimum_oos_trades=self.minimum_oos_trades,
                minimum_oos_net_pnl=self.minimum_oos_net_pnl,
                minimum_oos_profit_factor=(
                    self.minimum_oos_profit_factor
                ),
                issues=(str(exc),),
            )

        development_data = data[
            (data.index >= self.development_start)
            & (data.index <= self.development_end)
        ].copy()

        oos_data = data[
            (data.index >= self.oos_start)
            & (data.index <= self.oos_end)
        ].copy()

        issues: list[str] = []

        if development_data.empty:
            issues.append(
                "Development period contains no data."
            )

        if oos_data.empty:
            issues.append(
                "OOS period contains no data."
            )

        if issues:
            return RegimeOOSResult(
                passed=False,
                total_candles=len(data),
                development_candles=len(
                    development_data
                ),
                oos_candles=len(oos_data),
                development_trades=0,
                oos_trades=0,
                development_net_pnl=0.0,
                oos_net_pnl=0.0,
                development_profit_factor=0.0,
                oos_profit_factor=0.0,
                oos_win_rate=0.0,
                pnl_change=0.0,
                profit_factor_change=0.0,
                win_rate_change=0.0,
                direction_regimes=(),
                volatility_regimes=(),
                oos_metrics=None,
                minimum_oos_trades=self.minimum_oos_trades,
                minimum_oos_net_pnl=self.minimum_oos_net_pnl,
                minimum_oos_profit_factor=(
                    self.minimum_oos_profit_factor
                ),
                issues=tuple(issues),
            )

        development_result = self._run_period(
            development_data
        )

        oos_result = self._run_period(
            oos_data
        )

        development_metrics = self._period_metrics(
            development_result,
            period="DEVELOPMENT",
            data=development_data,
            initial_capital=self.initial_capital,
        )

        oos_metrics = self._period_metrics(
            oos_result,
            period="OOS",
            data=oos_data,
            initial_capital=self.initial_capital,
        )

        session_features = (
            self._calculate_session_features(data)
        )

        all_trades = (
            list(development_result.trades)
            + list(oos_result.trades)
        )

        direction_metrics: list[RegimeMetrics] = []

        for regime in DIRECTION_REGIMES:
            selected = []

            for trade in all_trades:
                entry_date = pd.Timestamp(
                    trade.entry_time
                ).normalize()

                if (
                    entry_date not in
                    session_features.index
                ):
                    continue

                if (
                    session_features.loc[
                        entry_date,
                        "direction",
                    ]
                    == regime
                ):
                    selected.append(trade)

            direction_metrics.append(
                self._calculate_trade_metrics(
                    selected,
                    regime=regime,
                    initial_capital=self.initial_capital,
                )
            )

        volatility_metrics: list[RegimeMetrics] = []

        for regime in VOLATILITY_REGIMES:
            selected = []

            for trade in all_trades:
                entry_date = pd.Timestamp(
                    trade.entry_time
                ).normalize()

                if (
                    entry_date not in
                    session_features.index
                ):
                    continue

                if (
                    session_features.loc[
                        entry_date,
                        "volatility",
                    ]
                    == regime
                ):
                    selected.append(trade)

            volatility_metrics.append(
                self._calculate_trade_metrics(
                    selected,
                    regime=regime,
                    initial_capital=self.initial_capital,
                )
            )

        pnl_change = (
            oos_metrics.net_pnl
            - development_metrics.net_pnl
        )

        profit_factor_change = (
            oos_metrics.profit_factor
            - development_metrics.profit_factor
        )

        win_rate_change = (
            oos_metrics.win_rate
            - development_metrics.win_rate
        )

        if (
            oos_metrics.trades
            < self.minimum_oos_trades
        ):
            issues.append(
                "OOS trade count is below the "
                "minimum required evidence."
            )

        if (
            oos_metrics.net_pnl
            <= self.minimum_oos_net_pnl
        ):
            issues.append(
                "OOS net P&L does not exceed the "
                "minimum required threshold."
            )

        if (
            oos_metrics.profit_factor
            <= self.minimum_oos_profit_factor
        ):
            issues.append(
                "OOS profit factor does not exceed "
                "the minimum required threshold."
            )

        passed = (
            not issues
            and development_metrics.trades > 0
            and oos_metrics.trades
            >= self.minimum_oos_trades
            and oos_metrics.net_pnl
            > self.minimum_oos_net_pnl
            and oos_metrics.profit_factor
            > self.minimum_oos_profit_factor
        )

        return RegimeOOSResult(
            passed=passed,
            total_candles=len(data),
            development_candles=len(
                development_data
            ),
            oos_candles=len(oos_data),
            development_trades=(
                development_metrics.trades
            ),
            oos_trades=oos_metrics.trades,
            development_net_pnl=(
                development_metrics.net_pnl
            ),
            oos_net_pnl=oos_metrics.net_pnl,
            development_profit_factor=(
                development_metrics.profit_factor
            ),
            oos_profit_factor=(
                oos_metrics.profit_factor
            ),
            oos_win_rate=oos_metrics.win_rate,
            pnl_change=pnl_change,
            profit_factor_change=(
                profit_factor_change
            ),
            win_rate_change=win_rate_change,
            direction_regimes=tuple(
                direction_metrics
            ),
            volatility_regimes=tuple(
                volatility_metrics
            ),
            oos_metrics=oos_metrics,
            minimum_oos_trades=self.minimum_oos_trades,
            minimum_oos_net_pnl=self.minimum_oos_net_pnl,
            minimum_oos_profit_factor=(
                self.minimum_oos_profit_factor
            ),
            issues=tuple(issues),
        )
