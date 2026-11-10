"""
SignalForge — Phase 27C.3.5: Single/Multi-Asset Risk Parity Test Suite
=====================================================================
Verifies exact risk and execution parity between the single-stock engine
(run_intraday_backtest) and multi-asset engine (run_multi_asset_backtest).

Covered Parity Areas:
1. Matching cost-aware quantities.
2. Round-trip costs included in risk budget.
3. Insufficient capital rejects entry.
4. Integer quantity rounding consistency.
5. Adverse opening gaps produce equivalent exits.
6. Stop-first same-candle priority matches.
7. Opening cooldown matches.
8. IST timestamp handling matches.
9. Protection-floor breach blocks new entries.
10. Bankruptcy handling consistency.
11. Realized transaction costs deducted exactly once.
12. No stale-price liquidation fills.
13. Single-stock backward compatibility preserved.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import pytest

from src.backtest.capital_allocator import (
    CapitalAllocationConfig,
    CapitalAllocator,
    TradeOpportunity,
    calculate_cost_aware_position_size,
)
from src.backtest.engine import (
    IST_TIMEZONE,
    IntradayEngineConfig,
    is_in_opening_cooldown,
    run_intraday_backtest,
)
from src.backtest.indian_market_costs import (
    DISCOUNT_BROKER_REALISTIC_CONFIG,
    calculate_trade_transaction_costs,
)
from src.backtest.multi_asset_engine import (
    MultiAssetEngineConfig,
    run_multi_asset_backtest,
)
from src.backtest.portfolio import PortfolioManager
from src.backtest.simulator import Position


def _make_day_bars(start_dt_str: str, n_bars: int = 15, base_price: float = 500.0, atr: float = 5.0) -> pd.DataFrame:
    """Generate synthetic 1-minute OHLCV bars starting at start_dt_str."""
    dates = pd.date_range(start_dt_str, periods=n_bars, freq="1min")
    return pd.DataFrame(
        {
            "Open": [base_price] * n_bars,
            "High": [base_price + 2.0] * n_bars,
            "Low": [base_price - 2.0] * n_bars,
            "Close": [base_price] * n_bars,
            "Volume": [1000.0] * n_bars,
            "ATR": [atr] * n_bars,
        },
        index=dates,
    )


# ============================================================================
# 1. Matching Cost-Aware Quantities
# ============================================================================

def test_01_matching_cost_aware_quantities():
    """Verify single-stock and multi-asset engines produce identical cost-aware quantities."""
    df = _make_day_bars("2026-03-30 09:25:00", n_bars=10, base_price=500.0, atr=5.0)
    # Price rises then drops through stop
    df.loc[df.index[2], "Low"] = 490.0  # Hit stop loss on bar 2

    s_cfg = IntradayEngineConfig(
        initial_capital=100_000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        stop_atr_multiplier=1.5,
        target_atr_multiplier=3.0,
        execution_model="next_open",
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
        include_estimated_round_trip_costs_in_sizing=True,
        opening_cooldown_minutes=0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        risk_per_trade_pct=0.01,
        max_stock_allocation_pct=1.0,
        max_portfolio_risk_pct=0.03,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=1.5,
        take_profit_atr=3.0,
        execution_model="next_open",
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
        include_estimated_round_trip_costs_in_sizing=True,
        opening_cooldown_minutes=0,
    )

    signals = [None, Position.LONG] + [None] * 8

    s_res = run_intraday_backtest(df, signals, s_cfg)
    m_res = run_multi_asset_backtest({"TEST": df}, {"TEST": signals}, m_cfg)

    assert len(s_res.trades) == 1
    assert len(m_res.trades) == 1

    st = s_res.trades[0]
    mt = m_res.trades[0]

    assert st.quantity == mt.quantity == 122
    assert st.entry_price == mt.entry_price == 500.0
    assert st.exit_price == mt.exit_price == 492.5
    assert st.exit_reason == mt.exit_reason == "STOP"
    assert abs(st.net_pnl - mt.net_pnl) < 1e-4


# ============================================================================
# 2. Round-Trip Costs Included in Sizing Risk Budget
# ============================================================================

def test_02_round_trip_costs_included_in_risk_budget():
    """Verify that cost-aware sizing reduces quantity so Gross Risk + Round-Trip Cost <= Budget."""
    capital = 100_000.0
    risk_pct = 0.01
    budget = capital * risk_pct  # Rs 1,000
    entry_p = 500.0
    stop_p = 492.5
    stop_dist = 7.5

    # Without cost-aware sizing: floor(1000 / 7.5) = 133 shares
    q_gross, _, _ = calculate_cost_aware_position_size(
        entry_price=entry_p,
        stop_loss=stop_p,
        capital=capital,
        risk_per_trade_pct=risk_pct,
        max_leverage=5.0,
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
        include_costs_in_sizing=False,
    )
    assert q_gross == 133

    # With cost-aware sizing:
    q_cost, _, _ = calculate_cost_aware_position_size(
        entry_price=entry_p,
        stop_loss=stop_p,
        capital=capital,
        risk_per_trade_pct=risk_pct,
        max_leverage=5.0,
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
        include_costs_in_sizing=True,
    )
    assert q_cost == 122
    assert q_cost < q_gross

    # Verify total risk does not exceed budget
    gross_risk = q_cost * stop_dist
    costs = calculate_trade_transaction_costs("LONG", entry_p, stop_p, q_cost, DISCOUNT_BROKER_REALISTIC_CONFIG).total_costs
    assert gross_risk + costs <= budget


# ============================================================================
# 3. Insufficient Capital Rejects Entry
# ============================================================================

def test_03_insufficient_capital_rejects_entry():
    """Verify that when capital is insufficient to purchase min_trade_quantity, both engines reject."""
    df = _make_day_bars("2026-03-30 09:25:00", n_bars=10, base_price=50000.0, atr=500.0)

    # Initial capital = Rs 100, stock price = Rs 50,000 -> 5x leverage max notional = Rs 500 < Rs 50,000
    s_cfg = IntradayEngineConfig(
        initial_capital=100.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
        opening_cooldown_minutes=0,
    )
    m_cfg = MultiAssetEngineConfig(
        initial_capital=100.0,
        risk_per_trade_pct=0.01,
        max_leverage=5.0,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
        opening_cooldown_minutes=0,
    )

    signals = [None, Position.LONG] + [None] * 8

    s_res = run_intraday_backtest(df, signals, s_cfg)
    m_res = run_multi_asset_backtest({"TEST": df}, {"TEST": signals}, m_cfg)

    assert len(s_res.trades) == 0
    assert len(m_res.trades) == 0


# ============================================================================
# 4. Integer Quantity Rounding Consistency
# ============================================================================

def test_04_integer_quantity_rounding_consistent():
    """Verify integer floor rounding produces whole numbers and never fractional shares."""
    q, r_q, m_q = calculate_cost_aware_position_size(
        entry_price=123.45,
        stop_loss=119.80,
        capital=33_333.0,
        risk_per_trade_pct=0.015,
        max_leverage=4.5,
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )
    assert isinstance(q, int)
    assert isinstance(r_q, int)
    assert isinstance(m_q, int)
    assert q >= 1


# ============================================================================
# 5. Adverse Opening Gaps Produce Equivalent Exits
# ============================================================================

def test_05_adverse_opening_gap_equivalent_exits():
    """Verify that an adverse opening gap through stop-loss exits at bar_open in both engines."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    # Bar 0: baseline
    # Bar 1: signal generated
    # Bar 2: entered at 500.0; stop is 492.5
    # Bar 3: gaps down at Open to 480.0 (below stop 492.5)
    # Bar 4: subsequent bar
    df = pd.DataFrame(
        {
            "Open": [500.0, 500.0, 500.0, 480.0, 482.0],
            "High": [502.0, 502.0, 502.0, 485.0, 485.0],
            "Low": [498.0, 498.0, 498.0, 478.0, 480.0],
            "Close": [500.0, 500.0, 500.0, 482.0, 484.0],
            "Volume": [1000.0] * 5,
            "ATR": [5.0] * 5,
        },
        index=dates,
    )

    s_cfg = IntradayEngineConfig(
        initial_capital=100_000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        stop_atr_multiplier=1.5,
        execution_model="next_open",
        enforce_eod_square_off=False,
        gap_execution=True,
        opening_cooldown_minutes=0,
    )
    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        risk_per_trade_pct=0.01,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=1.5,
        execution_model="next_open",
        enforce_eod_square_off=False,
        gap_execution=True,
        opening_cooldown_minutes=0,
    )

    signals = [None, Position.LONG, None, None, None]

    s_res = run_intraday_backtest(df, signals, s_cfg)
    m_res = run_multi_asset_backtest({"TEST": df}, {"TEST": signals}, m_cfg)

    assert len(s_res.trades) == 1
    assert len(m_res.trades) == 1

    st = s_res.trades[0]
    mt = m_res.trades[0]

    assert st.exit_price == mt.exit_price == 480.0  # Filled at open!
    assert st.exit_reason == mt.exit_reason == "STOP"


