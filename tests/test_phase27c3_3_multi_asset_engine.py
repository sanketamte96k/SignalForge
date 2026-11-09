"""
SignalForge — Phase 27C.3.3: Multi-Asset Synchronized Intraday Execution Engine Tests.

Verifies:
1. Synchronized chronological timeline processing across multiple symbols.
2. Deterministic event execution order (Events -> Prices -> Exits -> Signals -> Sizing -> Entries -> Snapshot).
3. Released margin availability: position exit on bar t frees margin immediately to fund new entry on bar t.
4. Independent position coexistence across multiple stocks (RELIANCE, ICICIBANK, TCS).
5. No double-spending: available margin constraints strictly enforced across concurrent positions.
6. Deterministic ranking: high-quality opportunities prioritized over lower-quality candidates.
7. Aggregate portfolio risk cap: entries rejected when total portfolio risk exceeds max_portfolio_risk_pct.
8. Single-stock allocation cap: per-stock notional exposure capped at max_stock_allocation_pct.
9. Missing candle handling: symbol missing at timestamp t cannot generate new trade.
10. Stale price protection: active position with missing candle uses last mark, does NOT trigger stop/target.
11. Session boundary square-off: all open positions squared off at session_end_time with exit_reason='EOD'.
12. Conservative same-candle collision: STOP evaluated before TARGET when both touched.
13. Adverse gap execution: fills at bar_open when market gaps through stop.
14. Portfolio protection floor breach: halts trading, closes open positions, and blocks new entries.
15. Canonical Phase 27B transaction costs integrated ex-ante in sizing and ex-post in PortfolioManager.
16. Comprehensive MultiAssetBacktestResult output (equity curve, performance metrics, per-symbol breakdown).
"""

import math
import pytest
import pandas as pd
import numpy as np

from src.backtest.capital_allocator import CapitalAllocationConfig, TradeOpportunity
from src.backtest.indian_market_costs import (
    DISCOUNT_BROKER_REALISTIC_CONFIG,
    STATUTORY_ONLY_CONFIG,
    IntradayCostConfig,
)
from src.backtest.multi_asset_engine import (
    MultiAssetEngineConfig,
    MultiAssetBacktestResult,
    run_multi_asset_backtest,
)
from src.backtest.portfolio import PortfolioManager
from src.backtest.simulator import Position


def _create_sample_stock_data(
    symbol: str,
    base_price: float,
    dates: pd.DatetimeIndex,
    price_offsets: list[float] | None = None,
    atr_val: float = 2.0,
) -> pd.DataFrame:
    """Helper to generate synthetic OHLCV intraday data for a symbol."""
    n = len(dates)
    if price_offsets is None:
        price_offsets = [0.0] * n

    opens = []
    highs = []
    lows = []
    closes = []

    for off in price_offsets:
        p = base_price + off
        opens.append(p)
        highs.append(p + 1.0)
        lows.append(p - 1.0)
        closes.append(p + 0.2)

    return pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": [1000.0] * n,
            "ATR": [atr_val] * n,
        },
        index=dates,
    )


# ============================================================================
# 1. Synchronized Timeline & Chronological Order
# ============================================================================

def test_01_synchronized_timeline_ascending_order():
    """Verify engine processes multiple symbols in strict ascending chronological order."""
    dates_rel = pd.date_range("2024-01-02 09:15:00", periods=5, freq="min")
    dates_tcs = pd.date_range("2024-01-02 09:16:00", periods=5, freq="min")  # Starts 1 min later

    df_rel = _create_sample_stock_data("RELIANCE", 2500.0, dates_rel)
    df_tcs = _create_sample_stock_data("TCS", 3500.0, dates_tcs)

    cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        execution_model="same_close",
        opening_cooldown_minutes=0,
    )

    data = {"RELIANCE": df_rel, "TCS": df_tcs}
    res = run_multi_asset_backtest(data_by_symbol=data, config=cfg)

    # Union of timestamps should be 6 timestamps (09:15 to 09:20)
    assert len(res.equity_curve) == 6
    assert res.equity_curve.index.is_monotonic_increasing
    assert res.equity_curve.index[0] == pd.Timestamp("2024-01-02 09:15:00")
    assert res.equity_curve.index[-1] == pd.Timestamp("2024-01-02 09:20:00")


# ============================================================================
# 2. Independent Position Coexistence Across Multiple Stocks
# ============================================================================

