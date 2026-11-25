"""
SignalForge — Phase 32J.6: Fixed Max 2 Independent Robustness Audit Runner
===========================================================================
File: scripts/run_phase32j_6_max2_robustness_audit.py
"""

from __future__ import annotations

import copy
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.run_phase32j_5_position_limits_backtest import (
    load_universe_inventory,
    load_and_resample_universe,
    run_position_limits_simulation,
    simulate_hypothetical_trade,
)
from src.strategy.dtp_v3_position_limits.config import (
    DTPV3PositionLimitsConfig,
    FixedLimitMode,
    DynamicLimitMode,
    MarketZone,
    OrderAction,
    DTPExitReason,
)
from src.strategy.dtp_v3_position_limits.cost_integration import calculate_dtp_roundtrip_costs
from src.strategy.dtp_v3_position_limits.indicators import calculate_dtp_indicators
from src.strategy.dtp_v3_position_limits.market_filter import NiftyPositionLimitsFilter
from src.strategy.dtp_v3_position_limits.portfolio_rules import DTPPositionLimitsTracker
from src.strategy.dtp_v3_position_limits.risk_manager import calculate_position_limit_sizing
from src.strategy.dtp_v3_position_limits.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    evaluate_exit_conditions,
    evaluate_next_open_execution,
    generate_eod_signal,
)
from src.strategy.dtp_v3.market_filter import evaluate_breadth_regime
from scripts.run_phase32d_3_dtp_v1_expanded_validation import calculate_signal_priority
from src.strategy.dtp_v3_max2_audit.config import DTPMax2AuditConfig, EntryPriorityMode

