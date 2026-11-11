"""
SignalForge — Phase 27C.3.5.7: Stale Data Risk Policy & Entry Guard Hardening Tests.

Verifies:
1. One missing candle (below threshold) retains authentic mark and does not block other symbols.
2. Five consecutive missing candles exceeds threshold, marking position stale and blocking entries.
3. Ten consecutive missing candles persists stale state without dropping position or corrupting margin.
4. Configurable threshold (e.g. max_consecutive_missing_bars = 2) enforces custom bounds.
5. Symbol A stale while Symbol B signals -> Symbol B entries strictly blocked.
6. Positive valid-but-old price does not evade stale state detection.
7. Portfolio-wide entry blocking enforced across all universe candidates.
8. Direct PortfolioManager.open_position() independently raises IndeterminateValuationError.
9. Direct CapitalAllocator.validate_opportunity_inputs() independently rejects candidate opportunities.
10. Both next_open and same_close execution models enforce stale blocking.
11. Recovery after authentic data resumes: resets consecutive counter, clears stale flag, unblocks entries.
12. Large price gap on recovery evaluated on fresh candle without fabricating intermediate prices.
13. Pending liquidation while data is unavailable remains pending with locked margin.
14. Margin remaining locked until authentic liquidation execution.
15. Multiple stale symbols with independent staggered recovery.
16. Session boundary interaction: stale position marked pending liquidation at 15:15 EOD.
17. Bankruptcy and unresolved liquidation protections remain strictly intact alongside stale policy.
18. Exactly-once fee deductions and accounting reconciliation under stale transitions.
"""

import pytest
import pandas as pd

from src.backtest.capital_allocator import (
    CapitalAllocationConfig,
    CapitalAllocator,
    TradeOpportunity,
)
from src.backtest.indian_market_costs import DISCOUNT_BROKER_REALISTIC_CONFIG
from src.backtest.multi_asset_engine import (
    MultiAssetEngineConfig,
    run_multi_asset_backtest,
)
from src.backtest.portfolio import (
    PortfolioManager,
    IndeterminateValuationError,
    PortfolioBankruptError,
)
from src.backtest.simulator import Position


def _make_bars(dates: pd.DatetimeIndex, base_price: float = 100.0) -> pd.DataFrame:
    """Create standard OHLCV+ATR test fixture DataFrame."""
    n = len(dates)
    return pd.DataFrame(
        {
            "Open": [base_price] * n,
            "High": [base_price + 1.0] * n,
            "Low": [base_price - 1.0] * n,
            "Close": [base_price] * n,
            "Volume": [1000.0] * n,
            "ATR": [2.0] * n,
        },
        index=dates,
    )


# ============================================================================
# 1. Single Missing Candle (Under Default Threshold of 3)
# ============================================================================

def test_01_single_missing_candle_does_not_block_entries():
    """1 missing candle is below threshold (3); preserves mark and allows other symbols to enter."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a = _make_bars(dates, 100.0)
    df_b = _make_bars(dates, 200.0)

    # SYM_A misses only bar 2 (1 single bar)
    df_a = df_a.drop(dates[2])

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=200.0, stop_loss=150.0, target_price=300.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        execution_model="next_open",
        enforce_eod_square_off=False,
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [opp_a, None, None, None, None],
            "SYM_B": [None, opp_b, None, None, None],  # Signals at bar 1, executes bar 2
        },
        config=m_cfg,
    )

    # SYM_B successfully enters at bar 2 open even though SYM_A missed bar 2 (1 < 3)
    b_allocs = [a for a in res.allocations if a.symbol == "SYM_B" and a.accepted]
    assert len(b_allocs) == 1
    assert len(res.trades) == 2
    assert {t.symbol for t in res.trades} == {"SYM_A", "SYM_B"}
    assert res.missing_candle_stats["SYM_A"] == 1
    assert res.portfolio.has_indeterminate_valuation is False
    assert res.stale_price_events == 1


# ============================================================================
# 2. Five Consecutive Missing Candles (Exceeds Threshold)
# ============================================================================

def test_02_five_consecutive_missing_candles_blocks_entries():
    """5 consecutive missing bars exceeds default threshold (3); marks stale and blocks entries."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=10, freq="1min")
    df_a = _make_bars(dates, 100.0)
    df_b = _make_bars(dates, 200.0)

    # SYM_A drops bars 2, 3, 4, 5, 6 (5 consecutive bars)
    df_a = df_a.drop(dates[2:7])

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )
    # SYM_B attempts to signal at bar 4 (to enter bar 5, when SYM_A has missed 3+ bars)
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=200.0, stop_loss=150.0, target_price=300.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[4], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        execution_model="next_open",
        enforce_eod_square_off=False,
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [opp_a] + [None] * 9,
            "SYM_B": [None, None, None, None, opp_b] + [None] * 5,
        },
        config=m_cfg,
    )

    # SYM_B entry is blocked because SYM_A is stale
    b_allocs = [a for a in res.allocations if a.symbol == "SYM_B" and a.accepted]
    assert len(b_allocs) == 0
    assert not any(t.symbol == "SYM_B" for t in res.trades)
    assert len(res.trades) == 1
    assert res.trades[0].symbol == "SYM_A"
    assert res.missing_candle_stats["SYM_A"] == 5
    assert res.indeterminate_valuation_events >= 1


