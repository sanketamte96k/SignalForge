"""Tests establishing causal indicator requirements."""

import pandas as pd

from src.indicators.indicators import (
    calculate_atr,
    calculate_ema,
    calculate_rsi,
    calculate_rvol,
)


def test_existing_indicator_warmup_contract():
    close = pd.Series(
        range(100, 151),
        dtype=float,
    )

    ema = calculate_ema(close, 20)
    rsi = calculate_rsi(close, 14)

    high = close + 2
    low = close - 2

    atr = calculate_atr(
        high,
        low,
        close,
        14,
    )

    volume = pd.Series(
        [1000.0] * len(close),
    )

    rvol = calculate_rvol(
        volume,
        20,
    )

    assert ema.iloc[:19].isna().all()
    assert pd.notna(ema.iloc[19])

    assert rsi.iloc[:14].isna().all()
    assert pd.notna(rsi.iloc[14])

    assert atr.iloc[:13].isna().all()
    assert pd.notna(atr.iloc[13])

    assert rvol.iloc[:19].isna().all()
    assert pd.notna(rvol.iloc[19])


def test_existing_indicators_are_deterministic():
    close = pd.Series(
        [
            100,
            101,
            99,
            102,
            104,
            103,
            105,
            107,
            106,
            108,
            110,
            109,
            111,
            113,
            112,
            114,
            116,
            115,
            117,
            119,
        ],
        dtype=float,
    )

    high = close + 1
    low = close - 1
    volume = pd.Series(
        range(100, 120),
        dtype=float,
    )

    first = {
        "ema": calculate_ema(close, 5),
        "rsi": calculate_rsi(close, 5),
        "atr": calculate_atr(
            high,
            low,
            close,
            5,
        ),
        "rvol": calculate_rvol(
            volume,
            5,
        ),
    }

    second = {
        "ema": calculate_ema(close, 5),
        "rsi": calculate_rsi(close, 5),
        "atr": calculate_atr(
            high,
            low,
            close,
            5,
        ),
        "rvol": calculate_rvol(
            volume,
            5,
        ),
    }

    for name in first:
        pd.testing.assert_series_equal(
            first[name],
            second[name],
        )