REPORTS_DIR = ROOT_DIR / "reports" / "phase32j_6"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def run_entry_priority_simulation(
    augmented_universe: Dict[str, pd.DataFrame],
    trading_dates: List[pd.Timestamp],
    sector_map: Dict[str, str],
    isin_map: Dict[str, str],
    nifty_filter: NiftyPositionLimitsFilter,
    fixed_limit: FixedLimitMode = FixedLimitMode.A2_MAX_2,
    dynamic_mode: DynamicLimitMode = DynamicLimitMode.NONE,
    apply_a2_risk_overlay: bool = False,
    risk_pct: float = 0.02,
    use_stress_costs: bool = False,
    initial_capital: float = 100000.0,
    experiment_tag: str = "ENTRY_PRIO",
    priority_mode: EntryPriorityMode = EntryPriorityMode.ORIGINAL,
) -> Dict[str, Any]:
    """Runs simulation with custom deterministic entry priority ranking."""
    symbols = sorted(list(augmented_universe.keys()))
    cost_tag = "STRESS" if use_stress_costs else "OFFICIAL"
    a2_tag = "A2OVERLAY" if apply_a2_risk_overlay else "NOA2"
    scenario_name = f"{experiment_tag}_{priority_mode.value}_MAX{fixed_limit.value}_{a2_tag}_{int(risk_pct*100)}pct_{cost_tag}"

    cfg = DTPV3PositionLimitsConfig(
        risk_fraction_per_trade=risk_pct,
        symbol_sector_map=sector_map,
        symbol_isin_map=isin_map,
        fixed_limit_mode=fixed_limit,
        dynamic_limit_mode=dynamic_mode,
        apply_a2_risk_overlay=apply_a2_risk_overlay,
    )
    portfolio = DTPPositionLimitsTracker(initial_capital=initial_capital, config=cfg)

    positions_state: Dict[str, DTPPositionState] = {}
    pending_signals: Dict[str, Tuple[DTPEODSignal, Tuple[float, float, str], float]] = {}
    executed_trades: List[Dict[str, Any]] = []
    rejected_entries: List[Dict[str, Any]] = []
    daily_records: List[Dict[str, Any]] = []
    position_count_records: List[Dict[str, Any]] = []
    trade_counter = 0

    peak_equity = initial_capital
    max_drawdown = 0.0

    for day_idx, current_ts in enumerate(trading_dates):
        current_dt = current_ts.date()

        # Step A: Evaluate active concurrent position limit for Day T session
        active_pos_limit, mkt_zone, dist_pct, limit_msg = nifty_filter.get_active_position_limit(
            decision_date=current_dt,
            dynamic_mode=dynamic_mode,
            fixed_limit=fixed_limit,
        )

        # Step B: Next-Day Open Execution for Pending Signals
        if pending_signals:
            if priority_mode == EntryPriorityMode.ORIGINAL:
                sorted_pending = sorted(pending_signals.items(), key=lambda item: item[1][1])
            elif priority_mode == EntryPriorityMode.CHOP_STRENGTH:
                # Lowest Choppiness Index (strongest trend) first, alphabetical tie-break
                prev_ts = trading_dates[day_idx - 1] if day_idx > 0 else current_ts
                sorted_pending = sorted(
                    pending_signals.items(),
                    key=lambda item: (
                        float(augmented_universe[item[0]].loc[prev_ts].get("chop_index", 50.0)),
                        item[0],
                    ),
                )
            elif priority_mode == EntryPriorityMode.REVERSE_ALPHA:
                # Reverse alphabetical tie-break
                sorted_pending = sorted(
                    pending_signals.items(),
                    key=lambda item: (item[1][1][0], [-ord(c) for c in item[0]]),
                )
            else:
                sorted_pending = sorted(pending_signals.items(), key=lambda item: item[1][1])

            for sym, (sig, prio_tuple, r_mult) in sorted_pending:
                today_open = float(augmented_universe[sym].loc[current_ts, "open"])
                action, fill_price, action_msg = evaluate_next_open_execution(
                    signal=sig,
                    next_open_price=today_open,
                    config=cfg,
                )
                if action != OrderAction.ENTER_LONG:
                    continue

                curr_prices = {s: float(augmented_universe[s].loc[current_ts, "open"]) for s in symbols}
                equity = portfolio.get_portfolio_equity(curr_prices)
                sector = cfg.symbol_sector_map.get(sym, "Diversified")
                sec_exp = portfolio.get_sector_exposure(sector, curr_prices)
                curr_dd = portfolio.get_current_drawdown(curr_prices)

                shares, size_msg = calculate_position_limit_sizing(
                    equity=equity,
                    available_cash=portfolio.cash,
                    entry_price=fill_price,
                    stop_price=sig.initial_stop_price,
                    sector=sector,
                    current_sector_exposure=sec_exp,
                    current_drawdown_pct=curr_dd,
                    risk_multiplier=r_mult,
                    config=cfg,
                )
                if shares <= 0:
                    continue

                can_open, gate_msg = portfolio.can_open_position(
                    symbol=sym,
                    entry_price=fill_price,
                    proposed_shares=shares,
                    active_position_limit=active_pos_limit,
                    sector=sector,
                    current_prices=curr_prices,
                )

                if not can_open:
                    hypo_res = simulate_hypothetical_trade(
                        symbol=sym,
                        entry_dt=current_dt,
                        entry_day_idx=day_idx,
                        fill_price=fill_price,
                        shares=shares,
                        initial_stop=sig.initial_stop_price,
                        r_distance=sig.r_distance,
                        augmented_universe=augmented_universe,
                        trading_dates=trading_dates,
                        cfg=cfg,
                        use_stress_costs=use_stress_costs,
                    )
                    rejected_entries.append({
                        "scenario_id": scenario_name,
                        "experiment_tag": experiment_tag,
                        "risk_tier": f"E{int(risk_pct*100)} ({int(risk_pct*100)}%)",
                        "cost_schedule": "Stress (₹317/cr)" if use_stress_costs else "Official (₹307/cr)",
                        "date": current_dt.isoformat(),
                        "symbol": sym,
                        "sector": sector,
                        "rejection_reason": gate_msg,
                        "market_zone": mkt_zone.value,
                        "active_position_limit": active_pos_limit,
                        "current_open_positions": portfolio.position_count,
                        "fill_price": round(fill_price, 2),
                        "shares": shares,
                        **hypo_res,
                    })
                    continue

                trade_counter += 1
                order_id = f"DTPV3_{trade_counter:04d}_BUY_{sym}_{current_dt.isoformat()}"
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

        # Step C: Session Exits
        full_exits: List[Tuple[str, str, float, str]] = []
        for sym, pos in list(portfolio.positions.items()):
            pos_state = positions_state[sym]
            bar = augmented_universe[sym].loc[current_ts]

            if day_idx == len(trading_dates) - 1:
                friction_rate = (cfg.execution_slippage_bps + cfg.execution_spread_bps) / 10000.0
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

            reason_obj, exit_px, exit_msg = evaluate_exit_conditions(
                pos=pos_state,
                current_high=high,
                current_low=low,
                current_close=close,
                current_open=open_px,
                current_atr=atr,
                current_ema50=ema50,
                current_rsi=rsi,
                current_bb_upper=bb_upper,
                config=cfg,
            )

            if reason_obj is not None:
                r_str = reason_obj.value if hasattr(reason_obj, "value") else str(reason_obj)
                full_exits.append((sym, r_str, exit_px, exit_msg))

        for sym, reason_str, exit_px, exit_msg in full_exits:
            active_pos = portfolio.positions[sym]
            isin = cfg.symbol_isin_map.get(sym, "DEFAULT_ISIN")
            breakdown, cost_summary = calculate_dtp_roundtrip_costs(
                symbol=sym,
                isin=isin,
                entry_date=active_pos.entry_date,
                exit_date=current_dt,
                entry_price=active_pos.entry_price,
                exit_price=exit_px,
                quantity=active_pos.quantity,
                use_stress_profile=use_stress_costs,
                order_id_prefix="DTPV3",
            )
            net_proceeds = cost_summary.sell_turnover - cost_summary.total_friction_costs
            portfolio.close_position(sym, exit_px, net_proceeds)
            pos_state = positions_state.pop(sym, None)

            gross_pnl = (exit_px - active_pos.entry_price) * active_pos.quantity
            tot_costs = float(cost_summary.total_friction_costs)
            net_pnl = gross_pnl - tot_costs

            executed_trades.append({
                "scenario_id": scenario_name,
                "experiment_tag": experiment_tag,
                "fixed_limit": fixed_limit.value if dynamic_mode == DynamicLimitMode.NONE else "DYNAMIC",
                "dynamic_mode": dynamic_mode.value,
                "apply_a2_risk_overlay": apply_a2_risk_overlay,
                "risk_tier": f"E{int(risk_pct*100)} ({int(risk_pct*100)}%)",
                "cost_schedule": "Stress (₹317/cr)" if use_stress_costs else "Official (₹307/cr)",
                "trade_id": len(executed_trades) + 1,
                "symbol": sym,
                "sector": cfg.symbol_sector_map.get(sym, "Diversified"),
                "entry_date": active_pos.entry_date,
                "exit_date": current_dt,
                "entry_price": round(active_pos.entry_price, 2),
                "exit_price": round(exit_px, 2),
                "quantity": active_pos.quantity,
                "holding_days": pos_state.holding_days if pos_state else 0,
                "exit_reason": reason_str,
                "gross_pnl": round(gross_pnl, 2),
                "total_costs": round(tot_costs, 2),
                "net_pnl": round(net_pnl, 2),
                "return_pct": round(cost_summary.net_return_pct, 2),
            })

        # Step D: EOD Signals
        reg_res = evaluate_breadth_regime(augmented_universe, bar_idx=day_idx, config=cfg)
        regime_state = reg_res[0] if isinstance(reg_res, tuple) else reg_res
        is_bearish_breadth = (regime_state == "BEARISH") or (hasattr(regime_state, "value") and regime_state.value == "BEARISH") or (regime_state == "UNKNOWN")

        zone_t, close_t, sma100_t, dist_t = nifty_filter.evaluate_market_zone(current_dt)

        if dynamic_mode in [DynamicLimitMode.B1, DynamicLimitMode.B2]:
            regime_permitted = True
        elif dynamic_mode == DynamicLimitMode.B3:
            regime_permitted = (close_t > sma100_t)
        else:
            regime_permitted = (close_t > sma100_t)

        if apply_a2_risk_overlay and (zone_t == MarketZone.CAUTION):
            next_day_risk_mult = 0.50
        else:
            next_day_risk_mult = 1.0

        if day_idx < len(trading_dates) - 2 and not is_bearish_breadth:
            if regime_permitted:
                for sym in symbols:
                    if sym in portfolio.positions:
                        continue
                    df_sym = augmented_universe[sym]
                    sig = generate_eod_signal(
                        symbol=sym,
                        df=df_sym,
                        market_regime=regime_state,
                        config=cfg,
                        bar_idx=day_idx,
                        signal_date=current_dt,
                    )
                    if sig is not None:
                        bar_t = df_sym.iloc[day_idx]
                        prio = calculate_signal_priority(sig, bar_t)
                        pending_signals[sym] = (sig, prio, next_day_risk_mult)

        curr_prices = {s: float(augmented_universe[s].loc[current_ts, "close"]) for s in symbols}
        eod_equity = portfolio.get_portfolio_equity(curr_prices)
        if eod_equity > peak_equity:
            peak_equity = eod_equity
        dd_pct = ((peak_equity - eod_equity) / peak_equity) * 100.0 if peak_equity > 0 else 0.0
        if dd_pct > max_drawdown:
            max_drawdown = dd_pct

    n_trades = len(executed_trades)
    wins = [t for t in executed_trades if t["net_pnl"] > 0]
    losses = [t for t in executed_trades if t["net_pnl"] <= 0]
    gross_pnl = sum(t["gross_pnl"] for t in executed_trades)
    total_costs = sum(t["total_costs"] for t in executed_trades)
    net_pnl = sum(t["net_pnl"] for t in executed_trades)
    win_rate = (len(wins) / n_trades * 100.0) if n_trades > 0 else 0.0
    w_sum = sum(t["net_pnl"] for t in wins)
    l_sum = abs(sum(t["net_pnl"] for t in losses))
    pf = (w_sum / l_sum) if l_sum > 0 else (99.0 if w_sum > 0 else 0.0)
    avg_w = (w_sum / len(wins)) if wins else 0.0
    avg_l = (l_sum / len(losses)) if losses else 0.0
    payoff = (avg_w / avg_l) if avg_l > 0 else 0.0

    final_equity = portfolio.cash + sum(
        p.quantity * float(augmented_universe[s].iloc[-1]["close"]) for s, p in portfolio.positions.items()
    )
    tot_ret = (final_equity - initial_capital) / initial_capital
    cagr = ((1.0 + tot_ret) ** (1.0 / 3.0) - 1.0) * 100.0 if tot_ret > -1.0 else -100.0

    return {
        "scenario_id": scenario_name,
        "completed_trades": n_trades,
        "rejected_entries_count": len(rejected_entries),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate, 2),
        "gross_pnl": round(gross_pnl, 2),
        "total_costs": round(total_costs, 2),
        "net_pnl": round(net_pnl, 2),
        "net_profit_factor": round(pf, 2),
        "payoff_ratio": round(payoff, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "cagr_pct": round(cagr, 2),
        "executed_trades": executed_trades,
        "rejected_entries": rejected_entries,
    }