def test_02_independent_position_coexistence():
    """Verify simultaneous positions in RELIANCE and TCS coexist without crosstalk."""
    dates = pd.date_range("2024-01-02 09:15:00", periods=5, freq="min")
    df_rel = _create_sample_stock_data("RELIANCE", 2500.0, dates, atr_val=25.0)
    df_tcs = _create_sample_stock_data("TCS", 3500.0, dates, atr_val=35.0)

    # Signal both symbols at bar 0
    signals = {
        "RELIANCE": [Position.LONG, None, None, None, None],
        "TCS": [Position.LONG, None, None, None, None],
    }

    cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        risk_per_trade_pct=0.01,
        max_portfolio_risk_pct=0.05,
        execution_model="same_close",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"RELIANCE": df_rel, "TCS": df_tcs},
        signals_by_symbol=signals,
        config=cfg,
    )

    # At bar 0, both positions should open
    # Final cleanup at bar 4 closes both positions
    assert len(res.trades) == 2
    symbols_traded = {t.symbol for t in res.trades}
    assert symbols_traded == {"RELIANCE", "TCS"}

    # Verify positions had independent sizing and price tracking
    rel_trade = next(t for t in res.trades if t.symbol == "RELIANCE")
    tcs_trade = next(t for t in res.trades if t.symbol == "TCS")

    assert rel_trade.entry_price == 2500.2
    assert tcs_trade.entry_price == 3500.2
    assert rel_trade.quantity > 0
    assert tcs_trade.quantity > 0


# ============================================================================
# 3. Released Margin Availability at Same Timestamp
# ============================================================================

def test_03_released_margin_available_for_new_entry_same_bar():
    """
    Verify that when an existing position exits at timestamp t,
    its margin is immediately freed and available to fund a new candidate entry at timestamp t.
    """
    dates = pd.date_range("2024-01-02 09:15:00", periods=4, freq="min")

    # Bar 0: RELIANCE enters at 2500.0 (ATR=25.0, target=2575.0)
    # Bar 1: RELIANCE high hits 2580.0 -> TARGET hit and exits!
    # Bar 1: TCS generates entry signal! Should be able to use the released margin.
    df_rel = pd.DataFrame(
        {
            "Open": [2500.0, 2500.0, 2580.0, 2580.0],
            "High": [2505.0, 2580.0, 2585.0, 2585.0],  # Bar 1 high = 2580 hits target
            "Low": [2495.0, 2495.0, 2575.0, 2575.0],
            "Close": [2500.0, 2578.0, 2580.0, 2580.0],
            "Volume": [1000.0] * 4,
            "ATR": [25.0] * 4,
        },
        index=dates,
    )

    df_tcs = pd.DataFrame(
        {
            "Open": [3500.0, 3500.0, 3510.0, 3510.0],
            "High": [3505.0, 3505.0, 3515.0, 3515.0],
            "Low": [3495.0, 3495.0, 3505.0, 3505.0],
            "Close": [3500.0, 3500.0, 3510.0, 3510.0],
            "Volume": [1000.0] * 4,
            "ATR": [35.0] * 4,
        },
        index=dates,
    )

    signals = {
        "RELIANCE": [Position.LONG, None, None, None],
        "TCS": [None, Position.LONG, None, None],  # Signals at bar 1
    }

    # Small initial capital so margin is tight: Rs 20,000 (Available margin Rs 17,000)
    # RELIANCE consumes ~Rs 5,000 margin. If not released, TCS might be restricted.
    cfg = MultiAssetEngineConfig(
        initial_capital=20_000.0,
        risk_per_trade_pct=0.01,
        max_stock_allocation_pct=0.80,
        max_portfolio_risk_pct=0.05,
        execution_model="same_close",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"RELIANCE": df_rel, "TCS": df_tcs},
        signals_by_symbol=signals,
        config=cfg,
    )

    # RELIANCE should exit at bar 1 with TARGET
    rel_trades = [t for t in res.trades if t.symbol == "RELIANCE"]
    assert len(rel_trades) == 1
    assert rel_trades[0].exit_reason == "TARGET"

    # TCS should be successfully accepted at bar 1
    tcs_allocs = [a for a in res.allocations if a.symbol == "TCS"]
    assert len(tcs_allocs) == 1
    assert tcs_allocs[0].accepted is True
    assert tcs_allocs[0].allocated_quantity > 0


# ============================================================================
# 4. No Double-Spending & Available Margin Constraints
# ============================================================================