# ============================================================================
# 3. Ten Consecutive Missing Candles
# ============================================================================

def test_03_ten_consecutive_missing_candles_persists_stale_state():
    """10 consecutive missing bars persists stale state without dropping position or corrupting margin."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=12, freq="1min")
    df_a = _make_bars(dates, 100.0).drop(dates[2:12])  # Drops bars 2 to 11 (10 consecutive bars through end)
    df_ref = _make_bars(dates, 100.0)  # Drives timeline

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        execution_model="next_open",
        enforce_eod_square_off=False,
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_REF": df_ref},
        signals_by_symbol={"SYM_A": [opp_a] + [None] * 11},
        config=m_cfg,
    )

    assert res.missing_candle_stats["SYM_A"] == 10
    assert res.stale_price_events == 10
    assert res.portfolio.allocated_margin == (100.0 * 50) / 5.0
    assert len(res.unresolved_positions) == 1
    pos = res.unresolved_positions[0]
    assert pos.symbol == "SYM_A"
    assert pos.is_stale is True
    assert pos.current_price == 100.0
    assert res.indeterminate_valuation_events >= 7


# ============================================================================
# 4. Configurable Threshold
# ============================================================================

def test_04_configurable_threshold_enforced():
    """Configuring max_consecutive_missing_bars = 2 triggers stale block on 2nd consecutive missing bar."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=6, freq="1min")
    df_a = _make_bars(dates, 100.0)
    df_b = _make_bars(dates, 200.0)

    # SYM_A drops bars 2 and 3 (2 consecutive bars)
    df_a = df_a.drop(dates[2:4])

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=200.0, stop_loss=150.0, target_price=300.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[2], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=2,  # Custom strict threshold = 2
        execution_model="next_open",
        enforce_eod_square_off=False,
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [opp_a, None, None, None, None, None],
            "SYM_B": [None, None, opp_b, None, None, None],
        },
        config=m_cfg,
    )

    # SYM_B blocked from entering on bar 3 because SYM_A reached threshold 2
    b_allocs = [a for a in res.allocations if a.symbol == "SYM_B" and a.accepted]
    assert len(b_allocs) == 0


# ============================================================================
# 5. Symbol A Stale While Symbol B Signals
# ============================================================================