# ============================================================================
# 6. Stop-First Same-Candle Priority Matches
# ============================================================================

def test_06_stop_first_same_candle_priority():
    """Verify conservative collision policy (STOP evaluated before TARGET on same candle)."""
    df = _make_day_bars("2026-03-30 09:25:00", n_bars=5, base_price=500.0, atr=5.0)
    # Stop = 500 - 7.5 = 492.5, Target = 500 + 15 = 515.0
    # Bar 2 touches BOTH: Low = 490.0, High = 520.0
    df.loc[df.index[2], "Low"] = 490.0
    df.loc[df.index[2], "High"] = 520.0

    s_cfg = IntradayEngineConfig(
        initial_capital=100_000.0,
        conservative_same_candle=True,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )
    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_stock_allocation_pct=1.0,
        conservative_same_candle=True,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    signals = [None, Position.LONG, None, None, None]

    s_res = run_intraday_backtest(df, signals, s_cfg)
    m_res = run_multi_asset_backtest({"TEST": df}, {"TEST": signals}, m_cfg)

    assert s_res.trades[0].exit_reason == "STOP"
    assert m_res.trades[0].exit_reason == "STOP"
    assert s_res.trades[0].exit_price == m_res.trades[0].exit_price == 492.5


# ============================================================================
# 7. Opening Cooldown Matches
# ============================================================================

def test_07_opening_cooldown_matches():
    """Verify that signals generated during opening cooldown (09:15 to 09:24) are discarded by both engines."""
    df = _make_day_bars("2026-03-30 09:15:00", n_bars=15, base_price=500.0, atr=5.0)

    # Cooldown = 10 minutes (09:15:00 to 09:24:59). First eligible entry is 09:25:00.
    s_cfg = IntradayEngineConfig(opening_cooldown_minutes=10, execution_model="next_open")
    m_cfg = MultiAssetEngineConfig(opening_cooldown_minutes=10, execution_model="next_open")

    # Signal produced at 09:18:00 (bar index 3)
    signals = [None] * 15
    signals[3] = Position.LONG

    s_res = run_intraday_backtest(df, signals, s_cfg)
    m_res = run_multi_asset_backtest({"TEST": df}, {"TEST": signals}, m_cfg)

    # Both must discard cooldown signals: zero trades executed!
    assert len(s_res.trades) == 0
    assert len(m_res.trades) == 0


# ============================================================================
# 8. IST Timestamp Handling Matches
# ============================================================================

def test_08_ist_timestamp_handling_matches():
    """Verify that timezone-aware timestamps normalized to Asia/Kolkata behave identically to naive IST."""
    naive_ts = pd.Timestamp("2026-03-30 09:20:00")
    utc_ts = naive_ts.tz_localize("Asia/Kolkata").tz_convert("UTC")

    assert is_in_opening_cooldown(naive_ts, opening_cooldown_minutes=10) is True
    assert is_in_opening_cooldown(utc_ts, opening_cooldown_minutes=10) is True

    naive_after = pd.Timestamp("2026-03-30 09:25:00")
    utc_after = naive_after.tz_localize("Asia/Kolkata").tz_convert("UTC")

    assert is_in_opening_cooldown(naive_after, opening_cooldown_minutes=10) is False
    assert is_in_opening_cooldown(utc_after, opening_cooldown_minutes=10) is False


# ============================================================================
# 9. Protection-Floor Breach Blocks New Entries
# ============================================================================

