"""
SignalForge — Phase 24G.13: Controlled Historical Evaluation of V2 Risk Engine
==============================================================================
Evaluates the remediated RiskEngineV2 against the causal SignalForge V1 baseline
across standardized historical partitions on ADANIPORTS 1m data:
  1. Training (In-Sample): 2017-01-02 through 2018-12-31
  2. Validation (Out-of-Sample): 2019-01-01 through 2019-12-31
  3. Holdout (Untouched Out-of-Sample): 2020-01-01 through 2020-12-31
  4. Combined Period (Descriptive Summary Only): 2017-01-02 through 2020-12-31

Enforces:
  - Strict preflight verification (frozen V1 config hash, dataset SHA-256)
  - Continuous causal indicator warmup across full historical context
  - No position or order leakage across partition boundaries
  - Deterministic repeat run verification (bit-for-bit SHA-256 trade log agreement)
  - Dual cost model evaluation: Historical Baseline (1 bps flat) vs Production Realistic Intraday
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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.engine import run_backtest
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
from src.strategy.backtest_strategy import (
    Position,
    StrategyConfig,
    calculate_timeframe_indicators,
    _make_cursors,
    _generate_filtered_signal,
    signal_result_to_position,
)

OUT_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G13_v2_controlled_evaluation"
DATA_PATH = PROJECT_ROOT / "data" / "historical" / "stocks" / "ADANIPORTS_1m.csv"
MANIFEST_PATH = PROJECT_ROOT / "data" / "historical" / "manifests" / "ADANIPORTS_1m_manifest.json"
SNAPSHOT_PATH = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase22_final_validation" / "strategy_snapshot.json"
REGISTRY_PATH = PROJECT_ROOT / "data" / "universe_registry.json"
PAPER_LEDGER_PATH = PROJECT_ROOT / "data" / "paper_trading" / "interactive_trades.json"

EXPECTED_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
EXPECTED_DATA_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"


def verify_preflight():
    print("=" * 80)
    print("PHASE 24G.13 PREFLIGHT VERIFICATION")
    print("=" * 80)

    # 1. Strategy Snapshot Hash
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    computed_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    print(f"Strategy Config Hash: {computed_hash}")
    assert computed_hash == EXPECTED_CONFIG_HASH, f"Hash mismatch: expected {EXPECTED_CONFIG_HASH}, got {computed_hash}"

    # 2. Dataset Manifest and Content Hash
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["content_hash"] == EXPECTED_DATA_HASH, "Manifest content hash mismatch"

    data_bytes = DATA_PATH.read_bytes()
    computed_data_hash = hashlib.sha256(data_bytes).hexdigest()
    print(f"ADANIPORTS SHA-256:  {computed_data_hash}")
    assert computed_data_hash == EXPECTED_DATA_HASH, f"Dataset hash mismatch: expected {EXPECTED_DATA_HASH}, got {computed_data_hash}"

    # 3. Registry & Paper Ledger integrity
    assert REGISTRY_PATH.exists(), "Universe registry missing"
    assert PAPER_LEDGER_PATH.exists(), "Paper trading ledger missing"

    print("Preflight verification passed successfully.\n")


def compute_metrics_v2(res: RiskEngineV2Result, p_name: str, p_slice: pd.DataFrame, runtime_s: float, cost_model_name: str) -> dict:
    trades = res.trades
    total_trades = len(trades)
    winning = [t for t in trades if t.net_pnl > 0]
    losing = [t for t in trades if t.net_pnl < 0]
    breakeven = [t for t in trades if t.net_pnl == 0]

    win_rate = (len(winning) / total_trades * 100.0) if total_trades > 0 else 0.0

    gross_pnl = sum(t.gross_pnl for t in trades)
    total_costs = sum(t.transaction_cost for t in trades)
    net_pnl = sum(t.net_pnl for t in trades)
    return_pct = (net_pnl / res.initial_capital * 100.0)

    # Fee breakdown
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

    # Profit factor
    gross_profit = sum(t.net_pnl for t in winning)
    gross_loss = abs(sum(t.net_pnl for t in losing))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

    # Average win, average loss, expectancy
    avg_win = (gross_profit / len(winning)) if len(winning) > 0 else 0.0
    avg_loss = (gross_loss / len(losing)) if len(losing) > 0 else 0.0
    win_prob = len(winning) / total_trades if total_trades > 0 else 0.0
    loss_prob = len(losing) / total_trades if total_trades > 0 else 0.0
    expectancy = (win_prob * avg_win) - (loss_prob * avg_loss)

    # Exit reason breakdown
    exit_counts: dict[str, int] = {}
    gap_through_count = 0
    for t in trades:
        exit_counts[t.exit_reason] = exit_counts.get(t.exit_reason, 0) + 1
        # Check if trade was gap-through-stop
        if t.side == PositionSide.LONG and t.exit_price < t.initial_stop:
            gap_through_count += 1
        elif t.side == PositionSide.SHORT and t.exit_price > t.initial_stop:
            gap_through_count += 1

    # Audit rejections breakdown
    rejection_counts: dict[str, int] = {}
    for r in res.audit_rejections:
        reason = r.get("reason", "UNKNOWN")
        rejection_counts[reason] = rejection_counts.get(reason, 0) + 1

    daily_loss_activations = exit_counts.get(ExitReason.DAILY_LOSS_HALT.value, 0) + rejection_counts.get(RejectionReason.DAILY_LOSS_LIMIT.value, 0)
    cooldown_activations = rejection_counts.get(RejectionReason.CONSECUTIVE_LOSS_COOLDOWN.value, 0)

    trading_days = len(set(p_slice.index.date))

    return {
        "engine": "V2",
        "cost_model": cost_model_name,
        "partition": p_name,
        "start_time": str(p_slice.index[0]),
        "end_time": str(p_slice.index[-1]),
        "candles": len(p_slice),
        "trading_days": trading_days,
        "total_trades": total_trades,
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "breakeven_trades": len(breakeven),
        "win_rate_pct": round(win_rate, 2),
        "gross_pnl": round(gross_pnl, 2),
        "brokerage": round(brokerage, 2),
        "statutory_charges": round(statutory_fees, 2),
        "slippage": round(slippage, 2),
        "total_transaction_costs": round(total_costs, 2),
        "net_pnl": round(net_pnl, 2),
        "return_pct": round(return_pct, 4),
        "profit_factor": round(profit_factor, 4) if np.isfinite(profit_factor) else None,
        "max_drawdown_amount": round(res.max_drawdown_amount, 2),
        "max_drawdown_pct": round(res.max_drawdown_pct, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy_per_trade": round(expectancy, 2),
        "max_consecutive_losses": res.max_consecutive_losses,
        "daily_loss_limit_activations": daily_loss_activations,
        "cooldown_activations": cooldown_activations,
        "stop_loss_exits": exit_counts.get(ExitReason.STOP_LOSS.value, 0),
        "trailing_stop_exits": exit_counts.get(ExitReason.TRAILING_STOP.value, 0),
        "target_exits": exit_counts.get(ExitReason.TAKE_PROFIT.value, 0),
        "max_holding_time_exits": exit_counts.get(ExitReason.MAX_TIME.value, 0),
        "eod_exits": exit_counts.get(ExitReason.EOD.value, 0),
        "gap_through_stop_exits": gap_through_count,
        "total_rejected_orders": len(res.audit_rejections),
        "rejection_breakdown": rejection_counts,
        "trade_log_hash": res.trade_log_hash,
        "runtime_seconds": round(runtime_s, 2),
    }


def compute_metrics_v1(v1_dict: dict, p_name: str, p_slice: pd.DataFrame, trades: list) -> dict:
    total_trades = v1_dict["total_trades"]
    winning = v1_dict["winning_trades"]
    losing = v1_dict["losing_trades"]
    win_rate = v1_dict["win_rate_pct"]
    gross_pnl = v1_dict["gross_pnl"]
    costs = v1_dict["transaction_costs"]
    net_pnl = v1_dict["net_pnl"]

    gross_profit = sum(t.net_pnl for t in trades if t.net_pnl > 0)
    gross_loss = abs(sum(t.net_pnl for t in trades if t.net_pnl < 0))
    avg_win = (gross_profit / winning) if winning > 0 else 0.0
    avg_loss = (gross_loss / losing) if losing > 0 else 0.0
    win_prob = winning / total_trades if total_trades > 0 else 0.0
    loss_prob = losing / total_trades if total_trades > 0 else 0.0
    expectancy = (win_prob * avg_win) - (loss_prob * avg_loss)

    # Max consecutive losses in V1
    streak = 0
    max_streak = 0
    for t in trades:
        if t.net_pnl < 0:
            streak += 1
            if streak > max_streak:
                max_streak = streak
        elif t.net_pnl > 0:
            streak = 0

    return {
        "engine": "V1",
        "cost_model": "historical_baseline (1 bps)",
        "partition": p_name,
        "start_time": str(p_slice.index[0]),
        "end_time": str(p_slice.index[-1]),
        "candles": len(p_slice),
        "trading_days": len(set(p_slice.index.date)),
        "total_trades": total_trades,
        "winning_trades": winning,
        "losing_trades": losing,
        "breakeven_trades": v1_dict.get("breakeven_trades", 0),
        "win_rate_pct": win_rate,
        "gross_pnl": gross_pnl,
        "brokerage": 0.0,
        "statutory_charges": 0.0,
        "slippage": 0.0,
        "total_transaction_costs": costs,
        "net_pnl": net_pnl,
        "return_pct": v1_dict["return_pct"],
        "profit_factor": v1_dict["profit_factor"],
        "max_drawdown_amount": v1_dict["max_drawdown_amount"],
        "max_drawdown_pct": v1_dict["max_drawdown_pct"],
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy_per_trade": round(expectancy, 2),
        "max_consecutive_losses": max_streak,
        "daily_loss_limit_activations": 0,
        "cooldown_activations": 0,
        "stop_loss_exits": 0,
        "trailing_stop_exits": 0,
        "target_exits": 0,
        "max_holding_time_exits": 0,
        "eod_exits": total_trades,  # In V1, essentially 100% exited at EOD / reversal
        "gap_through_stop_exits": 0,
        "total_rejected_orders": v1_dict.get("cancelled_eod_orders", 0),
        "rejection_breakdown": {"DAY_ROLLOVER_CANCELLED": v1_dict.get("cancelled_eod_orders", 0)},
        "trade_log_hash": v1_dict.get("trade_log_sha256", ""),
        "runtime_seconds": v1_dict.get("runtime_seconds", 0.0),
    }


def save_v2_trades_csv(trades: tuple[V2Trade, ...], filepath: Path) -> str:
    """Save detailed V2 trade records to CSV and return content SHA-256."""
    records = [t.to_dict() for t in trades]
    df_t = pd.DataFrame(records)
    df_t.to_csv(filepath, index=False)
    return hashlib.sha256(filepath.read_bytes()).hexdigest()


def main():
    verify_preflight()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading ADANIPORTS 1-minute historical dataset...")
    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"]).set_index("timestamp").sort_index()

    cfg_strat = StrategyConfig(
        ema_fast_period=20,
        ema_slow_period=50,
        rsi_period=14,
        atr_period=14,
        rvol_period=20,
        minimum_rvol=1.5,
        minimum_atr=0.0,
        minimum_long_rsi=60.0,
        use_rvol=True,
    )

    print("\nPre-computing multi-timeframe indicator series across full historical span for warm-up context...")
    t_ind0 = time.time()
    timeframe_data = calculate_timeframe_indicators(df, cfg_strat)
    print(f"Timeframe indicators precomputed in {time.time() - t_ind0:.2f}s.")

    print("Precomputing causal signal series across all timestamps...")
    t_sig0 = time.time()
    cursors = _make_cursors(timeframe_data, cfg_strat.use_rvol)
    signals_list = []
    for ts in df.index:
        s30 = cursors["30m"].update(ts)
        s15 = cursors["15m"].update(ts)
        s10 = cursors["10m"].update(ts)
        s5 = cursors["5m"].update(ts)
        if s30 is None or s15 is None or s10 is None or s5 is None:
            signals_list.append(None)
        else:
            res = _generate_filtered_signal(states=(s30, s15, s10, s5), config=cfg_strat)
            pos = signal_result_to_position(res)
            signals_list.append(PositionSide(pos.value) if pos is not None else None)
    signal_series = pd.Series(signals_list, index=df.index)
    print(f"Causal signals precomputed in {time.time() - t_sig0:.2f}s.")

    # Load existing V1 baseline metrics from Phase 24G.8
    v1_metrics_path = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G8_oos_validation" / "phase24G8_oos_metrics.json"
    with open(v1_metrics_path, "r", encoding="utf-8") as f:
        v1_data = json.load(f)
    v1_partitions = {p["partition"]: p for p in v1_data["partitions"]}

    partitions = {
        "training_2017_2018": {
            "name": "Training (2017–2018)",
            "v1_key": "Training (2017–2018)",
            "slice": df["2017-01-02 09:15:00":"2018-12-31 15:29:00"],
            "v1_trade_file": PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G8_oos_validation" / "trades_training_2017_2018.csv",
        },
        "validation_2019": {
            "name": "Validation (2019)",
            "v1_key": "Validation (2019)",
            "slice": df["2019-01-01 09:15:00":"2019-12-31 15:29:00"],
            "v1_trade_file": PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G8_oos_validation" / "trades_validation_2019.csv",
        },
        "holdout_2020": {
            "name": "Holdout Test (2020)",
            "v1_key": "Holdout Test (2020)",
            "slice": df["2020-01-01 09:15:00":"2020-12-31 15:29:00"],
            "v1_trade_file": PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G8_oos_validation" / "trades_holdout_2020.csv",
        },
        "combined_2017_2020": {
            "name": "Combined Period (2017–2020 Descriptive Summary)",
            "v1_key": "Combined Period (2017–2020 Descriptive Summary)",
            "slice": df["2017-01-02 09:15:00":"2020-12-31 15:29:00"],
            "v1_trade_file": PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G8_oos_validation" / "trades_combined_2017_2020.csv",
        },
    }

    # Documented V2 Configuration (Preserving SF-REG-DECISIONS-2026-V2 parameters)
    cfg_v2_baseline = RiskEngineConfigV2.pre_registered(
        registration_id="SF-V2-EVAL-PHASE24G13-BASELINE",
        initial_capital=100000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        k_stop=1.5,
        k_target=3.0,
        k_trail=None,
        trail_activation_r=1.0,
        max_holding_bars=None,
        morning_blackout_end=None,
        daily_loss_limit_pct=0.02,
        consecutive_loss_limit=3,
        cooldown_minutes=60,
        execution_model="next_open",
        cost_model=CostModelType.HISTORICAL_BASELINE,
        slippage=0.0,
    )

    cfg_v2_realistic = RiskEngineConfigV2.pre_registered(
        registration_id="SF-V2-EVAL-PHASE24G13-REALISTIC",
        initial_capital=100000.0,
        risk_per_trade=0.01,
        max_leverage=5.0,
        k_stop=1.5,
        k_target=3.0,
        k_trail=None,
        trail_activation_r=1.0,
        max_holding_bars=None,
        morning_blackout_end=None,
        daily_loss_limit_pct=0.02,
        consecutive_loss_limit=3,
        cooldown_minutes=60,
        execution_model="next_open",
        cost_model=CostModelType.REALISTIC_INTRADAY,
        slippage=0.0,
    )

    all_metrics = []
    sample_trades_report = []

    for p_id, p_info in partitions.items():
        p_name = p_info["name"]
        p_slice = p_info["slice"]
        p_sigs = signal_series.loc[p_slice.index[0]:p_slice.index[-1]].to_numpy()

        print("\n" + "=" * 80)
        print(f"EVALUATING PARTITION: {p_name}")
        print(f"Span: {p_slice.index[0]} to {p_slice.index[-1]} | {len(p_slice):,} candles | {len(set(p_slice.index.date))} days")
        print("=" * 80)

        # --------------------------------------------------------------------
        # 1. V1 Baseline Metrics
        # --------------------------------------------------------------------
        v1_raw = v1_partitions[p_info["v1_key"]]
        df_v1_trades = pd.read_csv(p_info["v1_trade_file"])
        # Mock class for trade metrics
        class MockV1Trade:
            def __init__(self, row):
                self.net_pnl = row["net_pnl"]
                self.gross_pnl = row["gross_pnl"]
                self.transaction_cost = row["transaction_cost"]
        v1_trade_objs = [MockV1Trade(r) for _, r in df_v1_trades.iterrows()]
        m_v1 = compute_metrics_v1(v1_raw, p_name, p_slice, v1_trade_objs)
        all_metrics.append(m_v1)
        print(f"[V1 Baseline]       Trades: {m_v1['total_trades']:4d} | Net P&L: Rs {m_v1['net_pnl']:10.2f} | Win Rate: {m_v1['win_rate_pct']:5.2f}% | Max DD: Rs {m_v1['max_drawdown_amount']:8.2f}")

        # --------------------------------------------------------------------
        # 2. V2 Evaluation: Baseline Cost Model (Flat 1 bps, comparable to V1)
        # --------------------------------------------------------------------
        t0 = time.time()
        engine_v2_base = RiskEngineV2(cfg_v2_baseline)
        res_v2_base_1 = engine_v2_base.run(p_slice, p_sigs)
        rt_v2_base = time.time() - t0

        # Deterministic repeat run
        res_v2_base_2 = engine_v2_base.run(p_slice, p_sigs)
        assert res_v2_base_1.trade_log_hash == res_v2_base_2.trade_log_hash, f"V2 Baseline repeat hash mismatch on {p_name}!"
        assert len(res_v2_base_1.trades) == len(res_v2_base_2.trades), f"V2 Baseline repeat trade count mismatch on {p_name}!"

        # Save V2 trade log
        v2_trade_file = OUT_DIR / f"trades_v2_baseline_{p_id}.csv"
        v2_csv_hash = save_v2_trades_csv(res_v2_base_1.trades, v2_trade_file)

        m_v2_base = compute_metrics_v2(res_v2_base_1, p_name, p_slice, rt_v2_base, "historical_baseline (1 bps)")
        m_v2_base["trade_log_csv_sha256"] = v2_csv_hash
        m_v2_base["deterministic_repeat_verified"] = True
        all_metrics.append(m_v2_base)
        print(f"[V2 Baseline 1 bps] Trades: {m_v2_base['total_trades']:4d} | Net P&L: Rs {m_v2_base['net_pnl']:10.2f} | Win Rate: {m_v2_base['win_rate_pct']:5.2f}% | Max DD: Rs {m_v2_base['max_drawdown_amount']:8.2f} | Hash: {res_v2_base_1.trade_log_hash[:16]}...")

        # --------------------------------------------------------------------
        # 3. V2 Evaluation: Realistic Indian Equity Friction Model
        # --------------------------------------------------------------------
        t0 = time.time()
        engine_v2_real = RiskEngineV2(cfg_v2_realistic)
        res_v2_real_1 = engine_v2_real.run(p_slice, p_sigs)
        rt_v2_real = time.time() - t0

        res_v2_real_2 = engine_v2_real.run(p_slice, p_sigs)
        assert res_v2_real_1.trade_log_hash == res_v2_real_2.trade_log_hash, f"V2 Realistic repeat hash mismatch on {p_name}!"

        v2_real_file = OUT_DIR / f"trades_v2_realistic_{p_id}.csv"
        v2_real_csv_hash = save_v2_trades_csv(res_v2_real_1.trades, v2_real_file)

        m_v2_real = compute_metrics_v2(res_v2_real_1, p_name, p_slice, rt_v2_real, "realistic_intraday (Indian statutory)")
        m_v2_real["trade_log_csv_sha256"] = v2_real_csv_hash
        m_v2_real["deterministic_repeat_verified"] = True
        all_metrics.append(m_v2_real)
        print(f"[V2 Realistic Fees] Trades: {m_v2_real['total_trades']:4d} | Net P&L: Rs {m_v2_real['net_pnl']:10.2f} | Win Rate: {m_v2_real['win_rate_pct']:5.2f}% | Max DD: Rs {m_v2_real['max_drawdown_amount']:8.2f} | Hash: {res_v2_real_1.trade_log_hash[:16]}...")

        # Collect sample trades for verification
        if p_id == "holdout_2020":
            sample_trades_report = extract_sample_trades(res_v2_base_1.trades)

    # Save summary dataframe & JSON
    df_metrics = pd.DataFrame(all_metrics)
    df_metrics.to_csv(OUT_DIR / "phase24G13_partition_comparison.csv", index=False)

    with open(OUT_DIR / "phase24G13_metrics.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "preflight": {
                    "dataset_sha256": EXPECTED_DATA_HASH,
                    "v1_config_hash": EXPECTED_CONFIG_HASH,
                    "target_symbol": "ADANIPORTS",
                },
                "metrics": all_metrics,
                "sample_trades": sample_trades_report,
            },
            f,
            indent=2,
        )

    print("\n" + "=" * 80)
    print("PHASE 24G.13 HISTORICAL EVALUATION COMPLETE")
    print("=" * 80)
    cols = [
        "engine",
        "cost_model",
        "partition",
        "total_trades",
        "win_rate_pct",
        "gross_pnl",
        "total_transaction_costs",
        "net_pnl",
        "profit_factor",
        "max_drawdown_amount",
        "stop_loss_exits",
        "target_exits",
        "eod_exits",
        "daily_loss_limit_activations",
    ]
    print(df_metrics[cols].to_string(index=False))
    print("=" * 80)


def extract_sample_trades(trades: tuple[V2Trade, ...]) -> list[dict]:
    """Find representative completed trades for each major exit reason."""
    found: dict[str, V2Trade] = {}
    gap_trade = None

    for t in trades:
        reason = t.exit_reason
        if reason not in found:
            found[reason] = t
        if gap_trade is None:
            if t.side == PositionSide.LONG and t.exit_price < t.initial_stop:
                gap_trade = t
            elif t.side == PositionSide.SHORT and t.exit_price > t.initial_stop:
                gap_trade = t

    samples = []
    for r, t in found.items():
        samples.append({
            "category": f"Standard Exit: {r}",
            "trade": t.to_dict(),
        })
    if gap_trade is not None:
        samples.append({
            "category": "Gap-Through-Stop Exit",
            "trade": gap_trade.to_dict(),
        })
    return samples


if __name__ == "__main__":
    main()

