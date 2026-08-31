import pytest

from src.strategy.signal_rules import (
    Direction,
    trend_direction,
    momentum_support,
    volume_support,
    volatility_is_acceptable,
)


# ============================================================
# TREND TESTS
# ============================================================

def test_bullish_trend():
    result = trend_direction(
        close=105,
        ema20=103,
        ema50=100,
    )

    assert result == Direction.LONG


def test_bearish_trend():
    result = trend_direction(
        close=95,
        ema20=97,
        ema50=100,
    )

    assert result == Direction.SHORT


def test_price_between_emas_is_no_trade():
    result = trend_direction(
        close=102,
        ema20=105,
        ema50=100,
    )

    assert result == Direction.NO_TRADE


def test_ema_alignment_missing_is_no_trade():
    result = trend_direction(
        close=105,
        ema20=100,
        ema50=102,
    )

    assert result == Direction.NO_TRADE


def test_equal_values_are_no_trade():
    result = trend_direction(
        close=100,
        ema20=100,
        ema50=95,
    )

    assert result == Direction.NO_TRADE


# ============================================================
# MOMENTUM TESTS
# ============================================================

def test_rsi_supports_long():
    assert momentum_support(
        Direction.LONG,
        60,
    )


def test_rsi_supports_short():
    assert momentum_support(
        Direction.SHORT,
        40,
    )


def test_rsi_does_not_support_long_at_50():
    assert not momentum_support(
        Direction.LONG,
        50,
    )


def test_rsi_does_not_support_short_at_50():
    assert not momentum_support(
        Direction.SHORT,
        50,
    )


def test_no_trade_has_no_momentum_support():
    assert not momentum_support(
        Direction.NO_TRADE,
        60,
    )


# ============================================================
# VOLUME TESTS
# ============================================================

def test_strong_volume_is_supported():
    assert volume_support(
        rvol=1.5,
        minimum_rvol=1.5,
    )


def test_high_volume_is_supported():
    assert volume_support(
        rvol=2.0,
        minimum_rvol=1.5,
    )


def test_low_volume_is_not_supported():
    assert not volume_support(
        rvol=1.2,
        minimum_rvol=1.5,
    )


def test_volume_threshold_is_configurable():
    assert volume_support(
        rvol=1.2,
        minimum_rvol=1.2,
    )


# ============================================================
# VOLATILITY TESTS
# ============================================================

def test_acceptable_atr():
    assert volatility_is_acceptable(
        atr=2.0,
        minimum_atr=1.5,
    )


def test_atr_at_threshold_is_acceptable():
    assert volatility_is_acceptable(
        atr=1.5,
        minimum_atr=1.5,
    )


def test_low_atr_is_not_acceptable():
    assert not volatility_is_acceptable(
        atr=1.0,
        minimum_atr=1.5,
    )


def test_volatility_threshold_is_configurable():
    assert volatility_is_acceptable(
        atr=1.0,
        minimum_atr=1.0,
    )