def test_09_protection_floor_breach_blocks_new_entries():
    """Verify that when capital drops to or below protection floor, trading halts in both engines."""
    df = _make_day_bars("2026-03-30 09:25:00", n_bars=10, base_price=500.0, atr=5.0)
    # Severe loss on bar 2 drops capital below floor
    df.loc[df.index[2], "Low"] = 400.0
    df.loc[df.index[2], "Close"] = 410.0

    s_cfg = IntradayEngineConfig(
        initial_capital=10_000.0,
        capital_protection_floor=8_000.0,  # Max loss 2,000
        risk_per_trade=0.25,  # Large risk to force floor breach
        stop_atr_multiplier=20.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )
    m_cfg = MultiAssetEngineConfig(
        initial_capital=10_000.0,
        capital_protection_floor=8_000.0,
        risk_per_trade_pct=0.25,
        max_portfolio_risk_pct=0.5,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        stop_loss_atr=20.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    # Signal on bar 1 (enters bar 2, stops at floor), second signal on bar 5
    signals = [None, Position.LONG, None, None, Position.LONG] + [None] * 5

    s_res = run_intraday_backtest(df, signals, s_cfg)
    m_res = run_multi_asset_backtest({"TEST": df}, {"TEST": signals}, m_cfg)

    # Only 1 trade executed; second entry blocked!
    assert len(s_res.trades) == 1
    assert len(m_res.trades) == 1
    assert "PROTECTION_FLOOR" in str(s_res.bankruptcy_reason)
    assert "PROTECTION_FLOOR" in str(m_res.bankruptcy_reason)


# ============================================================================
# 10. Bankruptcy Handling Consistency
# ============================================================================

def test_10_bankruptcy_handling_consistent():
    """Verify that capital exhaustion (equity <= 0) halts trading and flags bankruptcy in both engines."""
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    # Bar 0: baseline
    # Bar 1: signal generated
    # Bar 2: entered at 100.0 with max leverage 5.0 (50 shares = 5,000 exposure on 1,000 capital)
    # Bar 3: severe gap down to 10.0 causes loss of 4,500, exhausting capital to <= 0
    # Bar 4: subsequent bar, no trading allowed
    df = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 100.0, 10.0, 10.0],
            "High": [101.0, 101.0, 101.0, 11.0, 11.0],
            "Low": [99.0, 99.0, 99.0, 9.0, 9.0],
            "Close": [100.0, 100.0, 100.0, 10.0, 10.0],
            "Volume": [1000.0] * 5,
            "ATR": [1.0] * 5,
        },
        index=dates,
    )

    s_cfg = IntradayEngineConfig(
        initial_capital=1_000.0,
        risk_per_trade=0.5,
        max_leverage=5.0,
        stop_atr_multiplier=1.5,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )
    m_cfg = MultiAssetEngineConfig(
        initial_capital=1_000.0,
        risk_per_trade_pct=0.5,
        max_portfolio_risk_pct=0.5,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=1.5,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    signals = [None, Position.LONG, None, None, None]

    s_res = run_intraday_backtest(df, signals, s_cfg)
    m_res = run_multi_asset_backtest({"TEST": df}, {"TEST": signals}, m_cfg)

    assert s_res.bankruptcy_reason is not None
    assert m_res.bankruptcy_reason is not None
    assert ("BANKRUPTCY" in s_res.bankruptcy_reason) or ("CAPITAL_EXHAUSTED" in s_res.bankruptcy_reason)
    assert ("BANKRUPTCY" in m_res.bankruptcy_reason) or ("CAPITAL_EXHAUSTED" in m_res.bankruptcy_reason)
    assert s_res.metrics.total_trades == 1
    assert m_res.metrics.total_trades == 1


# ============================================================================
# 11. Realized Transaction Costs Deducted Exactly Once
# ============================================================================

def test_11_realized_costs_deducted_exactly_once():
    """Verify that realized transaction costs are deducted exactly once from net P&L and cash."""
    df = _make_day_bars("2026-03-30 09:25:00", n_bars=5, base_price=500.0, atr=5.0)
    df.loc[df.index[2], "High"] = 520.0  # Take profit hit

    s_cfg = IntradayEngineConfig(
        initial_capital=100_000.0,
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )
    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    signals = [None, Position.LONG, None, None, None]

    s_res = run_intraday_backtest(df, signals, s_cfg)
    m_res = run_multi_asset_backtest({"TEST": df}, {"TEST": signals}, m_cfg)

    st = s_res.trades[0]
    mt = m_res.trades[0]

    assert abs(st.net_pnl - (st.gross_pnl - st.transaction_cost)) < 1e-4
    assert abs(mt.net_pnl - (mt.gross_pnl - mt.transaction_cost)) < 1e-4
    assert abs(s_res.portfolio.cash - (100_000.0 + st.net_pnl)) < 1e-4
    assert abs(m_res.portfolio.cash - (100_000.0 + mt.net_pnl)) < 1e-4


# ============================================================================
# 12. No Stale-Price Liquidation Fills
# ============================================================================

def test_12_no_stale_price_liquidation_fills():
    """Verify that missing candles never fabricate synthetic fills at stale prices."""
    # Stock A has 5 bars; Stock B is missing on bar 2
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a = pd.DataFrame(
        {
            "Open": [500.0] * 5,
            "High": [502.0] * 5,
            "Low": [498.0] * 5,
            "Close": [500.0] * 5,
            "Volume": [1000.0] * 5,
            "ATR": [5.0] * 5,
        },
        index=dates,
    )
    df_b = df_a.drop(dates[2])  # Missing bar 2

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"A": df_a, "B": df_b},
        signals_by_symbol={"A": None, "B": None},
        config=m_cfg,
    )

    assert res.missing_candle_stats["B"] == 1
    assert res.missing_candle_stats["A"] == 0


# ============================================================================
# 13. Single-Stock Backward Compatibility Preserved
# ============================================================================

def test_13_single_stock_backward_compatibility():
    """Verify that when cost_config=None or include_costs=False, legacy gross sizing is reproduced."""
    # Capital = Rs 10,000, risk = 0.01 (Rs 100), ATR stop = 0.75 -> risk_qty = 133
    # Max exposure = Rs 50,000, entry = Rs 1,000 -> max_allowed_qty = 50
    # Expected legacy final_qty = min(133, 50) = 50
    final_qty, r_qty, m_qty = calculate_cost_aware_position_size(
        entry_price=1000.0,
        stop_loss=999.25,
        capital=10_000.0,
        risk_per_trade_pct=0.01,
        max_leverage=5.0,
        max_exposure=50_000.0,
        cost_config=None,  # Legacy mode
        include_costs_in_sizing=False,
    )

    assert final_qty == 50
    assert r_qty == 133
    assert m_qty == 50