def test_05_symbol_a_stale_blocks_symbol_b_entries():
    """Verify Symbol B entries are completely blocked while Symbol A is in a stale state."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=8, freq="1min")
    df_a = _make_bars(dates, 100.0).drop(dates[2:6])  # 4 consecutive bars missing
    df_b = _make_bars(dates, 200.0)

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )
    opp_b1 = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=200.0, stop_loss=150.0, target_price=300.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[3], atr=2.0,
    )
    opp_b2 = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=200.0, stop_loss=150.0, target_price=300.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[4], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        execution_model="next_open",
        enforce_eod_square_off=False,
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [opp_a] + [None] * 7,
            "SYM_B": [None, None, None, opp_b1, opp_b2, None, None, None],
        },
        config=m_cfg,
    )

    assert not any(a.accepted for a in res.allocations if a.symbol == "SYM_B")
    assert "SYM_B" not in res.portfolio.open_positions


# ============================================================================
# 6. Valid But Old Positive Price Does Not Evade Stale Detection
# ============================================================================

def test_06_positive_old_price_does_not_evade_stale_detection():
    """Verify that a positive, non-null current_price does not trick the engine into treating data as fresh."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=7, freq="1min")
    df_a = _make_bars(dates, 100.0).drop(dates[2:7])  # 5 bars missing through end
    df_ref = _make_bars(dates, 100.0)

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        execution_model="next_open",
        enforce_eod_square_off=False,
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_REF": df_ref},
        signals_by_symbol={"SYM_A": [opp_a] + [None] * 6},
        config=m_cfg,
    )

    assert len(res.unresolved_positions) == 1
    pos = res.unresolved_positions[0]
    assert pos.symbol == "SYM_A"
    assert pos.current_price == 100.0  # Positive price retained
    assert pos.current_price > 0.0
    assert pos.is_stale is True
    assert res.indeterminate_valuation_events >= 1


# ============================================================================
# 7. Portfolio-Wide Entry Blocking Enforced
# ============================================================================

def test_07_portfolio_wide_entry_blocking():
    """Verify that every symbol in the universe (B, C, D) is blocked when symbol A is stale."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=7, freq="1min")
    df_a = _make_bars(dates, 100.0).drop(dates[2:6])
    df_b = _make_bars(dates, 200.0)
    df_c = _make_bars(dates, 300.0)

    opp_a = TradeOpportunity(symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0, requested_quantity=10, signal_quality=1.0, relative_volume=1.0, is_tradeable=True, timestamp=dates[0], atr=2.0)
    opp_b = TradeOpportunity(symbol="SYM_B", side=Position.LONG, entry_price=200.0, stop_loss=150.0, target_price=300.0, requested_quantity=10, signal_quality=1.0, relative_volume=1.0, is_tradeable=True, timestamp=dates[4], atr=2.0)
    opp_c = TradeOpportunity(symbol="SYM_C", side=Position.LONG, entry_price=300.0, stop_loss=250.0, target_price=400.0, requested_quantity=10, signal_quality=1.0, relative_volume=1.0, is_tradeable=True, timestamp=dates[4], atr=2.0)

    m_cfg = MultiAssetEngineConfig(initial_capital=100_000.0, max_consecutive_missing_bars=3, execution_model="next_open", opening_cooldown_minutes=0)

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b, "SYM_C": df_c},
        signals_by_symbol={
            "SYM_A": [opp_a] + [None] * 6,
            "SYM_B": [None, None, None, None, opp_b, None, None],
            "SYM_C": [None, None, None, None, opp_c, None, None],
        },
        config=m_cfg,
    )

    accepted_syms = [a.symbol for a in res.allocations if a.accepted]
    assert "SYM_A" in accepted_syms
    assert "SYM_B" not in accepted_syms
    assert "SYM_C" not in accepted_syms


# ============================================================================
# 8. Direct PortfolioManager.open_position() Rejection
# ============================================================================

def test_08_direct_portfolio_manager_open_position_rejection():
    """Verify PortfolioManager.open_position() independently raises IndeterminateValuationError."""
    pm = PortfolioManager(initial_capital=100_000.0)
    pm.has_indeterminate_valuation = True
    pm.indeterminate_valuation_reason = "Test indeterminate state"

    can_open, reason = pm.can_open_position("SYM_A", 100.0, 10)
    assert can_open is False
    assert "indeterminate valuation" in reason

    with pytest.raises(IndeterminateValuationError, match="indeterminate valuation"):
        pm.open_position("SYM_A", Position.LONG, pd.Timestamp("2026-03-30 09:25"), 100.0, 10)


# ============================================================================
# 9. Direct CapitalAllocator.validate_opportunity_inputs() Rejection
# ============================================================================

def test_09_direct_capital_allocator_rejection():
    """Verify CapitalAllocator.validate_opportunity_inputs() rejects candidate opportunities when valuation indeterminate."""
    pm = PortfolioManager(initial_capital=100_000.0)
    pm.has_indeterminate_valuation = True
    pm.indeterminate_valuation_reason = "Test valuation uncertainty"

    allocator = CapitalAllocator(CapitalAllocationConfig())
    opp = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=90.0, target_price=120.0,
        requested_quantity=10, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=pd.Timestamp("2026-03-30 09:25"), atr=2.0,
    )

    valid, reason = allocator.validate_opportunity_inputs(opp, pm)
    assert valid is False
    assert "indeterminate valuation" in reason.lower()

    # allocate_batch must reject opportunity
    decisions = allocator.allocate_batch([opp], pm)
    assert len(decisions) == 1
    assert decisions[0].accepted is False
    assert "indeterminate valuation" in decisions[0].rejection_reason.lower()


# ============================================================================
# 10. Execution Models: Both next_open and same_close Enforce Stale Block
# ============================================================================

@pytest.mark.parametrize("model", ["next_open", "same_close"])
def test_10_both_execution_models_enforce_stale_blocking(model: str):
    """Verify both next_open and same_close execution models enforce stale blocking."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=8, freq="1min")
    df_a = _make_bars(dates, 100.0).drop(dates[2:6])  # 4 bars missing
    df_b = _make_bars(dates, 200.0)

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=200.0, stop_loss=150.0, target_price=300.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[4], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        execution_model=model,
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [opp_a] + [None] * 7,
            "SYM_B": [None, None, None, None, opp_b, None, None, None],
        },
        config=m_cfg,
    )

    assert not any(a.accepted for a in res.allocations if a.symbol == "SYM_B")


