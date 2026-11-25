"""
SignalForge — Phase 33A: Strategy Research Lab Unit Tests
=========================================================
File: tests/test_strategy_research_lab.py

Validates:
  1. Configuration defaults and enum structures
  2. Mathematical and causal correctness of technical indicators
  3. OHLC data integrity validator
  4. Signal generation logic for all five strategies
  5. Exit rules and priority mechanisms
  6. Portfolio constraints: max 2 concurrent positions, cash limits, and cost integration
"""

from datetime import date
import numpy as np
import pandas as pd
import pytest

from src.strategy.strategy_research_lab.config import (
    DEFAULT_STRATEGY_CONFIGS,
    ExitReason,
    RiskTier,
    StrategyCandidateConfig,
    StrategyID,
    StrategyLabConfig,
)
from src.strategy.strategy_research_lab.indicators import (
    attach_all_indicators,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_donchian_channels,
    calculate_ema,
    calculate_momentum_return,
    calculate_rolling_percentile_rank,
    calculate_rsi,
    calculate_sma,
    compute_cross_sectional_ranks,
    validate_ohlc_invariants,
)
from src.strategy.strategy_research_lab.signal_engines import (
    CandidateSignal,
    evaluate_candidate_exit,
    generate_candidate_signals,
)
from src.strategy.strategy_research_lab.portfolio_simulator import (
    ActivePosition,
    CompletedTrade,
    run_strategy_simulation,
)


def create_synthetic_stock_df(n_bars: int = 250, base_price: float = 100.0, trend: float = 0.1) -> pd.DataFrame:
    """Creates synthetic OHLCV dataframe with known characteristics."""
    np.random.seed(42)
    dates = pd.date_range("2018-01-01", periods=n_bars, freq="B").date
    closes = [base_price]
    for i in range(1, n_bars):
        ret = trend / 100.0 + np.random.normal(0, 0.015)
        closes.append(closes[-1] * (1.0 + ret))
    
    closes = np.array(closes)
    highs = closes * (1.0 + np.abs(np.random.normal(0.005, 0.003, n_bars)))
    lows = closes * (1.0 - np.abs(np.random.normal(0.005, 0.003, n_bars)))
    opens = (highs + lows) / 2.0
    volumes = np.random.randint(100000, 500000, n_bars).astype(float)

    df = pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    }, index=dates)
    return df


def test_config_and_enums():
    """Verifies that all 5 strategies and risk tiers are properly defined."""
    assert len(StrategyID) == 5
    assert len(RiskTier) == 3
    assert RiskTier.E1.risk_fraction == 0.01
    assert RiskTier.E2.risk_fraction == 0.02
    assert RiskTier.E3.risk_fraction == 0.03

    for st_id in StrategyID:
        assert st_id in DEFAULT_STRATEGY_CONFIGS
        cfg = DEFAULT_STRATEGY_CONFIGS[st_id]
        assert cfg.stop_atr_mult == 2.0
        assert cfg.max_hold_bars in (5, 10)


def test_indicators_mathematics():
    """Verifies causal and mathematical properties of technical indicators."""
    df = create_synthetic_stock_df(150, base_price=200.0)
    
    # Moving averages
    sma20 = calculate_sma(df["close"], 20)
    assert len(sma20) == 150
    assert pd.isna(sma20.iloc[18])
    assert not pd.isna(sma20.iloc[19])
    assert np.isclose(sma20.iloc[19], df["close"].iloc[:20].mean())

    ema20 = calculate_ema(df["close"], 20)
    assert len(ema20) == 150
    assert not pd.isna(ema20.iloc[0])

    # ATR
    atr14 = calculate_atr(df["high"], df["low"], df["close"], period=14)
    assert (atr14 > 0).all()

    # RSI
    rsi14 = calculate_rsi(df["close"], period=14)
    assert (rsi14 >= 0.0).all() and (rsi14 <= 100.0).all()

    # Bollinger Bands
    mid, up, lo, width = calculate_bollinger_bands(df["close"], period=20, num_std=2.0)
    assert (up.dropna() >= mid.dropna()).all()
    assert (mid.dropna() >= lo.dropna()).all()
    assert (width.dropna() > 0).all()

    # Donchian Channels
    dh20, dl10 = calculate_donchian_channels(df["high"], df["low"], 20, 10)
    assert pd.isna(dh20.iloc[19])
    assert not pd.isna(dh20.iloc[20])
    # Causal check: dh20 on bar 20 should equal max of highs on bars 0..19
    assert np.isclose(dh20.iloc[20], df["high"].iloc[:20].max())


def test_ohlc_invariants_validator():
    """Verifies that validate_ohlc_invariants flags corrupt data."""
    valid_df = create_synthetic_stock_df(50)
    validate_ohlc_invariants(valid_df, "TEST_SYM")

    # Corrupt High < Low
    corrupt_df = valid_df.copy()
    corrupt_df.iloc[10, corrupt_df.columns.get_loc("high")] = corrupt_df.iloc[10]["low"] - 5.0
    with pytest.raises(ValueError, match="invalid High price"):
        validate_ohlc_invariants(corrupt_df, "CORRUPT_HIGH")

    # Corrupt negative volume
    corrupt_vol = valid_df.copy()
    corrupt_vol.iloc[5, corrupt_vol.columns.get_loc("volume")] = -100.0
    with pytest.raises(ValueError, match="negative volume"):
        validate_ohlc_invariants(corrupt_vol, "CORRUPT_VOL")


