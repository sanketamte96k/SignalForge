import pandas as pd
import pytest

from src.signals.signal_engine import (
    Signal,
)
from src.strategy.backtest_strategy import (
    StrategyConfig,
    calculate_timeframe_indicators,
    create_signal_function,
    evaluate_timestamp,
    generate_signals,
)


def make_market_data(
    rows: int = 1000,
) -> pd.DataFrame:

    index = pd.date_range(
        "2026-08-24 09:15:00",
        periods=rows,
        freq="min",
    )

    close = pd.Series(
        range(100, 100 + rows),
        index=index,
        dtype=float,
    )

    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1000.0,
        },
        index=index,
    )


def test_default_strategy_config():
    config = StrategyConfig()

    assert config.ema_fast_period == 20
    assert config.ema_slow_period == 50
    assert config.rsi_period == 14
    assert config.atr_period == 14
    assert config.rvol_period == 20
    assert config.minimum_rvol == 1.5


def test_invalid_config_type():
    with pytest.raises(TypeError):
        calculate_timeframe_indicators(
            make_market_data(),
            config="invalid",
        )


def test_fast_ema_must_be_less_than_slow_ema():
    config = StrategyConfig(
        ema_fast_period=50,
        ema_slow_period=20,
    )

    with pytest.raises(ValueError):
        calculate_timeframe_indicators(
            make_market_data(),
            config=config,
        )


def test_invalid_market_data_type():
    with pytest.raises(TypeError):
        calculate_timeframe_indicators(
            [],
        )


def test_missing_market_column():
    data = make_market_data().drop(
        columns=["volume"]
    )

    with pytest.raises(ValueError):
        calculate_timeframe_indicators(
            data
        )


def test_timeframe_indicators_contains_all_timeframes():
    result = calculate_timeframe_indicators(
        make_market_data(
            2000
        )
    )

    assert set(result) == {
        "5m",
        "10m",
        "15m",
        "30m",
    }


def test_timeframe_indicators_have_required_columns():
    result = calculate_timeframe_indicators(
        make_market_data(
            2000
        )
    )

    required = {
        "open",
        "high",
        "low",
        "close",
        "volume",
        "ema20",
        "ema50",
        "rsi",
        "rvol",
        "atr",
    }

    for timeframe in result.values():
        assert required.issubset(
            timeframe.columns
        )


def test_generate_signals_returns_dataframe():
    result = generate_signals(
        make_market_data(
            2000
        )
    )

    assert isinstance(
        result,
        pd.DataFrame,
    )


def test_generate_signals_preserves_index():
    data = make_market_data(
        2000
    )

    result = generate_signals(
        data
    )

    assert result.index.equals(
        data.index
    )


def test_generate_signals_preserves_ohlcv():
    data = make_market_data(
        2000
    )

    result = generate_signals(
        data
    )

    for column in (
        "open",
        "high",
        "low",
        "close",
        "volume",
    ):
        assert result[column].equals(
            data[column]
        )


def test_generate_signals_contains_signal_columns():
    result = generate_signals(
        make_market_data(
            2000
        )
    )

    required = {
        "signal",
        "score",
        "confidence",
        "timeframe_alignment",
        "reason",
    }

    assert required.issubset(
        result.columns
    )


def test_signals_are_valid_signal_values():
    result = generate_signals(
        make_market_data(
            2000
        )
    )

    assert set(
        result["signal"]
    ).issubset(
        {
            Signal.BUY,
            Signal.SELL,
            Signal.NO_TRADE,
        }
    )


def test_confidence_is_bounded():
    result = generate_signals(
        make_market_data(
            2000
        )
    )

    assert (
        result["confidence"]
        .between(0, 100)
        .all()
    )


def test_score_is_non_negative():
    result = generate_signals(
        make_market_data(
            2000
        )
    )

    assert (
        result["score"] >= 0
    ).all()


def test_lookahead_is_not_used():
    data = make_market_data(
        2000
    )

    timestamp = pd.Timestamp(
        "2026-08-25 09:15:00"
    )

    data_without_future = data.loc[
        :timestamp
    ].copy()

    future_data = data.loc[
        timestamp + pd.Timedelta(minutes=1):
    ].copy()

    # Make the future dramatically different so
    # accidental lookahead becomes obvious.
    future_data.loc[:, "open"] = 100000.0
    future_data.loc[:, "high"] = 100001.0
    future_data.loc[:, "low"] = 99999.0
    future_data.loc[:, "close"] = 100000.0
    future_data.loc[:, "volume"] = 999999.0

    data_with_future = pd.concat(
        [
            data_without_future,
            future_data,
        ]
    )

    function_without_future = (
        create_signal_function(
            data_without_future
        )
    )

    function_with_future = (
        create_signal_function(
            data_with_future
        )
    )

    current_row = data_without_future.loc[
        timestamp
    ]

    previous_timestamp = (
        timestamp - pd.Timedelta(minutes=1)
    )

    previous_row = data_without_future.loc[
        previous_timestamp
    ]

    signal_without_future = (
        function_without_future(
            current_row,
            previous_row,
        )
    )

    signal_with_future = (
        function_with_future(
            current_row,
            previous_row,
        )
    )

    assert (
        signal_without_future
        == signal_with_future
    )


def test_empty_data_is_rejected():
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

    with pytest.raises(ValueError):
        generate_signals(data)