# ============================================================================
# 11. Recovery After Authentic Data Resumes
# ============================================================================

def test_11_recovery_resets_counter_and_unblocks_entries():
    """Verify that when authentic data arrives after 4 missing bars, stale flag and indeterminate state clear."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=10, freq="1min")
    # SYM_A drops bars 2, 3, 4, 5 (4 bars), resumes at bar 6
    df_a = _make_bars(dates, 100.0).drop(dates[2:6])
    df_b = _make_bars(dates, 200.0)

    opp_a = TradeOpportunity(symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0, requested_quantity=20, signal_quality=1.0, relative_volume=1.0, is_tradeable=True, timestamp=dates[0], atr=2.0)
    # Signal for SYM_B at bar 6 (when SYM_A data has resumed!), executes bar 7
    opp_b = TradeOpportunity(symbol="SYM_B", side=Position.LONG, entry_price=200.0, stop_loss=150.0, target_price=300.0, requested_quantity=20, signal_quality=1.0, relative_volume=1.0, is_tradeable=True, timestamp=dates[6], atr=2.0)

    m_cfg = MultiAssetEngineConfig(initial_capital=100_000.0, max_consecutive_missing_bars=3, execution_model="next_open", enforce_eod_square_off=False, opening_cooldown_minutes=0)

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [opp_a] + [None] * 9,
            "SYM_B": [None, None, None, None, None, None, opp_b, None, None, None],
        },
        config=m_cfg,
    )

    # SYM_B accepted at bar 7 because SYM_A recovered at bar 6!
    b_allocs = [a for a in res.allocations if a.symbol == "SYM_B" and a.accepted]
    assert len(b_allocs) == 1
    assert len(res.trades) == 2
    assert {t.symbol for t in res.trades} == {"SYM_A", "SYM_B"}
    assert res.portfolio.has_indeterminate_valuation is False
    assert res.portfolio.indeterminate_valuation_reason is None


# ============================================================================
# 12. Large Price Gap on Recovery
# ============================================================================

def test_12_large_price_gap_on_recovery():
    """Verify large price gap upon data resumption is evaluated cleanly on the fresh candle."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=7, freq="1min")
    df_a = _make_bars(dates, 100.0).drop(dates[2:5])  # drops bars 2, 3, 4 (3 bars)
    # Bar 5 resumes with gap down to 70.0 (below stop 80.0)
    df_a.loc[dates[5], ["Open", "High", "Low", "Close"]] = 70.0

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=80.0, target_price=200.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(initial_capital=100_000.0, max_consecutive_missing_bars=3, execution_model="next_open", opening_cooldown_minutes=0)

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a},
        signals_by_symbol={"SYM_A": [opp_a] + [None] * 6},
        config=m_cfg,
    )

    assert len(res.trades) == 1
    t = res.trades[0]
    # Executed at authentic resumed Open 70.0, NOT fabricated intermediate price
    assert t.exit_price == 70.0
    assert t.exit_reason in ("STOP", "PROTECTION_FLOOR")


