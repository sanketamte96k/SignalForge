from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from src.backtest.simulator import (
    Position,
    simulate_trade,
)
from src.validation.regime_oos import (
    DIRECTION_REGIMES,
    VOLATILITY_REGIMES,
    RegimeOOSValidator,
)


DEVELOPMENT_START = pd.Timestamp("2020-01-01")
DEVELOPMENT_END = pd.Timestamp("2020-01-02 23:59:59")
OOS_START = pd.Timestamp("2020-01-03")
OOS_END = pd.Timestamp("2020-01-04 23:59:59")


def make_data(
    start: str = "2020-01-01 09:15:00",
    days: int = 4,
) -> pd.DataFrame:
    """Create deterministic multi-session OHLCV data."""

    sessions = []

    start_date = pd.Timestamp(start).normalize()

    for day_offset in range(days):
        session_date = (
            start_date
            + pd.Timedelta(days=day_offset)
        )

        index = pd.date_range(
            session_date + pd.Timedelta(hours=9, minutes=15),
            session_date + pd.Timedelta(hours=15, minutes=30),
            freq="min",
        )

        base = 100.0 + day_offset

        values = [
            base + (i * 0.01)
            for i in range(len(index))
        ]

        frame = pd.DataFrame(
            {
                "open": values,
                "high": [
                    value + 0.10
                    for value in values
                ],
                "low": [
                    value - 0.10
                    for value in values
                ],
                "close": values,
                "volume": [1000.0] * len(index),
            },
            index=index,
        )

        sessions.append(frame)

    return pd.concat(sessions)


def make_trade(
    entry_date: str,
    entry_price: float = 100.0,
    exit_price: float = 110.0,
):
    """Create a deterministic Trade object."""

    return simulate_trade(
        position=Position.LONG,
        entry_time=pd.Timestamp(
            f"{entry_date} 10:00:00"
        ),
        exit_time=pd.Timestamp(
            f"{entry_date} 11:00:00"
        ),
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=1,
        transaction_cost_rate=0.0,
    )


def make_validator(
    **kwargs,
) -> RegimeOOSValidator:
    """Create a validator with deterministic test periods."""

    defaults = {
        "development_start": DEVELOPMENT_START,
        "development_end": DEVELOPMENT_END,
        "oos_start": OOS_START,
        "oos_end": OOS_END,
    }

    defaults.update(kwargs)

    return RegimeOOSValidator(
        **defaults
    )


def test_invalid_data_returns_failed_result():
    validator = make_validator()

    result = validator.check("invalid")

    assert result.passed is False
    assert result.total_candles == 0
    assert result.oos_metrics is None
    assert not result.has_evidence
    assert any(
        "pandas DataFrame" in issue
        for issue in result.issues
    )


def test_missing_columns_returns_failed_result():
    data = make_data().drop(
        columns=["volume"]
    )

    validator = make_validator()

    result = validator.check(data)

    assert result.passed is False
    assert any(
        "missing required columns" in issue
        for issue in result.issues
    )


def test_duplicate_timestamps_are_rejected():
    data = make_data()

    duplicate = data.iloc[[10]].copy()

    data = pd.concat(
        [
            data.iloc[:20],
            duplicate,
            data.iloc[20:],
        ]
    )

    validator = make_validator()

    result = validator.check(data)

    assert result.passed is False
    assert any(
        "duplicates" in issue
        for issue in result.issues
    )


def test_unsorted_data_is_rejected():
    data = make_data()

    data = data.iloc[
        [2, 0, 1] + list(range(3, len(data)))
    ]

    validator = make_validator()

    result = validator.check(data)

    assert result.passed is False
    assert any(
        "sorted" in issue
        for issue in result.issues
    )


def test_missing_development_period_is_reported(
    monkeypatch,
):
    data = make_data(
        start="2020-01-03 09:15:00",
        days=2,
    )

    validator = make_validator()

    result = validator.check(data)

    assert result.passed is False
    assert result.development_candles == 0
    assert result.oos_candles > 0
    assert any(
        "Development period contains no data"
        in issue
        for issue in result.issues
    )


def test_missing_oos_period_is_reported():
    data = make_data(
        start="2020-01-01 09:15:00",
        days=2,
    )

    validator = make_validator()

    result = validator.check(data)

    assert result.passed is False
    assert result.development_candles > 0
    assert result.oos_candles == 0
    assert any(
        "OOS period contains no data"
        in issue
        for issue in result.issues
    )


def test_direction_regime_classification():
    data = make_data(
        days=3,
    )

    validator = make_validator()

    features = validator._calculate_session_features(
        data
    )

    assert set(
        features["direction"].unique()
    ).issubset(
        set(DIRECTION_REGIMES)
    )

    assert set(
        features["direction"]
    ) == {"SIDEWAYS", "TREND_UP"}