def test_04_available_margin_prevents_double_spending():
    """Verify two candidate opportunities cannot overcommit available portfolio margin."""
    dates = pd.date_range("2024-01-02 09:15:00", periods=3, freq="min")

    df_a = _create_sample_stock_data("STOCK_A", 1000.0, dates, atr_val=10.0)
    df_b = _create_sample_stock_data("STOCK_B", 1000.0, dates, atr_val=10.0)

    # Both signal at bar 0
    signals = {
        "STOCK_A": [Position.LONG, None, None],
        "STOCK_B": [Position.LONG, None, None],
    }

    # Capital = Rs 10,000. Reserve = 15% -> usable = Rs 8,500.
    # Max leverage = 5x -> total margin capacity Rs 8,500.
    # Allow 100% stock allocation so STOCK_A can consume margin up to available.
    cfg = MultiAssetEngineConfig(
        initial_capital=10_000.0,
        risk_per_trade_pct=0.05,  # 5% risk per trade = Rs 500 budget
        max_portfolio_risk_pct=0.10,
        max_stock_allocation_pct=0.60,  # Each stock can take at most 60% of equity
        reserve_capital_pct=0.15,
        execution_model="same_close",
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"STOCK_A": df_a, "STOCK_B": df_b},
        signals_by_symbol=signals,
        config=cfg,
    )

    # Verify total allocated margin never exceeded available equity
    for snapshot in res.equity_curve.itertuples():
        assert snapshot.allocated_margin <= snapshot.equity * (1.0 - cfg.reserve_capital_pct) + 1.0


# ============================================================================
# 5. Deterministic Ranking of Competing Opportunities
# ============================================================================

def test_05_deterministic_ranking_quality_priority():
    """Verify higher signal quality opportunity receives allocation before lower quality candidate."""
    dates = pd.date_range("2024-01-02 09:15:00", periods=3, freq="min")

    df_high = _create_sample_stock_data("HIGH_Q", 1000.0, dates, atr_val=10.0)
    df_low = _create_sample_stock_data("LOW_Q", 1000.0, dates, atr_val=10.0)

    # Custom signal generator with different qualities
    def sig_gen(symbol, current_time, bar):
        if current_time == dates[0]:
            if symbol == "HIGH_Q":
                return TradeOpportunity(
                    symbol="HIGH_Q",
                    side=Position.LONG,
                    entry_price=1000.0,
                    stop_loss=985.0,
                    target_price=1030.0,
                    signal_quality=2.0,  # Superior quality
                    atr=10.0,
                )
            else:
                return TradeOpportunity(
                    symbol="LOW_Q",
                    side=Position.LONG,
                    entry_price=1000.0,
                    stop_loss=985.0,
                    target_price=1030.0,
                    signal_quality=0.5,  # Inferior quality
                    atr=10.0,
                )
        return None

    # Available margin is restricted so only ONE trade can be funded
    cfg = MultiAssetEngineConfig(
        initial_capital=5_000.0,
        risk_per_trade_pct=0.01,
        max_stock_allocation_pct=1.0,
        max_portfolio_risk_pct=0.05,
        execution_model="same_close",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"HIGH_Q": df_high, "LOW_Q": df_low},
        signal_generator=sig_gen,
        config=cfg,
    )

    # HIGH_Q must be accepted
    high_alloc = next(a for a in res.allocations if a.symbol == "HIGH_Q")
    assert high_alloc.accepted is True
    assert high_alloc.allocated_quantity > 0


# ============================================================================
# 6. Aggregate Portfolio Risk Limit Enforcement
# ============================================================================

def test_06_aggregate_portfolio_risk_limit_blocks_excess_positions():
    """Verify candidates are rejected when aggregate portfolio risk reaches max_portfolio_risk_pct."""
    dates = pd.date_range("2024-01-02 09:15:00", periods=3, freq="min")

    # 4 stocks all signaling at bar 0
    # Equity = Rs 100,000. Risk per trade = 1% (Rs 1,000). Max portfolio risk = 3% (Rs 3,000).
    # Exactly 3 stocks can enter; 4th must be rejected with PORTFOLIO_RISK_LIMIT.
    data = {
        f"STOCK_{i}": _create_sample_stock_data(f"STOCK_{i}", 1000.0, dates, atr_val=10.0)
        for i in range(1, 5)
    }

    signals = {f"STOCK_{i}": [Position.LONG, None, None] for i in range(1, 5)}

    cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        risk_per_trade_pct=0.01,
        max_portfolio_risk_pct=0.03,  # Max 3 concurrent risk units
        max_stock_allocation_pct=0.35,
        execution_model="same_close",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol=data,
        signals_by_symbol=signals,
        config=cfg,
    )

    accepted = [a for a in res.allocations if a.accepted]
    rejected = [a for a in res.allocations if not a.accepted]

    assert len(accepted) == 3
    assert len(rejected) == 1
    assert rejected[0].limiting_constraint == "PORTFOLIO_RISK_LIMIT"


