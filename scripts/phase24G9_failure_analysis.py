"""
SignalForge — Phase 24G.9: Strategy Failure Analysis and Research Gate

Performs an independent mathematical audit of Phase 24G.8 trade logs and
a descriptive diagnostic root-cause analysis of strategy failure across:
1. Training (2017–2018)
2. Validation (2019)
3. Holdout (2020)
4. Combined (2017–2020)

Strictly diagnostic: NO parameter tuning, NO optimization, NO new configuration.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

G8_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G8_oos_validation"
OUT_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G9_failure_analysis"
DATA_PATH = PROJECT_ROOT / "data" / "historical" / "stocks" / "ADANIPORTS_1m.csv"
MANIFEST_PATH = PROJECT_ROOT / "data" / "historical" / "manifests" / "ADANIPORTS_1m_manifest.json"
SNAPSHOT_PATH = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase22_final_validation" / "strategy_snapshot.json"

EXPECTED_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
EXPECTED_DATA_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"


def verify_preflight():
    print("=" * 80)
    print("PHASE 24G.9 PREFLIGHT VERIFICATION")
    print("=" * 80)

    # 1. Strategy Snapshot Hash
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    computed_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    print(f"Strategy Config Hash: {computed_hash}")
    assert computed_hash == EXPECTED_CONFIG_HASH, f"Hash mismatch: expected {EXPECTED_CONFIG_HASH}, got {computed_hash}"

    # 2. Dataset Manifest Hash
    data_bytes = DATA_PATH.read_bytes()
    computed_data_hash = hashlib.sha256(data_bytes).hexdigest()
    print(f"ADANIPORTS SHA-256:  {computed_data_hash}")
    assert computed_data_hash == EXPECTED_DATA_HASH, f"Dataset hash mismatch: expected {EXPECTED_DATA_HASH}, got {computed_data_hash}"

    print("Preflight verification passed successfully.\n")


def audit_trade_log(filepath: Path, capital_initial: float = 100000.0) -> dict:
    """Recalculate all performance metrics independently from the raw trade CSV."""
    df = pd.read_csv(filepath)
    if df.empty:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "breakeven_trades": 0,
            "win_rate_pct": 0.0,
            "gross_pnl": 0.0,
            "transaction_costs": 0.0,
            "net_pnl": 0.0,
            "return_pct": 0.0,
            "profit_factor": None,
            "max_drawdown_amount": 0.0,
            "max_drawdown_pct": 0.0,
            "final_equity": capital_initial,
            "long_trades": 0,
            "long_win_rate_pct": 0.0,
            "long_gross_pnl": 0.0,
            "long_net_pnl": 0.0,
            "short_trades": 0,
            "short_win_rate_pct": 0.0,
            "short_gross_pnl": 0.0,
            "short_net_pnl": 0.0,
        }

    total_trades = len(df)
    winning = df[df["net_pnl"] > 0]
    losing = df[df["net_pnl"] < 0]
    breakeven = df[df["net_pnl"] == 0]

    gross_pnl = df["gross_pnl"].sum()
    transaction_costs = df["transaction_cost"].sum()
    net_pnl = df["net_pnl"].sum()
    final_equity = capital_initial + net_pnl
    return_pct = (net_pnl / capital_initial) * 100.0

    win_rate = (len(winning) / total_trades * 100.0) if total_trades > 0 else 0.0

    gross_profit = winning["net_pnl"].sum()
    gross_loss = abs(losing["net_pnl"].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

    # Long vs Short
    long_df = df[df["position"].str.upper() == "LONG"]
    short_df = df[df["position"].str.upper() == "SHORT"]

    long_win = long_df[long_df["net_pnl"] > 0]
    short_win = short_df[short_df["net_pnl"] > 0]

    long_win_rate = (len(long_win) / len(long_df) * 100.0) if len(long_df) > 0 else 0.0
    short_win_rate = (len(short_win) / len(short_df) * 100.0) if len(short_df) > 0 else 0.0

    # Drawdown Calculation: Peak equity minus current running equity
    equity = capital_initial
    peak = capital_initial
    max_dd_amount = 0.0
    max_dd_pct = 0.0

    for pnl in df["net_pnl"]:
        equity += pnl
        if equity > peak:
            peak = equity
        dd_amount = peak - equity
        dd_pct = (dd_amount / peak * 100.0) if peak > 0 else 0.0
        if dd_amount > max_dd_amount:
            max_dd_amount = dd_amount
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

    return {
        "total_trades": total_trades,
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "breakeven_trades": len(breakeven),
        "win_rate_pct": round(win_rate, 2),
        "gross_pnl": round(gross_pnl, 2),
        "transaction_costs": round(transaction_costs, 2),
        "net_pnl": round(net_pnl, 2),
        "return_pct": round(return_pct, 4),
        "profit_factor": round(profit_factor, 4) if np.isfinite(profit_factor) else None,
        "max_drawdown_amount": round(max_dd_amount, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "final_equity": round(final_equity, 2),
        "long_trades": len(long_df),
        "long_win_rate_pct": round(long_win_rate, 2),
        "long_gross_pnl": round(long_df["gross_pnl"].sum(), 2),
        "long_net_pnl": round(long_df["net_pnl"].sum(), 2),
        "short_trades": len(short_df),
        "short_win_rate_pct": round(short_win_rate, 2),
        "short_gross_pnl": round(short_df["gross_pnl"].sum(), 2),
        "short_net_pnl": round(short_df["net_pnl"].sum(), 2),
    }


def analyze_duration_and_eod(df_trades: pd.DataFrame, partition_name: str) -> dict:
    """Analyze trade duration and determine whether exits were forced at EOD (15:29)."""
    if df_trades.empty:
        return {}

    entry_dt = pd.to_datetime(df_trades["entry_time"])
    exit_dt = pd.to_datetime(df_trades["exit_time"])
    durations = (exit_dt - entry_dt).dt.total_seconds() / 60.0

    # Check EOD exit (15:29:00)
    eod_exits = exit_dt.dt.time == pd.Timestamp("15:29:00").time()
    eod_exit_count = int(eod_exits.sum())
    eod_pct = (eod_exit_count / len(df_trades)) * 100.0

    reversal_exits = len(df_trades) - eod_exit_count

    return {
        "partition": partition_name,
        "total_trades": len(df_trades),
        "mean_duration_mins": round(durations.mean(), 1),
        "median_duration_mins": round(durations.median(), 1),
        "min_duration_mins": round(durations.min(), 1),
        "max_duration_mins": round(durations.max(), 1),
        "std_duration_mins": round(durations.std(), 1),
        "eod_exits_1529": eod_exit_count,
        "eod_exit_pct": round(eod_pct, 2),
        "reversal_exits": reversal_exits,
        "reversal_exit_pct": round(100.0 - eod_pct, 2),
    }


def analyze_hourly_distribution(df_trades: pd.DataFrame) -> pd.DataFrame:
    """Analyze win rates and P&L by entry hour."""
    df = df_trades.copy()
    entry_dt = pd.to_datetime(df["entry_time"])
    df["entry_hour"] = entry_dt.dt.hour

    hourly = []
    for hour, grp in df.groupby("entry_hour"):
        n = len(grp)
        wins = len(grp[grp["net_pnl"] > 0])
        wr = (wins / n * 100.0) if n > 0 else 0.0
        net = grp["net_pnl"].sum()
        gross = grp["gross_pnl"].sum()
        hourly.append({
            "entry_hour": f"{hour:02d}:00–{hour:02d}:59",
            "trades": n,
            "win_rate_pct": round(wr, 2),
            "gross_pnl": round(gross, 2),
            "net_pnl": round(net, 2),
            "avg_trade_net": round(net / n, 2) if n > 0 else 0.0,
        })
    return pd.DataFrame(hourly)


def analyze_monthly_performance(df_trades: pd.DataFrame) -> pd.DataFrame:
    """Analyze month-by-month performance across the combined dataset."""
    df = df_trades.copy()
    entry_dt = pd.to_datetime(df["entry_time"])
    df["year_month"] = entry_dt.dt.to_period("M").astype(str)

    monthly = []
    for ym, grp in df.groupby("year_month"):
        n = len(grp)
        wins = len(grp[grp["net_pnl"] > 0])
        wr = (wins / n * 100.0) if n > 0 else 0.0
        net = grp["net_pnl"].sum()
        gross = grp["gross_pnl"].sum()
        costs = grp["transaction_cost"].sum()
        monthly.append({
            "year_month": ym,
            "trades": n,
            "win_rate_pct": round(wr, 2),
            "gross_pnl": round(gross, 2),
            "costs": round(costs, 2),
            "net_pnl": round(net, 2),
            "profitable": net > 0,
        })
    return pd.DataFrame(monthly)


def analyze_streaks_and_concentration(df_trades: pd.DataFrame, partition_name: str) -> dict:
    """Analyze winning/losing streaks and P&L concentration."""
    if df_trades.empty:
        return {}

    pnl_series = df_trades["net_pnl"].tolist()

    max_win_streak = 0
    max_loss_streak = 0
    cur_win_streak = 0
    cur_loss_streak = 0

    for pnl in pnl_series:
        if pnl > 0:
            cur_win_streak += 1
            cur_loss_streak = 0
            if cur_win_streak > max_win_streak:
                max_win_streak = cur_win_streak
        elif pnl < 0:
            cur_loss_streak += 1
            cur_win_streak = 0
            if cur_loss_streak > max_loss_streak:
                max_loss_streak = cur_loss_streak
        else:
            cur_win_streak = 0
            cur_loss_streak = 0

    sorted_df = df_trades.sort_values(by="net_pnl", ascending=False)
    top_5_wins = sorted_df.head(5)["net_pnl"].tolist()
    top_5_losses = sorted_df.tail(5)["net_pnl"].tolist()

    top_5_wins_sum = sum(top_5_wins)
    total_net = df_trades["net_pnl"].sum()
    rem_net = total_net - top_5_wins_sum

    return {
        "partition": partition_name,
        "max_consecutive_wins": max_win_streak,
        "max_consecutive_losses": max_loss_streak,
        "total_net_pnl": round(total_net, 2),
        "top_5_wins_sum": round(top_5_wins_sum, 2),
        "net_without_top_5_wins": round(rem_net, 2),
        "top_5_losses_sum": round(sum(top_5_losses), 2),
        "largest_win": round(max(pnl_series), 2),
        "largest_loss": round(min(pnl_series), 2),
    }


def analyze_cost_sensitivity(df_trades: pd.DataFrame, partition_name: str) -> pd.DataFrame:
    """
    Evaluate sensitivity to transaction costs as diagnostic scenarios:
    0 bps (gross), 1 bps (official), 2 bps, 5 bps, 10 bps.
    """
    # Turnover for each trade = (entry_price + exit_price) * quantity
    turnovers = (df_trades["entry_price"] + df_trades["exit_price"]) * df_trades["quantity"]
    gross_pnls = df_trades["gross_pnl"]

    cost_rates = [0.0, 0.0001, 0.0002, 0.0005, 0.0010]
    rate_labels = ["0 bps (Gross)", "1 bps (Official)", "2 bps", "5 bps", "10 bps"]

    scenarios = []
    for rate, label in zip(cost_rates, rate_labels):
        trade_costs = turnovers * rate
        net_pnls = gross_pnls - trade_costs

        winning = net_pnls[net_pnls > 0]
        losing = net_pnls[net_pnls < 0]
        wr = (len(winning) / len(df_trades) * 100.0) if len(df_trades) > 0 else 0.0

        gross_profit = winning.sum()
        gross_loss = abs(losing.sum())
        pf = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

        scenarios.append({
            "partition": partition_name,
            "cost_scenario": label,
            "rate": rate,
            "total_costs": round(trade_costs.sum(), 2),
            "net_pnl": round(net_pnls.sum(), 2),
            "win_rate_pct": round(wr, 2),
            "profit_factor": round(pf, 4) if np.isfinite(pf) else None,
        })
    return pd.DataFrame(scenarios)


def main():
    verify_preflight()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load trade logs
    files = {
        "training_2017_2018": G8_DIR / "trades_training_2017_2018.csv",
        "validation_2019": G8_DIR / "trades_validation_2019.csv",
        "holdout_2020": G8_DIR / "trades_holdout_2020.csv",
        "trailing_stub_2021": G8_DIR / "trades_trailing_stub_2021.csv",
        "combined_2017_2020": G8_DIR / "trades_combined_2017_2020.csv",
    }

    partition_display = {
        "training_2017_2018": "Training (2017–2018)",
        "validation_2019": "Validation (2019)",
        "holdout_2020": "Holdout Test (2020)",
        "trailing_stub_2021": "Trailing Stub (2021-01-01)",
        "combined_2017_2020": "Combined (2017–2020)",
    }

    trade_dfs = {}
    recalculated = {}

    for k, p in files.items():
        if not p.exists():
            raise FileNotFoundError(f"Missing required Phase 24G.8 trade artifact: {p}")
        df_t = pd.read_csv(p)
        trade_dfs[k] = df_t
        recalculated[k] = audit_trade_log(p)

    # 2. Reconcile with phase24G8_oos_metrics.json
    with open(G8_DIR / "phase24G8_oos_metrics.json", "r", encoding="utf-8") as f:
        g8_metrics = json.load(f)

    g8_dict = {p["partition"]: p for p in g8_metrics["partitions"]}

    reconciliation_rows = []
    discrepancy_log = []

    for k, disp_name in partition_display.items():
        recalc = recalculated[k]
        # Match with g8_dict by starting name
        matched_g8 = None
        for g8_k, g8_val in g8_dict.items():
            if g8_k.startswith(disp_name.split()[0]):
                matched_g8 = g8_val
                break

        if matched_g8 is None:
            discrepancy_log.append(f"Could not find partition {disp_name} in Phase 24G.8 metrics JSON")
            continue

        keys_to_compare = [
            "total_trades",
            "winning_trades",
            "losing_trades",
            "win_rate_pct",
            "gross_pnl",
            "transaction_costs",
            "net_pnl",
            "profit_factor",
            "max_drawdown_amount",
            "final_equity",
            "long_trades",
            "long_net_pnl",
            "short_trades",
            "short_net_pnl",
        ]

        discrepancies = {}
        for prop in keys_to_compare:
            v_recalc = recalc.get(prop)
            v_g8 = matched_g8.get(prop)
            diff = abs(v_recalc - v_g8) if (v_recalc is not None and v_g8 is not None) else 0.0
            if diff > 1e-4:
                discrepancies[prop] = {"recalculated": v_recalc, "reported": v_g8, "delta": diff}
                discrepancy_log.append(f"[{disp_name}] Discrepancy on {prop}: recalc={v_recalc} vs reported={v_g8}")

        reconciliation_rows.append({
            "partition": disp_name,
            "trades_recalc": recalc["total_trades"],
            "trades_reported": matched_g8["total_trades"],
            "win_rate_recalc": recalc["win_rate_pct"],
            "win_rate_reported": matched_g8["win_rate_pct"],
            "net_pnl_recalc": recalc["net_pnl"],
            "net_pnl_reported": matched_g8["net_pnl"],
            "profit_factor_recalc": recalc["profit_factor"],
            "profit_factor_reported": matched_g8["profit_factor"],
            "max_dd_recalc": recalc["max_drawdown_amount"],
            "max_dd_reported": matched_g8["max_drawdown_amount"],
            "discrepancies_detected": len(discrepancies),
        })

    reconciliation_df = pd.DataFrame(reconciliation_rows)
    reconciliation_df.to_csv(OUT_DIR / "audit_reconciliation.csv", index=False)

    print("\n" + "=" * 80)
    print("INDEPENDENT AUDIT & RECONCILIATION TABLE")
    print("=" * 80)
    print(reconciliation_df.to_string(index=False))
    if not discrepancy_log:
        print(">> PERFECT RECONCILIATION: 0 discrepancies detected across all partitions.")
    else:
        print(f">> DISCREPANCIES DETECTED: {len(discrepancy_log)}")
        for d in discrepancy_log:
            print(f"   * {d}")

    # 3. Holding Duration & EOD Exit Analysis
    duration_rows = [
        analyze_duration_and_eod(trade_dfs[k], disp_name)
        for k, disp_name in partition_display.items()
    ]
    duration_df = pd.DataFrame(duration_rows)
    duration_df.to_csv(OUT_DIR / "duration_and_eod_analysis.csv", index=False)

    print("\n" + "=" * 80)
    print("HOLDING DURATION & EOD EXIT BEHAVIOR")
    print("=" * 80)
    print(duration_df[["partition", "total_trades", "mean_duration_mins", "median_duration_mins", "eod_exits_1529", "eod_exit_pct", "reversal_exits"]].to_string(index=False))

    # 4. Hourly Performance Breakdown
    combined_df = trade_dfs["combined_2017_2020"]
    hourly_df = analyze_hourly_distribution(combined_df)
    hourly_df.to_csv(OUT_DIR / "hourly_performance.csv", index=False)

    print("\n" + "=" * 80)
    print("HOURLY PERFORMANCE DISTRIBUTION (COMBINED 2017–2020)")
    print("=" * 80)
    print(hourly_df.to_string(index=False))

    # 5. Monthly Performance
    monthly_df = analyze_monthly_performance(combined_df)
    monthly_df.to_csv(OUT_DIR / "monthly_performance.csv", index=False)
    prof_months = len(monthly_df[monthly_df["profitable"]])
    loss_months = len(monthly_df[~monthly_df["profitable"]])
    print(f"\nMonthly Performance: {prof_months} profitable months vs {loss_months} losing months out of {len(monthly_df)} total months.")

    # 6. Concentration & Streak Analysis
    concentration_rows = [
        analyze_streaks_and_concentration(trade_dfs[k], disp_name)
        for k, disp_name in partition_display.items()
    ]
    concentration_df = pd.DataFrame(concentration_rows)
    concentration_df.to_csv(OUT_DIR / "top_trades_concentration.csv", index=False)

    print("\n" + "=" * 80)
    print("CONCENTRATION & STREAK ANALYSIS")
    print("=" * 80)
    print(concentration_df.to_string(index=False))

    # Detailed 2019 Concentration Stress Test
    df_2019 = trade_dfs["validation_2019"].sort_values(by="net_pnl", ascending=False)
    top_1 = df_2019.iloc[0]["net_pnl"]
    top_2 = df_2019.iloc[:2]["net_pnl"].sum()
    top_3 = df_2019.iloc[:3]["net_pnl"].sum()
    top_5 = df_2019.iloc[:5]["net_pnl"].sum()
    net_2019 = df_2019["net_pnl"].sum()

    print("\n" + "=" * 80)
    print("2019 VALIDATION GAIN CONCENTRATION STRESS TEST")
    print("=" * 80)
    print(f"Total 2019 Net P&L:               Rs {net_2019:.2f} (187 trades)")
    print(f"Top 1 Winning Trade:              Rs {top_1:.2f} ({top_1 / net_2019 * 100:.1f}% of total net profit)")
    print(f"Top 2 Winning Trades Sum:         Rs {top_2:.2f} ({top_2 / net_2019 * 100:.1f}% of total net profit)")
    print(f"Top 3 Winning Trades Sum:         Rs {top_3:.2f} ({top_3 / net_2019 * 100:.1f}% of total net profit)")
    print(f"Top 5 Winning Trades Sum:         Rs {top_5:.2f} ({top_5 / net_2019 * 100:.1f}% of total net profit)")
    print(f"Net P&L Without Top 5 Trades:     Rs {net_2019 - top_5:.2f} (across remaining 182 trades)")

    # 7. Cost Sensitivity Scenarios
    cost_dfs = [
        analyze_cost_sensitivity(trade_dfs[k], disp_name)
        for k, disp_name in partition_display.items()
    ]
    all_costs_df = pd.concat(cost_dfs, ignore_index=True)
    all_costs_df.to_csv(OUT_DIR / "cost_sensitivity_scenarios.csv", index=False)

    print("\n" + "=" * 80)
    print("TRANSACTION COST SENSITIVITY SCENARIOS (DIAGNOSTIC ONLY)")
    print("=" * 80)
    print(all_costs_df.to_string(index=False))

    # 8. Save Comprehensive Metrics JSON
    with open(OUT_DIR / "failure_analysis_metrics.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "preflight": {
                    "strategy_hash": EXPECTED_CONFIG_HASH,
                    "dataset_sha256": EXPECTED_DATA_HASH,
                    "dataset": "ADANIPORTS",
                },
                "audit_reconciliation": reconciliation_rows,
                "discrepancies": discrepancy_log,
                "duration_and_eod": duration_rows,
                "concentration_and_streaks": concentration_rows,
                "stress_test_2019": {
                    "total_net_pnl": round(net_2019, 2),
                    "top_1_trade": round(top_1, 2),
                    "top_2_trades": round(top_2, 2),
                    "top_3_trades": round(top_3, 2),
                    "top_5_trades": round(top_5, 2),
                    "net_without_top_5": round(net_2019 - top_5, 2),
                },
                "monthly_summary": {
                    "total_months": len(monthly_df),
                    "profitable_months": prof_months,
                    "losing_months": loss_months,
                },
                "cost_sensitivity": all_costs_df.to_dict(orient="records"),
            },
            f,
            indent=2,
        )

    print("\nDiagnostic failure analysis completed. All artifacts saved to:")
    print(f"  {OUT_DIR}")


if __name__ == "__main__":
    main()