def compute_bootstrap_results(trades: List[Dict[str, Any]], n_boot: int = 10000) -> Dict[str, Any]:
    if not trades:
        return {
            "n": 0, "mean_expectancy": 0.0, "std_error": 0.0, "t_stat": 0.0,
            "ci_95_lower": 0.0, "ci_95_upper": 0.0, "prob_positive_pct": 0.0
        }
    pnls = np.array([t["net_pnl"] for t in trades])
    n = len(pnls)
    rng = np.random.default_rng(42)
    boot_means = np.array([rng.choice(pnls, size=n, replace=True).mean() for _ in range(n_boot)])

    mean_exp = float(np.mean(boot_means))
    se = float(np.std(boot_means, ddof=1))
    t_stat = (mean_exp / se) if se > 0 else 0.0
    ci_lower = float(np.percentile(boot_means, 2.5))
    ci_upper = float(np.percentile(boot_means, 97.5))
    prob_pos = float((boot_means > 0).sum() / n_boot * 100.0)

    return {
        "n": n,
        "mean_expectancy": round(mean_exp, 2),
        "std_error": round(se, 2),
        "t_stat": round(t_stat, 2),
        "ci_95_lower": round(ci_lower, 2),
        "ci_95_upper": round(ci_upper, 2),
        "prob_positive_pct": round(prob_pos, 1),
    }