# ============================================================================
# 7. Single-Stock Allocation Cap
# ============================================================================

def test_07_single_stock_allocation_cap():
    """Verify max_stock_allocation_pct restricts quantity for an individual stock."""
    dates = pd.date_range("2024-01-02 09:15:00", periods=3, freq="min")
    df = _create_sample_stock_data("RELIANCE", 2500.0, dates, atr_val=5.0)

    # Very small stop distance (5.0 * 1.5 = 7.5) would allow huge quantity under risk budget
    # Equity Rs 100,000 * 35% * 5x leverage = Rs 175,000 max notional = 70 shares max
    signals = {"RELIANCE": [Position.LONG, None, None]}

    cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        risk_per_trade_pct=0.02,  # Rs 2,000 risk -> 2000 / 7.5 = 266 shares
        max_stock_allocation_pct=0.35,
        max_portfolio_risk_pct=0.05,
        execution_model="same_close",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"RELIANCE": df},
        signals_by_symbol=signals,
        config=cfg,
    )

    alloc = res.allocations[0]
    assert alloc.accepted is True
    # Notional value must not exceed Rs 175,000
    assert alloc.allocated_quantity * 2500.2 <= 175_000.0
    assert alloc.limiting_constraint == "STOCK_ALLOCATION_LIMIT"


# ============================================================================
# 8. Missing Candle Handling
# ============================================================================

def test_08_missing_candle_cannot_generate_entry():
    """Verify symbol with missing candle at timestamp t cannot generate an entry."""
    dates_rel = pd.date_range("2024-01-02 09:15:00", periods=5, freq="min")
    # TCS is missing bar 1 (09:16)
    dates_tcs = dates_rel.drop(dates_rel[1])

    df_rel = _create_sample_stock_data("RELIANCE", 2500.0, dates_rel)
    df_tcs = _create_sample_stock_data("TCS", 3500.0, dates_tcs)

    # Attempt to signal TCS at 09:16
    sig_tcs = pd.Series([Position.LONG] * len(dates_tcs), index=dates_tcs)
    # But RELIANCE has signal at 09:16
    sig_rel = pd.Series([None, Position.LONG, None, None, None], index=dates_rel)

    cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        execution_model="same_close",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"RELIANCE": df_rel, "TCS": df_tcs},
        signals_by_symbol={"RELIANCE": sig_rel, "TCS": sig_tcs},
        config=cfg,
    )

    # Missing candle stat for TCS must be 1
    assert res.missing_candle_stats["TCS"] == 1
    assert res.missing_candle_stats["RELIANCE"] == 0

    # RELIANCE entered at 09:16
    rel_alloc = next(a for a in res.allocations if a.symbol == "RELIANCE")
    assert rel_alloc.accepted is True


# ============================================================================
# 9. Stale Price Protection (No Stops/Targets Triggered by Stale Marks)
# ============================================================================

def test_09_stale_price_does_not_trigger_exits():
    """
    Verify that if a symbol with an active open position misses a candle,
    it uses the last valid mark for reporting but NEVER triggers stop or target exits.
    """
    dates_full = pd.date_range("2024-01-02 09:15:00", periods=5, freq="min")

    # RELIANCE enters at bar 0 (09:15)
    # RELIANCE is MISSING at bar 1 (09:16)
    # INFY is present at all bars
    dates_rel = dates_full.drop(dates_full[1])
    df_rel = _create_sample_stock_data("RELIANCE", 2500.0, dates_rel, atr_val=25.0)
    df_infy = _create_sample_stock_data("INFY", 1500.0, dates_full, atr_val=15.0)

    signals = {
        "RELIANCE": [Position.LONG, None, None, None],  # Signals at bar 0
        "INFY": [None, None, None, None, None],
    }

    cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        execution_model="same_close",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"RELIANCE": df_rel, "INFY": df_infy},
        signals_by_symbol=signals,
        config=cfg,
    )

    # At bar 1 (09:16), RELIANCE was missing, recorded as stale price event
    assert res.stale_price_events == 1
    assert res.stale_notional_exposure > 0.0

    # RELIANCE position was not closed at 09:16!
    # It closes only at end of data (EOD)
    assert len(res.trades) == 1
    assert res.trades[0].exit_time == dates_full[-1]
    assert res.trades[0].exit_reason == "EOD"


