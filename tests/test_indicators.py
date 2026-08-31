import pandas as pd
import pytest

from src.indicators.indicators import (
    calculate_ema,
    calculate_rsi,
)


def test_ema_returns_series():
    close = pd.Series(
        [100, 101, 102, 103, 104],
        dtype=float,
    )

    result = calculate_ema(close, 3)

    assert isinstance(result, pd.Series)
    assert len(result) == len(close)


def test_ema_preserves_index():
    index = pd.date_range(
        "2026-08-31 09:15",
        periods=5,
        freq="min",
    )

    close = pd.Series(
        [100, 101, 102, 103, 104],
        index=index,
        dtype=float,
    )

    result = calculate_ema(close, 3)

    assert result.index.equals(close.index)


def test_ema_initial_values_are_nan():
    close = pd.Series(
        [100, 101, 102, 103, 104],
        dtype=float,
    )

    result = calculate_ema(close, 3)

    assert result.iloc[0] != result.iloc[0]
    assert result.iloc[1] != result.iloc[1]
    assert pd.notna(result.iloc[2])


def test_ema_reacts_to_price():
    close = pd.Series(
        [100, 100, 100, 110],
        dtype=float,
    )

    result = calculate_ema(close, 3)

    assert result.iloc[-1] > 100


def test_invalid_period():
    close = pd.Series(
        [100, 101, 102],
        dtype=float,
    )

    with pytest.raises(ValueError):
        calculate_ema(close, 0)


def test_negative_period():
    close = pd.Series(
        [100, 101, 102],
        dtype=float,
    )

    with pytest.raises(ValueError):
        calculate_ema(close, -5)


def test_non_integer_period():
    close = pd.Series(
        [100, 101, 102],
        dtype=float,
    )

    with pytest.raises(TypeError):
        calculate_ema(close, 5.5)


def test_non_series_input():
    with pytest.raises(TypeError):
        calculate_ema([100, 101, 102], 3)


def test_empty_series():
    close = pd.Series(dtype=float)

    with pytest.raises(ValueError):
        calculate_ema(close, 3)


def test_missing_values():
    close = pd.Series(
        [100, 101, None, 103],
        dtype=float,
    )

    with pytest.raises(ValueError):
        calculate_ema(close, 3)

def test_rsi_returns_series():
    close = pd.Series(
        range(100, 121),
        dtype=float,
    )

    result = calculate_rsi(close, 14)

    assert isinstance(result, pd.Series)
    assert len(result) == len(close)


def test_rsi_preserves_index():
    index = pd.date_range(
        "2026-08-31 09:15",
        periods=21,
        freq="min",
    )

    close = pd.Series(
        range(100, 121),
        index=index,
        dtype=float,
    )

    result = calculate_rsi(close, 14)

    assert result.index.equals(close.index)


def test_rsi_is_bounded():
    close = pd.Series(
        [
            100,
            101,
            99,
            102,
            100,
            103,
            101,
            104,
            102,
            105,
            103,
            106,
            104,
            107,
            105,
            108,
            106,
            109,
            107,
            110,
        ],
        dtype=float,
    )

    result = calculate_rsi(close, 14)

    valid_values = result.dropna()

    assert (valid_values >= 0).all()
    assert (valid_values <= 100).all()


def test_rsi_rising_market_is_high():
    close = pd.Series(
        range(100, 121),
        dtype=float,
    )

    result = calculate_rsi(close, 14)

    assert result.iloc[-1] == 100.0


def test_rsi_falling_market_is_low():
    close = pd.Series(
        range(120, 99, -1),
        dtype=float,
    )

    result = calculate_rsi(close, 14)

    assert result.iloc[-1] == 0.0


def test_rsi_constant_market_is_neutral():
    close = pd.Series(
        [100.0] * 21,
    )

    result = calculate_rsi(close, 14)

    assert result.iloc[-1] == 50.0


def test_rsi_initial_values_are_nan():
    close = pd.Series(
        range(100, 121),
        dtype=float,
    )

    result = calculate_rsi(close, 14)

    assert result.iloc[:14].isna().all()
    assert pd.notna(result.iloc[14])


def test_rsi_invalid_period():
    close = pd.Series(
        range(100, 121),
        dtype=float,
    )

    with pytest.raises(ValueError):
        calculate_rsi(close, 0)


def test_rsi_non_integer_period():
    close = pd.Series(
        range(100, 121),
        dtype=float,
    )

    with pytest.raises(TypeError):
        calculate_rsi(close, 14.5)


def test_rsi_missing_values():
    close = pd.Series(
        [100, 101, None, 103, 104],
        dtype=float,
    )

    with pytest.raises(ValueError):
        calculate_rsi(close, 14)