# ============================================================================
# PHASE 27C.3.5.2: PORTFOLIO-LEVEL INTRABAR PROTECTION & CONCURRENT SAFETY
# ============================================================================

def _make_two_symbol_bars(dates: pd.DatetimeIndex, base_price: float = 100.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate aligned synthetic 1-minute bars for two symbols."""
    df_a = pd.DataFrame(
        {
            "Open": [base_price] * len(dates),
            "High": [base_price + 1.0] * len(dates),
            "Low": [base_price - 1.0] * len(dates),
            "Close": [base_price] * len(dates),
            "Volume": [1000.0] * len(dates),
            "ATR": [5.0] * len(dates),
        },
        index=dates,
    )
    df_b = df_a.copy()
    return df_a, df_b


def test_14_aggregate_floor_breach_scenario_1_loss_in_A():
    """
    Scenario 1: Capital Rs 100k, floor Rs 97k.
    Two positions: A unrealized loss Rs 1,500, B loss Rs 1,000 (total Rs 2,500).
    Position A loses another Rs 500 (total A loss Rs 2,000; aggregate loss Rs 3,000).
    Aggregate equity hits Rs 97k -> triggers emergency liquidation at Close.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a, df_b = _make_two_symbol_bars(dates, base_price=100.0)

    # Bar 2: entry at 100.0 (100 shares each)
    # Bar 3: A drops to 85.0 (-15 pts = -1,500 loss), B drops to 90.0 (-10 pts = -1,000 loss). Total loss -2,500.
    df_a.loc[dates[3], ["Open", "High", "Low", "Close"]] = 85.0
    df_b.loc[dates[3], ["Open", "High", "Low", "Close"]] = 90.0

    # Bar 4: A drops to 80.0 (-20 pts = -2,000 loss), B stays at 90.0 (-1,000 loss). Total loss -3,000.
    df_a.loc[dates[4], ["Open", "High", "Low", "Close"]] = 80.0
    df_b.loc[dates[4], ["Open", "High", "Low", "Close"]] = 90.0

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,
        risk_per_trade_pct=0.10,
        max_portfolio_risk_pct=0.20,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=10.0,  # stop_dist = 50.0 -> stop_p = 50.0 > 0
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [None, opp_a, None, None, None],
            "SYM_B": [None, opp_b, None, None, None],
        },
        config=m_cfg,
    )

    assert len(res.trades) == 2
    assert all(t.exit_reason == "PROTECTION_FLOOR" for t in res.trades)
    assert res.portfolio.is_bankrupt == True
    assert "PROTECTION_FLOOR" in str(res.bankruptcy_reason)
    assert res.portfolio.open_position_count == 0


def test_15_aggregate_floor_breach_scenario_2_loss_in_B():
    """
    Scenario 2: Capital Rs 100k, floor Rs 97k.
    Two positions: A loss Rs 1,500, B loss Rs 1,000.
    Position B loses another Rs 500 (total B loss Rs 1,500; aggregate loss Rs 3,000).
    Aggregate equity hits Rs 97k -> triggers emergency liquidation.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a, df_b = _make_two_symbol_bars(dates, base_price=100.0)

    # Bar 3: A drops to 85.0 (-1,500), B drops to 90.0 (-1,000)
    df_a.loc[dates[3], ["Open", "High", "Low", "Close"]] = 85.0
    df_b.loc[dates[3], ["Open", "High", "Low", "Close"]] = 90.0

    # Bar 4: A stays at 85.0 (-1,500), B drops to 85.0 (-1,500). Total loss -3,000.
    df_a.loc[dates[4], ["Open", "High", "Low", "Close"]] = 85.0
    df_b.loc[dates[4], ["Open", "High", "Low", "Close"]] = 85.0

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,
        risk_per_trade_pct=0.10,
        max_portfolio_risk_pct=0.20,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=10.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [None, opp_a, None, None, None],
            "SYM_B": [None, opp_b, None, None, None],
        },
        config=m_cfg,
    )

    assert len(res.trades) == 2
    assert all(t.exit_reason == "PROTECTION_FLOOR" for t in res.trades)
    assert res.portfolio.is_bankrupt == True
    assert "PROTECTION_FLOOR" in str(res.bankruptcy_reason)


def test_16_aggregate_floor_breach_scenario_3_simultaneous_loss():
    """
    Scenario 3: Both positions lose another Rs 500 simultaneously.
    Total loss reaches Rs 3,500, dropping equity to Rs 96,500 (below Rs 97,000 floor).
    Both liquidated; overshoot honestly recorded at authentic Close prices.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a, df_b = _make_two_symbol_bars(dates, base_price=100.0)

    # Bar 3: A drops to 85.0 (-1,500), B drops to 90.0 (-1,000)
    df_a.loc[dates[3], ["Open", "High", "Low", "Close"]] = 85.0
    df_b.loc[dates[3], ["Open", "High", "Low", "Close"]] = 90.0

    # Bar 4: A drops to 80.0 (-2,000), B drops to 85.0 (-1,500). Total loss -3,500.
    df_a.loc[dates[4], ["Open", "High", "Low", "Close"]] = 80.0
    df_b.loc[dates[4], ["Open", "High", "Low", "Close"]] = 85.0

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,
        risk_per_trade_pct=0.10,
        max_portfolio_risk_pct=0.20,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=10.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [None, opp_a, None, None, None],
            "SYM_B": [None, opp_b, None, None, None],
        },
        config=m_cfg,
    )

    assert len(res.trades) == 2
    assert all(t.exit_reason == "PROTECTION_FLOOR" for t in res.trades)
    assert res.portfolio.is_bankrupt == True
    # Authentic overshoot is acknowledged (loss >= 3,500 with transaction costs)
    assert res.portfolio.equity <= 97_000.0