# ============================================================================
# 10. Session Boundary & EOD Square-Off
# ============================================================================

def test_10_eod_square_off_enforced_at_session_cutoff():
    """Verify open positions square off at session_end_time (15:15) with exit_reason='EOD'."""
    dates = pd.date_range("2024-01-02 15:10:00", periods=8, freq="min")  # 15:10 to 15:17

    df = _create_sample_stock_data("RELIANCE", 2500.0, dates)
    signals = {"RELIANCE": [Position.LONG, None, None, None, None, None, None, None]}

    cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        session_end_time="15:15",
        enforce_eod_square_off=True,
        execution_model="same_close",
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"RELIANCE": df},
        signals_by_symbol=signals,
        config=cfg,
    )

    assert len(res.trades) == 1
    trade = res.trades[0]
    assert trade.exit_reason == "EOD"
    assert trade.exit_time == pd.Timestamp("2024-01-02 15:15:00")


# ============================================================================
# 11. Conservative Same-Candle Collision Handling
# ============================================================================

def test_11_conservative_same_candle_collision():
    """Verify STOP is evaluated before TARGET when both touched on the same candle."""
    dates = pd.date_range("2024-01-02 09:15:00", periods=3, freq="min")

    # Bar 0: Entry at 100.0. ATR = 2.0 -> Stop = 97.0, Target = 106.0
    # Bar 1: Low drops to 96.0 AND High spikes to 107.0 (Both hit!)
    df = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 100.0],
            "High": [100.5, 107.0, 100.5],
            "Low": [99.5, 96.0, 99.5],
            "Close": [100.0, 100.0, 100.0],
            "Volume": [1000.0] * 3,
            "ATR": [2.0] * 3,
        },
        index=dates,
    )

    cfg = MultiAssetEngineConfig(
        initial_capital=10_000.0,
        stop_loss_atr=1.5,
        take_profit_atr=3.0,
        conservative_same_candle=True,
        execution_model="same_close",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"TEST": df},
        signals_by_symbol={"TEST": [Position.LONG, None, None]},
        config=cfg,
    )

    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_reason == "STOP"
    assert t.exit_price == 97.0


# ============================================================================
# 12. Adverse Gap Execution Through Stop
# ============================================================================

def test_12_adverse_gap_execution():
    """Verify stop execution fills at bar_open when market gaps through stop."""
    dates = pd.date_range("2024-01-02 09:15:00", periods=3, freq="min")

    # Bar 0: Entry at 100.0. Stop = 97.0
    # Bar 1: Gaps down at Open to 95.0 (below stop 97.0)
    df = pd.DataFrame(
        {
            "Open": [100.0, 95.0, 95.0],
            "High": [100.5, 95.5, 95.5],
            "Low": [99.5, 94.0, 94.0],
            "Close": [100.0, 94.5, 95.0],
            "Volume": [1000.0] * 3,
            "ATR": [2.0] * 3,
        },
        index=dates,
    )

    cfg = MultiAssetEngineConfig(
        initial_capital=10_000.0,
        gap_execution=True,
        execution_model="same_close",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"TEST": df},
        signals_by_symbol={"TEST": [Position.LONG, None, None]},
        config=cfg,
    )

    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_reason == "STOP"
    assert t.exit_price == 95.0  # Filled at bar_open gap


# ============================================================================
# 13. Portfolio Capital Protection Floor Breach
# ============================================================================

