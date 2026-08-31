import pytest

from src.signals.signal_engine import (
    Signal,
    SignalResult,
    TimeframeState,
    generate_signal,
)


def bullish_state():
    return TimeframeState(
        close=105,
        ema20=103,
        ema50=100,
        rsi=60,
        rvol=2.0,
        atr=2.0,
    )


def bearish_state():
    return TimeframeState(
        close=95,
        ema20=97,
        ema50=100,
        rsi=40,
        rvol=2.0,
        atr=2.0,
    )


# ============================================================
# BASIC SIGNAL TESTS
# ============================================================

def test_all_bullish_timeframes_generate_buy():
    result = generate_signal(
        bullish_state(),
        bullish_state(),
        bullish_state(),
        bullish_state(),
    )

    assert isinstance(result, SignalResult)
    assert result.signal == Signal.BUY


def test_all_bearish_timeframes_generate_sell():
    result = generate_signal(
        bearish_state(),
        bearish_state(),
        bearish_state(),
        bearish_state(),
    )

    assert result.signal == Signal.SELL


def test_mixed_timeframes_generate_no_trade():
    result = generate_signal(
        bullish_state(),
        bullish_state(),
        bearish_state(),
        bullish_state(),
    )

    assert result.signal == Signal.NO_TRADE
    assert result.timeframe_alignment == 0


def test_neutral_timeframe_generates_no_trade():
    neutral = TimeframeState(
        close=102,
        ema20=105,
        ema50=100,
        rsi=60,
        rvol=2.0,
        atr=2.0,
    )

    result = generate_signal(
        bullish_state(),
        bullish_state(),
        neutral,
        bullish_state(),
    )

    assert result.signal == Signal.NO_TRADE


# ============================================================
# CONFIRMATION TESTS
# ============================================================

def test_strong_bullish_setup_has_full_confirmations():
    result = generate_signal(
        bullish_state(),
        bullish_state(),
        bullish_state(),
        bullish_state(),
    )

    assert result.score == 16
    assert result.confidence == 100.0
    assert result.timeframe_alignment == 4


def test_low_rsi_reduces_bullish_score():
    weak = TimeframeState(
        close=105,
        ema20=103,
        ema50=100,
        rsi=40,
        rvol=2.0,
        atr=2.0,
    )

    result = generate_signal(
        weak,
        bullish_state(),
        bullish_state(),
        bullish_state(),
    )

    assert result.signal == Signal.BUY
    assert result.score < 16


def test_low_rvol_reduces_score():
    weak = TimeframeState(
        close=105,
        ema20=103,
        ema50=100,
        rsi=60,
        rvol=1.0,
        atr=2.0,
    )

    result = generate_signal(
        weak,
        bullish_state(),
        bullish_state(),
        bullish_state(),
    )

    assert result.signal == Signal.BUY
    assert result.score < 16


def test_low_atr_reduces_score():
    weak = TimeframeState(
        close=105,
        ema20=103,
        ema50=100,
        rsi=60,
        rvol=2.0,
        atr=0.1,
    )

    result = generate_signal(
        weak,
        bullish_state(),
        bullish_state(),
        bullish_state(),
        minimum_atr=1.0,
    )

    assert result.signal == Signal.BUY
    assert result.score < 16


# ============================================================
# VALIDATION TESTS
# ============================================================

def test_invalid_timeframe_state_type():
    with pytest.raises(TypeError):
        generate_signal(
            bullish_state(),
            bullish_state(),
            bullish_state(),
            None,
        )


def test_invalid_rsi():
    invalid = TimeframeState(
        close=105,
        ema20=103,
        ema50=100,
        rsi=120,
        rvol=2.0,
        atr=2.0,
    )

    with pytest.raises(ValueError):
        generate_signal(
            invalid,
            bullish_state(),
            bullish_state(),
            bullish_state(),
        )


def test_negative_rvol():
    invalid = TimeframeState(
        close=105,
        ema20=103,
        ema50=100,
        rsi=60,
        rvol=-1.0,
        atr=2.0,
    )

    with pytest.raises(ValueError):
        generate_signal(
            invalid,
            bullish_state(),
            bullish_state(),
            bullish_state(),
        )


def test_negative_atr():
    invalid = TimeframeState(
        close=105,
        ema20=103,
        ema50=100,
        rsi=60,
        rvol=2.0,
        atr=-1.0,
    )

    with pytest.raises(ValueError):
        generate_signal(
            invalid,
            bullish_state(),
            bullish_state(),
            bullish_state(),
        )


def test_invalid_minimum_rvol():
    with pytest.raises(ValueError):
        generate_signal(
            bullish_state(),
            bullish_state(),
            bullish_state(),
            bullish_state(),
            minimum_rvol=-1.0,
        )


def test_invalid_minimum_atr():
    with pytest.raises(ValueError):
        generate_signal(
            bullish_state(),
            bullish_state(),
            bullish_state(),
            bullish_state(),
            minimum_atr=-1.0,
        )


# ============================================================
# RESULT TESTS
# ============================================================

def test_buy_result_contains_reason():
    result = generate_signal(
        bullish_state(),
        bullish_state(),
        bullish_state(),
        bullish_state(),
    )

    assert result.reason
    assert "confirmation" in result.reason.lower()


def test_sell_result_contains_reason():
    result = generate_signal(
        bearish_state(),
        bearish_state(),
        bearish_state(),
        bearish_state(),
    )

    assert result.reason
    assert result.signal == Signal.SELL


def test_confidence_is_bounded():
    result = generate_signal(
        bullish_state(),
        bullish_state(),
        bullish_state(),
        bullish_state(),
    )

    assert 0 <= result.confidence <= 100


def test_result_is_deterministic():
    first = generate_signal(
        bullish_state(),
        bullish_state(),
        bullish_state(),
        bullish_state(),
    )

    second = generate_signal(
        bullish_state(),
        bullish_state(),
        bullish_state(),
        bullish_state(),
    )

    assert first == second
    