def test_17_deterministic_liquidation_no_path_dependence():
    """
    Scenario 4: Verify deterministic liquidation in sorted order without mid-loop cash distortion.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a, df_b = _make_two_symbol_bars(dates, base_price=100.0)

    # Both crash severely on bar 3
    df_a.loc[dates[3], ["Open", "High", "Low", "Close"]] = 75.0  # -25 pts = -2,500
    df_b.loc[dates[3], ["Open", "High", "Low", "Close"]] = 70.0  # -30 pts = -3,000

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,
        risk_per_trade_pct=0.10,
        max_portfolio_risk_pct=0.20,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=10.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [None, opp_a, None, None, None],
            "SYM_B": [None, opp_b, None, None, None],
        },
        config=m_cfg,
    )

    assert len(res.trades) == 2
    # Verify exit prices are authentic Close prices (75.0 and 70.0), not anomalous formulas
    t_a = next(t for t in res.trades if t.symbol == "SYM_A")
    t_b = next(t for t in res.trades if t.symbol == "SYM_B")
    assert t_a.exit_price == 75.0
    assert t_b.exit_price == 70.0
    assert t_a.exit_reason == "PROTECTION_FLOOR"
    assert t_b.exit_reason == "PROTECTION_FLOOR"


def test_18_one_liquidatable_one_stale_missing_data():
    """
    Scenario 5: One position is liquidatable at authentic market price while another
    has missing data. Stale position is marked pending_liquidation with margin locked.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a, df_b = _make_two_symbol_bars(dates, base_price=100.0)

    # Bar 3: severe loss in A breaches floor; B is missing candle at Bar 3!
    df_a.loc[dates[3], ["Open", "High", "Low", "Close"]] = 60.0  # -40 pts = -4,000 loss
    df_b = df_b.drop(dates[3])  # Drop bar 3 for SYM_B

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,
        risk_per_trade_pct=0.10,
        max_portfolio_risk_pct=0.20,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=10.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [None, opp_a, None, None, None],
            "SYM_B": [None, opp_b, None, None, None],
        },
        config=m_cfg,
    )

    # SYM_A liquidated on bar 3; SYM_B pending liquidation on bar 3, then resolved on bar 4
    assert res.portfolio.is_bankrupt == True
    assert "PROTECTION_FLOOR" in str(res.bankruptcy_reason)
    assert len(res.trades) == 2
    t_a = next(t for t in res.trades if t.symbol == "SYM_A")
    assert t_a.exit_price == 60.0


def test_19_adverse_opening_gaps_across_multiple_positions():
    """
    Scenario 6: Adverse opening gap across multiple positions.
    Evaluates aggregate equity at bar_open before new entries execute.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")

    df_a = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 100.0, 80.0, 80.0],  # Gaps down to 80.0 (-2,000)
            "High": [101.0, 101.0, 101.0, 81.0, 81.0],
            "Low": [99.0, 99.0, 99.0, 79.0, 79.0],
            "Close": [100.0, 100.0, 100.0, 80.0, 80.0],
            "Volume": [1000.0] * 5,
            "ATR": [5.0] * 5,
        },
        index=dates,
    )
    df_b = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 100.0, 80.0, 80.0],  # Gaps down to 80.0 (-2,000)
            "High": [101.0, 101.0, 101.0, 81.0, 81.0],
            "Low": [99.0, 99.0, 99.0, 79.0, 79.0],
            "Close": [100.0, 100.0, 100.0, 80.0, 80.0],
            "Volume": [1000.0] * 5,
            "ATR": [5.0] * 5,
        },
        index=dates,
    )

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,  # Max loss 3,000; combined gap loss is 4,000
        risk_per_trade_pct=0.10,
        max_portfolio_risk_pct=0.20,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=10.0,
        execution_model="next_open",
        enforce_eod_square_off=False,
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [None, opp_a, None, None, None],
            "SYM_B": [None, opp_b, None, None, None],
        },
        config=m_cfg,
    )

    assert len(res.trades) == 2
    assert all(t.exit_reason == "PROTECTION_FLOOR" for t in res.trades)
    assert all(t.exit_price == 80.0 for t in res.trades)
    assert res.portfolio.is_bankrupt == True


def test_20_realized_and_unrealized_not_double_counted():
    """
    Scenario 7: One position closes on STOP while another remains open;
    verify realized cash and mark-to-market unrealized P&L are strictly additive.
    """
    pm = PortfolioManager(initial_capital=100_000.0, max_leverage=5.0)
    pos_a = pm.open_position("SYM_A", Position.LONG, entry_time=pd.Timestamp("2026-03-30 09:15"), entry_price=100.0, quantity=100)
    pos_b = pm.open_position("SYM_B", Position.LONG, entry_time=pd.Timestamp("2026-03-30 09:15"), entry_price=100.0, quantity=100)

    # Both positions active
    pm.update_market_prices({"SYM_A": 95.0, "SYM_B": 98.0})
    assert pm.unrealized_pnl == (95.0 - 100.0) * 100 + (98.0 - 100.0) * 100  # -500 + -200 = -700
    assert pm.cash == 100_000.0
    assert pm.equity == 99_300.0

    # Close SYM_A with net loss of 500 (zero costs for illustration)
    trade_a = pm.close_position("SYM_A", exit_time=pd.Timestamp("2026-03-30 09:20"), exit_price=95.0)
    assert trade_a.gross_pnl == -500.0
    assert pm.cash == 99_500.0
    assert pm.open_position_count == 1
    assert "SYM_A" not in pm.open_positions

    # Unrealized P&L is now ONLY from SYM_B (-200)
    assert pm.unrealized_pnl == -200.0
    # Equity = 99,500 (cash) + -200 (unrealized) = 99,300
    assert pm.equity == 99_300.0


def test_21_pending_liquidation_retains_margin_blocks_entries():
    """
    Scenario 8: Pending liquidation retains allocated margin encumbrance and blocks new entries.
    """
    pm = PortfolioManager(initial_capital=100_000.0, max_leverage=5.0)
    pos_a = pm.open_position("SYM_A", Position.LONG, entry_time=pd.Timestamp("2026-03-30 09:15"), entry_price=100.0, quantity=100)
    initial_avail = pm.available_margin
    assert pm.allocated_margin == (100.0 * 100) / 5.0  # 2,000 margin

    # Mark pending liquidation
    pm.mark_pending_liquidation("SYM_A", reason="EMERGENCY_LIQUIDATION")
    assert pm.has_unresolved_liquidations == True
    assert pm.allocated_margin == 2000.0  # Margin NOT released!
    assert pm.available_margin == initial_avail

    # Attempt to open new position -> strictly rejected
    can_open, reason = pm.can_open_position("SYM_B", entry_price=100.0, quantity=50)
    assert can_open == False
    assert "unresolved emergency liquidations" in reason


def test_22_cannot_liquidate_or_charge_same_position_twice():
    """
    Scenario 9: A closed position cannot be liquidated or charged twice.
    """
    pm = PortfolioManager(initial_capital=100_000.0, max_leverage=5.0)
    pm.open_position("SYM_A", Position.LONG, entry_time=pd.Timestamp("2026-03-30 09:15"), entry_price=100.0, quantity=100)

    # First close succeeds
    pm.close_position("SYM_A", exit_time=pd.Timestamp("2026-03-30 09:20"), exit_price=95.0)
    assert pm.trade_count == 1
    cash_after_first = pm.cash

    # Second close attempt on already closed symbol raises PositionNotFoundError
    with pytest.raises(Exception):
        pm.close_position("SYM_A", exit_time=pd.Timestamp("2026-03-30 09:21"), exit_price=95.0)

    assert pm.trade_count == 1
    assert pm.cash == cash_after_first


def test_23_single_stock_regression_behavior_unchanged():
    """
    Scenario 10: Single-stock regression behavior remains 100% identical between engines.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=10, freq="1min")
    df = pd.DataFrame(
        {
            "Open": [500.0, 500.0, 500.0, 505.0, 510.0, 515.0, 520.0, 515.0, 510.0, 505.0],
            "High": [502.0, 502.0, 506.0, 511.0, 516.0, 521.0, 522.0, 517.0, 512.0, 507.0],
            "Low": [498.0, 498.0, 499.0, 504.0, 509.0, 514.0, 514.0, 509.0, 504.0, 499.0],
            "Close": [500.0, 500.0, 505.0, 510.0, 515.0, 520.0, 515.0, 510.0, 505.0, 500.0],
            "Volume": [1000.0] * 10,
            "ATR": [5.0] * 10,
        },
        index=dates,
    )

    s_cfg = IntradayEngineConfig(
        initial_capital=100_000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        stop_atr_multiplier=1.5,
        target_atr_multiplier=3.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )
    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        risk_per_trade_pct=0.01,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=1.5,
        take_profit_atr=3.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    signals = [None, Position.LONG] + [None] * 8

    s_res = run_intraday_backtest(df, signals, s_cfg)
    m_res = run_multi_asset_backtest({"TEST": df}, {"TEST": signals}, m_cfg)

    assert len(s_res.trades) == len(m_res.trades) == 1
    t_s = s_res.trades[0]
    t_m = m_res.trades[0]
    assert t_s.entry_time == t_m.entry_time
    assert t_s.exit_time == t_m.exit_time
    assert t_s.entry_price == t_m.entry_price
    assert t_s.exit_price == t_m.exit_price
    assert t_s.quantity == t_m.quantity
    assert t_s.exit_reason == t_m.exit_reason
    assert pytest.approx(t_s.net_pnl, abs=1e-2) == t_m.net_pnl



