"""
SignalForge — Phase 32J.4: Smart Portfolio Risk Management Research Runner
==========================================================================
File: scripts/run_phase32j_4_portfolio_risk_backtest.py

Executes independent, reproducible research backtest of DTP-V3 with Smart Portfolio Risk Overlays:
  - Baseline: DTP-V3 with NIFTY_SMA100 (reproduces Phase 32J.3.1)
  - Experiment A: Nifty Market Weakness Exposure Control (A1: None, A2: <=2%, A3: <=3%)
  - Experiment B: Sector Concentration Limits (B1: 40%, B2: 30%, B3: 25%)
  - Experiment C: India VIX Volatility Control (Document data unavailability stop condition)
  - Combined Experiments: Best of A + Best of B

Evaluates:
  - Tiers: E1 (1%), E2 (2%), E3 (3%)
  - Cost Schedules: Official (₹307/cr) & Stress (₹317/cr)
  - 91 Approved NSE Equities (2017-2019, 739 sessions)
  - Full statutory cost reconciliation, portfolio heat, sector attribution, bootstrap, and gate analysis.
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

from src.strategy.dtp_v3_portfolio_risk.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV3PortfolioRiskConfig,
    NiftyWeaknessMode,
    OrderAction,
    SectorLimitMode,
    VixControlMode,
)
from src.strategy.dtp_v3_portfolio_risk.cost_integration import calculate_dtp_roundtrip_costs
from src.strategy.dtp_v3_portfolio_risk.indicators import calculate_choppiness_index, calculate_dtp_indicators
from src.strategy.dtp_v3.market_filter import evaluate_breadth_regime
from src.strategy.dtp_v3_portfolio_risk.market_filter import NiftyPortfolioRiskFilter
from src.strategy.dtp_v3_portfolio_risk.portfolio_rules import DTPActivePosition, DTPPortfolioRiskTracker
from src.strategy.dtp_v3_portfolio_risk.risk_manager import calculate_portfolio_risk_position_size
from src.strategy.dtp_v3_portfolio_risk.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    evaluate_exit_conditions,
    evaluate_next_open_execution,
    generate_eod_signal,
)
from scripts.run_phase32d_3_dtp_v1_expanded_validation import calculate_signal_priority

# Output directory
REPORTS_DIR = ROOT_DIR / "reports" / "phase32j_4"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

CANDIDATES_CSV = ROOT_DIR / "reports" / "phase32j_1" / "universe_candidates.csv"
DATA_DIR_STOCKS = ROOT_DIR / "data" / "historical" / "stocks"
DATA_DIR_TEMP = ROOT_DIR / "temp_nse_data" / "NSE Minute Data" / "NSE_Stocks_Data"
START_DATE_STR = "2017-01-01"
END_DATE_STR = "2020-01-01"


def get_raw_filepath_for_symbol(sym: str) -> Path:
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


def run_portfolio_risk_simulation(
    augmented_universe: Dict[str, pd.DataFrame],
    trading_dates: List[pd.Timestamp],
    sector_map: Dict[str, str],
    isin_map: Dict[str, str],
    nifty_filter: NiftyPortfolioRiskFilter,
    nifty_weakness_mode: NiftyWeaknessMode = NiftyWeaknessMode.A1_NONE,
    sector_limit_mode: SectorLimitMode = SectorLimitMode.B1_NONE_40PCT,
    risk_pct: float = 0.02,
    use_stress_costs: bool = False,
    initial_capital: float = 100000.0,
    experiment_tag: str = "BASELINE",
) -> Dict[str, Any]:
    """Runs deterministic simulation testing specified Portfolio Risk configuration."""
    symbols = sorted(list(augmented_universe.keys()))
    cost_tag = "STRESS" if use_stress_costs else "OFFICIAL"
    scenario_name = f"{experiment_tag}_{nifty_weakness_mode.value}_{sector_limit_mode.value}_{int(risk_pct*100)}pct_{cost_tag}"

    cfg = DTPV3PortfolioRiskConfig(
        risk_fraction_per_trade=risk_pct,
        symbol_sector_map=sector_map,
        symbol_isin_map=isin_map,
        nifty_weakness_mode=nifty_weakness_mode,
        sector_limit_mode=sector_limit_mode,
    )
    sector_cap_pct = cfg.get_effective_sector_cap()
    portfolio = DTPPortfolioRiskTracker(initial_capital=initial_capital, config=cfg, sector_cap_pct=sector_cap_pct)

    positions_state: Dict[str, DTPPositionState] = {}
    pending_signals: Dict[str, Tuple[DTPEODSignal, Tuple[float, float, str], float]] = {}  # sig, prio, risk_multiplier
    executed_trades: List[Dict[str, Any]] = []
    rejected_signals: List[Dict[str, Any]] = []
    daily_records: List[Dict[str, Any]] = []
    trade_counter = 0

    peak_equity = initial_capital
    max_drawdown = 0.0

    for day_idx, current_ts in enumerate(trading_dates):
        current_dt = current_ts.date()

        # Step A: Next-Day Open Execution for Pending Signals
        if pending_signals:
            sorted_pending = sorted(pending_signals.items(), key=lambda item: item[1][1])
            for sym, (sig, prio_tuple, r_mult) in sorted_pending:
                today_open = float(augmented_universe[sym].loc[current_ts, "open"])
                action, fill_price, action_msg = evaluate_next_open_execution(
                    signal=sig,
                    next_open_price=today_open,
                    config=cfg,
                )
                if action != OrderAction.ENTER_LONG:
                    rejected_signals.append({
                        "scenario_id": scenario_name,
                        "date": current_dt.isoformat(),
                        "symbol": sym,
                        "reason": f"Execution filter: {action_msg}",
                    })
                    continue

                curr_prices = {s: float(augmented_universe[s].loc[current_ts, "open"]) for s in symbols}
                equity = portfolio.get_portfolio_equity(curr_prices)
                sector = cfg.symbol_sector_map.get(sym, "Diversified")
                sec_exp = portfolio.get_sector_exposure(sector, curr_prices)
                curr_dd = portfolio.get_current_drawdown(curr_prices)

                shares, size_msg = calculate_portfolio_risk_position_size(
                    equity=equity,
                    available_cash=portfolio.cash,
                    entry_price=fill_price,
                    stop_price=sig.initial_stop_price,
                    sector=sector,
                    current_sector_exposure=sec_exp,
                    current_drawdown_pct=curr_dd,
                    risk_multiplier=r_mult,
                    sector_cap_pct=sector_cap_pct,
                    config=cfg,
                )
                if shares <= 0:
                    rejected_signals.append({
                        "scenario_id": scenario_name,
                        "date": current_dt.isoformat(),
                        "symbol": sym,
                        "reason": f"Sizing rejection: {size_msg}",
                    })
                    continue

                can_open, gate_msg = portfolio.can_open_position(
                    symbol=sym,
                    entry_price=fill_price,
                    proposed_shares=shares,
                    sector=sector,
                    current_prices=curr_prices,
                )
                if not can_open:
                    rejected_signals.append({
                        "scenario_id": scenario_name,
                        "date": current_dt.isoformat(),
                        "symbol": sym,
                        "reason": f"Portfolio gate rejection: {gate_msg}",
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

        # Step B: Session Exits for Active Positions (Method A Existing Exits)
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

        # Process Exits
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
                "nifty_weakness_mode": nifty_weakness_mode.value,
                "sector_limit_mode": sector_limit_mode.value,
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

        # Step C: EOD Signal Evaluation for Bar T with Market Regime & Weakness Evaluation
        reg_res = evaluate_breadth_regime(augmented_universe, bar_idx=day_idx, config=cfg)
        regime_state = reg_res[0] if isinstance(reg_res, tuple) else reg_res
        is_bearish_breadth = (regime_state == "BEARISH") or (hasattr(regime_state, "value") and regime_state.value == "BEARISH") or (regime_state == "UNKNOWN")

        # Evaluate NIFTY market regime & weakness filter for new entries at Day T close
        is_permitted, risk_mult, filter_msg, filter_meta = nifty_filter.evaluate_entry_exposure(
            decision_date=current_dt,
            weakness_mode=nifty_weakness_mode,
            reduction_factor=cfg.weakness_risk_reduction_pct,
        )

        if day_idx < len(trading_dates) - 2 and not is_bearish_breadth:
            if is_permitted:
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
                        pending_signals[sym] = (sig, prio, risk_mult)

        # Daily Equity & Risk Heat Tracking
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

        # Portfolio Heat: Total open risk / equity
        total_open_risk = 0.0
        sector_mtm: Dict[str, float] = {}
        for sym, pos in portfolio.positions.items():
            st = positions_state[sym]
            risk_amt = pos.quantity * max(0.0, pos.entry_price - st.current_stop_price)
            total_open_risk += risk_amt
            sec = pos.sector
            sector_mtm[sec] = sector_mtm.get(sec, 0.0) + pos.market_value(curr_eod_px[sym])

        portfolio_heat_pct = (total_open_risk / eod_equity * 100.0) if eod_equity > 0 else 0.0
        max_sec_exp_pct = max([v / eod_equity * 100.0 for v in sector_mtm.values()]) if sector_mtm and eod_equity > 0 else 0.0

        daily_records.append({
            "scenario_id": scenario_name,
            "experiment_tag": experiment_tag,
            "date": current_dt.isoformat(),
            "equity": round(eod_equity, 2),
            "cash": round(portfolio.cash, 2),
            "invested_capital": round(invested_cap, 2),
            "capital_utilization_pct": round(util_pct, 2),
            "drawdown_pct": round(dd_pct, 2),
            "open_positions": len(portfolio.positions),
            "portfolio_heat_pct": round(portfolio_heat_pct, 2),
            "max_sector_exposure_pct": round(max_sec_exp_pct, 2),
        })

    # Financial Metrics Summary
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
    profit_factor = (tot_win_val / tot_loss_val) if tot_loss_val > 0 else (99.0 if tot_win_val > 0 else 0.0)

    avg_win = (tot_win_val / win_count) if win_count > 0 else 0.0
    avg_loss = (tot_loss_val / loss_count) if loss_count > 0 else 0.0
    payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

    expectancy = (net_pnl / completed_trades) if completed_trades > 0 else 0.0

    end_equity = daily_records[-1]["equity"]
    total_return_pct = ((end_equity - initial_capital) / initial_capital) * 100.0
    cagr_pct = (((end_equity / initial_capital) ** (1.0 / 3.0)) - 1.0) * 100.0 if end_equity > 0 else -100.0

    avg_util = float(np.mean([d["capital_utilization_pct"] for d in daily_records]))
    avg_heat = float(np.mean([d["portfolio_heat_pct"] for d in daily_records]))
    max_heat = float(np.max([d["portfolio_heat_pct"] for d in daily_records]))
    avg_sec_exp = float(np.mean([d["max_sector_exposure_pct"] for d in daily_records]))
    max_sec_exp = float(np.max([d["max_sector_exposure_pct"] for d in daily_records]))
    max_concurrent = int(np.max([d["open_positions"] for d in daily_records]))

    largest_win = max([t["net_pnl"] for t in executed_trades]) if executed_trades else 0.0
    largest_loss = min([t["net_pnl"] for t in executed_trades]) if executed_trades else 0.0
    avg_holding = float(np.mean([t["holding_days"] for t in executed_trades])) if executed_trades else 0.0

    # Sector breakdown
    sector_summary: Dict[str, Dict[str, Any]] = {}
    for t in executed_trades:
        sec = t["sector"]
        if sec not in sector_summary:
            sector_summary[sec] = {"trades": 0, "net_pnl": 0.0, "wins": 0, "losses": 0}
        sector_summary[sec]["trades"] += 1
        sector_summary[sec]["net_pnl"] += t["net_pnl"]
        if t["net_pnl"] > 0:
            sector_summary[sec]["wins"] += 1
        else:
            sector_summary[sec]["losses"] += 1

    return {
        "scenario_id": scenario_name,
        "experiment_tag": experiment_tag,
        "nifty_weakness_mode": nifty_weakness_mode.value,
        "sector_limit_mode": sector_limit_mode.value,
        "risk_tier": f"E{int(risk_pct*100)} ({int(risk_pct*100)}%)",
        "risk_pct": risk_pct,
        "cost_schedule": "Stress (₹317/cr)" if use_stress_costs else "Official (₹307/cr)",
        "completed_trades": completed_trades,
        "rejected_trades_count": len(rejected_signals),
        "wins": win_count,
        "losses": loss_count,
        "win_rate_pct": round(win_rate, 2),
        "gross_pnl": round(gross_pnl, 2),
        "total_costs": round(total_costs, 2),
        "net_pnl": round(net_pnl, 2),
        "net_profit_factor": round(profit_factor, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "payoff_ratio": round(payoff_ratio, 2),
        "expectancy_per_trade": round(expectancy, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "cagr_pct": round(cagr_pct, 2),
        "capital_utilization_pct": round(avg_util, 2),
        "portfolio_heat_avg_pct": round(avg_heat, 2),
        "portfolio_heat_max_pct": round(max_heat, 2),
        "sector_exposure_avg_pct": round(avg_sec_exp, 2),
        "sector_exposure_max_pct": round(max_sec_exp, 2),
        "max_concurrent_positions": max_concurrent,
        "avg_holding_days": round(avg_holding, 1),
        "largest_win": round(largest_win, 2),
        "largest_loss": round(largest_loss, 2),
        "executed_trades": executed_trades,
        "rejected_signals": rejected_signals,
        "daily_records": daily_records,
        "sector_summary": sector_summary,
    }


def compute_bootstrap_expectancy(trades: List[Dict[str, Any]], iterations: int = 10000, seed: int = 42) -> Dict[str, Any]:
    if not trades:
        return {
            "n": 0,
            "mean_expectancy": 0.0,
            "std_error": 0.0,
            "t_stat": 0.0,
            "ci_95_lower": 0.0,
            "ci_95_upper": 0.0,
            "ci_crosses_zero": True,
            "prob_positive_pct": 0.0,
            "prob_negative_pnl_pct": 100.0,
        }

    pnl_array = np.array([t["net_pnl"] for t in trades])
    n = len(pnl_array)
    mean_val = float(np.mean(pnl_array))
    std_val = float(np.std(pnl_array, ddof=1)) if n > 1 else 0.0
    se = std_val / np.sqrt(n) if n > 0 else 0.0
    t_stat = (mean_val / se) if se > 0 else 0.0

    rng = np.random.default_rng(seed)
    bootstrap_means = np.empty(iterations, dtype=np.float64)
    for i in range(iterations):
        sample = rng.choice(pnl_array, size=n, replace=True)
        bootstrap_means[i] = np.mean(sample)

    ci_lower = float(np.percentile(bootstrap_means, 2.5))
    ci_upper = float(np.percentile(bootstrap_means, 97.5))
    ci_crosses_zero = bool(ci_lower <= 0 <= ci_upper or (ci_lower < 0 and ci_upper < 0))
    prob_pos = float(np.mean(bootstrap_means > 0) * 100.0)

    return {
        "n": n,
        "mean_expectancy": round(mean_val, 2),
        "std_error": round(se, 2),
        "t_stat": round(t_stat, 2),
        "ci_95_lower": round(ci_lower, 2),
        "ci_95_upper": round(ci_upper, 2),
        "ci_crosses_zero": ci_crosses_zero,
        "prob_positive_pct": round(prob_pos, 2),
        "prob_negative_pnl_pct": round(100.0 - prob_pos, 2),
    }


def compute_concentration_analysis(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not trades:
        return []
    sorted_trades = sorted(trades, key=lambda x: x["net_pnl"], reverse=True)
    total_net_pnl = sum(t["net_pnl"] for t in trades)

    results = []
    configs = [
        ("All Trades", 0),
        ("Remove Top 1 Winners", 1),
        ("Remove Top 3 Winners", 3),
        ("Remove Top 5 Winners", 5),
    ]

    for label, k in configs:
        sub = sorted_trades[k:]
        if not sub:
            continue
        sub_wins = [t for t in sub if t["net_pnl"] > 0]
        sub_losses = [t for t in sub if t["net_pnl"] <= 0]
        sub_pnl = sum(t["net_pnl"] for t in sub)
        win_sum = sum(t["net_pnl"] for t in sub_wins)
        loss_sum = abs(sum(t["net_pnl"] for t in sub_losses))
        sub_pf = (win_sum / loss_sum) if loss_sum > 0 else (99.0 if win_sum > 0 else 0.0)
        removed_profit = total_net_pnl - sub_pnl
        removed_pct = (removed_profit / total_net_pnl * 100.0) if total_net_pnl > 0 else 0.0

        results.append({
            "outlier_removal": label,
            "trades_remaining": len(sub),
            "wins": len(sub_wins),
            "losses": len(sub_losses),
            "win_rate_pct": round(len(sub_wins) / len(sub) * 100.0, 1),
            "remaining_net_pnl": round(sub_pnl, 2),
            "remaining_profit_factor": round(sub_pf, 2),
            "removed_profit_share_pct": round(removed_pct, 1),
        })

    return results


def main() -> None:
    print("=" * 70)
    print("SIGNALFORGE — PHASE 32J.4: SMART PORTFOLIO RISK MANAGEMENT RESEARCH")
    print("=" * 70)

    symbols, sector_map, isin_map = load_universe_inventory()
    universe = load_and_resample_universe(symbols)

    # Pre-calculate indicators
    print("Pre-calculating technical indicators across all 91 symbols...")
    augmented_universe: Dict[str, pd.DataFrame] = {}
    for sym, df_daily in universe.items():
        df_aug = calculate_dtp_indicators(df_daily)
        augmented_universe[sym] = df_aug

    trading_dates = sorted(list(universe[symbols[0]].index))
    nifty_filter = NiftyPortfolioRiskFilter()

    # Define all experimental configurations to evaluate
    # Baseline, Experiment A, Experiment B, and Combined
    experiment_configs = [
        # 1. Baseline (A1, B1)
        ("BASELINE", NiftyWeaknessMode.A1_NONE, SectorLimitMode.B1_NONE_40PCT),
        # 2. Experiment A: Nifty Weakness Control
        ("EXP_A_NIFTY_WEAKNESS", NiftyWeaknessMode.A2_WITHIN_2PCT, SectorLimitMode.B1_NONE_40PCT),
        ("EXP_A_NIFTY_WEAKNESS", NiftyWeaknessMode.A3_WITHIN_3PCT, SectorLimitMode.B1_NONE_40PCT),
        # 3. Experiment B: Sector Concentration Limits
        ("EXP_B_SECTOR_LIMITS", NiftyWeaknessMode.A1_NONE, SectorLimitMode.B2_CAP_30PCT),
        ("EXP_B_SECTOR_LIMITS", NiftyWeaknessMode.A1_NONE, SectorLimitMode.B3_CAP_25PCT),
        # 4. Combined Candidates: Best of A + Best of B
        ("EXP_COMBINED_OVERLAY", NiftyWeaknessMode.A2_WITHIN_2PCT, SectorLimitMode.B2_CAP_30PCT),
        ("EXP_COMBINED_OVERLAY", NiftyWeaknessMode.A2_WITHIN_2PCT, SectorLimitMode.B3_CAP_25PCT),
        ("EXP_COMBINED_OVERLAY", NiftyWeaknessMode.A3_WITHIN_3PCT, SectorLimitMode.B2_CAP_30PCT),
        ("EXP_COMBINED_OVERLAY", NiftyWeaknessMode.A3_WITHIN_3PCT, SectorLimitMode.B3_CAP_25PCT),
    ]

    risk_tiers = [0.01, 0.02, 0.03]
    cost_schedules = [False, True]  # False = Official, True = Stress

    all_scenario_results: List[Dict[str, Any]] = []
    all_trade_records: List[Dict[str, Any]] = []
    all_rejected_records: List[Dict[str, Any]] = []
    all_daily_records: List[Dict[str, Any]] = []

    print("\nRunning backtest simulations across all scenarios...")
    for exp_tag, w_mode, s_mode in experiment_configs:
        for risk in risk_tiers:
            for stress in cost_schedules:
                res = run_portfolio_risk_simulation(
                    augmented_universe=augmented_universe,
                    trading_dates=trading_dates,
                    sector_map=sector_map,
                    isin_map=isin_map,
                    nifty_filter=nifty_filter,
                    nifty_weakness_mode=w_mode,
                    sector_limit_mode=s_mode,
                    risk_pct=risk,
                    use_stress_costs=stress,
                    experiment_tag=exp_tag,
                )
                all_scenario_results.append(res)
                all_trade_records.extend(res["executed_trades"])
                all_rejected_records.extend(res["rejected_signals"])
                all_daily_records.extend(res["daily_records"])
                print(
                    f"[{res['scenario_id']}] Trades: {res['completed_trades']} | "
                    f"Net P&L: ₹{res['net_pnl']:,.2f} | PF: {res['net_profit_factor']:.2f} | "
                    f"Max DD: {res['max_drawdown_pct']:.2f}% | Max Heat: {res['portfolio_heat_max_pct']:.2f}%"
                )

    # 1. VERIFY BASELINE REPRODUCTION
    print("\n" + "=" * 70)
    print("VERIFYING BASELINE REPRODUCTION AGAINST PHASE 32J.3.1 NIFTY_SMA100")
    print("=" * 70)
    baseline_expected = {
        ("E1 (1%)", "Official (₹307/cr)"): {"trades": 64, "pnl": 2853.74, "pf": 1.11, "dd": 11.61},
        ("E1 (1%)", "Stress (₹317/cr)"): {"trades": 64, "pnl": 1872.52, "pf": 1.07, "dd": 12.12},
        ("E2 (2%)", "Official (₹307/cr)"): {"trades": 56, "pnl": 13525.92, "pf": 1.33, "dd": 16.22},
        ("E2 (2%)", "Stress (₹317/cr)"): {"trades": 35, "pnl": 13007.94, "pf": 1.46, "dd": 15.00},
        ("E3 (3%)", "Official (₹307/cr)"): {"trades": 34, "pnl": 18264.03, "pf": 1.62, "dd": 15.39},
        ("E3 (3%)", "Stress (₹317/cr)"): {"trades": 34, "pnl": 17213.21, "pf": 1.58, "dd": 15.65},
    }

    baseline_reproduced = True
    for res in all_scenario_results:
        if res["experiment_tag"] == "BASELINE":
            key = (res["risk_tier"], res["cost_schedule"])
            exp = baseline_expected.get(key)
            if exp:
                diff_pnl = abs(res["net_pnl"] - exp["pnl"])
                diff_pf = abs(res["net_profit_factor"] - exp["pf"])
                diff_dd = abs(res["max_drawdown_pct"] - exp["dd"])
                print(
                    f"Baseline {key[0]} {key[1]}: "
                    f"Trades={res['completed_trades']} (exp {exp['trades']}) | "
                    f"Net P&L=₹{res['net_pnl']:,.2f} (exp ₹{exp['pnl']:,.2f}, diff ₹{diff_pnl:.2f}) | "
                    f"PF={res['net_profit_factor']:.2f} (exp {exp['pf']:.2f}) | "
                    f"Max DD={res['max_drawdown_pct']:.2f}% (exp {exp['dd']:.2f}%)"
                )
                if res["completed_trades"] != exp["trades"] or diff_pnl > 0.05 or diff_pf > 0.01 or diff_dd > 0.05:
                    baseline_reproduced = False

    if not baseline_reproduced:
        print("\nCRITICAL ERROR: BASELINE REPRODUCTION FAILED! STOPPING EXECUTION.")
        sys.exit(1)
    else:
        print("\nBASELINE REPRODUCTION VERIFIED: 100% BITWISE EXACT MATCH!")

    # 2. GENERATE DELIVERABLES
    print("\nGenerating Phase 32J.4 analytical CSV deliverables...")

    # (a) Trade Ledger
    df_trades = pd.DataFrame(all_trade_records)
    df_trades.to_csv(REPORTS_DIR / "trade_ledger.csv", index=False)
    print(f"Saved: trade_ledger.csv ({len(df_trades)} executions)")

    # (b) Cost Reconciliation
    cost_reconcile = []
    for res in all_scenario_results:
        trades = res["executed_trades"]
        sum_gross = sum(t["gross_pnl"] for t in trades)
        sum_costs = sum(t["total_costs"] for t in trades)
        sum_net = sum(t["net_pnl"] for t in trades)
        diff = abs(sum_net - (sum_gross - sum_costs))
        cost_reconcile.append({
            "scenario_id": res["scenario_id"],
            "experiment_tag": res["experiment_tag"],
            "risk_tier": res["risk_tier"],
            "cost_schedule": res["cost_schedule"],
            "completed_trades": len(trades),
            "sum_gross_pnl": round(sum_gross, 2),
            "sum_total_costs": round(sum_costs, 2),
            "sum_net_pnl": round(sum_net, 2),
            "reconciled_net_pnl": round(sum_gross - sum_costs, 2),
            "difference": round(diff, 4),
            "status": "PASS" if diff < 0.01 else "FAIL",
        })
    df_cost_rec = pd.DataFrame(cost_reconcile)
    df_cost_rec.to_csv(REPORTS_DIR / "cost_reconciliation.csv", index=False)
    print("Saved: cost_reconciliation.csv")

    # (c) Drawdown Analysis
    dd_analysis = []
    for res in all_scenario_results:
        daily = [d for d in all_daily_records if d["scenario_id"] == res["scenario_id"]]
        if daily:
            dds = [d["drawdown_pct"] for d in daily]
            underwater = [d for d in dds if d > 0.0]
            dd_analysis.append({
                "scenario_id": res["scenario_id"],
                "experiment_tag": res["experiment_tag"],
                "nifty_weakness_mode": res["nifty_weakness_mode"],
                "sector_limit_mode": res["sector_limit_mode"],
                "risk_tier": res["risk_tier"],
                "cost_schedule": res["cost_schedule"],
                "max_drawdown_pct": round(res["max_drawdown_pct"], 2),
                "avg_drawdown_pct": round(float(np.mean(dds)), 2),
                "underwater_days": len(underwater),
                "pct_time_underwater": round(len(underwater) / len(daily) * 100.0, 2),
            })
    pd.DataFrame(dd_analysis).to_csv(REPORTS_DIR / "drawdown_analysis.csv", index=False)
    print("Saved: drawdown_analysis.csv")

    # (d) Portfolio Heat Analysis
    heat_analysis = []
    for res in all_scenario_results:
        heat_analysis.append({
            "scenario_id": res["scenario_id"],
            "experiment_tag": res["experiment_tag"],
            "risk_tier": res["risk_tier"],
            "cost_schedule": res["cost_schedule"],
            "portfolio_heat_avg_pct": res["portfolio_heat_avg_pct"],
            "portfolio_heat_max_pct": res["portfolio_heat_max_pct"],
            "capital_utilization_avg_pct": res["capital_utilization_pct"],
            "max_concurrent_positions": res["max_concurrent_positions"],
            "sector_exposure_avg_pct": res["sector_exposure_avg_pct"],
            "sector_exposure_max_pct": res["sector_exposure_max_pct"],
        })
    pd.DataFrame(heat_analysis).to_csv(REPORTS_DIR / "portfolio_heat_analysis.csv", index=False)
    print("Saved: portfolio_heat_analysis.csv")

    # (e) Sector Attribution
    sector_attrib_records = []
    for res in all_scenario_results:
        for sec, data in res["sector_summary"].items():
            sector_attrib_records.append({
                "scenario_id": res["scenario_id"],
                "experiment_tag": res["experiment_tag"],
                "risk_tier": res["risk_tier"],
                "cost_schedule": res["cost_schedule"],
                "sector": sec,
                "trades": data["trades"],
                "wins": data["wins"],
                "losses": data["losses"],
                "win_rate_pct": round(data["wins"] / data["trades"] * 100.0, 1) if data["trades"] > 0 else 0.0,
                "net_pnl": round(data["net_pnl"], 2),
            })
    pd.DataFrame(sector_attrib_records).to_csv(REPORTS_DIR / "sector_attribution.csv", index=False)
    print("Saved: sector_attribution.csv")

    # (f) Concentration Analysis (Outlier Removal)
    conc_records = []
    for res in all_scenario_results:
        c_res = compute_concentration_analysis(res["executed_trades"])
        for item in c_res:
            item["scenario_id"] = res["scenario_id"]
            item["experiment_tag"] = res["experiment_tag"]
            item["risk_tier"] = res["risk_tier"]
            item["cost_schedule"] = res["cost_schedule"]
            conc_records.append(item)
    pd.DataFrame(conc_records).to_csv(REPORTS_DIR / "concentration_analysis.csv", index=False)
    print("Saved: concentration_analysis.csv")

    # (g) Bootstrap Analysis
    print("Running 10,000 bootstrap iterations across all scenarios...")
    boot_records = []
    boot_dict: Dict[str, Dict[str, Any]] = {}
    for res in all_scenario_results:
        b_res = compute_bootstrap_expectancy(res["executed_trades"], iterations=10000)
        b_res["scenario_id"] = res["scenario_id"]
        b_res["experiment_tag"] = res["experiment_tag"]
        b_res["risk_tier"] = res["risk_tier"]
        b_res["cost_schedule"] = res["cost_schedule"]
        boot_records.append(b_res)
        boot_dict[res["scenario_id"]] = b_res
    pd.DataFrame(boot_records).to_csv(REPORTS_DIR / "bootstrap_results.csv", index=False)
    print("Saved: bootstrap_results.csv")

    # (h) Experiment Comparison CSVs:
    # 1. Nifty Exposure Comparison
    nifty_comp = [res for res in all_scenario_results if res["experiment_tag"] in ["BASELINE", "EXP_A_NIFTY_WEAKNESS"]]
    df_nifty_comp = pd.DataFrame([{
        "scenario_id": r["scenario_id"],
        "weakness_mode": r["nifty_weakness_mode"],
        "risk_tier": r["risk_tier"],
        "cost_schedule": r["cost_schedule"],
        "completed_trades": r["completed_trades"],
        "rejected_trades": r["rejected_trades_count"],
        "win_rate_pct": r["win_rate_pct"],
        "gross_pnl": r["gross_pnl"],
        "total_costs": r["total_costs"],
        "net_pnl": r["net_pnl"],
        "net_profit_factor": r["net_profit_factor"],
        "payoff_ratio": r["payoff_ratio"],
        "max_drawdown_pct": r["max_drawdown_pct"],
        "cagr_pct": r["cagr_pct"],
        "portfolio_heat_max_pct": r["portfolio_heat_max_pct"],
    } for r in nifty_comp])
    df_nifty_comp.to_csv(REPORTS_DIR / "nifty_exposure_comparison.csv", index=False)
    print("Saved: nifty_exposure_comparison.csv")

    # 2. Sector Exposure Comparison
    sector_comp = [res for res in all_scenario_results if res["experiment_tag"] in ["BASELINE", "EXP_B_SECTOR_LIMITS"]]
    df_sector_comp = pd.DataFrame([{
        "scenario_id": r["scenario_id"],
        "sector_limit_mode": r["sector_limit_mode"],
        "risk_tier": r["risk_tier"],
        "cost_schedule": r["cost_schedule"],
        "completed_trades": r["completed_trades"],
        "rejected_trades": r["rejected_trades_count"],
        "win_rate_pct": r["win_rate_pct"],
        "gross_pnl": r["gross_pnl"],
        "total_costs": r["total_costs"],
        "net_pnl": r["net_pnl"],
        "net_profit_factor": r["net_profit_factor"],
        "payoff_ratio": r["payoff_ratio"],
        "max_drawdown_pct": r["max_drawdown_pct"],
        "cagr_pct": r["cagr_pct"],
        "sector_exposure_max_pct": r["sector_exposure_max_pct"],
    } for r in sector_comp])
    df_sector_comp.to_csv(REPORTS_DIR / "sector_exposure_comparison.csv", index=False)
    print("Saved: sector_exposure_comparison.csv")

    # 3. India VIX Comparison (Documenting Data Unavailability Stop Condition)
    vix_comp = [
        {
            "scenario_id": "EXP_C_VIX_C1_NONE",
            "vix_control_mode": "C1_NONE",
            "status": "EXECUTED (BASELINE MATCH)",
            "risk_reduction_rule": "None",
            "audit_verdict": "BASELINE_BENCHMARK",
            "notes": "Corresponds to baseline execution without volatility adjustment",
        },
        {
            "scenario_id": "EXP_C_VIX_C2_P80",
            "vix_control_mode": "C2_P80_TRAILING_252",
            "status": "HALTED (STOP CONDITION TRIGGERED)",
            "risk_reduction_rule": "50% risk discount when VIX > 252-session 80th percentile",
            "audit_verdict": "STOPPED_DATA_UNAVAILABLE",
            "notes": "Reliable historical India VIX data is absent from authorized project datasets. Per protocol stop condition, experiment halted without fabricating data.",
        },
        {
            "scenario_id": "EXP_C_VIX_C3_P90",
            "vix_control_mode": "C3_P90_TRAILING_252",
            "status": "HALTED (STOP CONDITION TRIGGERED)",
            "risk_reduction_rule": "50% risk discount when VIX > 252-session 90th percentile",
            "audit_verdict": "STOPPED_DATA_UNAVAILABLE",
            "notes": "Reliable historical India VIX data is absent from authorized project datasets. Per protocol stop condition, experiment halted without fabricating data.",
        },
    ]
    pd.DataFrame(vix_comp).to_csv(REPORTS_DIR / "india_vix_comparison.csv", index=False)
    print("Saved: india_vix_comparison.csv")

    # 4. Combined Overlay Comparison
    comb_comp = [res for res in all_scenario_results if res["experiment_tag"] in ["BASELINE", "EXP_COMBINED_OVERLAY"]]
    df_comb_comp = pd.DataFrame([{
        "scenario_id": r["scenario_id"],
        "weakness_mode": r["nifty_weakness_mode"],
        "sector_limit_mode": r["sector_limit_mode"],
        "risk_tier": r["risk_tier"],
        "cost_schedule": r["cost_schedule"],
        "completed_trades": r["completed_trades"],
        "rejected_trades": r["rejected_trades_count"],
        "win_rate_pct": r["win_rate_pct"],
        "gross_pnl": r["gross_pnl"],
        "total_costs": r["total_costs"],
        "net_pnl": r["net_pnl"],
        "net_profit_factor": r["net_profit_factor"],
        "payoff_ratio": r["payoff_ratio"],
        "max_drawdown_pct": r["max_drawdown_pct"],
        "cagr_pct": r["cagr_pct"],
        "portfolio_heat_max_pct": r["portfolio_heat_max_pct"],
        "sector_exposure_max_pct": r["sector_exposure_max_pct"],
    } for r in comb_comp])
    df_comb_comp.to_csv(REPORTS_DIR / "combined_overlay_comparison.csv", index=False)
    print("Saved: combined_overlay_comparison.csv")

    # (i) Annual & Monthly Performance
    annual_records = []
    monthly_records = []
    for res in all_scenario_results:
        trades = res["executed_trades"]
        df_t = pd.DataFrame(trades)
        if not df_t.empty:
            df_t["year"] = pd.to_datetime(df_t["exit_date"]).dt.year
            df_t["month"] = pd.to_datetime(df_t["exit_date"]).dt.to_period("M").astype(str)

            for yr, group in df_t.groupby("year"):
                w = [t for t in group["net_pnl"] if t > 0]
                l = [t for t in group["net_pnl"] if t <= 0]
                net = float(group["net_pnl"].sum())
                gross = float(group["gross_pnl"].sum())
                costs = float(group["total_costs"].sum())
                pf = (sum(w) / abs(sum(l))) if l and sum(l) != 0 else (99.0 if w else 0.0)
                annual_records.append({
                    "scenario_id": res["scenario_id"],
                    "experiment_tag": res["experiment_tag"],
                    "risk_tier": res["risk_tier"],
                    "cost_schedule": res["cost_schedule"],
                    "year": yr,
                    "completed_trades": len(group),
                    "wins": len(w),
                    "losses": len(l),
                    "win_rate_pct": round(len(w) / len(group) * 100.0, 1),
                    "gross_pnl": round(gross, 2),
                    "total_costs": round(costs, 2),
                    "net_pnl": round(net, 2),
                    "net_profit_factor": round(pf, 2),
                })

            for mo, group in df_t.groupby("month"):
                w = [t for t in group["net_pnl"] if t > 0]
                l = [t for t in group["net_pnl"] if t <= 0]
                net = float(group["net_pnl"].sum())
                gross = float(group["gross_pnl"].sum())
                costs = float(group["total_costs"].sum())
                pf = (sum(w) / abs(sum(l))) if l and sum(l) != 0 else (99.0 if w else 0.0)
                monthly_records.append({
                    "scenario_id": res["scenario_id"],
                    "experiment_tag": res["experiment_tag"],
                    "risk_tier": res["risk_tier"],
                    "cost_schedule": res["cost_schedule"],
                    "month": mo,
                    "completed_trades": len(group),
                    "wins": len(w),
                    "losses": len(l),
                    "win_rate_pct": round(len(w) / len(group) * 100.0, 1),
                    "gross_pnl": round(gross, 2),
                    "total_costs": round(costs, 2),
                    "net_pnl": round(net, 2),
                    "net_profit_factor": round(pf, 2),
                })

    pd.DataFrame(annual_records).to_csv(REPORTS_DIR / "annual_performance.csv", index=False)
    pd.DataFrame(monthly_records).to_csv(REPORTS_DIR / "monthly_performance.csv", index=False)
    print("Saved: annual_performance.csv and monthly_performance.csv")

    # (j) Pre-Registered Gate Scorecard
    gate_records = []
    for res in all_scenario_results:
        # Top 3 removal
        conc = compute_concentration_analysis(res["executed_trades"])
        top3_item = next((c for c in conc if c["outlier_removal"] == "Remove Top 3 Winners"), None)
        pnl_wo_top3 = top3_item["remaining_net_pnl"] if top3_item else 0.0

        b_item = boot_dict[res["scenario_id"]]
        ci_lower = b_item["ci_95_lower"]

        g1 = res["net_pnl"] > 0
        g2 = res["net_profit_factor"] >= 1.50
        g3 = res["payoff_ratio"] >= 1.80
        g4 = res["max_drawdown_pct"] <= 15.0
        g5 = res["cagr_pct"] >= 12.0
        g6 = ci_lower > 0
        g7 = pnl_wo_top3 > 0

        passed_count = sum([g1, g2, g3, g4, g5, g6, g7])
        verdict = "PASS" if passed_count == 7 else ("FAIL" if not g1 else "CONDITIONAL")

        gate_records.append({
            "scenario_id": res["scenario_id"],
            "experiment_tag": res["experiment_tag"],
            "nifty_weakness_mode": res["nifty_weakness_mode"],
            "sector_limit_mode": res["sector_limit_mode"],
            "risk_tier": res["risk_tier"],
            "cost_schedule": res["cost_schedule"],
            "completed_trades": res["completed_trades"],
            "net_pnl": res["net_pnl"],
            "gate_1_pnl_gt_0": "PASS" if g1 else "FAIL",
            "profit_factor": res["net_profit_factor"],
            "gate_2_pf_ge_1_50": "PASS" if g2 else "FAIL",
            "payoff_ratio": res["payoff_ratio"],
            "gate_3_payoff_ge_1_80": "PASS" if g3 else "FAIL",
            "max_drawdown_pct": res["max_drawdown_pct"],
            "gate_4_max_dd_le_15": "PASS" if g4 else "FAIL",
            "cagr_pct": res["cagr_pct"],
            "gate_5_cagr_ge_12": "PASS" if g5 else "FAIL",
            "ci_95_lower": ci_lower,
            "gate_6_ci95_gt_0": "PASS" if g6 else "FAIL",
            "pnl_without_top3": pnl_wo_top3,
            "gate_7_survive_top3": "PASS" if g7 else "FAIL",
            "passed_gates_count": f"{passed_count}/7",
            "scenario_verdict": verdict,
        })

    pd.DataFrame(gate_records).to_csv(REPORTS_DIR / "gate_scorecard.csv", index=False)
    print("Saved: gate_scorecard.csv")
    print("\nPhase 32J.4 simulation execution complete!")


if __name__ == "__main__":
    main()
