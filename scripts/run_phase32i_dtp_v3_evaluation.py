"""
SignalForge — Phase 32I: DTP-V3 Comprehensive Evaluation & Deliverable Generator
================================================================================
File: scripts/run_phase32i_dtp_v3_evaluation.py

Executes reproducible evaluation of DTP-V3 against frozen DTP-V2 benchmark
on authorized 2017-2019 dataset (21 approved NSE equities, 739 sessions).
Generates all Phase 32I CSV deliverables and diagnostic statistics.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
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

# Benchmark DTP-V2
from src.strategy.dtp_v2.config import (
    DTPV2Config,
    DTPExitReason as DTPExitReasonV2,
    DTPRegimeState as DTPRegimeStateV2,
    OrderAction as OrderActionV2,
)
from src.strategy.dtp_v2.cost_integration import calculate_dtp_roundtrip_costs as calc_costs_v2
from src.strategy.dtp_v2.indicators import calculate_dtp_indicators as calc_ind_v2
from src.strategy.dtp_v2.market_filter import evaluate_breadth_regime as eval_regime_v2
from src.strategy.dtp_v2.portfolio_rules import DTPPortfolioTracker as PortfolioTrackerV2
from src.strategy.dtp_v2.risk_manager import calculate_dtp_position_size as calc_pos_size_v2
from src.strategy.dtp_v2.signal_engine import (
    DTPEODSignal as DTPEODSignalV2,
    DTPPositionState as DTPPositionStateV2,
    evaluate_exit_conditions as eval_exits_v2,
    evaluate_next_open_execution as eval_open_v2,
    generate_eod_signal as gen_signal_v2,
)

# New DTP-V3
from src.strategy.dtp_v3.config import (
    DTPV3Config,
    DTPExitReason as DTPExitReasonV3,
    DTPRegimeState as DTPRegimeStateV3,
    OrderAction as OrderActionV3,
)
from src.strategy.dtp_v3.cost_integration import calculate_dtp_roundtrip_costs as calc_costs_v3
from src.strategy.dtp_v3.indicators import calculate_dtp_indicators as calc_ind_v3, calculate_choppiness_index
from src.strategy.dtp_v3.market_filter import evaluate_breadth_regime as eval_regime_v3
from src.strategy.dtp_v3.portfolio_rules import DTPPortfolioTracker as PortfolioTrackerV3
from src.strategy.dtp_v3.risk_manager import calculate_dtp_position_size as calc_pos_size_v3
from src.strategy.dtp_v3.signal_engine import (
    DTPEODSignal as DTPEODSignalV3,
    DTPPositionState as DTPPositionStateV3,
    evaluate_exit_conditions as eval_exits_v3,
    evaluate_next_open_execution as eval_open_v3,
    generate_eod_signal as gen_signal_v3,
)

REPORTS_DIR = PROJECT_ROOT / "reports" / "phase32i"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def run_dtp_simulation(
    version: str, # "DTP-V2" or "DTP-V3"
    augmented_universe: Dict[str, pd.DataFrame],
    trading_dates: List[pd.Timestamp],
    risk_pct: float = 0.01,
    use_stress_costs: bool = False,
    initial_capital: float = 100000.0,
    use_chop_filter: bool = True,
    max_chop_index: float = 60.0,
    require_upper_half_close: bool = True,
) -> Dict[str, Any]:
    scenario_name = f"{version}_{int(risk_pct*100)}pct_{'STRESS' if use_stress_costs else 'OFFICIAL'}"

    if version == "DTP-V2":
        cfg = DTPV2Config(
            risk_fraction_per_trade=risk_pct,
            symbol_sector_map=EXPANDED_SECTOR_MAP,
            symbol_isin_map=EXPANDED_ISIN_MAP,
        )
        portfolio = PortfolioTrackerV2(initial_capital=initial_capital, config=cfg)
        eval_next_open = eval_open_v2
        calc_pos_size = calc_pos_size_v2
        eval_exits = eval_exits_v2
        eval_regime = eval_regime_v2
        gen_signal = gen_signal_v2
        calc_costs = calc_costs_v2
        PosStateClass = DTPPositionStateV2
        enter_action = OrderActionV2.ENTER_LONG
    else:
        cfg = DTPV3Config(
            risk_fraction_per_trade=risk_pct,
            symbol_sector_map=EXPANDED_SECTOR_MAP,
            symbol_isin_map=EXPANDED_ISIN_MAP,
            use_chop_filter=use_chop_filter,
            max_chop_index=max_chop_index,
            require_upper_half_close=require_upper_half_close,
        )
        portfolio = PortfolioTrackerV3(initial_capital=initial_capital, config=cfg)
        eval_next_open = eval_open_v3
        calc_pos_size = calc_pos_size_v3
        eval_exits = eval_exits_v3
        eval_regime = eval_regime_v3
        gen_signal = gen_signal_v3
        calc_costs = calc_costs_v3
        PosStateClass = DTPPositionStateV3
        enter_action = OrderActionV3.ENTER_LONG

    positions_state: Dict[str, Any] = {}
    pending_signals: Dict[str, Tuple[Any, Tuple[float, float, str]]] = {}
    executed_trades: List[Dict[str, Any]] = []
    daily_records: List[Dict[str, Any]] = []
    trade_counter = 0

    peak_equity = initial_capital
    max_drawdown = 0.0

    for day_idx, current_ts in enumerate(trading_dates):
        current_dt = current_ts.date()

        # Step A: Next-Day Open Execution
        if pending_signals:
            sorted_pending = sorted(pending_signals.items(), key=lambda item: item[1][1])
            for sym, (sig, prio_tuple) in sorted_pending:
                today_open = float(augmented_universe[sym].loc[current_ts, "open"])
                action, fill_price, action_msg = eval_next_open(
                    signal=sig,
                    next_open_price=today_open,
                    config=cfg,
                )
                if action != enter_action:
                    continue

                curr_prices = {s: float(augmented_universe[s].loc[current_ts, "open"]) for s in APPROVED_21_SYMBOLS}
                equity = portfolio.get_portfolio_equity(curr_prices)
                sector = cfg.symbol_sector_map.get(sym, "General")
                sec_exp = portfolio.get_sector_exposure(sector, curr_prices)

                if version == "DTP-V3":
                    curr_dd = portfolio.get_current_drawdown(curr_prices)
                    shares, size_msg = calc_pos_size(
                        equity=equity,
                        available_cash=portfolio.cash,
                        entry_price=fill_price,
                        stop_price=sig.initial_stop_price,
                        sector=sector,
                        current_sector_exposure=sec_exp,
                        current_drawdown_pct=curr_dd,
                        config=cfg,
                    )
                else:
                    shares, size_msg = calc_pos_size(
                        equity=equity,
                        available_cash=portfolio.cash,
                        entry_price=fill_price,
                        stop_price=sig.initial_stop_price,
                        sector=sector,
                        current_sector_exposure=sec_exp,
                        config=cfg,
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
                order_id = f"{version}_{trade_counter:04d}_BUY_{sym}_{current_dt.isoformat()}"
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
                positions_state[sym] = PosStateClass(
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

            # Last day liquidation
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

            reason_obj, exit_px, exit_msg = eval_exits(
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

        # Process exits
        for sym, reason_str, exit_px, exit_msg in full_exits:
            active_pos = portfolio.positions[sym]
            isin = cfg.symbol_isin_map.get(sym, "DEFAULT_ISIN")
            breakdown, cost_summary = calc_costs(
                symbol=sym,
                isin=isin,
                entry_date=active_pos.entry_date,
                exit_date=current_dt,
                entry_price=active_pos.entry_price,
                exit_price=exit_px,
                quantity=active_pos.quantity,
                use_stress_profile=use_stress_costs,
                order_id_prefix=f"{version}",
            )
            net_proceeds = cost_summary.sell_turnover - cost_summary.total_friction_costs
            portfolio.close_position(sym, exit_px, net_proceeds)
            pos_state = positions_state.pop(sym, None)

            gross_pnl = (exit_px - active_pos.entry_price) * active_pos.quantity
            tot_costs = float(cost_summary.total_friction_costs)
            net_pnl = gross_pnl - tot_costs

            executed_trades.append({
                "scenario_id": scenario_name,
                "version": version,
                "symbol": sym,
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

        # Step C: EOD Signal Evaluation for Bar T
        reg_res = eval_regime(augmented_universe, bar_idx=day_idx, config=cfg)
        regime_state = reg_res[0] if isinstance(reg_res, tuple) else reg_res
        is_bearish = (regime_state == "BEARISH") or (hasattr(regime_state, "value") and regime_state.value == "BEARISH") or (regime_state == "UNKNOWN")
        if day_idx < len(trading_dates) - 2 and not is_bearish:
            for sym in APPROVED_21_SYMBOLS:
                if sym in portfolio.positions:
                    continue
                df_sym = augmented_universe[sym]
                sig = gen_signal(
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
                    pending_signals[sym] = (sig, prio)

        # Daily Equity Tracking
        curr_eod_px = {s: float(augmented_universe[s].loc[current_ts, "close"]) for s in APPROVED_21_SYMBOLS}
        eod_equity = portfolio.get_portfolio_equity(curr_eod_px)
        invested_cap = portfolio.total_invested_capital()
        util_pct = (invested_cap / eod_equity) * 100.0 if eod_equity > 0 else 0.0

        if eod_equity > peak_equity:
            peak_equity = eod_equity
        dd_amt = peak_equity - eod_equity
        dd_pct = (dd_amt / peak_equity) * 100.0 if peak_equity > 0 else 0.0
        if dd_pct > max_drawdown:
            max_drawdown = dd_pct

        daily_records.append({
            "scenario_id": scenario_name,
            "date": current_dt,
            "equity": round(eod_equity, 2),
            "cash": round(portfolio.cash, 2),
            "invested_capital": round(invested_cap, 2),
            "capital_utilization_pct": round(util_pct, 2),
            "drawdown_pct": round(dd_pct, 2),
            "open_positions": portfolio.position_count,
        })

    # Summary Statistics
    n_trades = len(executed_trades)
    df_t = pd.DataFrame(executed_trades) if n_trades > 0 else pd.DataFrame(columns=["net_pnl", "gross_pnl", "total_costs", "holding_days", "exit_date", "entry_date"])
    df_d = pd.DataFrame(daily_records)

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
    avg_util = round(float(df_d["capital_utilization_pct"].mean()), 2)

    # Consecutive losses
    max_consec_losses = 0
    current_consec = 0
    for pnl in df_t["net_pnl"]:
        if pnl <= 0:
            current_consec += 1
            if current_consec > max_consec_losses:
                max_consec_losses = current_consec
        else:
            current_consec = 0

    return_to_dd = round(cagr / max_drawdown, 2) if max_drawdown > 0 else 999.0

    # Yearly breakdown
    yearly = {}
    if n_trades > 0:
        df_t["exit_year"] = pd.to_datetime(df_t["exit_date"]).dt.year
        for yr, grp in df_t.groupby("exit_year"):
            yearly[int(yr)] = {
                "trades": len(grp),
                "net_pnl": round(float(grp["net_pnl"].sum()), 2),
                "wr": round(len(grp[grp["net_pnl"] > 0]) / len(grp) * 100.0, 1),
            }

    return {
        "scenario_id": scenario_name,
        "version": version,
        "risk_fraction_pct": round(risk_pct * 100.0, 2),
        "cost_schedule": "Stress (₹317/cr)" if use_stress_costs else "Official (₹307/cr)",
        "completed_trades": n_trades,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(wr, 2),
        "gross_pnl": round(gross_pnl, 2),
        "total_costs": round(tot_costs, 2),
        "net_pnl": round(net_pnl, 2),
        "cagr_pct": cagr,
        "net_profit_factor": pf,
        "payoff_ratio": payoff,
        "max_drawdown_pct": round(max_drawdown, 2),
        "avg_holding_days": avg_hold,
        "capital_utilization_pct": avg_util,
        "max_consecutive_losses": max_consec_losses,
        "return_to_drawdown_ratio": return_to_dd,
        "yearly": yearly,
        "df_trades": df_t,
        "df_daily": df_d,
    }


def main():
    print("=" * 80)
    print("SignalForge — Phase 32I: DTP-V3 Comprehensive Evaluation")
    print("=" * 80)

    print("\n1. Loading and resynchronizing 21-stock daily universe...")
    raw_universe = load_and_resample_21_universe()
    trading_dates = list(raw_universe[APPROVED_21_SYMBOLS[0]].index)

    cfg_v2 = DTPV2Config(symbol_sector_map=EXPANDED_SECTOR_MAP, symbol_isin_map=EXPANDED_ISIN_MAP)
    cfg_v3 = DTPV3Config(symbol_sector_map=EXPANDED_SECTOR_MAP, symbol_isin_map=EXPANDED_ISIN_MAP)

    print("\n2. Precomputing indicators for DTP-V2 and DTP-V3...")
    aug_v2 = {}
    aug_v3 = {}
    for sym in APPROVED_21_SYMBOLS:
        aug_v2[sym] = calc_ind_v2(raw_universe[sym], config=cfg_v2)
        aug_v3[sym] = calc_ind_v3(raw_universe[sym], config=cfg_v3)

    print(f"Loaded {len(APPROVED_21_SYMBOLS)} symbols across {len(trading_dates)} sessions ({trading_dates[0].date()} to {trading_dates[-1].date()}).")

    # Scenarios to run:
    # 1. DTP-V2 Baseline (Official & Stress at 1% risk)
    # 2. DTP-V3 (E1: 1%, E2: 2%, E3: 3% under Official and Stress)
    scenarios = [
        ("DTP-V2", aug_v2, 0.01, False), # DTP-V2 Official
        ("DTP-V2", aug_v2, 0.01, True),  # DTP-V2 Stress
        ("DTP-V3", aug_v3, 0.01, False), # DTP-V3 E1 Official
        ("DTP-V3", aug_v3, 0.01, True),  # DTP-V3 E1 Stress
        ("DTP-V3", aug_v3, 0.02, False), # DTP-V3 E2 Official
        ("DTP-V3", aug_v3, 0.02, True),  # DTP-V3 E2 Stress
        ("DTP-V3", aug_v3, 0.03, False), # DTP-V3 E3 Official
        ("DTP-V3", aug_v3, 0.03, True),  # DTP-V3 E3 Stress
    ]

    all_results = []
    for ver, aug_dict, r_pct, use_stress in scenarios:
        sched = "Stress (₹317/cr)" if use_stress else "Official (₹307/cr)"
        print(f"\nRunning {ver} at {int(r_pct*100)}% risk under {sched}...")
        res = run_dtp_simulation(
            version=ver,
            augmented_universe=aug_dict,
            trading_dates=trading_dates,
            risk_pct=r_pct,
            use_stress_costs=use_stress,
            initial_capital=100000.0,
        )
        all_results.append(res)
        print(f"  Trades: {res['completed_trades']} | WinRate: {res['win_rate_pct']}% | Net: ₹{res['net_pnl']:,.2f} | PF: {res['net_profit_factor']} | Payoff: {res['payoff_ratio']} | MaxDD: {res['max_drawdown_pct']}% | CAGR: {res['cagr_pct']}%")
        print(f"  Yearly: {res['yearly']}")

    # 1. Create risk_comparison.csv
    # Focuses on DTP-V3 E1, E2, E3 across both cost schedules
    risk_rows = []
    for res in all_results:
        if res["version"] == "DTP-V3":
            cfg_name = f"E{int(res['risk_fraction_pct'])}"
            risk_rows.append({
                "risk_configuration": cfg_name,
                "risk_fraction_pct": res["risk_fraction_pct"],
                "cost_schedule": res["cost_schedule"],
                "completed_trades": res["completed_trades"],
                "win_rate_pct": res["win_rate_pct"],
                "gross_pnl": res["gross_pnl"],
                "total_costs": res["total_costs"],
                "net_pnl": res["net_pnl"],
                "cagr_pct": res["cagr_pct"],
                "net_profit_factor": res["net_profit_factor"],
                "payoff_ratio": res["payoff_ratio"],
                "max_drawdown_pct": res["max_drawdown_pct"],
                "capital_utilization_pct": res["capital_utilization_pct"],
                "max_consecutive_losses": res["max_consecutive_losses"],
                "return_to_drawdown_ratio": res["return_to_drawdown_ratio"],
            })
    df_risk = pd.DataFrame(risk_rows)
    risk_path = REPORTS_DIR / "risk_comparison.csv"
    df_risk.to_csv(risk_path, index=False)
    print(f"\nSaved {risk_path}")

    # 2. Create strategy_comparison.csv
    # Compares DTP-V1 (from Phase 32D.3/32E.2), DTP-V2, and DTP-V3
    strat_rows = []
    # Add DTP-V1 baseline reference
    strat_rows.append({
        "strategy_version": "DTP-V1",
        "risk_fraction_pct": 1.0,
        "cost_schedule": "Official (₹307/cr)",
        "completed_trades": 43,
        "win_rate_pct": 46.51,
        "gross_pnl": 10582.40,
        "total_costs": 5592.51,
        "net_pnl": 4989.89,
        "cagr_pct": 1.63,
        "net_profit_factor": 1.34,
        "payoff_ratio": 1.54,
        "max_drawdown_pct": 4.54,
    })
    strat_rows.append({
        "strategy_version": "DTP-V1",
        "risk_fraction_pct": 1.0,
        "cost_schedule": "Stress (₹317/cr)",
        "completed_trades": 43,
        "win_rate_pct": 46.51,
        "gross_pnl": 10582.40,
        "total_costs": 6344.20,
        "net_pnl": 4238.20,
        "cagr_pct": 1.39,
        "net_profit_factor": 1.28,
        "payoff_ratio": 1.48,
        "max_drawdown_pct": 4.86,
    })

    for res in all_results:
        strat_rows.append({
            "strategy_version": res["version"],
            "risk_fraction_pct": res["risk_fraction_pct"],
            "cost_schedule": res["cost_schedule"],
            "completed_trades": res["completed_trades"],
            "win_rate_pct": res["win_rate_pct"],
            "gross_pnl": res["gross_pnl"],
            "total_costs": res["total_costs"],
            "net_pnl": res["net_pnl"],
            "cagr_pct": res["cagr_pct"],
            "net_profit_factor": res["net_profit_factor"],
            "payoff_ratio": res["payoff_ratio"],
            "max_drawdown_pct": res["max_drawdown_pct"],
        })
    df_strat = pd.DataFrame(strat_rows)
    strat_path = REPORTS_DIR / "strategy_comparison.csv"
    df_strat.to_csv(strat_path, index=False)
    print(f"Saved {strat_path}")

    # 3. Create monthly_performance.csv
    # Calculate monthly metrics across all 36 calendar months for DTP-V3 E1 and E2
    # Reference: DTP-V3 E1 Official and DTP-V3 E2 Official
    v3_e1_trades = all_results[2]["df_trades"].copy()
    v3_e2_trades = all_results[4]["df_trades"].copy()

    monthly_rows = []
    all_months = pd.date_range("2017-01-01", "2019-12-31", freq="MS")

    for m_start in all_months:
        yr = m_start.year
        mo = m_start.month
        m_end = (m_start + pd.offsets.MonthEnd(1)).date()
        m_start_d = m_start.date()

        # For E1 Official
        e1_m = v3_e1_trades[(v3_e1_trades["exit_date"] >= m_start_d) & (v3_e1_trades["exit_date"] <= m_end)]
        n_t_e1 = len(e1_m)
        gross_e1 = float(e1_m["gross_pnl"].sum()) if n_t_e1 > 0 else 0.0
        costs_e1 = float(e1_m["total_costs"].sum()) if n_t_e1 > 0 else 0.0
        net_e1 = float(e1_m["net_pnl"].sum()) if n_t_e1 > 0 else 0.0
        wins_e1 = len(e1_m[e1_m["net_pnl"] > 0]) if n_t_e1 > 0 else 0
        loss_e1 = len(e1_m[e1_m["net_pnl"] <= 0]) if n_t_e1 > 0 else 0
        wr_e1 = (wins_e1 / n_t_e1 * 100.0) if n_t_e1 > 0 else 0.0
        gw_e1 = float(e1_m[e1_m["net_pnl"] > 0]["net_pnl"].sum()) if wins_e1 > 0 else 0.0
        gl_e1 = float(abs(e1_m[e1_m["net_pnl"] <= 0]["net_pnl"].sum())) if loss_e1 > 0 else 0.0
        pf_e1 = round(gw_e1 / gl_e1, 2) if gl_e1 > 0 else (999.0 if gw_e1 > 0 else 0.0)

        # For E2 Official
        e2_m = v3_e2_trades[(v3_e2_trades["exit_date"] >= m_start_d) & (v3_e2_trades["exit_date"] <= m_end)]
        n_t_e2 = len(e2_m)
        gross_e2 = float(e2_m["gross_pnl"].sum()) if n_t_e2 > 0 else 0.0
        costs_e2 = float(e2_m["total_costs"].sum()) if n_t_e2 > 0 else 0.0
        net_e2 = float(e2_m["net_pnl"].sum()) if n_t_e2 > 0 else 0.0
        wins_e2 = len(e2_m[e2_m["net_pnl"] > 0]) if n_t_e2 > 0 else 0
        loss_e2 = len(e2_m[e2_m["net_pnl"] <= 0]) if n_t_e2 > 0 else 0
        wr_e2 = (wins_e2 / n_t_e2 * 100.0) if n_t_e2 > 0 else 0.0
        gw_e2 = float(e2_m[e2_m["net_pnl"] > 0]["net_pnl"].sum()) if wins_e2 > 0 else 0.0
        gl_e2 = float(abs(e2_m[e2_m["net_pnl"] <= 0]["net_pnl"].sum())) if loss_e2 > 0 else 0.0
        pf_e2 = round(gw_e2 / gl_e2, 2) if gl_e2 > 0 else (999.0 if gw_e2 > 0 else 0.0)

        monthly_rows.append({
            "year": yr,
            "month": mo,
            "month_label": m_start.strftime("%Y-%m"),
            "e1_trades": n_t_e1,
            "e1_gross_pnl": round(gross_e1, 2),
            "e1_costs": round(costs_e1, 2),
            "e1_net_pnl": round(net_e1, 2),
            "e1_monthly_return_pct": round((net_e1 / 100000.0) * 100.0, 2),
            "e1_wins": wins_e1,
            "e1_losses": loss_e1,
            "e1_win_rate_pct": round(wr_e1, 1),
            "e1_profit_factor": pf_e1,
            "e2_trades": n_t_e2,
            "e2_gross_pnl": round(gross_e2, 2),
            "e2_costs": round(costs_e2, 2),
            "e2_net_pnl": round(net_e2, 2),
            "e2_monthly_return_pct": round((net_e2 / 100000.0) * 100.0, 2),
            "e2_wins": wins_e2,
            "e2_losses": loss_e2,
            "e2_win_rate_pct": round(wr_e2, 1),
            "e2_profit_factor": pf_e2,
        })

    df_monthly = pd.DataFrame(monthly_rows)
    monthly_path = REPORTS_DIR / "monthly_performance.csv"
    df_monthly.to_csv(monthly_path, index=False)
    print(f"Saved {monthly_path}")

    # Print summary metrics for quick reporting
    print("\n" + "=" * 80)
    print("PHASE 32I EVALUATION COMPLETE — SUMMARY MATRIX")
    print("=" * 80)
    for res in all_results:
        print(f"{res['scenario_id']:<35} | Trades: {res['completed_trades']:<2} | WR: {res['win_rate_pct']:>5.1f}% | Net: ₹{res['net_pnl']:>9.2f} | PF: {res['net_profit_factor']:>4.2f} | Payoff: {res['payoff_ratio']:>4.2f} | MaxDD: {res['max_drawdown_pct']:>5.2f}% | CAGR: {res['cagr_pct']:>5.2f}% | Util: {res['capital_utilization_pct']:>5.1f}% | ConsecLoss: {res['max_consecutive_losses']}")


if __name__ == "__main__":
    main()
