"""
SignalForge — Phase 32E.4: Independent DTP-V2 Robustness & Concentration Audit Runner
====================================================================================
File: scripts/run_phase32e_4_audit.py

Executes a forensic robustness, profit concentration, leave-one-out,
regime sensitivity, temporal consistency, execution slippage, and
bootstrap statistical audit of the DTP-V2 1.25%-1.50% sizing improvements.
Strictly read-only with respect to strategy and cost engine code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import math
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from scripts.run_phase32d_3_dtp_v1_expanded_validation import (
    APPROVED_21_SYMBOLS,
    EXPANDED_SECTOR_MAP,
    EXPANDED_ISIN_MAP,
    load_and_resample_21_universe,
)
from src.strategy.dtp_v2.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV2Config,
    OrderAction,
)
from src.strategy.dtp_v2.cost_integration import calculate_dtp_roundtrip_costs
from src.strategy.dtp_v2.market_filter import evaluate_breadth_regime

OUT_DIR = PROJECT_ROOT / "reports" / "phase32e_4"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_phase32e_3_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Loads Phase 32E.3 scenario summaries and trade ledger."""
    summary_path = PROJECT_ROOT / "reports" / "phase32e_3" / "phase32e_3_scenario_summary.csv"
    ledger_path = PROJECT_ROOT / "reports" / "phase32e_3" / "phase32e_3_trade_ledger.csv"
    
    if not summary_path.exists() or not ledger_path.exists():
        raise FileNotFoundError("Phase 32E.3 deliverables missing! Run Phase 32E.3 first.")
        
    df_summary = pd.read_csv(summary_path)
    df_trades = pd.read_csv(ledger_path)
    return df_summary, df_trades


