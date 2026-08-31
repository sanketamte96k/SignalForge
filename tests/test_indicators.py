import pandas as pd
import pytest

from src.indicators.indicators import (
    calculate_ema,
    calculate_rsi,
    calculate_atr,
    calculate_rvol,
)


# ============================================================
# EMA TESTS
# ============================================================

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


# ============================================================
# RSI TESTS
# ============================================================

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


# ============================================================
# ATR TESTS
# ============================================================

def test_atr_returns_series():
    high = pd.Series(
        [102, 103, 104, 105, 106],
        dtype=float,
    )

    low = pd.Series(
        [99, 100, 101, 102, 103],
        dtype=float,
    )

    close = pd.Series(
        [101, 102, 103, 104, 105],
        dtype=float,
    )

    result = calculate_atr(
        high,
        low,
        close,
        period=3,
    )

    assert isinstance(result, pd.Series)
    assert len(result) == len(close)


def test_atr_preserves_index():
    index = pd.date_range(
        "2026-08-31 09:15",
        periods=5,
        freq="min",
    )

    high = pd.Series(
        [102, 103, 104, 105, 106],
        index=index,
        dtype=float,
    )

    low = pd.Series(
        [99, 100, 101, 102, 103],
        index=index,
        dtype=float,
    )

    close = pd.Series(
        [101, 102, 103, 104, 105],
        index=index,
        dtype=float,
    )

    result = calculate_atr(
        high,
        low,
        close,
        period=3,
    )

    assert result.index.equals(index)


def test_atr_initial_values_are_nan():
    high = pd.Series(
        [102, 103, 104, 105, 106],
        dtype=float,
    )

    low = pd.Series(
        [99, 100, 101, 102, 103],
        dtype=float,
    )

    close = pd.Series(
        [101, 102, 103, 104, 105],
        dtype=float,
    )

    result = calculate_atr(
        high,
        low,
        close,
        period=3,
    )

    # With period=3, the first valid ATR appears
    # at index 2 after three true-range observations.
    assert result.iloc[:2].isna().all()
    assert pd.notna(result.iloc[2])


def test_atr_is_positive():
    high = pd.Series(
        [102, 103, 104, 105, 106, 107],
        dtype=float,
    )

    low = pd.Series(
        [99, 100, 101, 102, 103, 104],
        dtype=float,
    )

    close = pd.Series(
        [101, 102, 103, 104, 105, 106],
        dtype=float,
    )

    result = calculate_atr(
        high,
        low,
        close,
        period=3,
    )

    assert (result.dropna() > 0).all()


def test_atr_accounts_for_previous_close_gap():
    high = pd.Series(
        [101, 102, 112],
        dtype=float,
    )

    low = pd.Series(
        [99, 100, 110],
        dtype=float,
    )

    close = pd.Series(
        [100, 101, 111],
        dtype=float,
    )

    result = calculate_atr(
        high,
        low,
        close,
        period=2,
    )

    # The third candle has a larger true range because
    # of the gap from the previous close.
    assert result.iloc[-1] > result.iloc[-2]


def test_atr_invalid_period():
    high = pd.Series(
        [102, 103, 104],
        dtype=float,
    )

    low = pd.Series(
        [99, 100, 101],
        dtype=float,
    )

    close = pd.Series(
        [101, 102, 103],
        dtype=float,
    )

    with pytest.raises(ValueError):
        calculate_atr(
            high,
            low,
            close,
            period=0,
        )


def test_atr_non_integer_period():
    high = pd.Series(
        [102, 103, 104],
        dtype=float,
    )

    low = pd.Series(
        [99, 100, 101],
        dtype=float,
    )

    close = pd.Series(
        [101, 102, 103],
        dtype=float,
    )

    with pytest.raises(TypeError):
        calculate_atr(
            high,
            low,
            close,
            period=14.5,
        )