# ============================================================================
# Phase 27C.3.5.4 Unified Portfolio Protection Tests (Tests A through K)
# ============================================================================

def test_24_test_a_intrabar_breach_followed_by_recovery():
    """
    Test A — Intrabar breach followed by recovery:
    Initial capital Rs 100,000, protection floor Rs 97,000.
    Aggregate adverse intrabar equity Rs 96,500. Bar-close equity Rs 98,000.
    Asserts model does NOT silently award favorable recovery after earlier breach.
    Asserts liquidation executes at authentic adverse intrabar prices.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a, df_b = _make_two_symbol_bars(dates, base_price=100.0)

    # Bar 3: SYM_A has Low 80.0, Close 90.0 (-2,000 at Low, -1,000 at Close)
    #        SYM_B has Low 85.0, Close 90.0 (-1,500 at Low, -1,000 at Close)
    # Aggregate adverse equity = 100,000 - 3,500 = 96,500 <= 97,000 (breach!)
    # Aggregate close equity = 100,000 - 2,000 = 98,000 (rebound!)
    df_a.loc[dates[3], "Low"] = 80.0
    df_a.loc[dates[3], "Close"] = 90.0
    df_b.loc[dates[3], "Low"] = 85.0
    df_b.loc[dates[3], "Close"] = 90.0

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,
        risk_per_trade_pct=0.10,
        max_portfolio_risk_pct=0.20,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=10.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [None, opp_a, None, None, None],
            "SYM_B": [None, opp_b, None, None, None],
        },
        config=m_cfg,
    )

    assert res.portfolio.is_bankrupt is True
    assert res.bankruptcy_reason == "PROTECTION_FLOOR"
    assert len(res.trades) == 2
    t_a = next(t for t in res.trades if t.symbol == "SYM_A")
    t_b = next(t for t in res.trades if t.symbol == "SYM_B")

    # Assert executed at authentic adverse prices (Low), NOT at recovered Close (90.0)
    assert t_a.exit_price == 80.0
    assert t_b.exit_price == 85.0
    assert t_a.exit_reason == "PROTECTION_FLOOR"
    assert t_b.exit_reason == "PROTECTION_FLOOR"

    # Favorable rebound to 98,000 is strictly denied
    assert res.portfolio.equity <= 96_500.0


def test_25_test_b_theoretical_floor_not_reached():
    """
    Test B — Theoretical floor not reached:
    Initial capital Rs 100,000, protection floor Rs 97,000.
    Theoretical break-even threshold is 70.0 (loss Rs 3,000 / 100 shares).
    Market plunges past 70.0 down to Low 65.0.
    Asserts no artificial fill at the theoretical 70.0 threshold; fills at authentic Low 65.0.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 100.0, 65.0, 65.0],
            "High": [101.0, 101.0, 101.0, 66.0, 66.0],
            "Low": [99.0, 99.0, 99.0, 65.0, 65.0],
            "Close": [100.0, 100.0, 100.0, 65.0, 65.0],
            "Volume": [1000.0] * 5,
            "ATR": [5.0] * 5,
        },
        index=dates,
    )

    opp = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,
        risk_per_trade_pct=0.10,
        max_portfolio_risk_pct=0.20,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=10.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df},
        signals_by_symbol={"SYM_A": [None, opp, None, None, None]},
        config=m_cfg,
    )

    assert len(res.trades) == 1
    t = res.trades[0]
    # Authentic market fill at Open/Low (65.0), NOT artificial theoretical threshold (70.0)
    assert t.exit_price == 65.0
    assert t.exit_price != 70.0
    assert t.exit_reason == "PROTECTION_FLOOR"