def main() -> None:
    print("=" * 70)
    print("SIGNALFORGE — PHASE 32J.6: FIXED MAX 2 INDEPENDENT ROBUSTNESS AUDIT")
    print("=" * 70)

    symbols, sector_map, isin_map = load_universe_inventory()
    universe = load_and_resample_universe(symbols)

    print("Pre-calculating technical indicators across all 91 symbols...")
    augmented_universe: Dict[str, pd.DataFrame] = {}
    for sym, df_daily in universe.items():
        augmented_universe[sym] = calculate_dtp_indicators(df_daily)

    trading_dates = sorted(list(universe[symbols[0]].index))
    nifty_filter = NiftyPositionLimitsFilter()

    # =========================================================================
    # PART 1: REPRODUCTION OF PHASE 32J.5
    # =========================================================================
    print("\n--- PART 1: REPRODUCING PHASE 32J.5 CORE ARCHITECTURES ---")
    repro_matrix = [
        ("BASELINE_1_FIXED3", FixedLimitMode.A1_MAX_3, DynamicLimitMode.NONE, False),
        ("EXP_A_FIXED_MAX2", FixedLimitMode.A2_MAX_2, DynamicLimitMode.NONE, False),
        ("EXP_A_FIXED_MAX1", FixedLimitMode.A3_MAX_1, DynamicLimitMode.NONE, False),
        ("EXP_C_COMBINED_MAX2_A2", FixedLimitMode.A2_MAX_2, DynamicLimitMode.NONE, True),
    ]

    repro_results: List[Dict[str, Any]] = []
    trade_store: Dict[str, List[Dict[str, Any]]] = {}

    for tag, f_lim, d_mod, a2_ov in repro_matrix:
        for r_pct in [0.01, 0.02, 0.03]:
            for stress in [False, True]:
                res = run_position_limits_simulation(
                    augmented_universe=augmented_universe,
                    trading_dates=trading_dates,
                    sector_map=sector_map,
                    isin_map=isin_map,
                    nifty_filter=nifty_filter,
                    fixed_limit=f_lim,
                    dynamic_mode=d_mod,
                    apply_a2_risk_overlay=a2_ov,
                    risk_pct=r_pct,
                    use_stress_costs=stress,
                    experiment_tag=tag,
                )
                repro_results.append({
                    "scenario_id": res["scenario_id"],
                    "architecture": tag,
                    "risk_tier": res["risk_tier"],
                    "cost_schedule": res["cost_schedule"],
                    "completed_trades": res["completed_trades"],
                    "rejected_entries": res["rejected_entries_count"],
                    "win_rate_pct": res["win_rate_pct"],
                    "gross_pnl": res["gross_pnl"],
                    "total_costs": res["total_costs"],
                    "net_pnl": res["net_pnl"],
                    "net_profit_factor": res["net_profit_factor"],
                    "payoff_ratio": res["payoff_ratio"],
                    "max_drawdown_pct": res["max_drawdown_pct"],
                    "cagr_pct": res["cagr_pct"],
                })
                trade_store[res["scenario_id"]] = res["executed_trades"]
                print(f"[{res['scenario_id']}] Trades: {res['completed_trades']} | Net P&L: ₹{res['net_pnl']:,.2f} | PF: {res['net_profit_factor']:.2f} | Max DD: {res['max_drawdown_pct']:.2f}%")

    df_repro = pd.DataFrame(repro_results)
    df_repro.to_csv(REPORTS_DIR / "phase32j_5_reproduction.csv", index=False)
    print("Saved: phase32j_5_reproduction.csv")

    # =========================================================================
    # PART 2: STOCK CONCENTRATION AUDIT (FIXED MAX 2)
    # =========================================================================
    print("\n--- PART 2: STOCK CONCENTRATION AUDIT ---")
    max2_e2_off_sc = [s for s in trade_store.keys() if "EXP_A_FIXED_MAX2" in s and "2pct" in s and "OFFICIAL" in s][0]
    max2_e2_str_sc = [s for s in trade_store.keys() if "EXP_A_FIXED_MAX2" in s and "2pct" in s and "STRESS" in s][0]

    stock_conc_rows: List[Dict[str, Any]] = []
    for sc_name, use_stress in [(max2_e2_off_sc, False), (max2_e2_str_sc, True)]:
        trades = trade_store[sc_name]
        df_t = pd.DataFrame(trades)
        st_pnl = df_t.groupby("symbol")["net_pnl"].sum().sort_values(ascending=False)
        tot_net = st_pnl.sum()

        for k, label in [(0, "All Stocks"), (1, "Remove Top 1 Stock"), (3, "Remove Top 3 Stocks"), (5, "Remove Top 5 Stocks"), (10, "Remove Top 10 Stocks")]:
            top_k_syms = set(st_pnl.index[:k]) if k > 0 else set()
            sub_t = [t for t in trades if t["symbol"] not in top_k_syms]
            sub_pnl = sum(t["net_pnl"] for t in sub_t)
            sub_wins = [t for t in sub_t if t["net_pnl"] > 0]
            sub_loss = [t for t in sub_t if t["net_pnl"] <= 0]
            w_sum = sum(t["net_pnl"] for t in sub_wins)
            l_sum = abs(sum(t["net_pnl"] for t in sub_loss))
            sub_pf = (w_sum / l_sum) if l_sum > 0 else (99.0 if w_sum > 0 else 0.0)
            removed_share = ((tot_net - sub_pnl) / tot_net * 100.0) if tot_net > 0 else 0.0

            stock_conc_rows.append({
                "scenario_id": sc_name,
                "cost_schedule": "Stress (₹317/cr)" if use_stress else "Official (₹307/cr)",
                "pruning_level": label,
                "stocks_removed_count": k,
                "removed_stock_symbols": ", ".join(list(top_k_syms)),
                "remaining_trades": len(sub_t),
                "remaining_net_pnl": round(sub_pnl, 2),
                "remaining_profit_factor": round(sub_pf, 2),
                "removed_profit_share_pct": round(removed_share, 1),
                "is_profitable": sub_pnl > 0,
            })

    pd.DataFrame(stock_conc_rows).to_csv(REPORTS_DIR / "stock_concentration.csv", index=False)
    print("Saved: stock_concentration.csv")

    # Leave-One-Stock-Out (LOO) testing
    print("Running Leave-One-Stock-Out (LOO) testing for Fixed Max 2...")
    loo_stock_rows: List[Dict[str, Any]] = []
    trading_syms = sorted(list(set(t["symbol"] for t in trade_store[max2_e2_off_sc])))
    for sym_to_exclude in trading_syms:
        filtered_univ = {s: df for s, df in augmented_universe.items() if s != sym_to_exclude}
        for use_stress in [False, True]:
            res_loo = run_position_limits_simulation(
                augmented_universe=filtered_univ,
                trading_dates=trading_dates,
                sector_map=sector_map,
                isin_map=isin_map,
                nifty_filter=nifty_filter,
                fixed_limit=FixedLimitMode.A2_MAX_2,
                dynamic_mode=DynamicLimitMode.NONE,
                apply_a2_risk_overlay=False,
                risk_pct=0.02,
                use_stress_costs=use_stress,
                experiment_tag="LOO_STOCK",
            )
            base_pnl = 20552.50 if not use_stress else 19262.55
            delta = res_loo["net_pnl"] - base_pnl
            loo_stock_rows.append({
                "omitted_symbol": sym_to_exclude,
                "cost_schedule": "Stress (₹317/cr)" if use_stress else "Official (₹307/cr)",
                "completed_trades": res_loo["completed_trades"],
                "net_pnl": res_loo["net_pnl"],
                "profit_factor": res_loo["net_profit_factor"],
                "max_drawdown_pct": res_loo["max_drawdown_pct"],
                "delta_from_baseline_pnl": round(delta, 2),
                "impact_type": "POSITIVE_CONTRIBUTOR" if delta < 0 else "DRAG_REMOVED",
            })

    pd.DataFrame(loo_stock_rows).to_csv(REPORTS_DIR / "leave_one_stock_out.csv", index=False)
    print(f"Saved: leave_one_stock_out.csv ({len(loo_stock_rows)} runs)")

    # =========================================================================
    # PART 3: SECTOR CONCENTRATION AUDIT
    # =========================================================================
    print("\n--- PART 3: SECTOR CONCENTRATION AUDIT ---")
    sec_conc_rows: List[Dict[str, Any]] = []
    for sc_name, use_stress in [(max2_e2_off_sc, False), (max2_e2_str_sc, True)]:
        trades = trade_store[sc_name]
        df_t = pd.DataFrame(trades)
        sec_pnl = df_t.groupby("sector")["net_pnl"].sum().sort_values(ascending=False)
        tot_net = sec_pnl.sum()

        for k, label in [(0, "All Sectors"), (1, "Remove Top 1 Sector"), (2, "Remove Top 2 Sectors"), (3, "Remove Top 3 Sectors")]:
            top_k_secs = set(sec_pnl.index[:k]) if k > 0 else set()
            sub_t = [t for t in trades if t["sector"] not in top_k_secs]
            sub_pnl = sum(t["net_pnl"] for t in sub_t)
            sub_wins = [t for t in sub_t if t["net_pnl"] > 0]
            sub_loss = [t for t in sub_t if t["net_pnl"] <= 0]
            w_sum = sum(t["net_pnl"] for t in sub_wins)
            l_sum = abs(sum(t["net_pnl"] for t in sub_loss))
            sub_pf = (w_sum / l_sum) if l_sum > 0 else (99.0 if w_sum > 0 else 0.0)
            removed_share = ((tot_net - sub_pnl) / tot_net * 100.0) if tot_net > 0 else 0.0

            sec_conc_rows.append({
                "scenario_id": sc_name,
                "cost_schedule": "Stress (₹317/cr)" if use_stress else "Official (₹307/cr)",
                "pruning_level": label,
                "sectors_removed_count": k,
                "removed_sector_names": ", ".join(list(top_k_secs)),
                "remaining_trades": len(sub_t),
                "remaining_net_pnl": round(sub_pnl, 2),
                "remaining_profit_factor": round(sub_pf, 2),
                "removed_profit_share_pct": round(removed_share, 1),
                "is_profitable": sub_pnl > 0,
            })

    pd.DataFrame(sec_conc_rows).to_csv(REPORTS_DIR / "sector_concentration.csv", index=False)
    print("Saved: sector_concentration.csv")

    # Leave-One-Sector-Out (LOSO) testing
    print("Running Leave-One-Sector-Out (LOSO) testing for Fixed Max 2...")
    loo_sector_rows: List[Dict[str, Any]] = []
    unique_secs = sorted(list(set(sector_map.values())))
    for sec_to_exclude in unique_secs:
        filtered_univ = {s: df for s, df in augmented_universe.items() if sector_map.get(s) != sec_to_exclude}
        for use_stress in [False, True]:
            res_loso = run_position_limits_simulation(
                augmented_universe=filtered_univ,
                trading_dates=trading_dates,
                sector_map=sector_map,
                isin_map=isin_map,
                nifty_filter=nifty_filter,
                fixed_limit=FixedLimitMode.A2_MAX_2,
                dynamic_mode=DynamicLimitMode.NONE,
                apply_a2_risk_overlay=False,
                risk_pct=0.02,
                use_stress_costs=use_stress,
                experiment_tag="LOSO_SECTOR",
            )
            base_pnl = 20552.50 if not use_stress else 19262.55
            delta = res_loso["net_pnl"] - base_pnl
            loo_sector_rows.append({
                "omitted_sector": sec_to_exclude,
                "cost_schedule": "Stress (₹317/cr)" if use_stress else "Official (₹307/cr)",
                "completed_trades": res_loso["completed_trades"],
                "net_pnl": res_loso["net_pnl"],
                "profit_factor": res_loso["net_profit_factor"],
                "max_drawdown_pct": res_loso["max_drawdown_pct"],
                "delta_from_baseline_pnl": round(delta, 2),
                "impact_type": "POSITIVE_SECTOR" if delta < 0 else "DRAG_SECTOR",
            })

    pd.DataFrame(loo_sector_rows).to_csv(REPORTS_DIR / "leave_one_sector_out.csv", index=False)
    print(f"Saved: leave_one_sector_out.csv ({len(loo_sector_rows)} runs)")

    # =========================================================================
    # PART 4: TIME-PERIOD ROBUSTNESS
    # =========================================================================
    print("\n--- PART 4: TIME-PERIOD ROBUSTNESS ---")
    time_slices = [
        ("Full Sample (2017-2019)", date(2017, 1, 1), date(2019, 12, 31)),
        ("Calendar Year 2017", date(2017, 1, 1), date(2017, 12, 31)),
        ("Calendar Year 2018", date(2018, 1, 1), date(2018, 12, 31)),
        ("Calendar Year 2019", date(2019, 1, 1), date(2019, 12, 31)),
        ("H1 2017 (Jan-Jun)", date(2017, 1, 1), date(2017, 6, 30)),
        ("H2 2017 (Jul-Dec)", date(2017, 7, 1), date(2017, 12, 31)),
        ("H1 2018 (Jan-Jun)", date(2018, 1, 1), date(2018, 6, 30)),
        ("H2 2018 (Jul-Dec)", date(2018, 7, 1), date(2018, 12, 31)),
        ("H1 2019 (Jan-Jun)", date(2019, 1, 1), date(2019, 6, 30)),
        ("H2 2019 (Jul-Dec)", date(2019, 7, 1), date(2019, 12, 31)),
    ]

    time_rows: List[Dict[str, Any]] = []
    for slice_label, s_dt, e_dt in time_slices:
        sub_dates = [t for t in trading_dates if s_dt <= t.date() <= e_dt]
        for use_stress in [False, True]:
            res_time = run_position_limits_simulation(
                augmented_universe=augmented_universe,
                trading_dates=sub_dates,
                sector_map=sector_map,
                isin_map=isin_map,
                nifty_filter=nifty_filter,
                fixed_limit=FixedLimitMode.A2_MAX_2,
                dynamic_mode=DynamicLimitMode.NONE,
                apply_a2_risk_overlay=False,
                risk_pct=0.02,
                use_stress_costs=use_stress,
                experiment_tag="TIME_SLICE",
            )
            time_rows.append({
                "period_label": slice_label,
                "cost_schedule": "Stress (₹317/cr)" if use_stress else "Official (₹307/cr)",
                "start_date": s_dt.isoformat(),
                "end_date": e_dt.isoformat(),
                "completed_trades": res_time["completed_trades"],
                "wins": res_time["wins"],
                "losses": res_time["losses"],
                "win_rate_pct": res_time["win_rate_pct"],
                "net_pnl": res_time["net_pnl"],
                "profit_factor": res_time["net_profit_factor"],
                "payoff_ratio": res_time["payoff_ratio"],
                "max_drawdown_pct": res_time["max_drawdown_pct"],
                "cagr_pct": res_time["cagr_pct"],
                "is_profitable": res_time["net_pnl"] > 0,
            })

    pd.DataFrame(time_rows).to_csv(REPORTS_DIR / "time_period_robustness.csv", index=False)
    print("Saved: time_period_robustness.csv")

    # =========================================================================
    # PART 5: ENTRY PRIORITY AUDIT
    # =========================================================================
    print("\n--- PART 5: ENTRY PRIORITY AUDIT ---")
    priority_modes = [
        (EntryPriorityMode.ORIGINAL, "Original Deterministic Priority (ADX/Vol + Alpha tie-break)"),
        (EntryPriorityMode.CHOP_STRENGTH, "Trend-Strength Priority (Lowest Choppiness Index first)"),
        (EntryPriorityMode.REVERSE_ALPHA, "Neutral Tie-Break Priority (Reverse Alphabetical)"),
    ]

    prio_rows: List[Dict[str, Any]] = []
    for p_mode, p_desc in priority_modes:
        for use_stress in [False, True]:
            res_prio = run_entry_priority_simulation(
                augmented_universe=augmented_universe,
                trading_dates=trading_dates,
                sector_map=sector_map,
                isin_map=isin_map,
                nifty_filter=nifty_filter,
                fixed_limit=FixedLimitMode.A2_MAX_2,
                dynamic_mode=DynamicLimitMode.NONE,
                apply_a2_risk_overlay=False,
                risk_pct=0.02,
                use_stress_costs=use_stress,
                experiment_tag="ENTRY_PRIO",
                priority_mode=p_mode,
            )
            prio_rows.append({
                "entry_priority_rule": p_mode.value,
                "rule_description": p_desc,
                "cost_schedule": "Stress (₹317/cr)" if use_stress else "Official (₹307/cr)",
                "completed_trades": res_prio["completed_trades"],
                "rejected_entries": res_prio["rejected_entries_count"],
                "win_rate_pct": res_prio["win_rate_pct"],
                "net_pnl": res_prio["net_pnl"],
                "profit_factor": res_prio["net_profit_factor"],
                "payoff_ratio": res_prio["payoff_ratio"],
                "max_drawdown_pct": res_prio["max_drawdown_pct"],
                "cagr_pct": res_prio["cagr_pct"],
            })

    pd.DataFrame(prio_rows).to_csv(REPORTS_DIR / "entry_priority_comparison.csv", index=False)
    print("Saved: entry_priority_comparison.csv")

    # =========================================================================
    # PART 6: REJECTED ENTRY COUNTERFACTUAL AUDIT
    # =========================================================================
    print("\n--- PART 6: REJECTED ENTRY COUNTERFACTUAL AUDIT ---")
    df_rej_5 = pd.read_csv(ROOT_DIR / "reports" / "phase32j_5" / "rejected_entries.csv")
    max2_rejections = df_rej_5[df_rej_5["scenario_id"] == "EXP_A_FIXED_LIMITS_MAX2_NOA2_2pct_OFFICIAL"].copy()
    print(f"Total rejected entries in Max 2 E2 Official: {len(max2_rejections)}")

    max2_rejections["date_dt"] = pd.to_datetime(max2_rejections["date"]).dt.date
    max2_rejections["exit_dt"] = pd.to_datetime(max2_rejections["hypo_exit_date"]).dt.date

    rej_audit_records: List[Dict[str, Any]] = []
    for idx, r in max2_rejections.iterrows():
        simul_on_entry = max2_rejections[(max2_rejections["date_dt"] <= r["date_dt"]) & (max2_rejections["exit_dt"] >= r["date_dt"])]
        rej_audit_records.append({
            "rejection_id": idx + 1,
            "entry_date": r["date"],
            "symbol": r["symbol"],
            "sector": r["sector"],
            "shares": r["shares"],
            "fill_price": r["fill_price"],
            "hypo_exit_date": r["hypo_exit_date"],
            "hypo_exit_price": r["hypo_exit_price"],
            "hypo_holding_days": r["hypo_holding_days"],
            "hypo_gross_pnl": r["hypo_gross_pnl"],
            "hypo_total_costs": r["hypo_total_costs"],
            "hypo_net_pnl": r["hypo_net_pnl"],
            "hypo_outcome": r["hypo_outcome"],
            "concurrent_rejected_active": len(simul_on_entry),
            "competes_for_capital": len(simul_on_entry) > 1,
        })

    pd.DataFrame(rej_audit_records).to_csv(REPORTS_DIR / "rejected_entry_audit.csv", index=False)
    print("Saved: rejected_entry_audit.csv")

    # =========================================================================
    # PART 7: 10,000 BOOTSTRAP RESAMPLING ANALYSIS
    # =========================================================================
    print("\n--- PART 7: 10,000 BOOTSTRAP RESAMPLING ANALYSIS ---")
    boot_rows: List[Dict[str, Any]] = []
    for sc_name, trades in trade_store.items():
        if "EXP_A_FIXED_MAX2" in sc_name:
            b_res = compute_bootstrap_results(trades, n_boot=10000)
            boot_rows.append({
                "scenario_id": sc_name,
                "risk_tier": "E1 (1%)" if "1pct" in sc_name else ("E2 (2%)" if "2pct" in sc_name else "E3 (3%)"),
                "cost_schedule": "Stress (₹317/cr)" if "STRESS" in sc_name else "Official (₹307/cr)",
                **b_res,
                "ci_crosses_zero": b_res["ci_95_lower"] <= 0,
            })

    pd.DataFrame(boot_rows).to_csv(REPORTS_DIR / "bootstrap_results.csv", index=False)
    print("Saved: bootstrap_results.csv")

    # =========================================================================
    # PART 8: 7-GATE SCORECARD EVALUATION
    # =========================================================================
    print("\n--- PART 8: 7-GATE SCORECARD EVALUATION ---")
    scorecard_rows: List[Dict[str, Any]] = []
    for r in repro_results:
        if r["architecture"] == "EXP_A_FIXED_MAX2":
            trades = trade_store[r["scenario_id"]]
            b_res = compute_bootstrap_results(trades, n_boot=10000)

            sorted_t = sorted(trades, key=lambda x: x["net_pnl"], reverse=True)
            ex_top3_pnl = sum(t["net_pnl"] for t in sorted_t[3:])

            g1 = r["net_pnl"] > 0
            g2 = r["net_profit_factor"] >= 1.50
            g3 = r["payoff_ratio"] >= 1.80
            g4 = r["max_drawdown_pct"] <= 15.0
            g5 = r["cagr_pct"] >= 12.0
            g6 = b_res["ci_95_lower"] > 0
            g7 = ex_top3_pnl > 0

            passed = sum([g1, g2, g3, g4, g5, g6, g7])

            scorecard_rows.append({
                "scenario_id": r["scenario_id"],
                "risk_tier": r["risk_tier"],
                "cost_schedule": r["cost_schedule"],
                "completed_trades": r["completed_trades"],
                "net_pnl": r["net_pnl"],
                "gate_1_pnl_gt_0": "PASS" if g1 else "FAIL",
                "profit_factor": r["net_profit_factor"],
                "gate_2_pf_ge_1_50": "PASS" if g2 else "FAIL",
                "payoff_ratio": r["payoff_ratio"],
                "gate_3_payoff_ge_1_80": "PASS" if g3 else "FAIL",
                "max_drawdown_pct": r["max_drawdown_pct"],
                "gate_4_max_dd_le_15": "PASS" if g4 else "FAIL",
                "cagr_pct": r["cagr_pct"],
                "gate_5_cagr_ge_12": "PASS" if g5 else "FAIL",
                "ci_95_lower": b_res["ci_95_lower"],
                "gate_6_ci95_gt_0": "PASS" if g6 else "FAIL",
                "ex_top3_net_pnl": round(ex_top3_pnl, 2),
                "gate_7_survive_top3": "PASS" if g7 else "FAIL",
                "passed_gates_count": f"{passed}/7",
                "scenario_verdict": "CONDITIONAL",
            })

    pd.DataFrame(scorecard_rows).to_csv(REPORTS_DIR / "gate_scorecard.csv", index=False)
    print("Saved: gate_scorecard.csv")

    print("\nPhase 32J.6 Robustness Audit simulation complete!")


if __name__ == "__main__":
    main()
