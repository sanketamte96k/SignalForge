"""Exact numerical equivalence tests for causal indicators."""

import numpy as np
import pandas as pd

from src.indicators.indicators import (
    calculate_atr,
    calculate_ema,
    calculate_rsi,
    calculate_rvol,
)
from src.strategy.causal_indicators import (
    CausalIndicatorState,
)


def test_causal_indicators_match_batch_indicators():
    close = pd.Series(
        [
            100.0,
            101.0,
            99.0,
            102.0,
            104.0,
            103.0,
            105.0,
            107.0,
            106.0,
            108.0,
            110.0,
            109.0,
            111.0,
            113.0,
            112.0,
            114.0,
            116.0,
            115.0,
            117.0,
            119.0,
            118.0,
            120.0,
            122.0,
            121.0,
            123.0,
            125.0,
            124.0,
            126.0,
            128.0,
            127.0,
            129.0,
            131.0,
            130.0,
            132.0,
            134.0,
            133.0,
            135.0,
            137.0,
            136.0,
            138.0,
        ],
        dtype=float,
    )

    high = close + 1.5
    low = close - 1.5

    volume = pd.Series(
        [
            1000.0,
            1100.0,
            950.0,
            1200.0,
            1050.0,
            1300.0,
            1150.0,
            1400.0,
            1250.0,
            1500.0,
            1350.0,
            1450.0,
            1550.0,
            1650.0,
            1500.0,
            1750.0,
            1600.0,
            1800.0,
            1700.0,
            1900.0,
            1850.0,
            2000.0,
            1950.0,
            2100.0,
            2050.0,
            2200.0,
            2150.0,
            2300.0,
            2250.0,
            2400.0,
            2350.0,
            2500.0,
            2450.0,
            2600.0,
            2550.0,
            2700.0,
            2650.0,
            2800.0,
            2750.0,
            2900.0,
        ],
        dtype=float,
    )

    ema_fast_period = 5
    ema_slow_period = 10
    rsi_period = 5
    atr_period = 5
    rvol_period = 5

    batch_ema_fast = calculate_ema(
        close,
        ema_fast_period,
    )

    batch_ema_slow = calculate_ema(
        close,
        ema_slow_period,
    )

    batch_rsi = calculate_rsi(
        close,
        rsi_period,
    )

    batch_atr = calculate_atr(
        high,
        low,
        close,
        atr_period,
    )

    batch_rvol = calculate_rvol(
        volume,
        rvol_period,
    )

    state = CausalIndicatorState(
        ema_fast_period=ema_fast_period,
        ema_slow_period=ema_slow_period,
        rsi_period=rsi_period,
        atr_period=atr_period,
        rvol_period=rvol_period,
    )

    causal_ema_fast = []
    causal_ema_slow = []
    causal_rsi = []
    causal_atr = []
    causal_rvol = []

    for index in range(len(close)):
        snapshot = state.update(
            high=float(high.iloc[index]),
            low=float(low.iloc[index]),
            close=float(close.iloc[index]),
            volume=float(volume.iloc[index]),
        )

        causal_ema_fast.append(snapshot.ema_fast)
        causal_ema_slow.append(snapshot.ema_slow)
        causal_rsi.append(snapshot.rsi)
        causal_atr.append(snapshot.atr)
        causal_rvol.append(snapshot.rvol)

    def assert_series_match(
        expected: pd.Series,
        actual: list[float | None],
    ) -> None:
        expected_values = expected.to_numpy(
            dtype=float,
        )

        actual_values = np.array(
            [
                np.nan if value is None else value
                for value in actual
            ],
            dtype=float,
        )

        np.testing.assert_allclose(
            actual_values,
            expected_values,
            rtol=1e-12,
            atol=1e-12,
            equal_nan=True,
        )

    assert_series_match(
        batch_ema_fast,
        causal_ema_fast,
    )

    assert_series_match(
        batch_ema_slow,
        causal_ema_slow,
    )

    assert_series_match(
        batch_rsi,
        causal_rsi,
    )

    assert_series_match(
        batch_atr,
        causal_atr,
    )

    assert_series_match(
        batch_rvol,
        causal_rvol,
    )


def test_causal_state_does_not_change_without_update():
    state = CausalIndicatorState(
        ema_fast_period=5,
        ema_slow_period=10,
        rsi_period=5,
        atr_period=5,
        rvol_period=5,
    )

    first = state.update(
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1000.0,
    )

    before = state.snapshot()
    after = state.snapshot()

    assert before == after
    assert first == before


def test_causal_reset_restarts_indicator_state():
    state = CausalIndicatorState(
        ema_fast_period=5,
        ema_slow_period=10,
        rsi_period=5,
        atr_period=5,
        rvol_period=5,
    )

    first_run = []

    for value in range(100, 115):
        snapshot = state.update(
            high=float(value + 1),
            low=float(value - 1),
            close=float(value),
            volume=1000.0,
        )

        first_run.append(snapshot)

    state.reset()

    second_run = []

    for value in range(100, 115):
        snapshot = state.update(
            high=float(value + 1),
            low=float(value - 1),
            close=float(value),
            volume=1000.0,
        )

        second_run.append(snapshot)

    assert first_run == second_run