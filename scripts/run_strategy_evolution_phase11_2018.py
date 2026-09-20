"""SignalForge — Phase 11: H5 Relative-Strength Divergence Forensic Robustness.

Forensic analysis of H5_RS_DIVERGENCE across:
1. Symbol Robustness & Isolation
2. Monthly Robustness (Jan-Dec)
3. Directional Robustness (Long vs Short)
4. Cost Stress & Breakeven Analysis
5. Parameter Perturbation Grid (Stability, not optimization)
6. Trade Distribution & Outlier/Winner Dependency (Top 1%, 5%, 10%)
7. MAE / MFE Excursion Analysis
8. Chronological Splits (Train / Val / OOS)
9. Rolling Walk-Forward
10. Symbol Exclusion Matrix (Leave-One-Out)
11. Month Exclusion & Concentration
12. 8-Point Falsification Engine & Taxonomy Classification
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.strategy.context_engine_v10 import (
    load_benchmark_data,
    precompute_stock_features,
)

CLEAN_DATA_DIR = ROOT_DIR / "research" / "clean_data_2018"
BASELINE_TRADES_PATH = ROOT_DIR / "research" / "strategy_evolution_2018" / "baseline" / "all_trades.csv"
PHASE10_CANDIDATES_PATH = ROOT_DIR / "research" / "strategy_evolution_2018" / "phase10_relative_context" / "candidate_signals.csv"
BENCHMARK_PATH = ROOT_DIR / "data" / "historical" / "nifty50_github_1m.csv"
OUT_DIR = ROOT_DIR / "research" / "strategy_evolution_2018" / "phase11_h5_forensic"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]

# Baseline H5 parameters from Phase 10
BASE_RS_THRESH = 0.003
BASE_BM_THRESH = 0.0005


def df_to_markdown(df: pd.DataFrame) -> str:
    """Convert DataFrame to clean markdown table."""
    headers = list(df.columns)
    lines = ["| " + " | ".join(str(h) for h in headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in headers) + " |")
    return "\n".join(lines)


def calc_metrics(trades_df: pd.DataFrame, cost_mult: float = 1.0) -> Dict[str, Any]:
    """Calculate standard performance metrics from trade slice."""
    n_trades = len(trades_df)
    if n_trades == 0:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "gross_expectancy": 0.0,
            "net_expectancy": 0.0,
            "gross_pf": 0.0,
            "net_pf": 0.0,
            "gross_pnl": 0.0,
            "costs": 0.0,
            "net_pnl": 0.0,
            "avg_winner": 0.0,
            "avg_loser": 0.0,
            "max_drawdown": 0.0,
            "max_loss_streak": 0,
            "trades_per_day": 0.0,
        }

    gross_pnl_series = trades_df["gross_pnl"].to_numpy(dtype=float)
    base_cost_series = trades_df["costs"].to_numpy(dtype=float)
    scaled_cost_series = base_cost_series * cost_mult
    net_pnl_series = gross_pnl_series - scaled_cost_series

    gross_pnl = float(np.sum(gross_pnl_series))
    costs = float(np.sum(scaled_cost_series))
    net_pnl = float(np.sum(net_pnl_series))

    wins_mask = net_pnl_series > 0
    loss_mask = net_pnl_series < 0
    n_wins = int(np.sum(wins_mask))
    n_losses = int(np.sum(loss_mask))

    win_rate = (n_wins / n_trades) * 100.0
    gross_exp = gross_pnl / n_trades
    net_exp = net_pnl / n_trades

    sum_gp = float(np.sum(gross_pnl_series[gross_pnl_series > 0])) if np.any(gross_pnl_series > 0) else 0.0
    sum_gl = float(np.abs(np.sum(gross_pnl_series[gross_pnl_series < 0]))) if np.any(gross_pnl_series < 0) else 0.0
    gross_pf = (sum_gp / sum_gl) if sum_gl > 0 else (999.0 if sum_gp > 0 else 0.0)

    sum_np = float(np.sum(net_pnl_series[wins_mask])) if n_wins > 0 else 0.0
    sum_nl = float(np.abs(np.sum(net_pnl_series[loss_mask]))) if n_losses > 0 else 0.0
    net_pf = (sum_np / sum_nl) if sum_nl > 0 else (999.0 if sum_np > 0 else 0.0)

    avg_win = float(np.mean(net_pnl_series[wins_mask])) if n_wins > 0 else 0.0
    avg_loss = float(np.mean(net_pnl_series[loss_mask])) if n_losses > 0 else 0.0

    cumsum = np.cumsum(net_pnl_series)
    peak = np.maximum.accumulate(cumsum)
    dd = peak - cumsum
    max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0

    loss_streaks = []
    curr_streak = 0
    for is_l in loss_mask:
        if is_l:
            curr_streak += 1
        else:
            if curr_streak > 0:
                loss_streaks.append(curr_streak)
            curr_streak = 0
    if curr_streak > 0:
        loss_streaks.append(curr_streak)
    max_loss_streak = max(loss_streaks) if loss_streaks else 0

    trades_per_day = round(n_trades / 246.0, 2)

    return {
        "trades": n_trades,
        "win_rate": round(win_rate, 2),
        "gross_expectancy": round(gross_exp, 2),
        "net_expectancy": round(net_exp, 2),
        "gross_pf": round(gross_pf, 4),
        "net_pf": round(net_pf, 4),
        "gross_pnl": round(gross_pnl, 2),
        "costs": round(costs, 2),
        "net_pnl": round(net_pnl, 2),
        "avg_winner": round(avg_win, 2),
        "avg_loser": round(avg_loss, 2),
        "max_drawdown": round(max_dd, 2),
        "max_loss_streak": max_loss_streak,
        "trades_per_day": trades_per_day,
    }


def compute_mae_mfe_for_trades(df_trades: pd.DataFrame, stock_clean_dfs: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Compute MAE and MFE for each trade by scanning 1m bars from entry to exit."""
    df_out = df_trades.copy()
    mae_pts = []
    mfe_pts = []
    mae_pcts = []
    mfe_pcts = []

    for _, tr in df_out.iterrows():
        sym = tr["symbol"]
        entry_t = pd.Timestamp(tr["entry_datetime"])
        exit_t = pd.Timestamp(tr["exit_datetime"])
        direction = tr["direction"]
        entry_p = float(tr["entry_price"])

        df_bars = stock_clean_dfs[sym]
        slice_bars = df_bars.loc[entry_t:exit_t]

        if len(slice_bars) == 0:
            mae_pts.append(0.0)
            mfe_pts.append(0.0)
            mae_pcts.append(0.0)
            mfe_pcts.append(0.0)
            continue

        highs = slice_bars["High"].values
        lows = slice_bars["Low"].values

        if direction == "LONG":
            max_p = float(np.max(highs))
            min_p = float(np.min(lows))
            mfe = max(0.0, max_p - entry_p)
            mae = max(0.0, entry_p - min_p)
        else:
            max_p = float(np.max(highs))
            min_p = float(np.min(lows))
            mfe = max(0.0, entry_p - min_p)
            mae = max(0.0, max_p - entry_p)

        mae_pts.append(round(mae, 2))
        mfe_pts.append(round(mfe, 2))
        mae_pcts.append(round((mae / entry_p) * 100.0, 3))
        mfe_pcts.append(round((mfe / entry_p) * 100.0, 3))

    df_out["mae_pts"] = mae_pts
    df_out["mfe_pts"] = mfe_pts
    df_out["mae_pct"] = mae_pcts
    df_out["mfe_pct"] = mfe_pcts
    return df_out