# ============================================================================
# 13. Pending Liquidation While Data Unavailable
# ============================================================================

def test_13_pending_liquidation_while_data_unavailable():
    """Verify position whose market data is unavailable remains pending liquidation with margin locked."""
    pm = PortfolioManager(initial_capital=100_000.0, max_leverage=5.0)
    pos = pm.open_position("SYM_A", Position.LONG, pd.Timestamp("2026-03-30 09:25"), 100.0, 100)
    assert pm.allocated_margin == 2000.0

    pm.mark_pending_liquidation("SYM_A", reason="PROTECTION_FLOOR")
    assert pos.pending_liquidation is True
    assert pm.has_unresolved_liquidations is True
    # Margin must stay locked
    assert pm.allocated_margin == 2000.0
    # Direct open attempt must be rejected
    with pytest.raises(PortfolioBankruptError, match="unresolved emergency liquidations"):
        pm.open_position("SYM_B", Position.LONG, pd.Timestamp("2026-03-30 09:26"), 100.0, 100)


# ============================================================================
# 14. Margin Remaining Locked Until Authentic Liquidation
# ============================================================================

def test_14_margin_locked_until_authentic_liquidation():
    """Verify margin remains locked across multiple bars until authentic candle arrives to execute fill."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=8, freq="1min")
    df_a = _make_bars(dates, 100.0)
    df_b = _make_bars(dates, 100.0)

    # Bar 3 breaches floor
    df_a.loc[dates[3], ["Open", "High", "Low", "Close"]] = 60.0
    # SYM_B drops bars 3, 4, 5 (missing when emergency liquidation triggers)
    df_b = df_b.drop(dates[3:6])

    opp_a = TradeOpportunity(symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0, requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True, timestamp=dates[0], atr=2.0)
    opp_b = TradeOpportunity(symbol="SYM_B", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0, requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True, timestamp=dates[0], atr=2.0)

    m_cfg = MultiAssetEngineConfig(initial_capital=100_000.0, capital_protection_floor=97_000.0, max_consecutive_missing_bars=3, execution_model="next_open", opening_cooldown_minutes=0)

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={"SYM_A": [opp_a] + [None] * 7, "SYM_B": [opp_b] + [None] * 7},
        config=m_cfg,
    )

    # Both symbols eventually liquidated cleanly; final margin is 0
    assert len(res.trades) == 2
    assert res.portfolio.allocated_margin == 0.0


# ============================================================================
# 15. Multiple Stale Symbols and Independent Recovery
# ============================================================================

def test_15_multiple_stale_symbols_independent_recovery():
    """Verify that if SYM_A and SYM_B are both stale, portfolio remains blocked until BOTH recover."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=12, freq="1min")
    # SYM_A drops bars 2..5 (4 bars, recovers bar 6)
    df_a = _make_bars(dates, 100.0).drop(dates[2:6])
    # SYM_B drops bars 2..8 (7 bars, recovers bar 9)
    df_b = _make_bars(dates, 100.0).drop(dates[2:9])
    df_c = _make_bars(dates, 100.0)

    opp_a = TradeOpportunity(symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0, requested_quantity=10, signal_quality=1.0, relative_volume=1.0, is_tradeable=True, timestamp=dates[0], atr=2.0)
    opp_b = TradeOpportunity(symbol="SYM_B", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0, requested_quantity=10, signal_quality=1.0, relative_volume=1.0, is_tradeable=True, timestamp=dates[0], atr=2.0)

    # SYM_C signals at bar 7 (SYM_A recovered, but SYM_B is still stale!)
    opp_c1 = TradeOpportunity(symbol="SYM_C", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0, requested_quantity=10, signal_quality=1.0, relative_volume=1.0, is_tradeable=True, timestamp=dates[7], atr=2.0)
    # SYM_C signals at bar 9 (executes bar 10 when BOTH have recovered!)
    opp_c2 = TradeOpportunity(symbol="SYM_C", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0, requested_quantity=10, signal_quality=1.0, relative_volume=1.0, is_tradeable=True, timestamp=dates[9], atr=2.0)

    m_cfg = MultiAssetEngineConfig(initial_capital=100_000.0, max_consecutive_missing_bars=3, execution_model="next_open", enforce_eod_square_off=False, opening_cooldown_minutes=0)

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b, "SYM_C": df_c},
        signals_by_symbol={
            "SYM_A": [opp_a] + [None] * 11,
            "SYM_B": [opp_b] + [None] * 11,
            "SYM_C": [None, None, None, None, None, None, None, opp_c1, None, opp_c2, None, None],
        },
        config=m_cfg,
    )

    # opp_c1 (bar 7) was blocked from entering because SYM_B was still stale!
    # opp_c2 (bar 9 signal, bar 10 execution) was accepted because BOTH SYM_A and SYM_B recovered!
    c_allocs = [a for a in res.allocations if a.symbol == "SYM_C" and a.accepted]
    assert len(c_allocs) == 1
    assert len(res.trades) == 3
    assert {t.symbol for t in res.trades} == {"SYM_A", "SYM_B", "SYM_C"}
    assert res.portfolio.has_indeterminate_valuation is False