def calculate_metrics_from_trades(
    trades_df: pd.DataFrame,
    initial_capital: float = 100000.0,
    annual_trading_days: int = 739,
) -> Dict[str, Any]:
    """Calculates comprehensive performance metrics from a set of executed trades."""
    n_trades = len(trades_df)
    if n_trades == 0:
        return {
            "trades": 0, "win_rate_pct": 0.0, "net_pnl": 0.0, "gross_pnl": 0.0,
            "total_costs": 0.0, "net_pf": 0.0, "payoff_ratio": 0.0, "expectancy": 0.0,
            "avg_win": 0.0, "avg_loss": 0.0, "wins": 0, "losses": 0,
        }
        
    wins_df = trades_df[trades_df["net_pnl"] > 0]
    losses_df = trades_df[trades_df["net_pnl"] <= 0]
    n_wins = len(wins_df)
    n_losses = len(losses_df)
    
    net_pnl = float(trades_df["net_pnl"].sum())
    gross_pnl = float(trades_df["gross_pnl"].sum())
    total_costs = float(trades_df["total_costs"].sum())
    
    win_rate = (n_wins / n_trades) * 100.0
    gross_wins = float(wins_df["net_pnl"].sum())
    gross_losses = float(abs(losses_df["net_pnl"].sum()))
    net_pf = gross_wins / gross_losses if gross_losses > 0 else 999.0
    
    avg_win = float(wins_df["net_pnl"].mean()) if n_wins > 0 else 0.0
    avg_loss = float(abs(losses_df["net_pnl"].mean())) if n_losses > 0 else 0.0
    payoff = avg_win / avg_loss if avg_loss > 0 else 999.0
    expectancy = float(trades_df["net_pnl"].mean())
    
    return {
        "trades": n_trades,
        "wins": n_wins,
        "losses": n_losses,
        "win_rate_pct": round(win_rate, 2),
        "gross_pnl": round(gross_pnl, 2),
        "total_costs": round(total_costs, 2),
        "net_pnl": round(net_pnl, 2),
        "net_pf": round(net_pf, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "payoff_ratio": round(payoff, 2),
        "expectancy": round(expectancy, 2),
    }


def audit_profit_concentration(df_trades: pd.DataFrame, target_scenarios: List[str]) -> pd.DataFrame:
    """Computes Top 1, 3, 5, 10 trade profit contribution and impact of removing top winners."""
    rows = []
    
    for scen_id in target_scenarios:
        scen_trades = df_trades[df_trades["scenario_id"] == scen_id].sort_values(by="net_pnl", ascending=False).reset_index(drop=True)
        total_pnl = float(scen_trades["net_pnl"].sum())
        total_gross = float(scen_trades["gross_pnl"].sum())
        base_metrics = calculate_metrics_from_trades(scen_trades)
        
        for k in [1, 3, 5, 10]:
            top_k = scen_trades.iloc[:k]
            top_k_pnl = float(top_k["net_pnl"].sum())
            top_k_gross = float(top_k["gross_pnl"].sum())
            
            pnl_share_pct = (top_k_pnl / total_pnl) * 100.0 if total_pnl != 0 else 0.0
            gross_share_pct = (top_k_gross / total_gross) * 100.0 if total_gross != 0 else 0.0
            
            # Exclude top k
            remaining_trades = scen_trades.iloc[k:]
            rem_metrics = calculate_metrics_from_trades(remaining_trades)
            
            rows.append({
                "scenario_id": scen_id,
                "top_n_trades": k,
                "top_n_net_pnl": round(top_k_pnl, 2),
                "top_n_gross_pnl": round(top_k_gross, 2),
                "share_of_total_net_pnl_pct": round(pnl_share_pct, 2),
                "share_of_total_gross_pnl_pct": round(gross_share_pct, 2),
                "remaining_trades_count": rem_metrics["trades"],
                "remaining_net_pnl": rem_metrics["net_pnl"],
                "remaining_net_pf": rem_metrics["net_pf"],
                "remaining_win_rate_pct": rem_metrics["win_rate_pct"],
                "remaining_payoff_ratio": rem_metrics["payoff_ratio"],
                "profitable_without_top_n": "YES" if rem_metrics["net_pnl"] > 0 else "NO",
            })
            
    return pd.DataFrame(rows)


def audit_stock_concentration(df_trades: pd.DataFrame, target_scenarios: List[str]) -> pd.DataFrame:
    """Computes per-stock contribution and leave-one-stock-out (LOSO) sensitivity."""
    rows = []
    
    for scen_id in target_scenarios:
        scen_trades = df_trades[df_trades["scenario_id"] == scen_id].copy()
        total_pnl = float(scen_trades["net_pnl"].sum())
        base_metrics = calculate_metrics_from_trades(scen_trades)
        
        # Calculate HHI of stock net profits (for positive contributors)
        stock_pnls = scen_trades.groupby("symbol")["net_pnl"].sum()
        pos_pnls = stock_pnls[stock_pnls > 0]
        if pos_pnls.sum() > 0:
            shares = pos_pnls / pos_pnls.sum()
            hhi = float((shares ** 2).sum() * 10000.0)
        else:
            hhi = 0.0
            
        for sym in APPROVED_21_SYMBOLS:
            sym_trades = scen_trades[scen_trades["symbol"] == sym]
            n_t = len(sym_trades)
            sym_pnl = float(sym_trades["net_pnl"].sum()) if n_t > 0 else 0.0
            pnl_share = (sym_pnl / total_pnl) * 100.0 if total_pnl != 0 else 0.0
            
            # Leave-one-stock-out
            loso_trades = scen_trades[scen_trades["symbol"] != sym]
            loso_metrics = calculate_metrics_from_trades(loso_trades)
            
            rows.append({
                "scenario_id": scen_id,
                "symbol": sym,
                "sector": EXPANDED_SECTOR_MAP.get(sym, "Unknown"),
                "trades": n_t,
                "stock_net_pnl": round(sym_pnl, 2),
                "stock_net_pnl_share_pct": round(pnl_share, 2),
                "loso_remaining_trades": loso_metrics["trades"],
                "loso_remaining_net_pnl": loso_metrics["net_pnl"],
                "loso_remaining_net_pf": loso_metrics["net_pf"],
                "loso_remaining_win_rate_pct": loso_metrics["win_rate_pct"],
                "loso_pnl_impact_inr": round(loso_metrics["net_pnl"] - base_metrics["net_pnl"], 2),
                "hhi_stock_concentration": round(hhi, 1),
            })
            
    return pd.DataFrame(rows)


def audit_sector_concentration(df_trades: pd.DataFrame, target_scenarios: List[str]) -> pd.DataFrame:
    """Computes per-sector contribution and leave-one-sector-out (LOSO) sensitivity."""
    rows = []
    unique_sectors = sorted(list(set(EXPANDED_SECTOR_MAP.values())))
    
    for scen_id in target_scenarios:
        scen_trades = df_trades[df_trades["scenario_id"] == scen_id].copy()
        total_pnl = float(scen_trades["net_pnl"].sum())
        base_metrics = calculate_metrics_from_trades(scen_trades)
        
        for sec in unique_sectors:
            sec_trades = scen_trades[scen_trades["sector"] == sec]
            n_t = len(sec_trades)
            sec_pnl = float(sec_trades["net_pnl"].sum()) if n_t > 0 else 0.0
            pnl_share = (sec_pnl / total_pnl) * 100.0 if total_pnl != 0 else 0.0
            
            # Leave-one-sector-out
            loso_trades = scen_trades[scen_trades["sector"] != sec]
            loso_metrics = calculate_metrics_from_trades(loso_trades)
            
            rows.append({
                "scenario_id": scen_id,
                "sector": sec,
                "trades": n_t,
                "sector_net_pnl": round(sec_pnl, 2),
                "sector_net_pnl_share_pct": round(pnl_share, 2),
                "loso_remaining_trades": loso_metrics["trades"],
                "loso_remaining_net_pnl": loso_metrics["net_pnl"],
                "loso_remaining_net_pf": loso_metrics["net_pf"],
                "loso_remaining_win_rate_pct": loso_metrics["win_rate_pct"],
                "loso_pnl_impact_inr": round(loso_metrics["net_pnl"] - base_metrics["net_pnl"], 2),
                "profitable_without_sector": "YES" if loso_metrics["net_pnl"] > 0 else "NO",
            })
            
    return pd.DataFrame(rows)


def audit_market_regime(
    df_trades: pd.DataFrame,
    target_scenarios: List[str],
    universe_daily: Dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Categorizes trades by market breadth regime at entry date."""
    rows = []
    trading_dates = list(universe_daily[APPROVED_21_SYMBOLS[0]].index)
    date_to_idx = {ts.date(): idx for idx, ts in enumerate(trading_dates)}
    
    # Precompute breadth regime for all dates
    regime_cache = {}
    cfg = DTPV2Config()
    for d, idx in date_to_idx.items():
        state, _ = evaluate_breadth_regime(universe_daily, config=cfg, bar_idx=idx)
        regime_cache[d.isoformat()] = state.value
        
    for scen_id in target_scenarios:
        scen_trades = df_trades[df_trades["scenario_id"] == scen_id].copy()
        scen_trades["entry_regime"] = scen_trades["entry_date"].map(regime_cache).fillna("NEUTRAL")
        
        for reg in ["BULLISH", "NEUTRAL", "BEARISH"]:
            sub = scen_trades[scen_trades["entry_regime"] == reg]
            m = calculate_metrics_from_trades(sub)
            rows.append({
                "scenario_id": scen_id,
                "market_regime": reg,
                "trades": m["trades"],
                "wins": m["wins"],
                "losses": m["losses"],
                "win_rate_pct": m["win_rate_pct"],
                "gross_pnl": m["gross_pnl"],
                "total_costs": m["total_costs"],
                "net_pnl": m["net_pnl"],
                "net_pf": m["net_pf"],
                "payoff_ratio": m["payoff_ratio"],
                "expectancy_inr": m["expectancy"],
            })
            
    return pd.DataFrame(rows)


def audit_rolling_periods(df_trades: pd.DataFrame, target_scenarios: List[str]) -> pd.DataFrame:
    """Evaluates performance across calendar years and semi-annual subperiods."""
    rows = []
    
    for scen_id in target_scenarios:
        scen_trades = df_trades[df_trades["scenario_id"] == scen_id].copy()
        scen_trades["year"] = pd.to_datetime(scen_trades["entry_date"]).dt.year
        scen_trades["half"] = scen_trades["year"].astype(str) + "-H" + (
            (pd.to_datetime(scen_trades["entry_date"]).dt.month <= 6).map({True: "1", False: "2"})
        )
        
        # Yearly
        for yr in [2017, 2018, 2019]:
            sub = scen_trades[scen_trades["year"] == yr]
            m = calculate_metrics_from_trades(sub)
            rows.append({
                "scenario_id": scen_id,
                "period_type": "CALENDAR_YEAR",
                "period_label": str(yr),
                "trades": m["trades"],
                "wins": m["wins"],
                "losses": m["losses"],
                "win_rate_pct": m["win_rate_pct"],
                "net_pnl": m["net_pnl"],
                "net_pf": m["net_pf"],
                "payoff_ratio": m["payoff_ratio"],
                "expectancy_inr": m["expectancy"],
            })
            
        # Semi-annual
        for h in ["2017-H1", "2017-H2", "2018-H1", "2018-H2", "2019-H1", "2019-H2"]:
            sub = scen_trades[scen_trades["half"] == h]
            m = calculate_metrics_from_trades(sub)
            rows.append({
                "scenario_id": scen_id,
                "period_type": "SEMI_ANNUAL",
                "period_label": h,
                "trades": m["trades"],
                "wins": m["wins"],
                "losses": m["losses"],
                "win_rate_pct": m["win_rate_pct"],
                "net_pnl": m["net_pnl"],
                "net_pf": m["net_pf"],
                "payoff_ratio": m["payoff_ratio"],
                "expectancy_inr": m["expectancy"],
            })
            
    return pd.DataFrame(rows)


def audit_execution_sensitivity(
    df_trades: pd.DataFrame,
    target_scenarios: List[str],
) -> pd.DataFrame:
    """Tests execution sensitivity across additional slippage assumptions."""
    rows = []
    
    # Friction configurations:
    # Baseline: 10 bps roundtrip (5 bps slip + 5 bps spread)
    # Conservative: 15 bps roundtrip (10 bps slip + 5 bps spread)
    # Severe: 25 bps roundtrip (15 bps slip + 10 bps spread)
    # Extreme: 40 bps roundtrip (25 bps slip + 15 bps spread)
    friction_levels = [
        ("STANDARD_10BPS", 0.0010, "Standard: 5 bps slip + 5 bps spread (10 bps total)"),
        ("CONSERVATIVE_15BPS", 0.0015, "Conservative: 10 bps slip + 5 bps spread (15 bps total)"),
        ("SEVERE_25BPS", 0.0025, "Severe: 15 bps slip + 10 bps spread (25 bps total)"),
        ("EXTREME_40BPS", 0.0040, "Extreme: 25 bps slip + 15 bps spread (40 bps total)"),
    ]
    
    for scen_id in target_scenarios:
        scen_trades = df_trades[df_trades["scenario_id"] == scen_id].copy()
        is_stress = "STRESS" in scen_id
        
        for f_id, f_rate, f_desc in friction_levels:
            # Recompute total costs by adjusting execution friction
            adj_trades = scen_trades.copy()
            # Standard execution friction was 10 bps on turnover
            standard_friction = adj_trades["total_turnover"] * 0.0010
            new_friction = adj_trades["total_turnover"] * f_rate
            diff_friction = new_friction - standard_friction
            
            adj_trades["total_costs"] = adj_trades["total_costs"] + diff_friction
            adj_trades["net_pnl"] = adj_trades["gross_pnl"] - adj_trades["total_costs"]
            
            m = calculate_metrics_from_trades(adj_trades)
            rows.append({
                "scenario_id": scen_id,
                "friction_level_id": f_id,
                "friction_description": f_desc,
                "roundtrip_friction_bps": int(f_rate * 10000),
                "trades": m["trades"],
                "win_rate_pct": m["win_rate_pct"],
                "gross_pnl": m["gross_pnl"],
                "total_friction_costs": round(float(adj_trades["total_costs"].sum()), 2),
                "net_pnl": m["net_pnl"],
                "net_pf": m["net_pf"],
                "payoff_ratio": m["payoff_ratio"],
                "expectancy_inr": m["expectancy"],
                "cost_to_gross_pct": round((adj_trades["total_costs"].sum() / m["gross_pnl"]) * 100.0, 2) if m["gross_pnl"] > 0 else 999.0,
                "gate_1_net_pf_pass": "PASS" if m["net_pf"] >= 1.30 else "FAIL",
            })
            
    return pd.DataFrame(rows)


def audit_confidence_intervals(df_trades: pd.DataFrame, target_scenarios: List[str], n_bootstrap: int = 10000) -> pd.DataFrame:
    """Performs 10,000-iteration bootstrap resampling for 95% Confidence Intervals."""
    rows = []
    np.random.seed(42)
    
    for scen_id in target_scenarios:
        scen_trades = df_trades[df_trades["scenario_id"] == scen_id].copy()
        pnls = scen_trades["net_pnl"].values
        n_t = len(pnls)
        
        # Descriptive Distribution Stats
        mean_pnl = float(np.mean(pnls))
        median_pnl = float(np.median(pnls))
        std_pnl = float(np.std(pnls, ddof=1))
        # Skewness: m3 / m2^1.5
        m2 = float(np.mean((pnls - mean_pnl) ** 2))
        m3 = float(np.mean((pnls - mean_pnl) ** 3))
        m4 = float(np.mean((pnls - mean_pnl) ** 4))
        skew = m3 / (m2 ** 1.5) if m2 > 0 else 0.0
        kurt = (m4 / (m2 ** 2)) - 3.0 if m2 > 0 else 0.0
        
        # Bootstrap resampling
        boot_pf = []
        boot_wr = []
        boot_exp = []
        boot_payoff = []
        
        for _ in range(n_bootstrap):
            sample = np.random.choice(pnls, size=n_t, replace=True)
            wins = sample[sample > 0]
            losses = sample[sample <= 0]
            gwins = float(np.sum(wins)) if len(wins) > 0 else 0.0
            glosses = float(abs(np.sum(losses))) if len(losses) > 0 else 0.0
            
            pf = gwins / glosses if glosses > 0 else 999.0
            wr = (len(wins) / n_t) * 100.0
            exp = float(np.mean(sample))
            
            aw = float(np.mean(wins)) if len(wins) > 0 else 0.0
            al = float(abs(np.mean(losses))) if len(losses) > 0 else 0.0
            po = aw / al if al > 0 else 999.0
            
            boot_pf.append(pf)
            boot_wr.append(wr)
            boot_exp.append(exp)
            boot_payoff.append(po)
            
        ci_pf_low, ci_pf_high = np.percentile(boot_pf, [2.5, 97.5])
        ci_wr_low, ci_wr_high = np.percentile(boot_wr, [2.5, 97.5])
        ci_exp_low, ci_exp_high = np.percentile(boot_exp, [2.5, 97.5])
        ci_po_low, ci_po_high = np.percentile(boot_payoff, [2.5, 97.5])
        
        rows.append({
            "scenario_id": scen_id,
            "sample_size": n_t,
            "mean_net_pnl": round(mean_pnl, 2),
            "median_net_pnl": round(median_pnl, 2),
            "std_net_pnl": round(std_pnl, 2),
            "skewness": round(skew, 2),
            "excess_kurtosis": round(kurt, 2),
            "net_pf_point_est": round(float(np.mean(boot_pf)), 2),
            "net_pf_ci_95_lower": round(float(ci_pf_low), 2),
            "net_pf_ci_95_upper": round(float(ci_pf_high), 2),
            "win_rate_point_est": round(float(np.mean(boot_wr)), 2),
            "win_rate_ci_95_lower": round(float(ci_wr_low), 2),
            "win_rate_ci_95_upper": round(float(ci_wr_high), 2),
            "expectancy_point_est": round(float(np.mean(boot_exp)), 2),
            "expectancy_ci_95_lower": round(float(ci_exp_low), 2),
            "expectancy_ci_95_upper": round(float(ci_exp_high), 2),
            "payoff_point_est": round(float(np.mean(boot_payoff)), 2),
            "payoff_ci_95_lower": round(float(ci_po_low), 2),
            "payoff_ci_95_upper": round(float(ci_po_high), 2),
        })
        
    return pd.DataFrame(rows)


def audit_acceptance_gates(df_summary: pd.DataFrame, target_scenarios: List[str]) -> pd.DataFrame:
    """Evaluates all 6 unaltered acceptance gates across audited scenarios."""
    gate_defs = [
        ("GATE_1_NET_PF", "Net Profit Factor >= 1.30", 1.30, lambda s: s["net_pf"] >= 1.30, lambda s: f"{s['net_pf']:.2f}"),
        ("GATE_2_WIN_RATE", "Win Rate >= 45%", 45.0, lambda s: s["win_rate_pct"] >= 45.0, lambda s: f"{s['win_rate_pct']:.2f}%"),
        ("GATE_3_MAX_DD", "Maximum Drawdown <= 18%", 18.0, lambda s: s["max_drawdown_pct"] <= 18.0, lambda s: f"{s['max_drawdown_pct']:.2f}%"),
        ("GATE_4_TRADES", "Completed Trades >= 30", 30, lambda s: s["completed_trades"] >= 30, lambda s: f"{s['completed_trades']}"),
        ("GATE_5_CAGR", "CAGR >= 12%", 12.0, lambda s: s["cagr_pct"] >= 12.0, lambda s: f"{s['cagr_pct']:.2f}%"),
        ("GATE_6_PAYOFF", "Payoff Ratio >= 1.80", 1.80, lambda s: s["payoff_ratio"] >= 1.80, lambda s: f"{s['payoff_ratio']:.2f}"),
    ]
    
    rows = []
    sub_summary = df_summary[df_summary["scenario_id"].isin(target_scenarios)]
    
    for _, s in sub_summary.iterrows():
        for gid, gdesc, thresh, eval_fn, act_fn in gate_defs:
            status = "PASS" if eval_fn(s) else "FAIL"
            rows.append({
                "scenario_id": s["scenario_id"],
                "scenario_name": s["scenario_name"],
                "cost_schedule": s["cost_schedule"],
                "gate_id": gid,
                "gate_description": gdesc,
                "threshold": thresh,
                "actual_value": act_fn(s),
                "status": status,
            })
            
    return pd.DataFrame(rows)


def main():
    print("=" * 80)
    print("SignalForge — Phase 32E.4: Independent DTP-V2 Robustness & Concentration Audit")
    print("=" * 80)
    
    print("\n1. Loading Phase 32E.3 deliverables...")
    df_summary, df_trades = load_phase32e_3_data()
    print(f"Loaded scenario summary ({len(df_summary)} rows) and trade ledger ({len(df_trades)} trades).")
    
    target_scenarios = [
        "SCEN_BASE_DTP_V2_OFFICIAL_307",
        "SCEN_BASE_DTP_V2_STRESS_317",
        "SCEN_S3_RISK_125_OFFICIAL_307",
        "SCEN_S3_RISK_125_STRESS_317",
        "SCEN_S4_RISK_150_OFFICIAL_307",
        "SCEN_S4_RISK_150_STRESS_317",
    ]
    
    print("\n2. Loading universe daily data for regime evaluation...")
    universe_daily = load_and_resample_21_universe()
    
    print("\n3. Auditing Profit Concentration (Top 1, 3, 5, 10 trades)...")
    df_profit_conc = audit_profit_concentration(df_trades, target_scenarios)
    profit_conc_path = OUT_DIR / "profit_concentration.csv"
    df_profit_conc.to_csv(profit_conc_path, index=False)
    print(f"Saved {profit_conc_path}")
    
    print("\n4. Auditing Stock Concentration & Leave-One-Stock-Out...")
    df_stock_conc = audit_stock_concentration(df_trades, target_scenarios)
    stock_conc_path = OUT_DIR / "stock_concentration.csv"
    df_stock_conc.to_csv(stock_conc_path, index=False)
    print(f"Saved {stock_conc_path}")
    
    print("\n5. Auditing Sector Concentration & Leave-One-Sector-Out...")
    df_sector_conc = audit_sector_concentration(df_trades, target_scenarios)
    sector_conc_path = OUT_DIR / "sector_concentration.csv"
    df_sector_conc.to_csv(sector_conc_path, index=False)
    print(f"Saved {sector_conc_path}")
    
    print("\n6. Auditing Market Regime Sensitivity (Breadth Regimes)...")
    df_regime = audit_market_regime(df_trades, target_scenarios, universe_daily)
    regime_path = OUT_DIR / "market_regime_analysis.csv"
    df_regime.to_csv(regime_path, index=False)
    print(f"Saved {regime_path}")
    
    print("\n7. Auditing Temporal Consistency (Calendar Years & Semi-Annuals)...")
    df_rolling = audit_rolling_periods(df_trades, target_scenarios)
    rolling_path = OUT_DIR / "rolling_period_analysis.csv"
    df_rolling.to_csv(rolling_path, index=False)
    print(f"Saved {rolling_path}")
    
    print("\n8. Auditing Execution Sensitivity (Slippage Scaling)...")
    df_exec = audit_execution_sensitivity(df_trades, target_scenarios)
    exec_path = OUT_DIR / "execution_sensitivity.csv"
    df_exec.to_csv(exec_path, index=False)
    print(f"Saved {exec_path}")
    
    print("\n9. Auditing Statistical Robustness (Bootstrap 95% Confidence Intervals)...")
    df_ci = audit_confidence_intervals(df_trades, target_scenarios, n_bootstrap=10000)
    ci_path = OUT_DIR / "confidence_intervals.csv"
    df_ci.to_csv(ci_path, index=False)
    print(f"Saved {ci_path}")
    
    print("\n10. Auditing Acceptance Gates...")
    df_gates = audit_acceptance_gates(df_summary, target_scenarios)
    gates_path = OUT_DIR / "acceptance_gates.csv"
    df_gates.to_csv(gates_path, index=False)
    print(f"Saved {gates_path}")
    
    print("\nPhase 32E.4 Data Processing Complete. All 8 CSV deliverables saved in reports/phase32e_4/")

if __name__ == "__main__":
    main()
