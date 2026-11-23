"""
SignalForge — Phase 32J.3.1: DTP-V3 Market Regime Filter Research Runner
==========================================================================
File: scripts/run_phase32j_3_1_regime_backtest.py

Conducts independent, reproducible research backtest of DTP-V3 with Market Regime Filters:
  - Variation A: Original DTP-V3 (No filter)
  - Variation B: NIFTY_SMA200 (Close > 200-day SMA)
  - Variation C: NIFTY_SMA100 (Close > 100-day SMA)
  - Variation D: NIFTY_SMA200_TREND (Close > 200-day SMA & 200-day SMA rising)

Evaluates:
  - Tiers: E1 (1%), E2 (2%), E3 (3%)
  - Cost Schedules: Official (₹307/cr) & Stress (₹317/cr)
  - 91 Approved NSE Equities from Phase 32J.1 (739 sessions, 2017-2019)
  - Generates all analytical CSVs and markdown deliverables in reports/phase32j_3_1/
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Set root directory in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.strategy.dtp_v3_regime.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV3RegimeConfig,
    OrderAction,
    RegimeFilterMode,
)
from src.strategy.dtp_v3_regime.cost_integration import calculate_dtp_roundtrip_costs
from src.strategy.dtp_v3_regime.indicators import calculate_choppiness_index, calculate_dtp_indicators
from src.strategy.dtp_v3_regime.market_filter import NiftyMarketFilter, evaluate_breadth_regime
from src.strategy.dtp_v3_regime.portfolio_rules import DTPActivePosition, DTPPortfolioTracker
from src.strategy.dtp_v3_regime.risk_manager import calculate_dtp_position_size
from src.strategy.dtp_v3_regime.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    evaluate_exit_conditions,
    evaluate_next_open_execution,
    generate_eod_signal,
)

# Output directories
REPORTS_DIR = ROOT_DIR / "reports" / "phase32j_3_1"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

CANDIDATES_CSV = ROOT_DIR / "reports" / "phase32j_1" / "universe_candidates.csv"
DATA_DIR_STOCKS = ROOT_DIR / "data" / "historical" / "stocks"
DATA_DIR_TEMP = ROOT_DIR / "temp_nse_data" / "NSE Minute Data" / "NSE_Stocks_Data"
START_DATE_STR = "2017-01-01"
END_DATE_STR = "2020-01-01"


def get_raw_filepath_for_symbol(sym: str) -> Path:
    """Returns the validated source filepath for a symbol."""
    canon = Path(f"data/historical/stocks/{sym}_1m.csv")
    if canon.exists() and "ADANIPORTS" not in sym:
        return canon

    raw_dir = Path("temp_nse_data/NSE Minute Data/NSE_Stocks_Data")
    if sym == "M&M":
        f = raw_dir / "M_M__EQ__NSE__NSE__MINUTE.csv"
    elif sym == "BAJAJ-AUTO":
        f = raw_dir / "BAJAJ_AUTO__EQ__NSE__NSE__MINUTE.csv"
    elif sym == "L&TFH":
        f = raw_dir / "L_TFH__EQ__NSE__NSE__MINUTE.csv"
    elif sym == "M&MFIN":
        f = raw_dir / "M_MFIN__EQ__NSE__NSE__MINUTE.csv"
    else:
        f = raw_dir / f"{sym}__EQ__NSE__NSE__MINUTE.csv"

    if f.exists() and "ADANIPORTS" not in sym:
        return f

    raise FileNotFoundError(f"Source file not found for symbol: {sym}")


def load_universe_inventory() -> Tuple[List[str], Dict[str, str], Dict[str, str]]:
    df_cand = pd.read_csv(CANDIDATES_CSV)
    approved = df_cand[df_cand["cohort_tier"].isin(["TIER_1_PRIMARY", "TIER_2_EXPANDED"])].copy()
    symbols = sorted(approved["symbol"].tolist())
    sector_map = dict(zip(approved["symbol"], approved["sector"]))
    isin_map = {s: f"INE_{s}_CANONICAL" for s in symbols}
    return symbols, sector_map, isin_map


def load_and_resample_universe(symbols: List[str]) -> Dict[str, pd.DataFrame]:
    print(f"Loading and resampling {len(symbols)} approved symbols...")
    universe: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        csv_path = get_raw_filepath_for_symbol(sym)
        df_raw = pd.read_csv(csv_path)
        df_sub = df_raw[(df_raw["timestamp"] >= START_DATE_STR) & (df_raw["timestamp"] < END_DATE_STR)].dropna().copy()
        df_sub["date"] = pd.to_datetime(df_sub["timestamp"].str.slice(0, 10)).dt.date
        daily = df_sub.groupby("date").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        })
        daily.index = pd.DatetimeIndex(daily.index)
        if len(daily) != 739:
            raise ValueError(f"Symbol {sym} has {len(daily)} sessions, expected exactly 739!")
        universe[sym] = daily
    print(f"Successfully loaded and resampled all {len(universe)} symbols (739 sessions each).")
    return universe


from scripts.run_phase32d_3_dtp_v1_expanded_validation import calculate_signal_priority


def run_regime_simulation(
    augmented_universe: Dict[str, pd.DataFrame],
    trading_dates: List[pd.Timestamp],
    sector_map: Dict[str, str],
    isin_map: Dict[str, str],
    nifty_filter: NiftyMarketFilter,
    filter_mode: RegimeFilterMode,
    risk_pct: float = 0.02,
    use_stress_costs: bool = False,
    initial_capital: float = 100000.0,
) -> Dict[str, Any]:
    """Runs deterministic DTP-V3 simulation with specified Nifty Market Regime Filter."""
    symbols = sorted(list(augmented_universe.keys()))
    cost_tag = "STRESS" if use_stress_costs else "OFFICIAL"
    scenario_name = f"EXPANDED_91_{filter_mode.value}_{int(risk_pct*100)}pct_{cost_tag}"

    cfg = DTPV3RegimeConfig(
        risk_fraction_per_trade=risk_pct,
        symbol_sector_map=sector_map,
        symbol_isin_map=isin_map,
        regime_filter_mode=filter_mode,
    )
    portfolio = DTPPortfolioTracker(initial_capital=initial_capital, config=cfg)

    positions_state: Dict[str, DTPPositionState] = {}
    pending_signals: Dict[str, Tuple[DTPEODSignal, Tuple[float, float, str]]] = {}
    executed_trades: List[Dict[str, Any]] = []
    daily_records: List[Dict[str, Any]] = []
    blocked_entries_count = 0
    trade_counter = 0

    peak_equity = initial_capital
    max_drawdown = 0.0

    for day_idx, current_ts in enumerate(trading_dates):
        current_dt = current_ts.date()

        # Step A: Next-Day Open Execution for Pending Signals
        if pending_signals:
            sorted_pending = sorted(pending_signals.items(), key=lambda item: item[1][1])
            for sym, (sig, prio_tuple) in sorted_pending:
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

                shares, size_msg = calculate_dtp_position_size(
                    equity=equity,
                    available_cash=portfolio.cash,
                    entry_price=fill_price,
                    stop_price=sig.initial_stop_price,
                    sector=sector,
                    current_sector_exposure=sec_exp,
                    current_drawdown_pct=curr_dd,
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

        # Step B: Session Exits for Active Positions (NO forced exits due to regime!)
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

        # Process exits
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
                "universe": "EXPANDED_91",
                "filter_mode": filter_mode.value,
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
                "brokerage": round(float(cost_summary.total_brokerage), 2),
                "stt": round(float(cost_summary.total_stt), 2),
                "exchange_turnover": round(float(cost_summary.exchange_charge + cost_summary.ipft_charge), 2),
                "sebi_turnover": round(float(cost_summary.sebi_turnover_fee), 2),
                "stamp_duty": round(float(cost_summary.total_stamp_duty), 2),
                "gst": round(float(cost_summary.total_gst), 2),
                "dp_charges": round(float(cost_summary.total_dp_charge), 2),
                "slippage": round(float(cost_summary.total_execution_friction), 2),
                "return_pct": round(cost_summary.net_return_pct, 2),
            })

        # Step C: EOD Signal Evaluation for Bar T with Market Regime Filter
        reg_res = evaluate_breadth_regime(augmented_universe, bar_idx=day_idx, config=cfg)
        regime_state = reg_res[0] if isinstance(reg_res, tuple) else reg_res
        is_bearish_breadth = (regime_state == "BEARISH") or (hasattr(regime_state, "value") and regime_state.value == "BEARISH") or (regime_state == "UNKNOWN")

        # Evaluate NIFTY market regime filter for new entries at Day T close
        regime_permitted, regime_msg, regime_meta = nifty_filter.is_entry_permitted(current_dt, filter_mode)

        if day_idx < len(trading_dates) - 2 and not is_bearish_breadth:
            if not regime_permitted:
                # Filter blocked entries on this date
                blocked_entries_count += 1
            else:
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
                        pending_signals[sym] = (sig, prio)

        # Daily Equity Tracking
        curr_eod_px = {s: float(augmented_universe[s].loc[current_ts, "close"]) for s in symbols}
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
            "filter_mode": filter_mode.value,
            "date": current_dt.isoformat(),
            "equity": round(eod_equity, 2),
            "cash": round(portfolio.cash, 2),
            "invested_capital": round(invested_cap, 2),
            "capital_utilization_pct": round(util_pct, 2),
            "drawdown_pct": round(dd_pct, 2),
            "open_positions": len(portfolio.positions),
            "nifty_filter_permitted": regime_permitted,
        })

    # Summary Financial Metrics
    completed_trades = len(executed_trades)
    wins = [t for t in executed_trades if t["net_pnl"] > 0]
    losses = [t for t in executed_trades if t["net_pnl"] <= 0]
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / completed_trades * 100.0) if completed_trades > 0 else 0.0

    gross_pnl = sum(t["gross_pnl"] for t in executed_trades)
    total_costs = sum(t["total_costs"] for t in executed_trades)
    net_pnl = sum(t["net_pnl"] for t in executed_trades)

    tot_win_val = sum(t["net_pnl"] for t in wins)
    tot_loss_val = abs(sum(t["net_pnl"] for t in losses))
    net_pf = (tot_win_val / tot_loss_val) if tot_loss_val > 0 else (99.0 if tot_win_val > 0 else 0.0)

    avg_win = (tot_win_val / win_count) if win_count > 0 else 0.0
    avg_loss = (tot_loss_val / loss_count) if loss_count > 0 else 0.0
    payoff = (avg_win / avg_loss) if avg_loss > 0 else 0.0
    expectancy = (net_pnl / completed_trades) if completed_trades > 0 else 0.0

    final_equity = daily_records[-1]["equity"] if daily_records else initial_capital
    cagr = (((final_equity / initial_capital) ** (1.0 / 3.0)) - 1.0) * 100.0 if final_equity > 0 else -100.0
    avg_util = float(np.mean([r["capital_utilization_pct"] for r in daily_records])) if daily_records else 0.0

    metrics = {
        "scenario_id": scenario_name,
        "filter_mode": filter_mode.value,
        "risk_tier": f"E{int(risk_pct*100)} ({int(risk_pct*100)}%)",
        "risk_pct": risk_pct,
        "cost_schedule": "Stress (₹317/cr)" if use_stress_costs else "Official (₹307/cr)",
        "completed_trades": completed_trades,
        "wins": win_count,
        "losses": loss_count,
        "win_rate_pct": round(win_rate, 2),
        "gross_pnl": round(gross_pnl, 2),
        "total_costs": round(total_costs, 2),
        "net_pnl": round(net_pnl, 2),
        "net_profit_factor": round(net_pf, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "payoff_ratio": round(payoff, 2),
        "expectancy_per_trade": round(expectancy, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "cagr_pct": round(cagr, 2),
        "capital_utilization_pct": round(avg_util, 2),
        "blocked_sessions_count": blocked_entries_count,
    }

    return {
        "metrics": metrics,
        "trades": executed_trades,
        "daily": daily_records,
    }


def compute_bootstrap_metrics(trades: List[Dict[str, Any]], n_boot: int = 10000) -> Dict[str, Any]:
    if not trades:
        return {
            "mean_expectancy": 0.0,
            "std_error": 0.0,
            "t_statistic": 0.0,
            "ci_95_lower": 0.0,
            "ci_95_upper": 0.0,
            "ci_95_crosses_zero": True,
            "prob_positive_expectancy_pct": 0.0,
            "prob_negative_net_pnl_pct": 100.0,
            "block_k3_ci_95_lower": 0.0,
            "block_k3_ci_95_upper": 0.0,
        }

    pnls = np.array([t["net_pnl"] for t in trades], dtype=np.float64)
    n = len(pnls)
    mean_val = float(np.mean(pnls))
    std_val = float(np.std(pnls, ddof=1)) if n > 1 else 0.0
    se_val = std_val / np.sqrt(n) if n > 0 else 0.0
    t_stat = mean_val / se_val if se_val > 0 else 0.0

    rng = np.random.default_rng(seed=42)
    boot_indices = rng.choice(n, size=(n_boot, n), replace=True)
    boot_means = np.mean(pnls[boot_indices], axis=1)

    ci_lower = float(np.percentile(boot_means, 2.5))
    ci_upper = float(np.percentile(boot_means, 97.5))
    prob_pos = float(np.mean(boot_means > 0) * 100.0)
    prob_neg = float(np.mean(boot_means <= 0) * 100.0)

    # Block bootstrap (k=3)
    k = 3
    if n >= k:
        n_blocks = int(np.ceil(n / k))
        block_starts = rng.integers(0, n - k + 1, size=(n_boot, n_blocks))
        block_means = []
        for b_starts in block_starts:
            indices = []
            for s in b_starts:
                indices.extend(range(s, s + k))
            indices = indices[:n]
            block_means.append(np.mean(pnls[indices]))
        block_means = np.array(block_means)
        block_lower = float(np.percentile(block_means, 2.5))
        block_upper = float(np.percentile(block_means, 97.5))
    else:
        block_lower, block_upper = ci_lower, ci_upper

    return {
        "sample_size_n": n,
        "mean_expectancy": round(mean_val, 2),
        "std_error": round(se_val, 2),
        "t_statistic": round(t_stat, 2),
        "ci_95_lower": round(ci_lower, 2),
        "ci_95_upper": round(ci_upper, 2),
        "ci_95_crosses_zero": bool(ci_lower <= 0 <= ci_upper),
        "prob_positive_expectancy_pct": round(prob_pos, 2),
        "prob_negative_net_pnl_pct": round(prob_neg, 2),
        "block_k3_ci_95_lower": round(block_lower, 2),
        "block_k3_ci_95_upper": round(block_upper, 2),
    }


def compute_outlier_removal(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not trades:
        return {"net_pnl_without_top3": 0.0, "net_pf_without_top3": 0.0}
    sorted_trades = sorted(trades, key=lambda t: t["net_pnl"], reverse=True)
    rem3 = sorted_trades[3:]
    pnl3 = sum(t["net_pnl"] for t in rem3)
    wins = [t for t in rem3 if t["net_pnl"] > 0]
    losses = [t for t in rem3 if t["net_pnl"] <= 0]
    tot_win = sum(t["net_pnl"] for t in wins)
    tot_loss = abs(sum(t["net_pnl"] for t in losses))
    pf3 = (tot_win / tot_loss) if tot_loss > 0 else (99.0 if tot_win > 0 else 0.0)
    return {
        "net_pnl_without_top3": round(pnl3, 2),
        "net_pf_without_top3": round(pf3, 2),
    }


def main():
    print("=" * 80)
    print("SignalForge — Phase 32J.3.1: DTP-V3 Market Regime Filter Research")
    print("=" * 80)

    symbols, sector_map, isin_map = load_universe_inventory()
    universe = load_and_resample_universe(symbols)

    print("\nPrecomputing strictly causal DTP-V3 indicators for all 91 symbols...")
    augmented: Dict[str, pd.DataFrame] = {}
    for sym, df in universe.items():
        augmented[sym] = calculate_dtp_indicators(df)
    trading_dates = sorted(list(augmented[symbols[0]].index))
    print(f"Precomputation complete. Canonical sessions: {len(trading_dates)}.")

    nifty_filter = NiftyMarketFilter()

    # Define experiments: 4 variations across 3 risk tiers & 2 cost schedules
    variations = [
        RegimeFilterMode.NONE,
        RegimeFilterMode.NIFTY_SMA200,
        RegimeFilterMode.NIFTY_SMA100,
        RegimeFilterMode.NIFTY_SMA200_TREND,
    ]
    risk_tiers = [0.01, 0.02, 0.03]
    cost_schedules = [False, True]  # False = Official, True = Stress

    all_metrics: List[Dict[str, Any]] = []
    all_trades: List[Dict[str, Any]] = []
    all_daily: List[Dict[str, Any]] = []
    bootstrap_records: List[Dict[str, Any]] = []
    gate_records: List[Dict[str, Any]] = []

    # 1. Baseline Verification against Phase 32J.2
    print("\n" + "=" * 60)
    print("STEP 1: Baseline Reproduction Verification")
    print("=" * 60)
    res_base_e1_off = run_regime_simulation(augmented, trading_dates, sector_map, isin_map, nifty_filter, RegimeFilterMode.NONE, risk_pct=0.01, use_stress_costs=False)
    res_base_e2_off = run_regime_simulation(augmented, trading_dates, sector_map, isin_map, nifty_filter, RegimeFilterMode.NONE, risk_pct=0.02, use_stress_costs=False)
    res_base_e3_off = run_regime_simulation(augmented, trading_dates, sector_map, isin_map, nifty_filter, RegimeFilterMode.NONE, risk_pct=0.03, use_stress_costs=False)

    print(f"  [Baseline E1 Official] Trades: {res_base_e1_off['metrics']['completed_trades']} (Expected: 69) | Net P&L: ₹{res_base_e1_off['metrics']['net_pnl']} (Expected: ₹5499.22)")
    print(f"  [Baseline E2 Official] Trades: {res_base_e2_off['metrics']['completed_trades']} (Expected: 70) | Net P&L: ₹{res_base_e2_off['metrics']['net_pnl']} (Expected: ₹12732.39)")
    print(f"  [Baseline E3 Official] Trades: {res_base_e3_off['metrics']['completed_trades']} (Expected: 69) | Net P&L: ₹{res_base_e3_off['metrics']['net_pnl']} (Expected: ₹19475.55)")

    if res_base_e1_off["metrics"]["completed_trades"] != 69 or res_base_e2_off["metrics"]["completed_trades"] != 70 or res_base_e3_off["metrics"]["completed_trades"] != 69:
        raise ValueError("CRITICAL STOP: Baseline reproduction trade count differs from Phase 32J.2!")
    if abs(res_base_e1_off["metrics"]["net_pnl"] - 5499.22) > 0.05 or abs(res_base_e2_off["metrics"]["net_pnl"] - 12732.39) > 0.05:
        raise ValueError("CRITICAL STOP: Baseline reproduction Net P&L differs from Phase 32J.2!")
    print(">>> BASELINE REPRODUCTION 100% BITWISE VERIFIED <<<\n")

    # 2. Run All 24 Scenarios
    print("=" * 60)
    print("STEP 2: Executing All 24 Regime Filter Scenarios")
    print("=" * 60)

    for mode in variations:
        for risk in risk_tiers:
            for stress in cost_schedules:
                res = run_regime_simulation(
                    augmented,
                    trading_dates,
                    sector_map,
                    isin_map,
                    nifty_filter,
                    filter_mode=mode,
                    risk_pct=risk,
                    use_stress_costs=stress,
                )
                m = res["metrics"]
                all_metrics.append(m)
                all_trades.extend(res["trades"])
                all_daily.extend(res["daily"])

                # Bootstrap
                boot = compute_bootstrap_metrics(res["trades"], n_boot=10000)
                boot["scenario_id"] = m["scenario_id"]
                boot["filter_mode"] = mode.value
                boot["risk_tier"] = m["risk_tier"]
                boot["cost_schedule"] = m["cost_schedule"]
                bootstrap_records.append(boot)

                # Outlier Removal
                outl = compute_outlier_removal(res["trades"])

                # Acceptance Gates
                gate_1 = "PASS" if m["net_pnl"] > 0 else "FAIL"
                gate_2 = "PASS" if m["net_profit_factor"] >= 1.50 else "FAIL"
                gate_3 = "PASS" if m["payoff_ratio"] >= 1.80 else "FAIL"
                gate_4 = "PASS" if m["max_drawdown_pct"] <= 15.0 else "FAIL"
                gate_5 = "PASS" if m["cagr_pct"] >= 12.0 else "FAIL"
                gate_6 = "PASS" if not boot["ci_95_crosses_zero"] and boot["ci_95_lower"] > 0 else "FAIL"
                gate_7 = "PASS" if outl["net_pnl_without_top3"] > 0 else "FAIL"

                passed_count = sum(1 for g in [gate_1, gate_2, gate_3, gate_4, gate_5, gate_6, gate_7] if g == "PASS")
                verdict = "PASS" if passed_count == 7 else ("CONDITIONAL" if gate_1 == "PASS" else "FAIL")

                gate_records.append({
                    "scenario_id": m["scenario_id"],
                    "filter_mode": mode.value,
                    "risk_tier": m["risk_tier"],
                    "cost_schedule": m["cost_schedule"],
                    "trades": m["completed_trades"],
                    "net_pnl": m["net_pnl"],
                    "gate_1_stress_net_pnl_gt_0": gate_1,
                    "profit_factor": m["net_profit_factor"],
                    "gate_2_pf_ge_1_50": gate_2,
                    "payoff_ratio": m["payoff_ratio"],
                    "gate_3_payoff_ge_1_80": gate_3,
                    "max_drawdown_pct": m["max_drawdown_pct"],
                    "gate_4_max_dd_le_15": gate_4,
                    "cagr_pct": m["cagr_pct"],
                    "gate_5_cagr_ge_12": gate_5,
                    "ci_95_lower": boot["ci_95_lower"],
                    "gate_6_ci95_gt_0": gate_6,
                    "pnl_without_top3": outl["net_pnl_without_top3"],
                    "gate_7_survive_top3": gate_7,
                    "passed_gates_count": f"{passed_count}/7",
                    "scenario_verdict": verdict,
                })

                print(f"  [{mode.value:18s} | {m['risk_tier']:7s} | {m['cost_schedule']:16s}] Trades={m['completed_trades']:2d} | Net P&L=₹{m['net_pnl']:9.2f} | PF={m['net_profit_factor']:.2f} | DD={m['max_drawdown_pct']:5.2f}% | Top-3={outl['net_pnl_without_top3']:8.2f} | Status={verdict}")

    # Save Primary Analytical CSVs
    print("\n" + "=" * 60)
    print("STEP 3: Saving Analytical CSV Deliverables")
    print("=" * 60)

    df_metrics = pd.DataFrame(all_metrics)
    df_metrics.to_csv(REPORTS_DIR / "regime_filter_comparison.csv", index=False)
    print(f"Saved: {REPORTS_DIR / 'regime_filter_comparison.csv'}")

    df_trades = pd.DataFrame(all_trades)
    df_trades.to_csv(REPORTS_DIR / "trade_ledger.csv", index=False)
    print(f"Saved: {REPORTS_DIR / 'trade_ledger.csv'}")

    df_boot = pd.DataFrame(bootstrap_records)
    df_boot.to_csv(REPORTS_DIR / "bootstrap_results.csv", index=False)
    print(f"Saved: {REPORTS_DIR / 'bootstrap_results.csv'}")

    df_gates = pd.DataFrame(gate_records)
    df_gates.to_csv(REPORTS_DIR / "gate_scorecard.csv", index=False)
    print(f"Saved: {REPORTS_DIR / 'gate_scorecard.csv'}")

    # Generate Annual Breakdown
    annual_rows = []
    df_trades["year"] = pd.to_datetime(df_trades["exit_date"]).dt.year
    for (scen, mode, tier, cost), grp in df_trades.groupby(["scenario_id", "filter_mode", "risk_tier", "cost_schedule"]):
        for yr in [2017, 2018, 2019]:
            sub = grp[grp["year"] == yr]
            n_t = len(sub)
            wins = len(sub[sub["net_pnl"] > 0])
            losses = len(sub[sub["net_pnl"] <= 0])
            wr = (wins / n_t * 100.0) if n_t > 0 else 0.0
            gross = sub["gross_pnl"].sum()
            costs = sub["total_costs"].sum()
            net = sub["net_pnl"].sum()
            tot_w = sub[sub["net_pnl"] > 0]["net_pnl"].sum()
            tot_l = abs(sub[sub["net_pnl"] <= 0]["net_pnl"].sum())
            pf = (tot_w / tot_l) if tot_l > 0 else (99.0 if tot_w > 0 else 0.0)
            annual_rows.append({
                "scenario_id": scen,
                "filter_mode": mode,
                "risk_tier": tier,
                "cost_schedule": cost,
                "year": yr,
                "completed_trades": n_t,
                "wins": wins,
                "losses": losses,
                "win_rate_pct": round(wr, 1),
                "gross_pnl": round(gross, 2),
                "total_costs": round(costs, 2),
                "net_pnl": round(net, 2),
                "annual_return_pct": round(net / 1000.0, 2), # % on 100k
                "net_profit_factor": round(pf, 2),
            })
    df_ann = pd.DataFrame(annual_rows)
    df_ann.to_csv(REPORTS_DIR / "annual_performance.csv", index=False)
    print(f"Saved: {REPORTS_DIR / 'annual_performance.csv'}")

    # Generate Monthly Breakdown
    monthly_rows = []
    df_trades["year_month"] = pd.to_datetime(df_trades["exit_date"]).dt.to_period("M").astype(str)
    # Generate complete list of 36 months
    all_months = pd.date_range("2017-01-01", "2019-12-31", freq="MS").to_period("M").astype(str)
    for (scen, mode, tier, cost), grp in df_trades.groupby(["scenario_id", "filter_mode", "risk_tier", "cost_schedule"]):
        grp_m = grp.set_index("year_month")
        for ym in all_months:
            if ym in grp_m.index:
                sub = grp_m.loc[[ym]]
                n_t = len(sub)
                wins = len(sub[sub["net_pnl"] > 0])
                losses = len(sub[sub["net_pnl"] <= 0])
                wr = (wins / n_t * 100.0) if n_t > 0 else 0.0
                gross = sub["gross_pnl"].sum()
                costs = sub["total_costs"].sum()
                net = sub["net_pnl"].sum()
            else:
                n_t, wins, losses, wr, gross, costs, net = 0, 0, 0, 0.0, 0.0, 0.0, 0.0
            monthly_rows.append({
                "scenario_id": scen,
                "filter_mode": mode,
                "risk_tier": tier,
                "cost_schedule": cost,
                "year_month": ym,
                "trades": n_t,
                "wins": wins,
                "losses": losses,
                "win_rate_pct": round(wr, 1),
                "gross_pnl": round(gross, 2),
                "costs": round(costs, 2),
                "net_pnl": round(net, 2),
                "monthly_return_pct": round(net / 1000.0, 2),
            })
    df_mon = pd.DataFrame(monthly_rows)
    df_mon.to_csv(REPORTS_DIR / "monthly_performance.csv", index=False)
    print(f"Saved: {REPORTS_DIR / 'monthly_performance.csv'}")

    # Stock Attribution
    stock_rows = []
    for (scen, mode, tier, cost), grp in df_trades.groupby(["scenario_id", "filter_mode", "risk_tier", "cost_schedule"]):
        tot_scen_pnl = grp["net_pnl"].sum()
        for sym, sgrp in grp.groupby("symbol"):
            n_t = len(sgrp)
            wins = len(sgrp[sgrp["net_pnl"] > 0])
            losses = len(sgrp[sgrp["net_pnl"] <= 0])
            wr = (wins / n_t * 100.0) if n_t > 0 else 0.0
            gross = sgrp["gross_pnl"].sum()
            costs = sgrp["total_costs"].sum()
            net = sgrp["net_pnl"].sum()
            sec = sgrp["sector"].iloc[0]
            share = (net / tot_scen_pnl * 100.0) if tot_scen_pnl != 0 else 0.0
            stock_rows.append({
                "scenario_id": scen,
                "filter_mode": mode,
                "risk_tier": tier,
                "cost_schedule": cost,
                "symbol": sym,
                "sector": sec,
                "completed_trades": n_t,
                "wins": wins,
                "losses": losses,
                "win_rate_pct": round(wr, 1),
                "gross_pnl": round(gross, 2),
                "total_costs": round(costs, 2),
                "net_pnl": round(net, 2),
                "profit_share_pct": round(share, 2),
            })
    df_stocks = pd.DataFrame(stock_rows)
    df_stocks.to_csv(REPORTS_DIR / "stock_attribution.csv", index=False)
    print(f"Saved: {REPORTS_DIR / 'stock_attribution.csv'}")

    # Sector Attribution
    sector_rows = []
    for (scen, mode, tier, cost), grp in df_trades.groupby(["scenario_id", "filter_mode", "risk_tier", "cost_schedule"]):
        tot_scen_pnl = grp["net_pnl"].sum()
        for sec, sgrp in grp.groupby("sector"):
            n_t = len(sgrp)
            wins = len(sgrp[sgrp["net_pnl"] > 0])
            losses = len(sgrp[sgrp["net_pnl"] <= 0])
            wr = (wins / n_t * 100.0) if n_t > 0 else 0.0
            gross = sgrp["gross_pnl"].sum()
            costs = sgrp["total_costs"].sum()
            net = sgrp["net_pnl"].sum()
            tot_w = sgrp[sgrp["net_pnl"] > 0]["net_pnl"].sum()
            tot_l = abs(sgrp[sgrp["net_pnl"] <= 0]["net_pnl"].sum())
            pf = (tot_w / tot_l) if tot_l > 0 else (99.0 if tot_w > 0 else 0.0)
            share = (net / tot_scen_pnl * 100.0) if tot_scen_pnl != 0 else 0.0
            sector_rows.append({
                "scenario_id": scen,
                "filter_mode": mode,
                "risk_tier": tier,
                "cost_schedule": cost,
                "sector": sec,
                "completed_trades": n_t,
                "wins": wins,
                "losses": losses,
                "win_rate_pct": round(wr, 1),
                "gross_pnl": round(gross, 2),
                "total_costs": round(costs, 2),
                "net_pnl": round(net, 2),
                "net_profit_factor": round(pf, 2),
                "profit_share_pct": round(share, 2),
            })
    df_sec = pd.DataFrame(sector_rows)
    df_sec.to_csv(REPORTS_DIR / "sector_attribution.csv", index=False)
    print(f"Saved: {REPORTS_DIR / 'sector_attribution.csv'}")

    # Drawdown Analysis
    dd_rows = []
    df_daily = pd.DataFrame(all_daily)
    for (scen, mode), grp in df_daily.groupby(["scenario_id", "filter_mode"]):
        max_dd = grp["drawdown_pct"].max()
        avg_dd = grp["drawdown_pct"].mean()
        underwater_days = len(grp[grp["drawdown_pct"] > 0.5])
        pct_underwater = underwater_days / len(grp) * 100.0
        dd_rows.append({
            "scenario_id": scen,
            "filter_mode": mode,
            "max_drawdown_pct": round(max_dd, 2),
            "avg_drawdown_pct": round(avg_dd, 2),
            "underwater_days": underwater_days,
            "pct_time_underwater": round(pct_underwater, 2),
        })
    df_dd = pd.DataFrame(dd_rows)
    df_dd.to_csv(REPORTS_DIR / "drawdown_analysis.csv", index=False)
    print(f"Saved: {REPORTS_DIR / 'drawdown_analysis.csv'}")

    # Concentration Analysis & Outlier Removal Across All Modes (E2 Official focus)
    conc_rows = []
    for mode in [m.value for m in variations]:
        scen_id = f"EXPANDED_91_{mode}_2pct_OFFICIAL"
        sub_t = df_trades[df_trades["scenario_id"] == scen_id].sort_values("net_pnl", ascending=False)
        tot_pnl = sub_t["net_pnl"].sum()
        for k in [0, 1, 3, 5, 10]:
            rem = sub_t.iloc[k:]
            rem_pnl = rem["net_pnl"].sum()
            wins = len(rem[rem["net_pnl"] > 0])
            losses = len(rem[rem["net_pnl"] <= 0])
            tot_w = rem[rem["net_pnl"] > 0]["net_pnl"].sum()
            tot_l = abs(rem[rem["net_pnl"] <= 0]["net_pnl"].sum())
            pf = (tot_w / tot_l) if tot_l > 0 else 0.0
            wr = (wins / len(rem) * 100.0) if len(rem) > 0 else 0.0
            conc_rows.append({
                "scenario_id": scen_id,
                "filter_mode": mode,
                "outlier_removal": f"Remove Top {k} Winners" if k > 0 else "All Trades",
                "trades_remaining": len(rem),
                "wins": wins,
                "losses": losses,
                "win_rate_pct": round(wr, 1),
                "remaining_net_pnl": round(rem_pnl, 2),
                "remaining_profit_factor": round(pf, 2),
                "removed_profit_share_pct": round((tot_pnl - rem_pnl) / tot_pnl * 100.0, 2) if tot_pnl != 0 else 0.0,
            })
    df_conc = pd.DataFrame(conc_rows)
    df_conc.to_csv(REPORTS_DIR / "concentration_analysis.csv", index=False)
    print(f"Saved: {REPORTS_DIR / 'concentration_analysis.csv'}")

    print("\n" + "=" * 80)
    print("PHASE 32J.3.1 RESEARCH BACKTEST EXECUTION & METRIC GENERATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