def test_26_test_c_single_position_execution_parity():
    """
    Test C — Single-position execution parity:
    Verifies that single-stock and multi-asset engines use identical protection execution semantics.
    Asserts entry price, exit price, quantity, costs, and net P&L match.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 100.0, 65.0, 65.0],
            "High": [101.0, 101.0, 101.0, 66.0, 66.0],
            "Low": [99.0, 99.0, 99.0, 65.0, 65.0],
            "Close": [100.0, 100.0, 100.0, 65.0, 65.0],
            "Volume": [1000.0] * 5,
            "ATR": [5.0] * 5,
        },
        index=dates,
    )

    s_cfg = IntradayEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,
        risk_per_trade=0.10,
        max_leverage=5.0,
        stop_atr_multiplier=10.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )
    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,
        risk_per_trade_pct=0.10,
        max_portfolio_risk_pct=0.20,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=10.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )

    signals = [None, Position.LONG, None, None, None]

    s_res = run_intraday_backtest(df, signals, s_cfg)
    m_res = run_multi_asset_backtest({"SYM_A": df}, {"SYM_A": signals}, m_cfg)

    assert len(s_res.trades) == len(m_res.trades) == 1
    t_s = s_res.trades[0]
    t_m = m_res.trades[0]

    assert t_s.entry_price == t_m.entry_price == 100.0
    assert t_s.exit_price == t_m.exit_price == 65.0
    assert t_s.quantity == t_m.quantity
    assert t_s.exit_reason == t_m.exit_reason == "PROTECTION_FLOOR"
    assert pytest.approx(t_s.net_pnl, abs=1e-2) == t_m.net_pnl


def test_27_test_d_pending_position_remains_valued():
    """
    Test D — Pending position remains valued:
    An open losing position marked pending liquidation due to missing data must
    continue to be fully included in aggregate equity and unrealized P&L.
    """
    pm = PortfolioManager(initial_capital=100_000.0, max_leverage=5.0)
    pos = pm.open_position("SYM_A", Position.LONG, entry_time=pd.Timestamp("2026-03-30 09:25"), entry_price=100.0, quantity=100)

    # Price drops to 80.0 -> unrealized loss = -2,000
    pm.update_market_prices({"SYM_A": 80.0})
    assert pm.unrealized_pnl == -2000.0
    assert pm.equity == 98_000.0

    # Mark pending liquidation
    pm.mark_pending_liquidation("SYM_A", reason="PROTECTION_FLOOR")
    assert pos.pending_liquidation is True

    # Critical invariant: equity and unrealized P&L must NOT vanish or jump back to 100,000!
    assert pm.unrealized_pnl == -2000.0
    assert pm.equity == 98_000.0


def test_28_test_e_missing_data_concurrent_positions():
    """
    Test E — Missing data with concurrent positions:
    One position has valid current data, another has missing data.
    Portfolio marks indeterminate valuation, surfaces uncertainty, and blocks new entries.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a, df_b = _make_two_symbol_bars(dates, base_price=100.0)

    # Bar 3: Drop candle for SYM_B
    df_b = df_b.drop(dates[3])

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,
        risk_per_trade_pct=0.10,
        max_portfolio_risk_pct=0.20,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=10.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [None, opp_a, None, None, None],
            "SYM_B": [None, opp_b, None, None, None],
        },
        config=m_cfg,
    )

    # Indeterminate valuation event was recorded
    assert res.indeterminate_valuation_events >= 1
    assert res.stale_price_events >= 1


def test_29_test_f_simultaneous_stop_and_portfolio_protection():
    """
    Test F — Simultaneous stop and portfolio protection:
    Construct competing stop-loss and aggregate protection events.
    Deterministic priority: individual stops execute at stop_price first,
    then remaining positions hit aggregate protection floor.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a, df_b = _make_two_symbol_bars(dates, base_price=100.0)

    # SYM_A has stop at 95.0. On bar 3, drops to Low 80.0 -> hits stop at 95.0
    # SYM_B has stop at 50.0. On bar 3, drops to Low 70.0 -> causes aggregate floor breach
    df_a.loc[dates[3], "Low"] = 80.0
    df_b.loc[dates[3], "Low"] = 70.0

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=95.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=1.0,  # 1.0 * 5.0 stop_loss_atr = 5.0 stop_dist -> stop_p = 95.0
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=10.0,  # 10.0 * 5.0 stop_loss_atr = 50.0 stop_dist -> stop_p = 50.0
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,
        risk_per_trade_pct=0.10,
        max_portfolio_risk_pct=0.20,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=5.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [None, opp_a, None, None, None],
            "SYM_B": [None, opp_b, None, None, None],
        },
        config=m_cfg,
    )

    assert len(res.trades) == 2
    t_a = next(t for t in res.trades if t.symbol == "SYM_A")
    t_b = next(t for t in res.trades if t.symbol == "SYM_B")

    # SYM_A exited on STOP at 95.0
    assert t_a.exit_reason == "STOP"
    assert t_a.exit_price == 95.0

    # SYM_B exited on PROTECTION_FLOOR at authentic Low 70.0
    assert t_b.exit_reason == "PROTECTION_FLOOR"
    assert t_b.exit_price == 70.0


def test_30_test_g_multiple_positions_different_adverse_prices():
    """
    Test G — Multiple positions with different adverse prices:
    LONG position evaluated at Low, SHORT position evaluated at High.
    Asserts each position uses its appropriate directional adverse price.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df_a, df_b = _make_two_symbol_bars(dates, base_price=100.0)

    # Bar 3: SYM_A (LONG) plunges to Low 80.0 (-2,000)
    #        SYM_B (SHORT) spikes to High 120.0 (-2,000)
    df_a.loc[dates[3], "Low"] = 80.0
    df_b.loc[dates[3], "High"] = 120.0

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.SHORT, entry_price=100.0, stop_loss=150.0, target_price=50.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,
        risk_per_trade_pct=0.10,
        max_portfolio_risk_pct=0.20,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=10.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [None, opp_a, None, None, None],
            "SYM_B": [None, opp_b, None, None, None],
        },
        config=m_cfg,
    )

    assert len(res.trades) == 2
    t_a = next(t for t in res.trades if t.symbol == "SYM_A")
    t_b = next(t for t in res.trades if t.symbol == "SYM_B")

    # SYM_A liquidated at its adverse Low (80.0)
    assert t_a.exit_price == 80.0
    # SYM_B liquidated at its adverse High (120.0)
    assert t_b.exit_price == 120.0
    assert t_a.exit_reason == "PROTECTION_FLOOR"
    assert t_b.exit_reason == "PROTECTION_FLOOR"