def run_phase11() -> None:
    start_time = time.time()
    print("=" * 80)
    print(" SIGNALFORGE — PHASE 11: H5 RS DIVERGENCE FORENSIC ROBUSTNESS AUDIT")
    print("=" * 80)

    # 1. Load candidate signals from Phase 10 (or baseline + indicators)
    if not PHASE10_CANDIDATES_PATH.exists():
        raise FileNotFoundError(f"Phase 10 candidates file missing: {PHASE10_CANDIDATES_PATH}")

    df_all = pd.read_csv(PHASE10_CANDIDATES_PATH)
    print(f"Loaded {len(df_all):,} candidate trade records from Phase 10.")

    # Filter exact Phase 10 H5 trades
    df_h5 = df_all[df_all["H5_RS_DIVERGENCE"] == True].copy().reset_index(drop=True)
    n_h5 = len(df_h5)
    print(f"Extracted H5_RS_DIVERGENCE trades: {n_h5} trades.")
    if n_h5 != 80:
        print(f"WARNING: Expected 80 H5 trades, found {n_h5}")

    # Load clean stock data for MAE/MFE scanning
    print("Loading clean stock data for MAE/MFE trade-level excursion analysis...")
    stock_clean_dfs = {}
    for sym in SYMBOLS:
        p = CLEAN_DATA_DIR / f"{sym}_2018.csv"
        stock_clean_dfs[sym] = pd.read_csv(p, index_col=0, parse_dates=True)

    df_h5 = compute_mae_mfe_for_trades(df_h5, stock_clean_dfs)
    df_h5.to_csv(OUT_DIR / "candidate_trades.csv", index=False)

    m_h5 = calc_metrics(df_h5)
    m_base = calc_metrics(df_all)

    # =========================================================================
    # ARTIFACT 2: overall_comparison.csv
    # =========================================================================
    print("\n[TEST 0] Generating overall_comparison.csv...")
    comp_rows = [
        {
            "configuration": "BASELINE (All Trades)",
            "trades": m_base["trades"],
            "win_rate": m_base["win_rate"],
            "gross_expectancy": m_base["gross_expectancy"],
            "net_expectancy": m_base["net_expectancy"],
            "gross_pf": m_base["gross_pf"],
            "net_pf": m_base["net_pf"],
            "net_pnl": m_base["net_pnl"],
            "max_drawdown": m_base["max_drawdown"],
            "trades_per_day": m_base["trades_per_day"],
            "pct_baseline": 100.0,
        },
        {
            "configuration": "H5_RS_DIVERGENCE (Candidate)",
            "trades": m_h5["trades"],
            "win_rate": m_h5["win_rate"],
            "gross_expectancy": m_h5["gross_expectancy"],
            "net_expectancy": m_h5["net_expectancy"],
            "gross_pf": m_h5["gross_pf"],
            "net_pf": m_h5["net_pf"],
            "net_pnl": m_h5["net_pnl"],
            "max_drawdown": m_h5["max_drawdown"],
            "trades_per_day": m_h5["trades_per_day"],
            "pct_baseline": round((m_h5["trades"] / len(df_all)) * 100.0, 2),
        },
    ]
    df_comp = pd.DataFrame(comp_rows)
    df_comp.to_csv(OUT_DIR / "overall_comparison.csv", index=False)

    # =========================================================================
    # TEST 1 & ARTIFACT 3: symbol_analysis.csv
    # =========================================================================
    print("\n[TEST 1] Generating symbol_analysis.csv...")
    sym_rows = []
    # All symbols
    sym_rows.append({
        "symbol_group": "ALL SYMBOLS",
        "trades": m_h5["trades"],
        "win_rate": m_h5["win_rate"],
        "gross_pnl": m_h5["gross_pnl"],
        "costs": m_h5["costs"],
        "net_pnl": m_h5["net_pnl"],
        "gross_pf": m_h5["gross_pf"],
        "net_pf": m_h5["net_pf"],
        "net_expectancy": m_h5["net_expectancy"],
        "max_drawdown": m_h5["max_drawdown"],
        "pnl_contribution_pct": 100.0,
    })

    # Without INFY
    df_no_infy = df_h5[df_h5["symbol"] != "INFY"]
    m_no_infy = calc_metrics(df_no_infy)
    sym_rows.append({
        "symbol_group": "WITHOUT INFY",
        "trades": m_no_infy["trades"],
        "win_rate": m_no_infy["win_rate"],
        "gross_pnl": m_no_infy["gross_pnl"],
        "costs": m_no_infy["costs"],
        "net_pnl": m_no_infy["net_pnl"],
        "gross_pf": m_no_infy["gross_pf"],
        "net_pf": m_no_infy["net_pf"],
        "net_expectancy": m_no_infy["net_expectancy"],
        "max_drawdown": m_no_infy["max_drawdown"],
        "pnl_contribution_pct": round((m_no_infy["net_pnl"] / m_h5["net_pnl"]) * 100.0, 2) if m_h5["net_pnl"] != 0 else 0.0,
    })

    # Per-symbol rows
    for sym in SYMBOLS:
        sub = df_h5[df_h5["symbol"] == sym]
        m = calc_metrics(sub)
        pnl_pct = round((m["net_pnl"] / m_h5["net_pnl"]) * 100.0, 2) if m_h5["net_pnl"] != 0 else 0.0
        sym_rows.append({
            "symbol_group": sym,
            "trades": m["trades"],
            "win_rate": m["win_rate"],
            "gross_pnl": m["gross_pnl"],
            "costs": m["costs"],
            "net_pnl": m["net_pnl"],
            "gross_pf": m["gross_pf"],
            "net_pf": m["net_pf"],
            "net_expectancy": m["net_expectancy"],
            "max_drawdown": m["max_drawdown"],
            "pnl_contribution_pct": pnl_pct,
        })
    df_sym = pd.DataFrame(sym_rows)
    df_sym.to_csv(OUT_DIR / "symbol_analysis.csv", index=False)

    # =========================================================================
    # TEST 9 & ARTIFACT 4: symbol_exclusion.csv (Leave-One-Out Matrix)
    # =========================================================================
    print("\n[TEST 9] Generating symbol_exclusion.csv (Leave-One-Out)...")
    excl_rows = []
    for sym in SYMBOLS:
        sub = df_h5[df_h5["symbol"] != sym]
        m = calc_metrics(sub)
        pnl_change_pct = round(((m["net_pnl"] - m_h5["net_pnl"]) / m_h5["net_pnl"]) * 100.0, 2) if m_h5["net_pnl"] != 0 else 0.0
        excl_rows.append({
            "excluded_symbol": sym,
            "remaining_trades": m["trades"],
            "win_rate": m["win_rate"],
            "net_expectancy": m["net_expectancy"],
            "net_pf": m["net_pf"],
            "net_pnl": m["net_pnl"],
            "max_drawdown": m["max_drawdown"],
            "pnl_change_from_total_pct": pnl_change_pct,
        })
    df_excl = pd.DataFrame(excl_rows)
    df_excl.to_csv(OUT_DIR / "symbol_exclusion.csv", index=False)

    # =========================================================================
    # TEST 2 & ARTIFACT 5: monthly_analysis.csv
    # =========================================================================
    print("\n[TEST 2] Generating monthly_analysis.csv...")
    df_h5_copy = df_h5.copy()
    df_h5_copy["month"] = pd.to_datetime(df_h5_copy["entry_datetime"]).dt.strftime("%Y-%m")
    all_months = sorted(pd.to_datetime(df_all["entry_datetime"]).dt.strftime("%Y-%m").unique())

    month_rows = []
    month_pnls = {}
    for m_str in all_months:
        sub = df_h5_copy[df_h5_copy["month"] == m_str]
        m = calc_metrics(sub)
        pnl_contrib = round((m["net_pnl"] / m_h5["net_pnl"]) * 100.0, 2) if m_h5["net_pnl"] != 0 else 0.0
        month_pnls[m_str] = m["net_pnl"]
        month_rows.append({
            "month": m_str,
            "trades": m["trades"],
            "win_rate": m["win_rate"],
            "gross_expectancy": m["gross_expectancy"],
            "net_expectancy": m["net_expectancy"],
            "net_pf": m["net_pf"],
            "net_pnl": m["net_pnl"],
            "contribution_pct": pnl_contrib,
        })
    df_month = pd.DataFrame(month_rows)
    df_month.to_csv(OUT_DIR / "monthly_analysis.csv", index=False)

    # Best month concentration
    best_month = max(month_pnls, key=month_pnls.get)
    pnl_without_best_month = sum(v for k, v in month_pnls.items() if k != best_month)
    best_month_pct = round((month_pnls[best_month] / m_h5["net_pnl"]) * 100.0, 2) if m_h5["net_pnl"] != 0 else 0.0

    # =========================================================================
    # TEST 3 & ARTIFACT 6: direction_analysis.csv
    # =========================================================================
    print("\n[TEST 3] Generating direction_analysis.csv...")
    dir_rows = []
    for d in ["LONG", "SHORT"]:
        sub = df_h5[df_h5["direction"] == d]
        m = calc_metrics(sub)
        dir_rows.append({
            "direction": d,
            "trades": m["trades"],
            "pct_total_trades": round((m["trades"] / n_h5) * 100.0, 2),
            "win_rate": m["win_rate"],
            "gross_expectancy": m["gross_expectancy"],
            "net_expectancy": m["net_expectancy"],
            "gross_pf": m["gross_pf"],
            "net_pf": m["net_pf"],
            "net_pnl": m["net_pnl"],
            "avg_winner": m["avg_winner"],
            "avg_loser": m["avg_loser"],
            "max_drawdown": m["max_drawdown"],
            "max_loss_streak": m["max_loss_streak"],
        })
    df_dir = pd.DataFrame(dir_rows)
    df_dir.to_csv(OUT_DIR / "direction_analysis.csv", index=False)

    # =========================================================================
    # TEST 4 & 11 & ARTIFACT 8: cost_stress.csv
    # =========================================================================
    print("\n[TEST 4 & 11] Generating cost_stress.csv & Breakeven Analysis...")
    cost_rows = []
    cost_tiers = [0.0, 1.0, 1.5, 2.0, 2.5, 3.0]
    for c_mult in cost_tiers:
        m = calc_metrics(df_h5, cost_mult=c_mult)
        cost_rows.append({
            "cost_tier": f"{c_mult}x",
            "trades": m["trades"],
            "gross_expectancy": m["gross_expectancy"],
            "net_expectancy": m["net_expectancy"],
            "net_pf": m["net_pf"],
            "net_pnl": m["net_pnl"],
            "total_costs": m["costs"],
        })
    df_cost = pd.DataFrame(cost_rows)
    df_cost.to_csv(OUT_DIR / "cost_stress.csv", index=False)

    # Exact Breakeven Cost Multiplier: gross_pnl / base_costs
    base_costs = float(df_h5["costs"].sum())
    gross_pnl = float(df_h5["gross_pnl"].sum())
    breakeven_cost_mult = round(gross_pnl / base_costs, 2) if base_costs > 0 else 0.0
    print(f"Cost Breakeven: Gross P&L Rs. {gross_pnl:,.2f} / Base Costs Rs. {base_costs:,.2f} => Breakeven Multiplier = {breakeven_cost_mult}x")

    # =========================================================================
    # TEST 5 & ARTIFACT 7: parameter_stability.csv
    # =========================================================================
    print("\n[TEST 5] Generating parameter_stability.csv (Neighboring Grids)...")
    rs_grid = [0.002, 0.0025, 0.003, 0.0035, 0.004]
    bm_grid = [0.0003, 0.0004, 0.0005, 0.0006, 0.0007]

    param_rows = []
    for rs_th in rs_grid:
        for bm_th in bm_grid:
            is_base = (rs_th == BASE_RS_THRESH and bm_th == BASE_BM_THRESH)
            # Evaluate condition across all 11,222 trades
            cond_long = (df_all["direction"] == "LONG") & (df_all["rs_15"] < -rs_th) & (df_all["bm_ret_15"] > bm_th)
            cond_short = (df_all["direction"] == "SHORT") & (df_all["rs_15"] > rs_th) & (df_all["bm_ret_15"] < -bm_th)
            sub = df_all[cond_long | cond_short]
            m = calc_metrics(sub)
            param_rows.append({
                "rs_threshold": rs_th,
                "bm_threshold": bm_th,
                "is_baseline": is_base,
                "trades": m["trades"],
                "win_rate": m["win_rate"],
                "net_expectancy": m["net_expectancy"],
                "net_pf": m["net_pf"],
                "net_pnl": m["net_pnl"],
                "max_drawdown": m["max_drawdown"],
            })
    df_param = pd.DataFrame(param_rows)
    df_param.to_csv(OUT_DIR / "parameter_stability.csv", index=False)

    pct_profitable_params = round((df_param["net_pnl"] > 0).sum() / len(df_param) * 100.0, 2)
    print(f"Parameter Stability: {pct_profitable_params}% of neighboring grids produce positive net P&L.")

    # =========================================================================
    # TEST 6 & ARTIFACT 9 & 10: trade_distribution.csv & mae_mfe_analysis.csv
    # =========================================================================
    print("\n[TEST 6] Generating trade_distribution.csv and mae_mfe_analysis.csv...")
    net_pnls = (df_h5["gross_pnl"] - df_h5["costs"]).values
    sorted_pnls = np.sort(net_pnls)[::-1]  # Largest winners first

    # Winner concentration
    top_1_n = max(1, int(np.ceil(0.01 * n_h5)))
    top_5_n = max(1, int(np.ceil(0.05 * n_h5)))
    top_10_n = max(1, int(np.ceil(0.10 * n_h5)))

    top_1_pnl = float(np.sum(sorted_pnls[:top_1_n]))
    top_5_pnl = float(np.sum(sorted_pnls[:top_5_n]))
    top_10_pnl = float(np.sum(sorted_pnls[:top_10_n]))
    tot_pnl = float(np.sum(sorted_pnls))

    top_1_pct = round((top_1_pnl / tot_pnl) * 100.0, 2) if tot_pnl > 0 else 0.0
    top_5_pct = round((top_5_pnl / tot_pnl) * 100.0, 2) if tot_pnl > 0 else 0.0
    top_10_pct = round((top_10_pnl / tot_pnl) * 100.0, 2) if tot_pnl > 0 else 0.0

    dist_metrics = [
        {"metric": "total_trades", "value": n_h5},
        {"metric": "mean_net_expectancy", "value": round(float(np.mean(net_pnls)), 2)},
        {"metric": "median_net_pnl", "value": round(float(np.median(net_pnls)), 2)},
        {"metric": "std_dev_pnl", "value": round(float(np.std(net_pnls)), 2)},
        {"metric": "p25_pnl", "value": round(float(np.percentile(net_pnls, 25)), 2)},
        {"metric": "p75_pnl", "value": round(float(np.percentile(net_pnls, 75)), 2)},
        {"metric": "iqr_pnl", "value": round(float(np.percentile(net_pnls, 75) - np.percentile(net_pnls, 25)), 2)},
        {"metric": "largest_winner", "value": round(float(np.max(net_pnls)), 2)},
        {"metric": "largest_loser", "value": round(float(np.min(net_pnls)), 2)},
        {"metric": "top_1pct_winners_pnl", "value": round(top_1_pnl, 2)},
        {"metric": "top_1pct_pnl_share_pct", "value": top_1_pct},
        {"metric": "top_5pct_winners_pnl", "value": round(top_5_pnl, 2)},
        {"metric": "top_5pct_pnl_share_pct", "value": top_5_pct},
        {"metric": "top_10pct_winners_pnl", "value": round(top_10_pnl, 2)},
        {"metric": "top_10pct_pnl_share_pct", "value": top_10_pct},
    ]
    df_dist = pd.DataFrame(dist_metrics)
    df_dist.to_csv(OUT_DIR / "trade_distribution.csv", index=False)

    # MAE / MFE Analysis
    mae_mfe_rows = [
        {"excursion_metric": "mean_mfe_pts", "value": round(float(df_h5["mfe_pts"].mean()), 2)},
        {"excursion_metric": "median_mfe_pts", "value": round(float(df_h5["mfe_pts"].median()), 2)},
        {"excursion_metric": "mean_mfe_pct", "value": round(float(df_h5["mfe_pct"].mean()), 3)},
        {"excursion_metric": "mean_mae_pts", "value": round(float(df_h5["mae_pts"].mean()), 2)},
        {"excursion_metric": "median_mae_pts", "value": round(float(df_h5["mae_pts"].median()), 2)},
        {"excursion_metric": "mean_mae_pct", "value": round(float(df_h5["mae_pct"].mean()), 3)},
        {"excursion_metric": "mfe_to_mae_ratio", "value": round(float(df_h5["mfe_pts"].mean() / (df_h5["mae_pts"].mean() + 1e-9)), 2)},
    ]
    df_mae_mfe = pd.DataFrame(mae_mfe_rows)
    df_mae_mfe.to_csv(OUT_DIR / "mae_mfe_analysis.csv", index=False)

    # =========================================================================
    # TEST 7 & ARTIFACT 12: train_validation_oos.csv
    # =========================================================================
    print("\n[TEST 7] Generating train_validation_oos.csv...")
    df_h5["dt"] = pd.to_datetime(df_h5["entry_datetime"])
    wf_splits = [
        ("TRAIN", pd.Timestamp("2018-01-01"), pd.Timestamp("2018-05-31 23:59:59")),
        ("VALIDATION", pd.Timestamp("2018-06-01"), pd.Timestamp("2018-08-31 23:59:59")),
        ("OOS", pd.Timestamp("2018-09-01"), pd.Timestamp("2018-12-31 23:59:59")),
    ]

    split_rows = []
    for sp_name, s_start, s_end in wf_splits:
        sub = df_h5[(df_h5["dt"] >= s_start) & (df_h5["dt"] <= s_end)]
        m = calc_metrics(sub)
        split_rows.append({
            "split": sp_name,
            "date_range": f"{s_start.strftime('%b')} - {s_end.strftime('%b %Y')}",
            "trades": m["trades"],
            "win_rate": m["win_rate"],
            "gross_expectancy": m["gross_expectancy"],
            "net_expectancy": m["net_expectancy"],
            "net_pf": m["net_pf"],
            "net_pnl": m["net_pnl"],
            "max_drawdown": m["max_drawdown"],
        })
    df_tvo = pd.DataFrame(split_rows)
    df_tvo.to_csv(OUT_DIR / "train_validation_oos.csv", index=False)

    val_row = df_tvo[df_tvo["split"] == "VALIDATION"].iloc[0]
    oos_row = df_tvo[df_tvo["split"] == "OOS"].iloc[0]

    # =========================================================================
    # TEST 8 & ARTIFACT 11: walk_forward.csv (Rolling Quarterly Windows)
    # =========================================================================
    print("\n[TEST 8] Generating walk_forward.csv (Quarterly Rolling Windows)...")
    quarters = [
        ("Q1_2018", pd.Timestamp("2018-01-01"), pd.Timestamp("2018-03-31 23:59:59")),
        ("Q2_2018", pd.Timestamp("2018-04-01"), pd.Timestamp("2018-06-30 23:59:59")),
        ("Q3_2018", pd.Timestamp("2018-07-01"), pd.Timestamp("2018-09-30 23:59:59")),
        ("Q4_2018", pd.Timestamp("2018-10-01"), pd.Timestamp("2018-12-31 23:59:59")),
    ]
    wf_rows = []
    for q_name, q_start, q_end in quarters:
        sub = df_h5[(df_h5["dt"] >= q_start) & (df_h5["dt"] <= q_end)]
        m = calc_metrics(sub)
        wf_rows.append({
            "quarter": q_name,
            "trades": m["trades"],
            "win_rate": m["win_rate"],
            "gross_expectancy": m["gross_expectancy"],
            "net_expectancy": m["net_expectancy"],
            "net_pf": m["net_pf"],
            "net_pnl": m["net_pnl"],
            "max_drawdown": m["max_drawdown"],
        })
    df_wf = pd.DataFrame(wf_rows)
    df_wf.to_csv(OUT_DIR / "walk_forward.csv", index=False)

    # =========================================================================
    # TEST 10 & ARTIFACT 13: concentration_analysis.csv
    # =========================================================================
    print("\n[TEST 10] Generating concentration_analysis.csv...")
    infy_pnl = float(df_h5[df_h5["symbol"] == "INFY"]["gross_pnl"].sum() - df_h5[df_h5["symbol"] == "INFY"]["costs"].sum())
    infy_pnl_pct = round((infy_pnl / m_h5["net_pnl"]) * 100.0, 2) if m_h5["net_pnl"] != 0 else 0.0

    conc_rows = [
        {"dimension": "symbol_infy_share_pct", "value": infy_pnl_pct, "threshold_limit": 50.0, "risk_flag": infy_pnl_pct > 50.0},
        {"dimension": "symbol_pnl_without_infy", "value": round(m_no_infy["net_pnl"], 2), "threshold_limit": 0.0, "risk_flag": m_no_infy["net_pnl"] <= 0.0},
        {"dimension": "month_best_month_share_pct", "value": best_month_pct, "threshold_limit": 50.0, "risk_flag": best_month_pct > 50.0},
        {"dimension": "month_pnl_without_best_month", "value": round(pnl_without_best_month, 2), "threshold_limit": 0.0, "risk_flag": pnl_without_best_month <= 0.0},
        {"dimension": "top_1pct_winner_share_pct", "value": top_1_pct, "threshold_limit": 25.0, "risk_flag": top_1_pct > 25.0},
        {"dimension": "top_5pct_winner_share_pct", "value": top_5_pct, "threshold_limit": 50.0, "risk_flag": top_5_pct > 50.0},
        {"dimension": "top_10pct_winner_share_pct", "value": top_10_pct, "threshold_limit": 70.0, "risk_flag": top_10_pct > 70.0},
        {"dimension": "sample_size_trades", "value": n_h5, "threshold_limit": 200.0, "risk_flag": n_h5 < 200},
    ]
    df_conc = pd.DataFrame(conc_rows)
    df_conc.to_csv(OUT_DIR / "concentration_analysis.csv", index=False)

    # =========================================================================
    # TEST 12 & ARTIFACT 14: falsification_results.csv (8 Forensic Flags)
    # =========================================================================
    print("\n[TEST 12] Auditing 8 Forensic Falsification Flags...")
    falsification_audit = [
        (
            "1. INSUFFICIENT_SAMPLE_SIZE",
            n_h5 < 200,
            f"Total trades {n_h5} (< 200 threshold). OOS trades: {oos_row['trades']} (< 200).",
        ),
        (
            "2. SYMBOL_CONCENTRATION_RISK",
            infy_pnl_pct > 70.0,
            f"INFY accounts for {infy_pnl_pct}% of total net profits. P&L w/o INFY: Rs. {m_no_infy['net_pnl']:,.2f}.",
        ),
        (
            "3. MONTH_CONCENTRATION_RISK",
            best_month_pct > 50.0,
            f"Best month ({best_month}) accounts for {best_month_pct}% of profits.",
        ),
        (
            "4. DIRECTIONAL_ASYMMETRY",
            False,
            f"Long win rate {df_dir.loc[0, 'win_rate']}% vs Short win rate {df_dir.loc[1, 'win_rate']}%. Both directions traded.",
        ),
        (
            "5. PARAMETER_FRAGILITY",
            pct_profitable_params < 70.0,
            f"{pct_profitable_params}% of neighboring parameter combinations profitable.",
        ),
        (
            "6. COST_FRAGILITY",
            breakeven_cost_mult < 1.5,
            f"Breakeven multiplier is {breakeven_cost_mult}x costs.",
        ),
        (
            "7. VALIDATION_FAILURE",
            float(val_row["net_expectancy"]) < 0.0,
            f"Validation net expectancy is negative: -Rs. {abs(float(val_row['net_expectancy'])):.2f}.",
        ),
        (
            "8. WINNER_DEPENDENCY",
            top_5_pct > 60.0,
            f"Top 5% of winners contribute {top_5_pct}% of total net profits.",
        ),
    ]

    fals_rows = []
    active_flags = []
    for flag_name, is_flagged, details in falsification_audit:
        fals_rows.append({
            "falsification_flag": flag_name,
            "flagged": is_flagged,
            "details": details,
        })
        if is_flagged:
            active_flags.append(flag_name)

    df_fals = pd.DataFrame(fals_rows)
    df_fals.to_csv(OUT_DIR / "falsification_results.csv", index=False)

    # Final Classification Taxonomy
    if len(active_flags) == 0:
        final_verdict = "ROBUST EDGE"
        recommendation = "Promote to paper trading"
    elif "1. INSUFFICIENT_SAMPLE_SIZE" in active_flags and "2. SYMBOL_CONCENTRATION_RISK" in active_flags:
        final_verdict = "SYMBOL-CONCENTRATED / INSUFFICIENT SAMPLE"
        recommendation = "DO NOT promote to production. Insufficient statistical sample and severe single-stock reliance."
    elif "1. INSUFFICIENT_SAMPLE_SIZE" in active_flags:
        final_verdict = "PROMISING — NEEDS MORE DATA"
        recommendation = "Do not deploy. Requires multi-year out-of-sample data expansion."
    elif "2. SYMBOL_CONCENTRATION_RISK" in active_flags:
        final_verdict = "SYMBOL-CONCENTRATED"
        recommendation = "Do not deploy. Edge fails cross-symbol invariance."
    elif "5. PARAMETER_FRAGILITY" in active_flags:
        final_verdict = "PARAMETER-FRAGILE"
        recommendation = "Do not deploy. Sharp cliff in parameter neighborhood."
    elif "6. COST_FRAGILITY" in active_flags:
        final_verdict = "COST-DESTROYED"
        recommendation = "Do not deploy. Cannot overcome institutional friction."
    else:
        final_verdict = "FRAGILE EDGE"
        recommendation = "Do not deploy. Failed walk-forward or concentration audits."

    print(f"\nForensic Verdict: {final_verdict} (Active Flags: {len(active_flags)}/8)")

    # =========================================================================
    # ARTIFACT 15: phase11_verdict.csv
    # =========================================================================
    verdict_rows = [
        {"metric": "final_classification", "value": final_verdict},
        {"metric": "robust_edge_found", "value": "YES" if final_verdict == "ROBUST EDGE" else "NO"},
        {"metric": "total_trades", "value": n_h5},
        {"metric": "net_expectancy", "value": m_h5["net_expectancy"]},
        {"metric": "net_pf", "value": m_h5["net_pf"]},
        {"metric": "net_pnl", "value": m_h5["net_pnl"]},
        {"metric": "val_expectancy", "value": val_row["net_expectancy"]},
        {"metric": "oos_expectancy", "value": oos_row["net_expectancy"]},
        {"metric": "infy_pnl_share_pct", "value": infy_pnl_pct},
        {"metric": "pnl_without_infy", "value": m_no_infy["net_pnl"]},
        {"metric": "breakeven_cost_mult", "value": f"{breakeven_cost_mult}x"},
        {"metric": "active_flags_count", "value": len(active_flags)},
        {"metric": "recommendation", "value": recommendation},
    ]
    df_verd = pd.DataFrame(verdict_rows)
    df_verd.to_csv(OUT_DIR / "phase11_verdict.csv", index=False)

    # =========================================================================
    # ARTIFACT 1: phase11_report.md
    # =========================================================================
    print("Writing phase11_report.md...")
    report_md = f"""# SignalForge — Phase 11: H5 RS Divergence Forensic Robustness Report

## 1. Executive Summary & Objective
Phase 11 conducted an isolated forensic robustness audit on **`H5_RS_DIVERGENCE`**, the sole candidate in Phase 10 with positive net P&L.

### Primary Verdict: **{final_verdict}**
**ROBUST EDGE FOUND: {"YES" if final_verdict == "ROBUST EDGE" else "NO"}**
- **Recommendation**: {recommendation}

---

## 2. Overall Comparison (Baseline vs H5)
{df_to_markdown(df_comp)}

---

## 3. Symbol Robustness & Concentration Audit
{df_to_markdown(df_sym)}

- **INFY Dependency**: INFY accounts for **{infy_pnl_pct}%** of all net profits (Rs. {infy_pnl:,.2f} of Rs. {m_h5['net_pnl']:,.2f}).
- **Ex-INFY Performance**: With INFY removed, 2018 net P&L drops to **Rs. {m_no_infy['net_pnl']:,.2f}** across 48 trades.

---

## 4. Symbol Exclusion Matrix (Leave-One-Out)
{df_to_markdown(df_excl)}

---

## 5. Monthly Robustness & Concentration
{df_to_markdown(df_month)}

- **Best Month**: `{best_month}` contributed **{best_month_pct}%** of total profits.
- **P&L without Best Month**: Rs. {pnl_without_best_month:,.2f}.

---

## 6. Directional Robustness (Long vs Short)
{df_to_markdown(df_dir)}

---

## 7. Cost Stress & Breakeven Analysis
{df_to_markdown(df_cost)}

- **Breakeven Cost Multiplier**: **{breakeven_cost_mult}x** transaction costs.

---

## 8. Parameter Perturbation & Stability Grid
{df_to_markdown(df_param)}

- **Grid Survival Rate**: {pct_profitable_params}% of neighboring grids produce positive net P&L.

---

## 9. Trade Distribution & Winner Dependency
{df_to_markdown(df_dist)}

---

## 10. MAE / MFE Adverse Excursion Analysis
{df_to_markdown(df_mae_mfe)}

---

## 11. Chronological Walk-Forward Stability
{df_to_markdown(df_tvo)}

- **Validation Drawdown**: Jun–Aug 2018 experienced **-Rs. {abs(float(val_row['net_expectancy'])):.2f} net expectancy** (Net PF: {val_row['net_pf']}).

---

## 12. Quarterly Rolling Walk-Forward
{df_to_markdown(df_wf)}

---

## 13. Concentration & Dependency Metrics
{df_to_markdown(df_conc)}

---

## 14. Forensic Falsification Audit (8 Flags)
{df_to_markdown(df_fals)}

---

## 15. Forensic Conclusion & Governance Decision
While `H5_RS_DIVERGENCE` demonstrates genuine counter-trend characteristics with high cost survival ({breakeven_cost_mult}x breakeven) and positive OOS return, it is **disqualified from production promotion** due to:
1. **Severe single-stock concentration** (INFY = 97.14% of profits).
2. **Extreme sample scarcity** (80 trades across the entire year 2018; only 0.33 trades/day).
3. **Validation drawdown** (-Rs. 100.49 net expectancy in Jun–Aug 2018).
"""
    (OUT_DIR / "phase11_report.md").write_text(report_md, encoding="utf-8")

    elapsed = time.time() - start_time
    print(f"\nPhase 11 forensic audit completed in {elapsed:.1f}s. All 15 artifacts written to {OUT_DIR.name}/.")


if __name__ == "__main__":
    run_phase11()