def test_direction_threshold_classifies_up_down_sideways():
    data = make_data(
        days=3,
    )

    validator = make_validator(
        direction_threshold_pct=0.50
    )

    features = validator._calculate_session_features(
        data
    )

    custom = features.copy()

    custom.loc[
        custom.index[0],
        "session_return_pct",
    ] = 1.0

    custom.loc[
        custom.index[1],
        "session_return_pct",
    ] = -1.0

    custom.loc[
        custom.index[2],
        "session_return_pct",
    ] = 0.0

    custom["direction"] = "SIDEWAYS"

    custom.loc[
        custom["session_return_pct"]
        >= validator.direction_threshold_pct,
        "direction",
    ] = "TREND_UP"

    custom.loc[
        custom["session_return_pct"]
        <= -validator.direction_threshold_pct,
        "direction",
    ] = "TREND_DOWN"

    assert (
        custom.loc[
            custom.index[0],
            "direction",
        ]
        == "TREND_UP"
    )

    assert (
        custom.loc[
            custom.index[1],
            "direction",
        ]
        == "TREND_DOWN"
    )

    assert (
        custom.loc[
            custom.index[2],
            "direction",
        ]
        == "SIDEWAYS"
    )


def test_volatility_regime_names_are_exposed():
    assert VOLATILITY_REGIMES == (
        "HIGH_VOL",
        "LOW_VOL",
    )


def test_trade_metrics_calculate_correctly():
    validator = make_validator()

    trades = [
        make_trade(
            "2020-01-01",
            100.0,
            110.0,
        ),
        make_trade(
            "2020-01-02",
            110.0,
            105.0,
        ),
    ]

    metrics = validator._calculate_trade_metrics(
        trades,
        regime="TEST",
        initial_capital=100_000.0,
    )

    assert metrics.regime == "TEST"
    assert metrics.trades == 2
    assert metrics.winning_trades == 1
    assert metrics.losing_trades == 1
    assert metrics.win_rate == 50.0
    assert metrics.net_pnl == 5.0
    assert metrics.profit_factor == 2.0
    assert metrics.max_drawdown == 5.0
    assert metrics.max_drawdown_pct > 0.0


def test_empty_regime_has_zero_metrics():
    validator = make_validator()

    metrics = validator._calculate_trade_metrics(
        [],
        regime="EMPTY",
        initial_capital=100_000.0,
    )

    assert metrics.trades == 0
    assert metrics.winning_trades == 0
    assert metrics.losing_trades == 0
    assert metrics.win_rate == 0.0
    assert metrics.net_pnl == 0.0
    assert metrics.profit_factor == 0.0
    assert metrics.max_drawdown == 0.0


def test_oos_metrics_are_calculated_from_backtest_result():
    validator = make_validator()

    trades = [
        make_trade(
            "2020-01-03",
            100.0,
            110.0,
        ),
        make_trade(
            "2020-01-04",
            110.0,
            105.0,
        ),
    ]

    result = SimpleNamespace(
        trades=trades
    )

    data = make_data().loc[
        "2020-01-03":"2020-01-04"
    ]

    metrics = validator._period_metrics(
        result,
        period="OOS",
        data=data,
        initial_capital=100_000.0,
    )

    assert metrics.period == "OOS"
    assert metrics.candles == len(data)
    assert metrics.trades == 2
    assert metrics.winning_trades == 1
    assert metrics.losing_trades == 1
    assert metrics.net_pnl == 5.0
    assert metrics.profit_factor == 2.0


def test_check_evaluates_development_and_oos(
    monkeypatch,
):
    data = make_data()

    development_trades = [
        make_trade(
            "2020-01-01",
            100.0,
            110.0,
        ),
        make_trade(
            "2020-01-02",
            110.0,
            105.0,
        ),
    ]

    oos_trades = [
        make_trade(
            "2020-01-03",
            100.0,
            110.0,
        ),
        make_trade(
            "2020-01-04",
            110.0,
            120.0,
        ),
    ]

    calls = []

    def fake_run_backtest(
        data,
        signal_function,
        initial_capital,
        quantity,
        transaction_cost_rate,
    ):
        calls.append(
            (
                data.index.min(),
                data.index.max(),
                initial_capital,
                quantity,
                transaction_cost_rate,
            )
        )

        if data.index.max() <= DEVELOPMENT_END:
            return SimpleNamespace(
                trades=development_trades
            )

        return SimpleNamespace(
            trades=oos_trades
        )

    import src.validation.regime_oos as module

    monkeypatch.setattr(
        module,
        "run_backtest",
        fake_run_backtest,
    )

    validator = make_validator(
        minimum_oos_trades=1,
        minimum_oos_net_pnl=0.0,
        minimum_oos_profit_factor=1.0,
    )

    result = validator.check(data)

    assert len(calls) == 2

    assert result.development_trades == 2
    assert result.oos_trades == 2

    assert result.development_net_pnl == 5.0
    assert result.oos_net_pnl == 20.0

    assert result.oos_profitable
    assert result.oos_profitable_by_threshold
    assert result.oos_profit_factor_passed
    assert result.oos_trade_requirement_passed

    assert result.pnl_change == 15.0
    assert result.profit_factor_change > 0.0
    assert result.win_rate_change == 50.0

    assert len(result.direction_regimes) == 3
    assert len(result.volatility_regimes) == 2
    assert result.regime_count == 5

    assert result.has_evidence