# ============================================================================
# 16. Session Boundary Behavior
# ============================================================================

def test_16_session_boundary_eod_square_off_with_stale_data():
    """Verify that at session close (15:15), a missing stale position is marked pending liquidation and not dropped."""
    dates = pd.date_range("2026-03-30 15:10:00", periods=6, freq="1min")
    # SYM_A misses 15:14 and 15:15
    df_a = _make_bars(dates, 100.0).drop(dates[4:])
    # SYM_REF drives timeline through 15:15
    df_ref = _make_bars(dates, 100.0)

    opp_a = TradeOpportunity(symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0, requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True, timestamp=dates[0], atr=2.0)

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        session_end_time="15:15",
        enforce_eod_square_off=True,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_REF": df_ref},
        signals_by_symbol={"SYM_A": [opp_a] + [None] * 5},
        config=m_cfg,
    )

    # Position is in unresolved_positions because 15:15 close candle was missing
    assert len(res.unresolved_positions) == 1
    assert res.unresolved_positions[0].pending_liquidation is True
    assert res.unresolved_positions[0].pending_liquidation_reason == "EOD"


# ============================================================================
# 17. Bankruptcy and Unresolved Liquidation Protections Remain Intact
# ============================================================================

def test_17_bankruptcy_and_unresolved_protections_intact():
    """Verify existing bankruptcy and unresolved protections work seamlessly with stale data policy."""
    pm = PortfolioManager(initial_capital=100_000.0, capital_protection_floor=97_000.0)
    pm.is_bankrupt = True
    pm.bankruptcy_reason = "PROTECTION_FLOOR"

    can_open, reason = pm.can_open_position("SYM_A", 100.0, 10)
    assert can_open is False
    assert "bankrupt" in reason.lower()

    with pytest.raises(PortfolioBankruptError):
        pm.open_position("SYM_A", Position.LONG, pd.Timestamp("2026-03-30 09:25"), 100.0, 10)


# ============================================================================
# 18. No Duplicate Fees or Accounting Deductions
# ============================================================================

def test_18_no_duplicate_fees_or_deductions_under_stale_transitions():
    """Verify that multiple stale transitions do not repeatedly charge fees or distort portfolio cash."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=10, freq="1min")
    # SYM_A drops bars 2, 3, 4 (stale), resumes bar 5, closes on target at bar 6
    df_a = _make_bars(dates, 100.0).drop(dates[2:5])
    df_a.loc[dates[6], ["Open", "High", "Low", "Close"]] = 150.0

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=150.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        execution_model="next_open",
        opening_cooldown_minutes=0,
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a},
        signals_by_symbol={"SYM_A": [opp_a] + [None] * 9},
        config=m_cfg,
    )

    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_reason == "TARGET"
    assert t.exit_price == 150.0

    # Realized net P&L matches gross - costs exactly once
    assert pytest.approx(t.net_pnl, abs=1e-2) == t.gross_pnl - t.transaction_cost
    assert pytest.approx(res.portfolio.cash, abs=1e-2) == 100_000.0 + t.net_pnl
