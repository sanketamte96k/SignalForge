"""
SignalForge — Phase 27C.3.5.9: Portfolio Risk-Reason Ownership & Global Feed-Outage Detection Tests.

Verifies:
1. Independent risk reason ownership: Subsystem A adding a risk blocker cannot be cleared by Subsystem B.
2. Multiple symbols independently contributing stale position risk blockers (STALE_POSITION:SYM_A, STALE_POSITION:SYM_B).
3. Partial recovery: Symbol A recovers, Symbol B remains stale. Blocker for Symbol A is removed, blocker for Symbol B remains.
4. Complete recovery: Both Symbol A and Symbol B recover. All blockers removed, portfolio has_indeterminate_valuation becomes False.
5. Coexistence of STALE_POSITION and INVALID_MARK: Clearing one does not clear the other.
6. PortfolioManager.reset() cleanly purges all active risk blockers.
7. Prefix clearing utility: clear_indeterminate_risk_reasons_by_prefix.
8. Backward compatibility: pm.has_indeterminate_valuation = True / False setters behave consistently.
9. Global feed outage detected with expected_timeline: Simultaneous drop marks GLOBAL_FEED_OUTAGE.
10. Global feed outage detected with expected_end_time.
11. Global feed outage recovery: Resumed candles clear GLOBAL_FEED_OUTAGE blocker.
12. Global feed outage at session end: Positions marked pending liquidation with locked margin; no synthetic fills.
13. Outage status metadata when expected timeline is omitted: LIMITED_TO_RECEIVED_UNION.
14. Both execution models (next_open and same_close) protect against global feed outage.
15. Full accounting reconciliation: Net P&L, cash, equity, and margin remain 100% consistent across outage.
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
    RiskReason,
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
# 1. Independent Risk Reason Ownership
# ============================================================================

def test_01_independent_risk_reasons_subsystem_isolation():
    """Verify Subsystem A adding a risk blocker cannot be cleared by Subsystem B."""
    pm = PortfolioManager(initial_capital=100_000.0)
    assert pm.has_indeterminate_valuation is False
    assert len(pm.active_risk_reasons) == 0

    # Subsystem A registers STALE_POSITION
    pm.add_indeterminate_risk_reason(
        f"{RiskReason.STALE_POSITION}:SYM_A",
        "SYM_A feed disconnected for 3 bars",
    )
    # Subsystem B registers GLOBAL_FEED_OUTAGE
    pm.add_indeterminate_risk_reason(
        RiskReason.GLOBAL_FEED_OUTAGE,
        "All data feeds disconnected simultaneously",
    )

    assert pm.has_indeterminate_valuation is True
    assert len(pm.active_risk_reasons) == 2
    assert f"{RiskReason.STALE_POSITION}:SYM_A" in pm.active_risk_reasons
    assert RiskReason.GLOBAL_FEED_OUTAGE in pm.active_risk_reasons

    # Subsystem A clears its blocker
    removed = pm.remove_indeterminate_risk_reason(f"{RiskReason.STALE_POSITION}:SYM_A")
    assert removed is True

    # Crucial assertion: Subsystem B's blocker MUST remain active!
    assert pm.has_indeterminate_valuation is True
    assert len(pm.active_risk_reasons) == 1
    assert RiskReason.GLOBAL_FEED_OUTAGE in pm.active_risk_reasons
    assert "All data feeds disconnected" in pm.indeterminate_valuation_reason


# ============================================================================
# 2. Multiple Symbols Stale & Partial Recovery
# ============================================================================

def test_02_multiple_symbols_stale_partial_recovery():
    """Verify Symbol A recovery clears only Symbol A blocker while Symbol B blocker remains."""
    pm = PortfolioManager(initial_capital=100_000.0)
    pm.add_indeterminate_risk_reason(f"{RiskReason.STALE_POSITION}:SYM_A", "SYM_A missing 4 bars")
    pm.add_indeterminate_risk_reason(f"{RiskReason.STALE_POSITION}:SYM_B", "SYM_B missing 5 bars")

    assert pm.has_indeterminate_valuation is True
    assert len(pm.active_risk_reasons) == 2

    # Symbol A recovers
    pm.remove_indeterminate_risk_reason(f"{RiskReason.STALE_POSITION}:SYM_A")

    # Valuation is STILL indeterminate due to Symbol B!
    assert pm.has_indeterminate_valuation is True
    assert len(pm.active_risk_reasons) == 1
    assert f"{RiskReason.STALE_POSITION}:SYM_B" in pm.active_risk_reasons
    assert "SYM_B missing 5 bars" in pm.indeterminate_valuation_reason

    # Attempt to open position must be rejected
    can_open, reason = pm.can_open_position("SYM_C", 100.0, 10)
    assert can_open is False
    assert "SYM_B missing 5 bars" in reason


# ============================================================================
# 3. Multiple Symbols Stale & Complete Recovery
# ============================================================================

def test_03_multiple_symbols_stale_complete_recovery():
    """Verify that only when ALL offending symbols recover does has_indeterminate_valuation clear."""
    pm = PortfolioManager(initial_capital=100_000.0)
    pm.add_indeterminate_risk_reason(f"{RiskReason.STALE_POSITION}:SYM_A", "SYM_A missing")
    pm.add_indeterminate_risk_reason(f"{RiskReason.STALE_POSITION}:SYM_B", "SYM_B missing")

    pm.remove_indeterminate_risk_reason(f"{RiskReason.STALE_POSITION}:SYM_A")
    assert pm.has_indeterminate_valuation is True

    pm.remove_indeterminate_risk_reason(f"{RiskReason.STALE_POSITION}:SYM_B")
    assert pm.has_indeterminate_valuation is False
    assert pm.indeterminate_valuation_reason is None
    assert len(pm.active_risk_reasons) == 0

    can_open, _ = pm.can_open_position("SYM_C", 100.0, 10)
    assert can_open is True


# ============================================================================
# 4. Coexistence of STALE_POSITION and INVALID_MARK
# ============================================================================

def test_04_coexistence_stale_and_invalid_mark():
    """Verify distinct risk reason types coexist and clear independently."""
    pm = PortfolioManager(initial_capital=100_000.0)
    pm.add_indeterminate_risk_reason(f"{RiskReason.STALE_POSITION}:SYM_A", "SYM_A stale")
    pm.add_indeterminate_risk_reason(f"{RiskReason.INVALID_MARK}:SYM_B", "SYM_B price <= 0")

    # Stale position clears
    pm.remove_indeterminate_risk_reason(f"{RiskReason.STALE_POSITION}:SYM_A")
    assert pm.has_indeterminate_valuation is True
    assert f"{RiskReason.INVALID_MARK}:SYM_B" in pm.active_risk_reasons
    assert "price <= 0" in pm.indeterminate_valuation_reason

    # Invalid mark clears
    pm.remove_indeterminate_risk_reason(f"{RiskReason.INVALID_MARK}:SYM_B")
    assert pm.has_indeterminate_valuation is False


# ============================================================================
# 5. Portfolio Reset Clears All Risk Reasons
# ============================================================================

def test_05_portfolio_reset_clears_all_risk_reasons():
    """Verify portfolio.reset() purges all active risk blockers."""
    pm = PortfolioManager(initial_capital=100_000.0)
    pm.add_indeterminate_risk_reason("REASON_1", "Desc 1")
    pm.add_indeterminate_risk_reason("REASON_2", "Desc 2")
    pm.add_indeterminate_risk_reason("REASON_3", "Desc 3")
    assert pm.has_indeterminate_valuation is True

    pm.reset()
    assert pm.has_indeterminate_valuation is False
    assert pm.indeterminate_valuation_reason is None
    assert len(pm.active_risk_reasons) == 0


# ============================================================================
# 6. Prefix Clearing Utility
# ============================================================================

def test_06_prefix_clearing_utility():
    """Verify clear_indeterminate_risk_reasons_by_prefix selectively clears matching keys."""
    pm = PortfolioManager(initial_capital=100_000.0)
    pm.add_indeterminate_risk_reason(f"{RiskReason.STALE_POSITION}:SYM_A", "Stale A")
    pm.add_indeterminate_risk_reason(f"{RiskReason.STALE_POSITION}:SYM_B", "Stale B")
    pm.add_indeterminate_risk_reason(RiskReason.GLOBAL_FEED_OUTAGE, "Global outage")

    removed = pm.clear_indeterminate_risk_reasons_by_prefix(f"{RiskReason.STALE_POSITION}:")
    assert removed == 2
    assert len(pm.active_risk_reasons) == 1
    assert RiskReason.GLOBAL_FEED_OUTAGE in pm.active_risk_reasons


# ============================================================================
# 7. Backward Compatibility Properties and Setters
# ============================================================================

def test_07_backward_compatible_properties_and_setters():
    """Verify legacy manual setters and getters remain 100% compatible."""
    pm = PortfolioManager(initial_capital=100_000.0)
    assert pm.has_indeterminate_valuation is False

    pm.has_indeterminate_valuation = True
    assert pm.has_indeterminate_valuation is True
    assert RiskReason.LEGACY_MANUAL in pm.active_risk_reasons

    pm.indeterminate_valuation_reason = "Manual test blocker"
    assert pm.indeterminate_valuation_reason == "Manual test blocker"

    pm.has_indeterminate_valuation = False
    assert pm.has_indeterminate_valuation is False
    assert pm.indeterminate_valuation_reason is None


# ============================================================================
# 8. Global Feed Outage Detected With Expected Timeline
# ============================================================================

def test_08_global_feed_outage_detected_with_expected_timeline():
    """
    Verify complete simultaneous feed outage is detected when expected_timeline is provided.
    Feeds for both SYM_A and SYM_B cut off at bar 2. Timeline continues through bar 7.
    """
    dates_all = pd.date_range("2026-03-30 09:25:00", periods=8, freq="1min")
    # Both symbols have data only for bars 0 and 1! (Cut off at bar 2)
    df_a = _make_bars(dates_all[:2], 100.0)
    df_b = _make_bars(dates_all[:2], 200.0)

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=20, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates_all[0], atr=2.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=200.0, stop_loss=150.0, target_price=300.0,
        requested_quantity=20, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates_all[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        execution_model="next_open",
        enforce_eod_square_off=False,
        opening_cooldown_minutes=0,
        expected_timeline=dates_all,  # Explicit master timeline!
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={"SYM_A": [opp_a, None], "SYM_B": [opp_b, None]},
        config=m_cfg,
    )

    assert res.expected_timeline_provided is True
    assert res.global_outage_detection_status == "ACTIVE"
    assert res.global_feed_outage_events >= 1
    assert RiskReason.GLOBAL_FEED_OUTAGE in res.active_risk_reasons
    assert len(res.unresolved_positions) == 2
    for pos in res.unresolved_positions:
        assert pos.is_stale is True
        assert pos.pending_liquidation is True
        assert pos.pending_liquidation_reason == "GLOBAL_FEED_OUTAGE"


# ============================================================================
# 9. Global Feed Outage Detected With Expected End Time
# ============================================================================

def test_09_global_feed_outage_detected_with_expected_end_time():
    """Verify complete simultaneous feed outage is detected when expected_end_time is provided."""
    dates_received = pd.date_range("2026-03-30 09:25:00", periods=2, freq="1min")
    expected_end = pd.Timestamp("2026-03-30 09:32:00")  # 8 minutes total

    df_a = _make_bars(dates_received, 100.0)
    df_b = _make_bars(dates_received, 200.0)

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=20, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates_received[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        execution_model="next_open",
        enforce_eod_square_off=False,
        opening_cooldown_minutes=0,
        expected_end_time=expected_end,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={"SYM_A": [opp_a, None], "SYM_B": [None, None]},
        config=m_cfg,
    )

    assert res.expected_timeline_provided is True
    assert res.global_feed_outage_events >= 1
    assert res.portfolio.has_indeterminate_valuation is True
    assert len(res.unresolved_positions) == 1
    assert res.unresolved_positions[0].symbol == "SYM_A"


# ============================================================================
# 10. Global Feed Outage Recovery
# ============================================================================

def test_10_global_feed_outage_recovery():
    """Verify that when data feeds resume after a global outage, GLOBAL_FEED_OUTAGE clears."""
    dates_all = pd.date_range("2026-03-30 09:25:00", periods=10, freq="1min")
    # Outage on bars 2, 3, 4, 5 (4 bars). Resumes on bars 6..9!
    df_a = _make_bars(dates_all, 100.0).drop(dates_all[2:6])
    df_b = _make_bars(dates_all, 200.0).drop(dates_all[2:6])

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=20, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates_all[0], atr=2.0,
    )
    # Signal for SYM_B at bar 6 (upon recovery!), enters bar 7
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=200.0, stop_loss=150.0, target_price=300.0,
        requested_quantity=20, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates_all[6], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        execution_model="next_open",
        enforce_eod_square_off=False,
        opening_cooldown_minutes=0,
        expected_timeline=dates_all,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [opp_a, None, None, None, None, None],
            "SYM_B": [None, None, opp_b, None, None, None],
        },
        config=m_cfg,
    )

    # During bars 4 and 5, global outage was active
    assert res.global_feed_outage_events >= 1
    # Upon bar 6 arrival, outage cleared!
    assert RiskReason.GLOBAL_FEED_OUTAGE not in res.portfolio.active_risk_reasons
    assert res.portfolio.has_indeterminate_valuation is False
    # opp_b was accepted and executed!
    b_allocs = [a for a in res.allocations if a.symbol == "SYM_B" and a.accepted]
    assert len(b_allocs) == 1
    assert len(res.trades) == 2


# ============================================================================
# 11. Global Feed Outage Session End & Unresolved Positions
# ============================================================================

def test_11_global_feed_outage_session_end_unresolved_positions():
    """Verify that feeds cutting off through session end leave margin strictly locked without fake fills."""
    dates_all = pd.date_range("2026-03-30 09:25:00", periods=8, freq="1min")
    df_a = _make_bars(dates_all[:2], 100.0)

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates_all[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        execution_model="next_open",
        opening_cooldown_minutes=0,
        expected_timeline=dates_all,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a},
        signals_by_symbol={"SYM_A": [opp_a, None]},
        config=m_cfg,
    )

    assert len(res.trades) == 0  # No fake fill!
    assert len(res.unresolved_positions) == 1
    pos = res.unresolved_positions[0]
    assert pos.symbol == "SYM_A"
    assert pos.pending_liquidation is True
    assert pos.pending_liquidation_reason == "GLOBAL_FEED_OUTAGE"
    assert res.portfolio.allocated_margin == (100.0 * 50) / 5.0  # Margin stays locked


# ============================================================================
# 12. Outage Status Without Expected Timeline (Documentation Limitation)
# ============================================================================

def test_12_outage_status_without_expected_timeline():
    """Verify result explicitly documents limited outage detection when expected timeline is omitted."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a = _make_bars(dates, 100.0)

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        opening_cooldown_minutes=0,
        # Neither expected_timeline nor expected_end_time provided
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a},
        signals_by_symbol={"SYM_A": [None] * 5},
        config=m_cfg,
    )

    assert res.expected_timeline_provided is False
    assert res.global_outage_detection_status == "LIMITED_TO_RECEIVED_UNION"


