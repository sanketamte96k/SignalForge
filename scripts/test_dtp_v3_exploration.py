"""
SignalForge — Phase 32I: DTP-V3 Strategy Exploration & Sensitivity Analysis
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_phase32d_3_dtp_v1_expanded_validation import (
    load_and_resample_21_universe,
    calculate_signal_priority,
    APPROVED_21_SYMBOLS,
    EXPANDED_SECTOR_MAP,
    EXPANDED_ISIN_MAP,
)
from src.strategy.dtp_v2.config import (
    DTPV2Config,
    DTPExitReason,
    DTPRegimeState,
    OrderAction,
)
from src.strategy.dtp_v2.cost_integration import calculate_dtp_roundtrip_costs
from src.strategy.dtp_v2.indicators import calculate_dtp_indicators
from src.strategy.dtp_v2.market_filter import evaluate_breadth_regime
from src.strategy.dtp_v2.portfolio_rules import DTPPortfolioTracker
from src.strategy.dtp_v2.risk_manager import calculate_dtp_position_size
from src.strategy.dtp_v2.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    evaluate_next_open_execution,
    is_trend_aligned,
    is_pullback_active,
    check_reversal_trigger,
)

# Choppiness Index calculation
def calculate_choppiness_index(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    sum_tr = tr.rolling(window=period).sum()
    max_hi = high.rolling(window=period).max()
    min_lo = low.rolling(window=period).min()
    range_hl = (max_hi - min_lo).replace(0.0, np.nan)
    ci = 100.0 * np.log10(sum_tr / range_hl) / np.log10(period)
    return ci.fillna(50.0)

def run_simulation(
    augmented_universe: Dict[str, pd.DataFrame],
    trading_dates: List[pd.Timestamp],
    risk_pct: float = 0.01,
    adx_min: float = 20.0,
    use_chop_filter: bool = False,
    max_chop_index: float = 58.0,
    ema20_proximity_pct: float = 0.010,
    pullback_window_days: int = 3,
    require_upper_half_close: bool = False,
    adaptive_stop: bool = False,
    min_stop_atr: float = 1.5,
    breakeven_r: float = 1.0,
    trailing_r: float = 1.5,
    trailing_atr_mult: float = 2.0,
    profit_target_r: float = 3.0,
    max_holding_sessions: int = 10,
    dynamic_time_exit: bool = False,
    use_stress_costs: bool = False,
    initial_capital: float = 100000.0,
) -> Dict[str, Any]:
    config = DTPV2Config(
        risk_fraction_per_trade=risk_pct,
        max_concurrent_positions=3,
        symbol_sector_map=EXPANDED_SECTOR_MAP,
        symbol_isin_map=EXPANDED_ISIN_MAP,
        adx_min_threshold=adx_min,
        ema20_proximity_pct=ema20_proximity_pct,
        pullback_window_days=pullback_window_days,
        breakeven_r_mult=breakeven_r,
        trailing_r_mult=trailing_r,
        trailing_atr_mult=trailing_atr_mult,
        profit_target_r_mult=profit_target_r,
        max_holding_sessions=max_holding_sessions,
    )

    portfolio = DTPPortfolioTracker(initial_capital=initial_capital, config=config)
    positions_state: Dict[str, DTPPositionState] = {}
    pending_signals: Dict[str, Tuple[DTPEODSignal, Tuple[float, float, str]]] = {}
    executed_trades: List[Dict[str, Any]] = []
    trade_counter = 0

    daily_equity_list = []
    peak_equity = initial_capital
    max_drawdown = 0.0

    for day_idx, current_ts in enumerate(trading_dates):
        current_dt = current_ts.date()

        # Step A: Next-Day Open Execution
        if pending_signals:
            sorted_pending = sorted(pending_signals.items(), key=lambda item: item[1][1])
            for sym, (sig, prio_tuple) in sorted_pending:
                today_open = float(augmented_universe[sym].loc[current_ts, "open"])
                action, fill_price, action_msg = evaluate_next_open_execution(
                    signal=sig,
                    next_open_price=today_open,
                    config=config,
                )
                if action != OrderAction.ENTER_LONG:
                    continue

                curr_prices = {s: float(augmented_universe[s].loc[current_ts, "open"]) for s in APPROVED_21_SYMBOLS}
                equity = portfolio.get_portfolio_equity(curr_prices)
                sector = config.symbol_sector_map.get(sym, "General")
                sec_exp = portfolio.get_sector_exposure(sector, curr_prices)

                shares, size_msg = calculate_dtp_position_size(
                    equity=equity,
                    available_cash=portfolio.cash,
                    entry_price=fill_price,
                    stop_price=sig.initial_stop_price,
                    sector=sector,
                    current_sector_exposure=sec_exp,
                    config=config,
                )
                if shares <= 0:
                    continue

                can_open, gate_msg = portfolio.can_open_position(
                    symbol=sym,
                    entry_price=fill_price,
                    proposed_shares=shares,
                    sector=sector,
                    current_prices=curr_prices,
                )
                if not can_open:
                    continue

                trade_counter += 1
                order_id = f"EXP_{trade_counter:04d}_BUY_{sym}_{current_dt.isoformat()}"
                portfolio.open_position(
                    symbol=sym,
                    entry_price=fill_price,
                    shares=shares,
                    stop_price=sig.initial_stop_price,
                    r_distance=sig.r_distance,
                    entry_date=current_dt,
                    order_id=order_id,
                    sector=sector,
                )
                positions_state[sym] = DTPPositionState(
                    symbol=sym,
                    entry_date=current_dt,
                    entry_price=fill_price,
                    quantity=shares,
                    initial_stop_price=sig.initial_stop_price,
                    current_stop_price=sig.initial_stop_price,
                    r_distance=sig.r_distance,
                    highest_high=fill_price,
                    highest_close=fill_price,
                )

            pending_signals.clear()

        # Step B: Session Exits
        full_exits: List[Tuple[str, str, float, str]] = []
        for sym, pos in list(portfolio.positions.items()):
            pos_state = positions_state[sym]
            bar = augmented_universe[sym].loc[current_ts]

            # Last day forced liquidation
            if day_idx == len(trading_dates) - 1:
                friction_rate = (config.execution_slippage_bps + config.execution_spread_bps) / 10000.0
                exit_px = float(bar["close"]) * (1.0 - friction_rate)
                full_exits.append((sym, "MANUAL_CLOSE", exit_px, "End of validation period liquidation"))
                continue

            high = float(bar["high"])
            low = float(bar["low"])
            close = float(bar["close"])
            open_px = float(bar["open"])
            atr = float(bar.get("atr", 1.0))
            ema50 = float(bar.get("ema_slow", close))
            rsi = float(bar.get("rsi", 50.0))
            bb_upper = float(bar.get("bb_upper", close * 1.10))

            # Custom exit logic evaluation
            pos_state.holding_days += 1
            friction_rate = (config.execution_slippage_bps + config.execution_spread_bps) / 10000.0

            if high > pos_state.highest_high:
                pos_state.highest_high = high
            if close > pos_state.highest_close:
                pos_state.highest_close = close

            # 1. Stop loss
            if low <= pos_state.current_stop_price:
                raw_exit = min(open_px, pos_state.current_stop_price)
                exit_px = raw_exit * (1.0 - friction_rate)
                if pos_state.is_trailing_activated:
                    reason = "TRAILING_STOP"
                elif pos_state.is_breakeven_activated:
                    reason = "BREAKEVEN_STOP"
                else:
                    reason = "INITIAL_STOP"
                full_exits.append((sym, reason, exit_px, "Stop-loss hit"))
                continue

            # 2. Advance Trailing Stops
            excursion_r = (pos_state.highest_high - pos_state.entry_price) / pos_state.r_distance

            # Breakeven advancement
            if excursion_r >= breakeven_r and not pos_state.is_breakeven_activated:
                pos_state.is_breakeven_activated = True
                be_stop = pos_state.entry_price * (1.0 + config.breakeven_cost_buffer_pct)
                pos_state.current_stop_price = max(pos_state.current_stop_price, be_stop)

            # Chandelier Trailing advancement
            if excursion_r >= trailing_r:
                pos_state.is_trailing_activated = True
                chand_stop = pos_state.highest_high - (trailing_atr_mult * atr)
                pos_state.current_stop_price = max(pos_state.current_stop_price, chand_stop)

            # 3. Full Profit Target
            target_px = pos_state.entry_price + (profit_target_r * pos_state.r_distance)
            if high >= target_px:
                exit_px = target_px * (1.0 - friction_rate)
                full_exits.append((sym, "PROFIT_TARGET", exit_px, f"Profit target +{profit_target_r}R hit"))
                continue

            # 4. Overbought Blowoff
            if rsi >= config.rsi_overbought_threshold and high >= bb_upper:
                exit_px = close * (1.0 - friction_rate)
                full_exits.append((sym, "DYNAMIC_OVERBOUGHT", exit_px, "Overbought exit"))
                continue

            # 5. Trend Breakdown
            if close < ema50:
                pos_state.consecutive_closes_below_ema50 += 1
            else:
                pos_state.consecutive_closes_below_ema50 = 0

            if pos_state.consecutive_closes_below_ema50 >= config.consecutive_breakdown_bars:
                exit_px = close * (1.0 - friction_rate)
                full_exits.append((sym, "TREND_BREAKDOWN", exit_px, "Trend breakdown < EMA50"))
                continue

            # 6. Time limit exit
            if dynamic_time_exit:
                if pos_state.holding_days >= max_holding_sessions:
                    # If position has made decent excursion (>= 1.0R) and is still above 20 EMA, give it up to 15 sessions
                    ema20 = float(bar.get("ema_fast", close))
                    if excursion_r >= 1.0 and close >= ema20 and pos_state.holding_days < 15:
                        pass # Hold position
                    elif excursion_r < trailing_r:
                        exit_px = close * (1.0 - friction_rate)
                        full_exits.append((sym, "TIME_LIMIT", exit_px, f"Time limit ({pos_state.holding_days} sessions)"))
                        continue
            else:
                if pos_state.holding_days >= max_holding_sessions and excursion_r < trailing_r:
                    exit_px = close * (1.0 - friction_rate)
                    full_exits.append((sym, "TIME_LIMIT", exit_px, f"Time limit ({pos_state.holding_days} sessions)"))
                    continue

        # Process exits
        for sym, reason_str, exit_px, exit_msg in full_exits:
            active_pos = portfolio.positions[sym]
            isin = config.symbol_isin_map.get(sym, "INE000000000")
            breakdown, cost_summary = calculate_dtp_roundtrip_costs(
                symbol=sym,
                isin=isin,
                entry_date=active_pos.entry_date,
                exit_date=current_dt,
                entry_price=active_pos.entry_price,
                exit_price=exit_px,
                quantity=active_pos.quantity,
                use_stress_profile=use_stress_costs,
                order_id_prefix="EXP",
            )
            net_proceeds = cost_summary.sell_turnover - cost_summary.total_friction_costs
            portfolio.close_position(sym, exit_px, net_proceeds)
            pos_state = positions_state.pop(sym, None)

            gross_pnl = (exit_px - active_pos.entry_price) * active_pos.quantity
            tot_costs = float(cost_summary.total_friction_costs)
            net_pnl = gross_pnl - tot_costs

            executed_trades.append({
                "symbol": sym,
                "entry_date": active_pos.entry_date,
                "exit_date": current_dt,
                "entry_price": active_pos.entry_price,
                "exit_price": exit_px,
                "quantity": active_pos.quantity,
                "holding_days": pos_state.holding_days if pos_state else 0,
                "exit_reason": reason_str,
                "gross_pnl": gross_pnl,
                "total_costs": tot_costs,
                "net_pnl": net_pnl,
            })

        # Step C: EOD Signal Evaluation for Bar T
        regime_state = evaluate_breadth_regime(augmented_universe, bar_idx=day_idx, config=config)
        if day_idx < len(trading_dates) - 2 and regime_state not in (DTPRegimeState.BEARISH, DTPRegimeState.UNKNOWN):
            for sym in APPROVED_21_SYMBOLS:
                if sym in portfolio.positions:
                    continue

                df_sym = augmented_universe[sym]
                if day_idx < max(config.ema_slow_period, pullback_window_days + 1):
                    continue

                row = df_sym.iloc[day_idx]
                c = float(row["close"])
                atr = float(row["atr"])

                # Macro Trend Filter
                trend_ok, _ = is_trend_aligned(df_sym, day_idx, config)
                if not trend_ok:
                    continue

                # Choppiness Filter
                if use_chop_filter and "chop_index" in row:
                    chop = float(row["chop_index"])
                    if chop > max_chop_index:
                        continue

                # Pullback & Reversal Trigger
                rev_ok, _ = check_reversal_trigger(df_sym, day_idx, config)
                if not rev_ok:
                    continue

                # Upper half close filter
                if require_upper_half_close:
                    h = float(row["high"])
                    l = float(row["low"])
                    if (h - l) > 0 and (c - l) / (h - l) < 0.50:
                        continue

                # Stop loss calculation
                w_start = max(0, day_idx - pullback_window_days)
                lowest_low = float(df_sym["low"].iloc[w_start : day_idx + 1].min())

                if adaptive_stop:
                    # Dynamic floor at min_stop_atr (e.g. 1.5 * ATR) to avoid premature noise stops
                    atr_stop = c - (2.0 * atr)
                    buff_low = lowest_low - (0.15 * atr)
                    initial_stop = min(buff_low, atr_stop)
                    if (c - initial_stop) < min_stop_atr * atr:
                        initial_stop = c - (min_stop_atr * atr)
                else:
                    atr_stop = c - (config.initial_stop_atr_mult * atr)
                    initial_stop = min(lowest_low, atr_stop)

                # Cap stop at 3.0 * ATR
                max_stop_distance = config.max_stop_atr_mult * atr
                if (c - initial_stop) > max_stop_distance:
                    initial_stop = c - max_stop_distance

                r_distance = c - initial_stop
                if r_distance <= 0:
                    continue

                sig = DTPEODSignal(
                    symbol=sym,
                    signal_date=current_dt,
                    action=OrderAction.ENTER_LONG,
                    entry_trigger_price=c,
                    initial_stop_price=initial_stop,
                    r_distance=r_distance,
                    regime=regime_state,
                    notes=[],
                )
                prio_tuple = calculate_signal_priority(sig, row)
                pending_signals[sym] = (sig, prio_tuple)

        # Track daily equity
        curr_eod_px = {s: float(augmented_universe[s].loc[current_ts, "close"]) for s in APPROVED_21_SYMBOLS}
        eod_equity = portfolio.get_portfolio_equity(curr_eod_px)
        if eod_equity > peak_equity:
            peak_equity = eod_equity
        dd = (peak_equity - eod_equity) / peak_equity
        if dd > max_drawdown:
            max_drawdown = dd

    # Summary metrics
    n_trades = len(executed_trades)
    df_t = pd.DataFrame(executed_trades) if n_trades > 0 else pd.DataFrame(columns=["net_pnl", "gross_pnl", "total_costs", "holding_days", "exit_date"])
    net_pnl = float(df_t["net_pnl"].sum()) if n_trades > 0 else 0.0
    gross_pnl = float(df_t["gross_pnl"].sum()) if n_trades > 0 else 0.0
    tot_costs = float(df_t["total_costs"].sum()) if n_trades > 0 else 0.0
    wins = len(df_t[df_t["net_pnl"] > 0]) if n_trades > 0 else 0
    losses = len(df_t[df_t["net_pnl"] <= 0]) if n_trades > 0 else 0
    wr = (wins / n_trades * 100.0) if n_trades > 0 else 0.0
    g_wins = float(df_t[df_t["net_pnl"] > 0]["net_pnl"].sum()) if wins > 0 else 0.0
    g_loss = float(abs(df_t[df_t["net_pnl"] <= 0]["net_pnl"].sum())) if losses > 0 else 0.0
    pf = round(g_wins / g_loss, 2) if g_loss > 0 else 999.0
    avg_win = g_wins / wins if wins > 0 else 0.0
    avg_loss = g_loss / losses if losses > 0 else 0.0
    payoff = round(avg_win / avg_loss, 2) if avg_loss > 0 else 999.0
    cagr = round(((eod_equity / initial_capital) ** (1.0 / 3.0) - 1.0) * 100.0, 2)
    avg_hold = round(float(df_t["holding_days"].mean()), 1) if n_trades > 0 else 0.0

    yearly = {}
    if n_trades > 0:
        df_t["year"] = pd.to_datetime(df_t["exit_date"]).dt.year
        for yr, grp in df_t.groupby("year"):
            yearly[int(yr)] = {
                "trades": len(grp),
                "net_pnl": round(float(grp["net_pnl"].sum()), 2),
                "wr": round(len(grp[grp["net_pnl"] > 0]) / len(grp) * 100.0, 1),
            }

    return {
        "trades": n_trades,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(wr, 2),
        "gross_pnl": round(gross_pnl, 2),
        "total_costs": round(tot_costs, 2),
        "net_pnl": round(net_pnl, 2),
        "net_pf": pf,
        "payoff": payoff,
        "max_dd_pct": round(max_drawdown * 100.0, 2),
        "cagr_pct": cagr,
        "avg_hold": avg_hold,
        "yearly": yearly,
        "final_equity": round(eod_equity, 2),
    }

def main():
    print("=" * 80)
    print("Loading 2017-2019 Universe...")
    print("=" * 80)
    raw_universe = load_and_resample_21_universe()
    cfg_default = DTPV2Config(symbol_sector_map=EXPANDED_SECTOR_MAP, symbol_isin_map=EXPANDED_ISIN_MAP)

    universe_augmented = {}
    for sym in APPROVED_21_SYMBOLS:
        df_ind = calculate_dtp_indicators(raw_universe[sym], config=cfg_default)
        df_ind["chop_index"] = calculate_choppiness_index(df_ind["high"], df_ind["low"], df_ind["close"], period=14)
        universe_augmented[sym] = df_ind

    trading_dates = list(raw_universe[APPROVED_21_SYMBOLS[0]].index)

    # 1. Exact DTP-V2 reproduction check
    print("\n--- 1. BASELINE REPRODUCTION (DTP-V2 1.0% Risk) ---")
    base_res = run_simulation(universe_augmented, trading_dates, risk_pct=0.01)
    print(f"Trades: {base_res['trades']}, Net: ₹{base_res['net_pnl']:,.2f}, WR: {base_res['win_rate_pct']}%, PF: {base_res['net_pf']}, Payoff: {base_res['payoff']}, MaxDD: {base_res['max_dd_pct']}%, CAGR: {base_res['cagr_pct']}%")
    print(f"Yearly: {base_res['yearly']}")

    # 2. Test individual filter improvements
    tests = [
        ("Choppiness Filter (CI <= 58)", {"use_chop_filter": True, "max_chop_index": 58.0}),
        ("Choppiness Filter (CI <= 60)", {"use_chop_filter": True, "max_chop_index": 60.0}),
        ("Adaptive Stop (Floor 1.5 ATR)", {"adaptive_stop": True, "min_stop_atr": 1.5}),
        ("Adaptive Stop (Floor 1.8 ATR)", {"adaptive_stop": True, "min_stop_atr": 1.8}),
        ("Upper Half Close Filter", {"require_upper_half_close": True}),
        ("EMA20 Proximity 1.5%", {"ema20_proximity_pct": 0.015}),
        ("EMA20 Proximity 2.0%", {"ema20_proximity_pct": 0.020}),
        ("Pullback Window 4 Days", {"pullback_window_days": 4}),
        ("Breakeven at 1.2R", {"breakeven_r": 1.2}),
        ("Dynamic Time Exit (Hold to 15 if > EMA20)", {"dynamic_time_exit": True}),
        ("Profit Target 3.5R", {"profit_target_r": 3.5}),
    ]

    print("\n--- 2. INDIVIDUAL COMPONENT SENSITIVITY (at 1% Risk) ---")
    for name, params in tests:
        res = run_simulation(universe_augmented, trading_dates, risk_pct=0.01, **params)
        print(f"{name:<45} | Trades: {res['trades']:<3} | Net: ₹{res['net_pnl']:>8.2f} | WR: {res['win_rate_pct']:>5.1f}% | PF: {res['net_pf']:>4.2f} | Payoff: {res['payoff']:>4.2f} | MaxDD: {res['max_dd_pct']:>4.2f}% | 2019: ₹{res['yearly'].get(2019, {}).get('net_pnl', 0.0):>7.2f}")

if __name__ == "__main__":
    main()

def run_combined_tests():
    raw_universe = load_and_resample_21_universe()
    cfg_default = DTPV2Config(symbol_sector_map=EXPANDED_SECTOR_MAP, symbol_isin_map=EXPANDED_ISIN_MAP)

    universe_augmented = {}
    for sym in APPROVED_21_SYMBOLS:
        df_ind = calculate_dtp_indicators(raw_universe[sym], config=cfg_default)
        df_ind["chop_index"] = calculate_choppiness_index(df_ind["high"], df_ind["low"], df_ind["close"], period=14)
        universe_augmented[sym] = df_ind

    trading_dates = list(raw_universe[APPROVED_21_SYMBOLS[0]].index)

    print("\n" + "=" * 80)
    print("--- 3. COMBINED DTP-V3 CANDIDATES (1%, 2%, 3% RISK) ---")
    print("=" * 80)

    combos = [
        # Combo 1: Chop Filter CI <= 60 + Upper Half Close
        ("Combo1_CI60_UpperHalf_1pct", {"use_chop_filter": True, "max_chop_index": 60.0, "require_upper_half_close": True, "risk_pct": 0.01}),
        ("Combo1_CI60_UpperHalf_2pct", {"use_chop_filter": True, "max_chop_index": 60.0, "require_upper_half_close": True, "risk_pct": 0.02}),
        ("Combo1_CI60_UpperHalf_3pct", {"use_chop_filter": True, "max_chop_index": 60.0, "require_upper_half_close": True, "risk_pct": 0.03}),

        # Combo 2: Chop Filter CI <= 62 + Upper Half Close
        ("Combo2_CI62_UpperHalf_1pct", {"use_chop_filter": True, "max_chop_index": 62.0, "require_upper_half_close": True, "risk_pct": 0.01}),
        ("Combo2_CI62_UpperHalf_2pct", {"use_chop_filter": True, "max_chop_index": 62.0, "require_upper_half_close": True, "risk_pct": 0.02}),
        ("Combo2_CI62_UpperHalf_3pct", {"use_chop_filter": True, "max_chop_index": 62.0, "require_upper_half_close": True, "risk_pct": 0.03}),

        # Combo 3: Chop Filter CI <= 60 + Upper Half Close + Stress Costs
        ("Combo1_CI60_UpperHalf_1pct_STRESS", {"use_chop_filter": True, "max_chop_index": 60.0, "require_upper_half_close": True, "risk_pct": 0.01, "use_stress_costs": True}),
        ("Combo1_CI60_UpperHalf_2pct_STRESS", {"use_chop_filter": True, "max_chop_index": 60.0, "require_upper_half_close": True, "risk_pct": 0.02, "use_stress_costs": True}),
        ("Combo1_CI60_UpperHalf_3pct_STRESS", {"use_chop_filter": True, "max_chop_index": 60.0, "require_upper_half_close": True, "risk_pct": 0.03, "use_stress_costs": True}),
    ]

    for name, params in combos:
        res = run_simulation(universe_augmented, trading_dates, **params)
        print(f"{name:<35} | Trades: {res['trades']:<2} | Net: ₹{res['net_pnl']:>9.2f} | WR: {res['win_rate_pct']:>5.1f}% | PF: {res['net_pf']:>4.2f} | Payoff: {res['payoff']:>4.2f} | MaxDD: {res['max_dd_pct']:>5.2f}% | CAGR: {res['cagr_pct']:>5.2f}% | Costs: ₹{res['total_costs']:>7.2f}")
        print(f"  Yearly: {res['yearly']}")

if __name__ == "__main__":
    run_combined_tests()