def test_atr_mismatched_indexes():
    high = pd.Series(
        [102, 103, 104],
        index=[0, 1, 2],
        dtype=float,
    )

    low = pd.Series(
        [99, 100, 101],
        index=[1, 2, 3],
        dtype=float,
    )

    close = pd.Series(
        [101, 102, 103],
        index=[0, 1, 2],
        dtype=float,
    )

    with pytest.raises(ValueError):
        calculate_atr(
            high,
            low,
            close,
            period=2,
        )


def test_atr_missing_values():
    high = pd.Series(
        [102, None, 104],
        dtype=float,
    )

    low = pd.Series(
        [99, 100, 101],
        dtype=float,
    )

    close = pd.Series(
        [101, 102, 103],
        dtype=float,
    )

    with pytest.raises(ValueError):
        calculate_atr(
            high,
            low,
            close,
            period=2,
        )
# ============================================================
# RVOL TESTS
# ============================================================

def test_rvol_returns_series():
    volume = pd.Series(
        [1000, 1100, 1200, 1300, 1400],
        dtype=float,
    )

    result = calculate_rvol(
        volume,
        period=3,
    )

    assert isinstance(result, pd.Series)
    assert len(result) == len(volume)


def test_rvol_preserves_index():
    index = pd.date_range(
        "2026-08-31 09:15",
        periods=5,
        freq="min",
    )

    volume = pd.Series(
        [1000, 1100, 1200, 1300, 1400],
        index=index,
        dtype=float,
    )

    result = calculate_rvol(
        volume,
        period=3,
    )

    assert result.index.equals(index)


def test_rvol_initial_values_are_nan():
    volume = pd.Series(
        [1000, 1100, 1200, 1300, 1400],
        dtype=float,
    )

    result = calculate_rvol(
        volume,
        period=3,
    )

    assert result.iloc[:2].isna().all()
    assert pd.notna(result.iloc[2])


def test_rvol_average_volume_is_one():
    volume = pd.Series(
        [1000, 1000, 1000, 1000, 1000],
        dtype=float,
    )

    result = calculate_rvol(
        volume,
        period=3,
    )

    assert (result.dropna() == 1.0).all()


def test_rvol_above_average_volume():
    volume = pd.Series(
        [1000, 1000, 1000, 2000],
        dtype=float,
    )

    result = calculate_rvol(
        volume,
        period=3,
    )

    assert result.iloc[-1] > 1.0


def test_rvol_below_average_volume():
    volume = pd.Series(
        [1000, 1000, 1000, 500],
        dtype=float,
    )

    result = calculate_rvol(
        volume,
        period=3,
    )

    assert result.iloc[-1] < 1.0


def test_rvol_zero_volume():
    volume = pd.Series(
        [0, 0, 0, 0],
        dtype=float,
    )

    result = calculate_rvol(
        volume,
        period=3,
    )

    assert result.iloc[-1] != result.iloc[-1]


def test_rvol_invalid_period():
    volume = pd.Series(
        [1000, 1100, 1200],
        dtype=float,
    )

    with pytest.raises(ValueError):
        calculate_rvol(
            volume,
            period=0,
        )


def test_rvol_non_integer_period():
    volume = pd.Series(
        [1000, 1100, 1200],
        dtype=float,
    )

    with pytest.raises(TypeError):
        calculate_rvol(
            volume,
            period=20.5,
        )


def test_rvol_non_series_input():
    with pytest.raises(TypeError):
        calculate_rvol(
            [1000, 1100, 1200],
            period=3,
        )


def test_rvol_empty_series():
    volume = pd.Series(
        dtype=float,
    )

    with pytest.raises(ValueError):
        calculate_rvol(
            volume,
            period=3,
        )


def test_rvol_missing_values():
    volume = pd.Series(
        [1000, None, 1200, 1300],
        dtype=float,
    )

    with pytest.raises(ValueError):
        calculate_rvol(
            volume,
            period=3,
        )


def test_rvol_negative_volume():
    volume = pd.Series(
        [1000, 1100, -1200, 1300],
        dtype=float,
    )

    with pytest.raises(ValueError):
        calculate_rvol(
            volume,
            period=3,
        )