def test_13_portfolio_protection_floor_halts_trading():
    """Verify portfolio halts and blocks new entries when equity drops below protection floor."""
    dates = pd.date_range("2024-01-02 09:15:00", periods=6, freq="min")

    # Initial Rs 10,000. Floor Rs 8,000 (Loss limit Rs 2,000).
    # Trade 1 takes a loss that breaches floor.
    df = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 70.0, 70.0, 70.0, 70.0],
            "High": [100.5, 100.5, 70.5, 70.5, 70.5, 70.5],
            "Low": [99.5, 70.0, 69.0, 69.0, 69.0, 69.0],
            "Close": [100.0, 70.0, 70.0, 70.0, 70.0, 70.0],
            "Volume": [1000.0] * 6,
            "ATR": [5.0] * 6,
        },
        index=dates,
    )

    # Signal on bar 0 and bar 3
    signals = {"RELIANCE": [Position.LONG, None, None, Position.LONG, None, None]}

    cfg = MultiAssetEngineConfig(
        initial_capital=10_000.0,
        capital_protection_floor=8_000.0,
        risk_per_trade_pct=0.25,  # Large risk to force floor breach
        max_portfolio_risk_pct=0.30,
        max_stock_allocation_pct=1.0,
        execution_model="same_close",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"RELIANCE": df},
        signals_by_symbol=signals,
        config=cfg,
    )

    # First trade caused equity <= 8,000
    assert res.portfolio.equity <= 8_000.0
    assert res.portfolio.is_bankrupt is True
    assert res.bankruptcy_reason == "PROTECTION_FLOOR"

    # Bar 3 signal MUST be blocked
    assert len(res.trades) == 1


# ============================================================================
# 14. Next-Open Execution Model Synchronization
# ============================================================================

def test_14_next_open_execution_model():
    """Verify 'next_open' model queues signal at bar t close and fills at bar t+1 open."""
    dates = pd.date_range("2024-01-02 09:15:00", periods=4, freq="min")

    # Signal at bar 0 (09:15 close).
    # Bar 1 (09:16) Open = 2505.0. Entry must fill at 2505.0!
    df = pd.DataFrame(
        {
            "Open": [2500.0, 2505.0, 2510.0, 2510.0],
            "High": [2502.0, 2515.0, 2515.0, 2515.0],
            "Low": [2498.0, 2504.0, 2508.0, 2508.0],
            "Close": [2500.0, 2512.0, 2510.0, 2510.0],
            "Volume": [1000.0] * 4,
            "ATR": [10.0] * 4,
        },
        index=dates,
    )

    signals = {"RELIANCE": [Position.LONG, None, None, None]}

    cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"RELIANCE": df},
        signals_by_symbol=signals,
        config=cfg,
    )

    assert len(res.trades) == 1
    trade = res.trades[0]
    assert trade.entry_time == dates[1]  # Filled at 09:16
    assert trade.entry_price == 2505.0   # Filled at bar_open


# ============================================================================
# 15. Canonical Transaction Cost Integration
# ============================================================================

def test_15_canonical_transaction_costs_integrated():
    """Verify canonical Phase 27B transaction costs are deducted upon trade closure."""
    dates = pd.date_range("2024-01-02 09:15:00", periods=3, freq="min")
    df = _create_sample_stock_data("RELIANCE", 2500.0, dates, atr_val=10.0)

    cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
        execution_model="same_close",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"RELIANCE": df},
        signals_by_symbol={"RELIANCE": [Position.LONG, None, None]},
        config=cfg,
    )

    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.transaction_cost > 0.0
    assert t.net_pnl == pytest.approx(t.gross_pnl - t.transaction_cost, abs=1e-2)
    assert res.portfolio.cash == pytest.approx(100_000.0 + t.net_pnl, abs=1e-2)


# ============================================================================
# 16. Comprehensive Output & Per-Symbol Breakdown
# ============================================================================

def test_16_comprehensive_result_and_symbol_breakdown():
    """Verify MultiAssetBacktestResult returns valid equity curve, metrics, and per-symbol metrics."""
    dates = pd.date_range("2024-01-02 09:15:00", periods=5, freq="min")
    df_rel = _create_sample_stock_data("RELIANCE", 2500.0, dates)
    df_tcs = _create_sample_stock_data("TCS", 3500.0, dates)

    cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        execution_model="same_close",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"RELIANCE": df_rel, "TCS": df_tcs},
        signals_by_symbol={
            "RELIANCE": [Position.LONG, None, None, None, None],
            "TCS": [None, Position.SHORT, None, None, None],
        },
        config=cfg,
    )

    # 1. Equity curve structure
    assert isinstance(res.equity_curve, pd.DataFrame)
    assert "equity" in res.equity_curve.columns
    assert "cash" in res.equity_curve.columns
    assert "allocated_margin" in res.equity_curve.columns
    assert "available_margin" in res.equity_curve.columns

    # 2. Performance metrics
    assert res.metrics.total_trades == 2

    # 3. Symbol breakdown
    assert "RELIANCE" in res.symbol_metrics
    assert "TCS" in res.symbol_metrics
    assert res.symbol_metrics["RELIANCE"]["trades"] == 1
    assert res.symbol_metrics["TCS"]["trades"] == 1