# ============================================================================
# 13. Both Execution Models Protect Against Global Outage
# ============================================================================

@pytest.mark.parametrize("model", ["next_open", "same_close"])
def test_13_both_execution_models_protect_against_global_outage(model: str):
    """Verify both next_open and same_close models block new entries during a global feed outage."""
    dates_all = pd.date_range("2026-03-30 09:25:00", periods=8, freq="1min")
    df_a = _make_bars(dates_all[:2], 100.0)
    df_b = _make_bars(dates_all, 200.0)  # SYM_B tries to enter during outage

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=20, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates_all[0], atr=2.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=200.0, stop_loss=150.0, target_price=300.0,
        requested_quantity=20, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates_all[5], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        execution_model=model,
        opening_cooldown_minutes=0,
        expected_timeline=dates_all,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [opp_a, None],
            "SYM_B": [None, None, None, None, None, opp_b, None, None],
        },
        config=m_cfg,
    )

    # SYM_B is blocked because SYM_A is in a prolonged missing state (indeterminate valuation)
    assert not any(a.symbol == "SYM_B" and a.accepted for a in res.allocations)


# ============================================================================
# 14. Full Accounting Reconciliation Across Outage
# ============================================================================

def test_14_accounting_invariants_across_global_feed_outage():
    """Verify equity, cash, and margin identities hold exactly across global feed outage transitions."""
    dates_all = pd.date_range("2026-03-30 09:25:00", periods=10, freq="1min")
    # SYM_A opens bar 1, outage bars 2..5, resumes bar 6, exits on target at bar 7
    df_a = _make_bars(dates_all, 100.0).drop(dates_all[2:6])
    df_a.loc[dates_all[7], ["Open", "High", "Low", "Close"]] = 150.0

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=150.0,
        requested_quantity=50, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates_all[0], atr=2.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_consecutive_missing_bars=3,
        execution_model="next_open",
        opening_cooldown_minutes=0,
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
        expected_timeline=dates_all,
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

    # Invariants
    assert pytest.approx(t.net_pnl, abs=1e-2) == t.gross_pnl - t.transaction_cost
    assert pytest.approx(res.portfolio.cash, abs=1e-2) == 100_000.0 + t.net_pnl
    assert pytest.approx(res.portfolio.equity, abs=1e-2) == res.portfolio.cash
    assert res.portfolio.allocated_margin == 0.0