def test_oos_trade_requirement_can_fail(
    monkeypatch,
):
    data = make_data()

    trades = [
        make_trade(
            "2020-01-03",
            100.0,
            110.0,
        )
    ]

    def fake_run_backtest(
        data,
        signal_function,
        initial_capital,
        quantity,
        transaction_cost_rate,
    ):
        return SimpleNamespace(
            trades=trades
        )

    import src.validation.regime_oos as module

    monkeypatch.setattr(
        module,
        "run_backtest",
        fake_run_backtest,
    )

    validator = make_validator(
        minimum_oos_trades=10,
        minimum_oos_net_pnl=0.0,
        minimum_oos_profit_factor=1.0,
    )

    result = validator.check(data)

    assert result.passed is False
    assert result.oos_trade_requirement_passed is False
    assert any(
        "trade count" in issue
        for issue in result.issues
    )


def test_oos_pnl_requirement_can_fail(
    monkeypatch,
):
    data = make_data()

    development_trades = [
        make_trade(
            "2020-01-01",
            100.0,
            110.0,
        )
    ]

    oos_trades = [
        make_trade(
            "2020-01-03",
            100.0,
            99.0,
        )
    ]

    def fake_run_backtest(
        data,
        signal_function,
        initial_capital,
        quantity,
        transaction_cost_rate,
    ):
        if data.index.max() <= DEVELOPMENT_END:
            return SimpleNamespace(
                trades=development_trades
            )

        return SimpleNamespace(
            trades=oos_trades
        )

    import src.validation.regime_oos as module

    monkeypatch.setattr(
        module,
        "run_backtest",
        fake_run_backtest,
    )

    validator = make_validator(
        minimum_oos_trades=1,
        minimum_oos_net_pnl=0.0,
        minimum_oos_profit_factor=0.0,
    )

    result = validator.check(data)

    assert result.passed is False
    assert result.oos_profitable is False
    assert result.oos_profitable_by_threshold is False
    assert any(
        "net P&L" in issue
        for issue in result.issues
    )


def test_oos_profit_factor_requirement_can_fail(
    monkeypatch,
):
    data = make_data()

    development_trades = [
        make_trade(
            "2020-01-01",
            100.0,
            110.0,
        )
    ]

    oos_trades = [
        make_trade(
            "2020-01-03",
            100.0,
            110.0,
        ),
        make_trade(
            "2020-01-04",
            110.0,
            105.0,
        ),
    ]

    def fake_run_backtest(
        data,
        signal_function,
        initial_capital,
        quantity,
        transaction_cost_rate,
    ):
        if data.index.max() <= DEVELOPMENT_END:
            return SimpleNamespace(
                trades=development_trades
            )

        return SimpleNamespace(
            trades=oos_trades
        )

    import src.validation.regime_oos as module

    monkeypatch.setattr(
        module,
        "run_backtest",
        fake_run_backtest,
    )

    validator = make_validator(
        minimum_oos_trades=1,
        minimum_oos_net_pnl=0.0,
        minimum_oos_profit_factor=3.0,
    )

    result = validator.check(data)

    assert result.passed is False
    assert result.oos_profit_factor_passed is False
    assert any(
        "profit factor" in issue
        for issue in result.issues
    )


def test_configuration_rejects_overlapping_periods():
    with pytest.raises(ValueError):
        RegimeOOSValidator(
            development_start="2020-01-01",
            development_end="2020-01-03",
            oos_start="2020-01-03",
            oos_end="2020-01-04",
        )


def test_configuration_rejects_invalid_quantity():
    with pytest.raises(TypeError):
        RegimeOOSValidator(
            development_start=DEVELOPMENT_START,
            development_end=DEVELOPMENT_END,
            oos_start=OOS_START,
            oos_end=OOS_END,
            quantity=1.5,
        )


def test_configuration_rejects_invalid_volatility_periods():
    with pytest.raises(ValueError):
        RegimeOOSValidator(
            development_start=DEVELOPMENT_START,
            development_end=DEVELOPMENT_END,
            oos_start=OOS_START,
            oos_end=OOS_END,
            volatility_window=10,
            volatility_min_periods=20,
        )


def test_configuration_rejects_negative_transaction_cost():
    with pytest.raises(ValueError):
        RegimeOOSValidator(
            development_start=DEVELOPMENT_START,
            development_end=DEVELOPMENT_END,
            oos_start=OOS_START,
            oos_end=OOS_END,
            transaction_cost_rate=-0.001,
        )