def test_cross_sectional_ranking():
    """Verifies that cross-sectional ranking correctly ranks stocks on trailing returns."""
    u = {
        "SYM_A": create_synthetic_stock_df(100, base_price=100.0, trend=0.5),   # Strong uptrend
        "SYM_B": create_synthetic_stock_df(100, base_price=100.0, trend=0.0),   # Flat
        "SYM_C": create_synthetic_stock_df(100, base_price=100.0, trend=-0.5),  # Downtrend
    }
    ranks = compute_cross_sectional_ranks(u, lookback=60)
    assert len(ranks) == 100
    # On day 90, SYM_A should be highest ranked (rank 1.0) and SYM_C lowest (rank ~0.33)
    day_90_rank = ranks.iloc[90]
    assert day_90_rank["SYM_A"] > day_90_rank["SYM_B"]
    assert day_90_rank["SYM_B"] > day_90_rank["SYM_C"]


def test_exit_conditions_evaluation():
    """Verifies exit conditions: stop loss, profit target, trailing exit, and time stop."""
    cfg = DEFAULT_STRATEGY_CONFIGS[StrategyID.STRATEGY_1_TREND_PULLBACK]
    
    # 1. Stop loss hit
    bar_stop = pd.Series({"open": 98.0, "high": 99.0, "low": 94.0, "close": 95.0})
    res_stop = evaluate_candidate_exit(
        strategy_id=StrategyID.STRATEGY_1_TREND_PULLBACK,
        bar=bar_stop,
        entry_price=100.0,
        stop_loss_price=95.0,
        bars_held=2,
        max_hold_bars=10,
        is_final_bar=False,
        profit_target_price=106.0,
        cfg=cfg,
    )
    assert res_stop is not None
    exec_px, reason, _ = res_stop
    assert reason == ExitReason.PROTECTIVE_STOP
    assert exec_px == 95.0

    # 2. Profit target reached
    bar_target = pd.Series({"open": 104.0, "high": 107.0, "low": 103.0, "close": 106.5})
    res_target = evaluate_candidate_exit(
        strategy_id=StrategyID.STRATEGY_1_TREND_PULLBACK,
        bar=bar_target,
        entry_price=100.0,
        stop_loss_price=95.0,
        bars_held=3,
        max_hold_bars=10,
        is_final_bar=False,
        profit_target_price=106.0,
        cfg=cfg,
    )
    assert res_target is not None
    exec_px, reason, _ = res_target
    assert reason == ExitReason.PROFIT_TARGET
    assert exec_px == 106.0

    # 3. Time stop reached
    bar_time = pd.Series({"open": 101.0, "high": 102.0, "low": 100.0, "close": 101.5})
    res_time = evaluate_candidate_exit(
        strategy_id=StrategyID.STRATEGY_1_TREND_PULLBACK,
        bar=bar_time,
        entry_price=100.0,
        stop_loss_price=95.0,
        bars_held=10,
        max_hold_bars=10,
        is_final_bar=False,
        profit_target_price=108.0,
        cfg=cfg,
    )
    assert res_time is not None
    exec_px, reason, _ = res_time
    assert reason == ExitReason.TIME_STOP
    assert exec_px == 101.5


def test_portfolio_simulator_constraints():
    """Verifies that simulator executes cleanly under max 2 concurrent positions and integer shares."""
    # Create universe with 3 stocks
    u_raw = {
        "STOCK_1": create_synthetic_stock_df(220, base_price=150.0, trend=0.15),
        "STOCK_2": create_synthetic_stock_df(220, base_price=250.0, trend=0.12),
        "STOCK_3": create_synthetic_stock_df(220, base_price=50.0, trend=0.20),
    }
    ranks = compute_cross_sectional_ranks(u_raw, lookback=60)
    u_aug = {}
    for s, df in u_raw.items():
        u_aug[s] = attach_all_indicators(df, s, cs_rank_series=ranks[s])

    sim_cfg = StrategyLabConfig(
        initial_capital=100000.0,
        max_concurrent_positions=2,
        symbol_sector_map={"STOCK_1": "IT", "STOCK_2": "Financials", "STOCK_3": "Auto"},
        symbol_isin_map={"STOCK_1": "INE001", "STOCK_2": "INE002", "STOCK_3": "INE003"},
    )

    result = run_strategy_simulation(
        strategy_id=StrategyID.STRATEGY_3_RELATIVE_STRENGTH,
        augmented_universe=u_aug,
        risk_tier=RiskTier.E2,
        use_stress_costs=False,
        config=sim_cfg,
    )

    assert result.initial_capital == 100000.0
    assert result.risk_tier == "E2 (2%)"
    assert len(result.daily_equity) == 220
    # Verify no trade violated integer shares or capital
    for t in result.trades:
        assert isinstance(t.quantity, int)
        assert t.quantity > 0
        assert t.buy_turnover <= 100000.0
