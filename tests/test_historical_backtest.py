import pandas as pd
import pytest

from src.validation.historical_backtest import (
    HistoricalBacktestValidator,
)


def make_market_data(
    start: str = "2026-08-31 09:15",
    periods: int = 3000,
    volume: float = 1000.0,
) -> pd.DataFrame:
    index = pd.date_range(
        start=start,
        periods=periods,
        freq="min",
    )

    close = [
        100.0 + (index_position * 0.01)
        for index_position in range(periods)
    ]

    return pd.DataFrame(
        {
            "open": close,
            "high": [
                price + 0.5
                for price in close
            ],
            "low": [
                price - 0.5
                for price in close
            ],
            "close": close,
            "volume": [volume] * periods,
        },
        index=index,
    )


def test_historical_backtest_runs_successfully():
    data = make_market_data()

    result = HistoricalBacktestValidator().check(
        data
    )

    assert result.total_candles == 3000
    assert result.total_trades >= 0

    assert result.winning_trades >= 0
    assert result.losing_trades >= 0

    assert (
        result.winning_trades
        + result.losing_trades
        <= result.total_trades
    )

    assert 0.0 <= result.win_rate <= 100.0
    assert result.max_drawdown >= 0.0
    assert result.max_losing_streak >= 0


def test_trade_count_is_consistent():
    data = make_market_data()

    result = HistoricalBacktestValidator().check(
        data
    )

    assert (
        result.total_trades
        == result.winning_trades
        + result.losing_trades
        + (
            result.total_trades
            - result.winning_trades
            - result.losing_trades
        )
    )


def test_profitable_property_matches_net_pnl():
    data = make_market_data()

    result = HistoricalBacktestValidator().check(
        data
    )

    assert result.profitable is (
        result.net_pnl
        > result.minimum_net_pnl_required
    )


def test_trade_evidence_property_matches_threshold():
    data = make_market_data()

    validator = HistoricalBacktestValidator(
        minimum_trades_required=5
    )

    result = validator.check(data)

    assert result.has_trade_evidence is (
        result.total_trades >= 5
    )


def test_custom_trade_threshold_can_fail():
    data = make_market_data()

    validator = HistoricalBacktestValidator(
        minimum_trades_required=10_000
    )

    result = validator.check(data)

    assert result.passed is False
    assert result.has_trade_evidence is False
    assert any(
        "did not generate enough trades"
        in issue
        for issue in result.issues
    )


def test_custom_pnl_threshold_can_fail():
    data = make_market_data()

    validator = HistoricalBacktestValidator(
        minimum_net_pnl_required=1_000_000.0
    )

    result = validator.check(data)

    assert result.passed is False
    assert result.profitable is False
    assert any(
        "net P&L did not exceed"
        in issue
        for issue in result.issues
    )


def test_zero_transaction_costs_are_supported():
    data = make_market_data()

    validator = HistoricalBacktestValidator(
        transaction_cost_rate=0.0
    )

    result = validator.check(data)

    assert result.total_candles == 3000


def test_transaction_costs_are_passed_to_backtest():
    data = make_market_data()

    no_cost = HistoricalBacktestValidator(
        transaction_cost_rate=0.0
    ).check(data)

    with_cost = HistoricalBacktestValidator(
        transaction_cost_rate=0.001
    ).check(data)

    assert (
        with_cost.net_pnl
        <= no_cost.net_pnl
    )


def test_zero_volume_dataset_is_supported():
    data = make_market_data(
        volume=0.0
    )

    result = HistoricalBacktestValidator().check(
        data
    )

    assert result.total_candles == 3000


