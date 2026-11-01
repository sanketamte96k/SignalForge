"""
SignalForge — Phase 24G.15: Quantitative Strategy Research Experiment Runner
============================================================================
Executes controlled historical evaluations of four alternative strategy hypotheses:
  - Hypothesis A: Trend Pullback & Continuation
  - Hypothesis B: Volatility Compression & Breakout
  - Hypothesis C: Regime-Filtered Mean Reversion
  - Hypothesis D: Regime-Adaptive Multi-Strategy

Across chronological partitions on ADANIPORTS 1m:
  1. Training (2017–2018): Initial hypothesis development & filtering
  2. Validation (2019): Out-of-sample persistence & candidate freeze
  3. Holdout (2020): Final frozen candidate verification (diagnostic only)
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.risk_engine_v2 import (
    CostBreakdown,
    CostModelType,
    ExitReason,
    PositionSide,
    RejectionReason,
    RiskEngineConfigV2,
    RiskEngineV2,
    RiskEngineV2Result,
    V2Trade,
)
from research.strategy_evolution_2018.phase24G15_strategy_research.research_hypotheses import (
    build_multi_timeframe_features,
    generate_hypothesis_signals,
)

OUT_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G15_strategy_research"
DATA_PATH = PROJECT_ROOT / "data" / "historical" / "stocks" / "ADANIPORTS_1m.csv"
SNAPSHOT_PATH = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase22_final_validation" / "strategy_snapshot.json"
REGISTRY_PATH = PROJECT_ROOT / "data" / "universe_registry.json"
PAPER_LEDGER_PATH = PROJECT_ROOT / "data" / "paper_trading" / "interactive_trades.json"

EXPECTED_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
EXPECTED_DATA_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"


def verify_preflight():
    print("=" * 80)
    print("PHASE 24G.15 RESEARCH PREFLIGHT VERIFICATION")
    print("=" * 80)

    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    cfg_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    print(f"Strategy Snapshot Hash: {cfg_hash}")
    assert cfg_hash == EXPECTED_CONFIG_HASH, f"Config hash mismatch: expected {EXPECTED_CONFIG_HASH}, got {cfg_hash}"

    data_bytes = DATA_PATH.read_bytes()
    data_hash = hashlib.sha256(data_bytes).hexdigest()
    print(f"ADANIPORTS SHA-256:     {data_hash}")
    assert data_hash == EXPECTED_DATA_HASH, f"Data hash mismatch: expected {EXPECTED_DATA_HASH}, got {data_hash}"

    assert REGISTRY_PATH.exists(), "Universe registry missing"
    assert PAPER_LEDGER_PATH.exists(), "Paper ledger missing"
    print("Preflight verification passed successfully.\n")


def compute_metrics(
    res: RiskEngineV2Result,
    hypothesis_name: str,
    cost_model_name: str,
    partition_name: str,
    p_slice: pd.DataFrame,
    runtime_s: float,
) -> dict:
    """Compute complete 21-metric standardized quantitative profile."""
    trades = res.trades
    total_trades = len(trades)
    winning = [t for t in trades if t.net_pnl > 0]
    losing = [t for t in trades if t.net_pnl < 0]
    breakeven = [t for t in trades if t.net_pnl == 0]

    win_rate = (len(winning) / total_trades * 100.0) if total_trades > 0 else 0.0
    gross_pnl = sum(t.gross_pnl for t in trades)
    total_costs = sum(t.transaction_cost for t in trades)
    net_pnl = sum(t.net_pnl for t in trades)
    ret_pct = (net_pnl / res.initial_capital * 100.0)

    brokerage = sum(t.cost_breakdown.brokerage for t in trades)
    statutory_fees = sum(
        t.cost_breakdown.stt
        + t.cost_breakdown.exchange_charges
        + t.cost_breakdown.sebi_charges
        + t.cost_breakdown.stamp_duty
        + t.cost_breakdown.gst
        for t in trades
    )
    slippage = sum(t.cost_breakdown.slippage for t in trades)

    gross_profit = sum(t.net_pnl for t in winning)
    gross_loss = abs(sum(t.net_pnl for t in losing))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

    avg_win = (gross_profit / len(winning)) if len(winning) > 0 else 0.0
    avg_loss = (gross_loss / len(losing)) if len(losing) > 0 else 0.0
    win_prob = len(winning) / total_trades if total_trades > 0 else 0.0
    loss_prob = len(losing) / total_trades if total_trades > 0 else 0.0
    expectancy = (win_prob * avg_win) - (loss_prob * avg_loss)

    exit_counts: dict[str, int] = {}
    gap_count = 0
    holding_bars_list = []
    buy_turnover = 0.0
    sell_turnover = 0.0

    for t in trades:
        exit_counts[t.exit_reason] = exit_counts.get(t.exit_reason, 0) + 1
        holding_bars_list.append(t.bars_held)
        buy_turnover += t.entry_price * t.quantity if t.side == PositionSide.LONG else t.exit_price * t.quantity
        sell_turnover += t.exit_price * t.quantity if t.side == PositionSide.LONG else t.entry_price * t.quantity
        if t.side == PositionSide.LONG and t.exit_price < t.initial_stop:
            gap_count += 1
        elif t.side == PositionSide.SHORT and t.exit_price > t.initial_stop:
            gap_count += 1

    rejection_counts: dict[str, int] = {}
    for r in res.audit_rejections:
        reason = r.get("reason", "UNKNOWN")
        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1

    trading_days = len(set(p_slice.index.date))
    avg_hold = float(np.mean(holding_bars_list)) if holding_bars_list else 0.0
    med_hold = float(np.median(holding_bars_list)) if holding_bars_list else 0.0

    return {
        "hypothesis": hypothesis_name,
        "cost_model": cost_model_name,
        "partition": partition_name,
        "trading_days": trading_days,
        "total_trades": total_trades,
        "avg_trades_per_day": round(total_trades / trading_days, 2) if trading_days > 0 else 0.0,
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate_pct": round(win_rate, 2),
        "gross_pnl": round(gross_pnl, 2),
        "total_costs": round(total_costs, 2),
        "brokerage": round(brokerage, 2),
        "statutory_charges": round(statutory_fees, 2),
        "slippage": round(slippage, 2),
        "net_pnl": round(net_pnl, 2),
        "return_pct": round(ret_pct, 4),
        "profit_factor": round(profit_factor, 4) if np.isfinite(profit_factor) else None,
        "max_drawdown_amount": round(res.max_drawdown_amount, 2),
        "max_drawdown_pct": round(res.max_drawdown_pct, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy_per_trade": round(expectancy, 2),
        "avg_holding_bars": round(avg_hold, 1),
        "median_holding_bars": round(med_hold, 1),
        "total_traded_notional": round(buy_turnover + sell_turnover, 2),
        "stop_loss_exits": exit_counts.get(ExitReason.STOP_LOSS.value, 0),
        "target_exits": exit_counts.get(ExitReason.TAKE_PROFIT.value, 0),
        "eod_exits": exit_counts.get(ExitReason.EOD.value, 0),
        "gap_through_stop_exits": gap_count,
        "daily_loss_limit_activations": exit_counts.get(ExitReason.DAILY_LOSS_HALT.value, 0) + rejection_counts.get(RejectionReason.DAILY_LOSS_LIMIT.value, 0),
        "cooldown_activations": rejection_counts.get(RejectionReason.CONSECUTIVE_LOSS_COOLDOWN.value, 0),
        "insufficient_capital_rejections": rejection_counts.get(RejectionReason.INSUFFICIENT_CAPITAL.value, 0),
        "total_rejected_orders": len(res.audit_rejections),
        "trade_log_hash": res.trade_log_hash,
        "runtime_seconds": round(runtime_s, 2),
    }


def save_trades_csv(trades: tuple[V2Trade, ...], filepath: Path) -> str:
    records = [t.to_dict() for t in trades]
    df_t = pd.DataFrame(records)
    df_t.to_csv(filepath, index=False)
    return hashlib.sha256(filepath.read_bytes()).hexdigest()


def main():
    verify_preflight()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading ADANIPORTS 1m historical dataset...")
    df_raw = pd.read_csv(DATA_PATH, parse_dates=["timestamp"]).set_index("timestamp").sort_index()

    print("Building multi-timeframe feature matrix (5m, 15m, 30m)...")
    t0 = time.time()
    features = build_multi_timeframe_features(df_raw)
    print(f"Features ready in {time.time() - t0:.2f}s.")

    hypotheses = [
        "HYPOTHESIS_A_TREND_PULLBACK",
        "HYPOTHESIS_B_VOLATILITY_BREAKOUT",
        "HYPOTHESIS_C_MEAN_REVERSION",
        "HYPOTHESIS_D_REGIME_ADAPTIVE",
    ]

    print("\nPre-generating signal streams for all hypotheses...")
    signals_dict = {}
    for hyp in hypotheses:
        t_sig = time.time()
        sig_series = generate_hypothesis_signals(features, hyp)
        signals_dict[hyp] = sig_series
        valid_count = sig_series.dropna().count()
        longs = (sig_series == PositionSide.LONG).sum()
        shorts = (sig_series == PositionSide.SHORT).sum()
        print(f"  [{hyp}] generated {valid_count} signals ({longs} LONG, {shorts} SHORT) in {time.time() - t_sig:.2f}s.")

    partitions = {
        "training_2017_2018": {
            "name": "Training (2017–2018)",
            "slice": df_raw["2017-01-02 09:15:00":"2018-12-31 15:29:00"],
        },
        "validation_2019": {
            "name": "Validation (2019)",
            "slice": df_raw["2019-01-01 09:15:00":"2019-12-31 15:29:00"],
        },
        "holdout_2020": {
            "name": "Holdout Test (2020)",
            "slice": df_raw["2020-01-01 09:15:00":"2020-12-31 15:29:00"],
        },
    }

    # Standard V2 Engine Configurations
    cfg_baseline = RiskEngineConfigV2.pre_registered(
        registration_id="SF-V2-RESEARCH-PHASE24G15-BASE",
        initial_capital=100000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        k_stop=1.5,
        k_target=3.0,
        daily_loss_limit_pct=0.02,
        consecutive_loss_limit=3,
        cooldown_minutes=60,
        execution_model="next_open",
        cost_model=CostModelType.HISTORICAL_BASELINE,
        slippage=0.0,
    )

    cfg_realistic = RiskEngineConfigV2.pre_registered(
        registration_id="SF-V2-RESEARCH-PHASE24G15-REAL",
        initial_capital=100000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        k_stop=1.5,
        k_target=3.0,
        daily_loss_limit_pct=0.02,
        consecutive_loss_limit=3,
        cooldown_minutes=60,
        execution_model="next_open",
        cost_model=CostModelType.REALISTIC_INTRADAY,
        slippage=0.0,
    )

    all_results = []
    trade_hashes = {}

    # ------------------------------------------------------------------------
    # STEP 1: Evaluate Training (2017–2018) & Validation (2019)
    # ------------------------------------------------------------------------
    for p_id in ("training_2017_2018", "validation_2019"):
        p_info = partitions[p_id]
        p_name = p_info["name"]
        p_slice = p_info["slice"]

        print("\n" + "=" * 80)
        print(f"EVALUATING PARTITION: {p_name} ({len(p_slice):,} candles)")
        print("=" * 80)

        for hyp in hypotheses:
            p_sigs = signals_dict[hyp].loc[p_slice.index[0]:p_slice.index[-1]].to_numpy()

            # 1. Baseline Cost Model (1 bps)
            t_run = time.time()
            engine_b = RiskEngineV2(cfg_baseline)
            res_b = engine_b.run(p_slice, p_sigs)
            rt_b = time.time() - t_run

            mb = compute_metrics(res_b, hyp, "1 bps baseline", p_name, p_slice, rt_b)
            all_results.append(mb)

            csv_file_b = OUT_DIR / f"trades_{hyp}_{p_id}_baseline.csv"
            h_b = save_trades_csv(res_b.trades, csv_file_b)
            trade_hashes[csv_file_b.name] = h_b

            print(f"[{hyp[:24]:24s} | 1 bps] Trades: {mb['total_trades']:4d} | Win: {mb['win_rate_pct']:5.2f}% | Gross: Rs {mb['gross_pnl']:9.2f} | Net: Rs {mb['net_pnl']:9.2f} | PF: {str(mb['profit_factor']):6s} | DD: Rs {mb['max_drawdown_amount']:8.2f}")

            # 2. Realistic Statutory Friction Model
            t_run = time.time()
            engine_r = RiskEngineV2(cfg_realistic)
            res_r = engine_r.run(p_slice, p_sigs)
            rt_r = time.time() - t_run

            mr = compute_metrics(res_r, hyp, "realistic statutory", p_name, p_slice, rt_r)
            all_results.append(mr)

            csv_file_r = OUT_DIR / f"trades_{hyp}_{p_id}_realistic.csv"
            h_r = save_trades_csv(res_r.trades, csv_file_r)
            trade_hashes[csv_file_r.name] = h_r

            print(f"[{hyp[:24]:24s} | Real ] Trades: {mr['total_trades']:4d} | Win: {mr['win_rate_pct']:5.2f}% | Gross: Rs {mr['gross_pnl']:9.2f} | Net: Rs {mr['net_pnl']:9.2f} | PF: {str(mr['profit_factor']):6s} | DD: Rs {mr['max_drawdown_amount']:8.2f}")

    # ------------------------------------------------------------------------
    # STEP 2: Candidate Freezing & Selection for Holdout Verification
    # ------------------------------------------------------------------------
    # Based on Training & Validation results, identify top candidate to evaluate on Holdout
    print("\n" + "=" * 80)
    print("ANALYZING TRAINING & VALIDATION SELECTION CRITERIA...")
    print("=" * 80)
    df_interim = pd.DataFrame(all_results)
    print(df_interim[["hypothesis", "cost_model", "partition", "total_trades", "win_rate_pct", "gross_pnl", "net_pnl", "profit_factor", "expectancy_per_trade"]].to_string(index=False))

    # Evaluate best candidate on Holdout 2020 (Untouched Out-of-Sample)
    # To maintain strict research integrity, evaluate ALL 4 on Holdout to report full out-of-sample evidence
    p_info = partitions["holdout_2020"]
    p_name = p_info["name"]
    p_slice = p_info["slice"]

    print("\n" + "=" * 80)
    print(f"EVALUATING UNTOUCHED HOLDOUT (2020): Diagnostic Out-of-Sample Test")
    print("=" * 80)

    for hyp in hypotheses:
        p_sigs = signals_dict[hyp].loc[p_slice.index[0]:p_slice.index[-1]].to_numpy()

        # 1. Baseline
        t_run = time.time()
        engine_b = RiskEngineV2(cfg_baseline)
        res_b = engine_b.run(p_slice, p_sigs)
        rt_b = time.time() - t_run
        mb = compute_metrics(res_b, hyp, "1 bps baseline", p_name, p_slice, rt_b)
        all_results.append(mb)
        csv_file_b = OUT_DIR / f"trades_{hyp}_holdout_2020_baseline.csv"
        trade_hashes[csv_file_b.name] = save_trades_csv(res_b.trades, csv_file_b)

        # 2. Realistic
        t_run = time.time()
        engine_r = RiskEngineV2(cfg_realistic)
        res_r = engine_r.run(p_slice, p_sigs)
        rt_r = time.time() - t_run
        mr = compute_metrics(res_r, hyp, "realistic statutory", p_name, p_slice, rt_r)
        all_results.append(mr)
        csv_file_r = OUT_DIR / f"trades_{hyp}_holdout_2020_realistic.csv"
        trade_hashes[csv_file_r.name] = save_trades_csv(res_r.trades, csv_file_r)

        print(f"[{hyp[:24]:24s} | Holdout Base] Trades: {mb['total_trades']:4d} | Win: {mb['win_rate_pct']:5.2f}% | Gross: Rs {mb['gross_pnl']:9.2f} | Net: Rs {mb['net_pnl']:9.2f} | PF: {str(mb['profit_factor']):6s}")
        print(f"[{hyp[:24]:24s} | Holdout Real] Trades: {mr['total_trades']:4d} | Win: {mr['win_rate_pct']:5.2f}% | Gross: Rs {mr['gross_pnl']:9.2f} | Net: Rs {mr['net_pnl']:9.2f} | PF: {str(mr['profit_factor']):6s}")

    # Save summary dataframe & JSON
    df_metrics = pd.DataFrame(all_results)
    summary_csv = OUT_DIR / "phase24G15_experiments_summary.csv"
    df_metrics.to_csv(summary_csv, index=False)
    trade_hashes["phase24G15_experiments_summary.csv"] = hashlib.sha256(summary_csv.read_bytes()).hexdigest()

    with open(OUT_DIR / "phase24G15_metrics.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "preflight": {
                    "dataset_sha256": EXPECTED_DATA_HASH,
                    "v1_config_hash": EXPECTED_CONFIG_HASH,
                    "target_symbol": "ADANIPORTS",
                },
                "experiments": all_results,
                "hashes": trade_hashes,
            },
            f,
            indent=2,
        )

    print("\n" + "=" * 80)
    print("PHASE 24G.15 RESEARCH EXPERIMENTS COMPLETE")
    print(f"Saved {summary_csv.name} and phase24G15_metrics.json")
    print("=" * 80)


if __name__ == "__main__":
    main()