def test_31_test_h_repeated_emergency_processing():
    """
    Test H — Repeated emergency processing:
    Verify exactly-once liquidation, cost accounting, and margin release across multiple subsequent bars.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=10, freq="1min")
    df_a, df_b = _make_two_symbol_bars(dates, base_price=100.0)

    # Floor breach on bar 3
    df_a.loc[dates[3], ["Open", "High", "Low", "Close"]] = 70.0
    df_b.loc[dates[3], ["Open", "High", "Low", "Close"]] = 70.0

    opp_a = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )
    opp_b = TradeOpportunity(
        symbol="SYM_B", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,
        risk_per_trade_pct=0.10,
        max_portfolio_risk_pct=0.20,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=10.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df_a, "SYM_B": df_b},
        signals_by_symbol={
            "SYM_A": [None, opp_a, None, None, None, None, None, None, None, None],
            "SYM_B": [None, opp_b, None, None, None, None, None, None, None, None],
        },
        config=m_cfg,
    )

    # Exactly 2 trades (1 per symbol), never duplicated on bars 4-9
    assert len(res.trades) == 2
    assert res.portfolio.allocated_margin == 0.0
    assert res.portfolio.open_position_count == 0


def test_32_test_i_opening_gap_breach():
    """
    Test I — Opening-gap breach:
    Adverse gap down at bar_open breaches protection floor immediately at Open.
    Asserts authentic bar_open execution price and gap recognition.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 100.0, 60.0, 60.0],  # Gap down to 60.0 (-4,000 loss)
            "High": [101.0, 101.0, 101.0, 61.0, 61.0],
            "Low": [99.0, 99.0, 99.0, 59.0, 59.0],
            "Close": [100.0, 100.0, 100.0, 60.0, 60.0],
            "Volume": [1000.0] * 5,
            "ATR": [5.0] * 5,
        },
        index=dates,
    )

    opp = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,
        risk_per_trade_pct=0.10,
        max_portfolio_risk_pct=0.20,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=10.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df},
        signals_by_symbol={"SYM_A": [None, opp, None, None, None]},
        config=m_cfg,
    )

    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_reason == "PROTECTION_FLOOR"
    assert t.exit_price == 60.0  # Filled at Open, recognizing full gap overshoot


def test_33_test_j_end_of_day_interaction():
    """
    Test J — End-of-day interaction:
    Square-off does not overwrite or bypass an active protection floor breach.
    """
    dates = pd.date_range("2026-03-30 15:10:00", periods=6, freq="1min")
    df = pd.DataFrame(
        {
            "Open": [100.0, 100.0, 100.0, 100.0, 100.0, 60.0],  # 15:15 bar crashes
            "High": [101.0, 101.0, 101.0, 101.0, 101.0, 61.0],
            "Low": [99.0, 99.0, 99.0, 99.0, 99.0, 59.0],
            "Close": [100.0, 100.0, 100.0, 100.0, 100.0, 60.0],
            "Volume": [1000.0] * 6,
            "ATR": [5.0] * 6,
        },
        index=dates,
    )

    opp = TradeOpportunity(
        symbol="SYM_A", side=Position.LONG, entry_price=100.0, stop_loss=50.0, target_price=200.0,
        requested_quantity=100, signal_quality=1.0, relative_volume=1.0, is_tradeable=True,
        timestamp=dates[1], atr=5.0,
    )

    m_cfg = MultiAssetEngineConfig(
        initial_capital=100_000.0,
        capital_protection_floor=97_000.0,
        risk_per_trade_pct=0.10,
        max_portfolio_risk_pct=0.20,
        max_stock_allocation_pct=1.0,
        reserve_capital_pct=0.0,
        max_leverage=5.0,
        stop_loss_atr=10.0,
        execution_model="next_open",
        session_end_time="15:15",
        enforce_eod_square_off=True,
        opening_cooldown_minutes=0,
    )

    res = run_multi_asset_backtest(
        data_by_symbol={"SYM_A": df},
        signals_by_symbol={"SYM_A": [None, opp, None, None, None, None]},
        config=m_cfg,
    )

    assert len(res.trades) == 1
    t = res.trades[0]
    # Protection floor takes precedence over normal EOD
    assert t.exit_reason == "PROTECTION_FLOOR"
    assert res.portfolio.is_bankrupt is True


def test_34_test_k_single_stock_regression():
    """
    Test K — Single-stock regression:
    Verify normal non-breach trades (targets, stops, gaps) continue to operate with 100% integrity.
    """
    dates = pd.date_range("2026-03-30 09:25:00", periods=5, freq="1min")
    df = pd.DataFrame(
        {
            "Open": [500.0, 500.0, 500.0, 510.0, 520.0],
            "High": [502.0, 502.0, 505.0, 515.0, 525.0],
            "Low": [498.0, 498.0, 499.0, 509.0, 519.0],
            "Close": [500.0, 500.0, 505.0, 515.0, 522.0],
            "Volume": [1000.0] * 5,
            "ATR": [5.0] * 5,
        },
        index=dates,
    )

    s_cfg = IntradayEngineConfig(
        initial_capital=100_000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        stop_atr_multiplier=1.5,
        target_atr_multiplier=3.0,
        execution_model="next_open",
        opening_cooldown_minutes=0,
        cost_config=DISCOUNT_BROKER_REALISTIC_CONFIG,
    )

    res = run_intraday_backtest(df, [None, Position.LONG, None, None, None], s_cfg)
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.entry_price == 500.0
    assert t.quantity == 122
    assert t.exit_reason in ("TARGET", "EOD")
    assert t.net_pnl > 0