def test_empty_dataframe_fails():
    data = pd.DataFrame(
        columns=[
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
        index=pd.DatetimeIndex([]),
    )

    result = HistoricalBacktestValidator().check(
        data
    )

    assert result.passed is False
    assert result.total_candles == 0
    assert result.total_trades == 0
    assert result.issues == (
        "Market data cannot be empty.",
    )


def test_non_dataframe_input_fails():
    result = HistoricalBacktestValidator().check(
        "invalid"
    )

    assert result.passed is False
    assert result.total_candles == 0
    assert result.issues == (
        "Market data must be a pandas DataFrame.",
    )


def test_invalid_index_fails():
    data = pd.DataFrame(
        {
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.0],
            "volume": [1000.0],
        }
    )

    result = HistoricalBacktestValidator().check(
        data
    )

    assert result.passed is False
    assert result.issues == (
        "Market data index must be a DatetimeIndex.",
    )


def test_missing_required_column_fails():
    data = make_market_data().drop(
        columns=["volume"]
    )

    result = HistoricalBacktestValidator().check(
        data
    )

    assert result.passed is False
    assert result.total_candles == 0
    assert len(result.issues) == 1
    assert "Missing required columns" in result.issues[0]


def test_backtest_failure_is_reported():
    data = make_market_data()

    data.index = pd.DatetimeIndex(
        [
            data.index[0],
            data.index[0],
        ]
        + list(data.index[2:])
    )

    result = HistoricalBacktestValidator().check(
        data
    )

    assert result.passed is False
    assert result.total_trades == 0
    assert any(
        "Historical backtest failed"
        in issue
        for issue in result.issues
    )


def test_custom_quantity_is_supported():
    data = make_market_data()

    result = HistoricalBacktestValidator(
        quantity=10
    ).check(data)

    assert result.total_candles == 3000


def test_configuration_rejects_invalid_capital():
    with pytest.raises(
        ValueError,
        match="initial_capital must be greater than zero",
    ):
        HistoricalBacktestValidator(
            initial_capital=0
        )


def test_configuration_rejects_invalid_quantity():
    with pytest.raises(
        ValueError,
        match="quantity must be greater than zero",
    ):
        HistoricalBacktestValidator(
            quantity=0
        )


def test_configuration_rejects_negative_transaction_cost():
    with pytest.raises(
        ValueError,
        match="transaction_cost_rate cannot be negative",
    ):
        HistoricalBacktestValidator(
            transaction_cost_rate=-0.01
        )


def test_configuration_rejects_invalid_trade_threshold():
    with pytest.raises(
        ValueError,
        match="minimum_trades_required must be greater than zero",
    ):
        HistoricalBacktestValidator(
            minimum_trades_required=0
        )


def test_configuration_rejects_boolean_trade_threshold():
    with pytest.raises(
        TypeError,
        match="minimum_trades_required must be an integer",
    ):
        HistoricalBacktestValidator(
            minimum_trades_required=True
        )


def test_configuration_rejects_invalid_capital_type():
    with pytest.raises(
        TypeError,
        match="initial_capital must be numeric",
    ):
        HistoricalBacktestValidator(
            initial_capital="100000"
        )


def test_configuration_rejects_invalid_quantity_type():
    with pytest.raises(
        TypeError,
        match="quantity must be an integer",
    ):
        HistoricalBacktestValidator(
            quantity=1.5
        )


def test_configuration_rejects_invalid_cost_type():
    with pytest.raises(
        TypeError,
        match="transaction_cost_rate must be numeric",
    ):
        HistoricalBacktestValidator(
            transaction_cost_rate="0.01"
        )


def test_configuration_rejects_invalid_strategy_config():
    with pytest.raises(
        TypeError,
        match="strategy_config must be a StrategyConfig",
    ):
        HistoricalBacktestValidator(
            strategy_config="invalid"
        )


def test_configuration_rejects_invalid_execution_model():
    with pytest.raises(
        ValueError,
        match="Unsupported execution_model",
    ):
        HistoricalBacktestValidator(
            execution_model="invalid_model"
        )


def test_historical_backtest_validator_supports_next_open_execution():
    data = make_market_data(periods=500)
    validator = HistoricalBacktestValidator(execution_model="next_open")
    result = validator.check(data)
    assert result.execution_model == "next_open"
    assert isinstance(result.trades, tuple)
