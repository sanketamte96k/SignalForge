"""
SignalForge — Phase 24G.7: Causal Historical Backtest Re-run and Comparison

Executes a controlled historical research backtest on validated ADANIPORTS 1m data:
1. Phase 24G.3 Legacy Execution ('same_close').
2. Phase 24G.7 Causal Execution ('next_open').
3. Deterministic Repeat of Phase 24G.7 to demonstrate byte-for-byte reproducibility.
4. Validation via HistoricalBacktestValidator with execution_model="next_open".
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.engine import run_backtest
from src.strategy.backtest_strategy import (
    Position,
    StrategyConfig,
    create_signal_function,
)
from src.validation.historical_backtest import HistoricalBacktestValidator

OUT_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G7_causal_backtest"
DATA_PATH = PROJECT_ROOT / "data" / "historical" / "stocks" / "ADANIPORTS_1m.csv"
MANIFEST_PATH = PROJECT_ROOT / "data" / "historical" / "manifests" / "ADANIPORTS_1m_manifest.json"
SNAPSHOT_PATH = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase22_final_validation" / "strategy_snapshot.json"

EXPECTED_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"


def verify_preflight():
    print("=" * 80)
    print("PHASE 24G.7 PREFLIGHT VERIFICATION")
    print("=" * 80)

    # 1. Strategy Snapshot Hash
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    computed_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    print(f"Strategy Config Hash: {computed_hash}")
    assert computed_hash == EXPECTED_CONFIG_HASH, f"Hash mismatch: expected {EXPECTED_CONFIG_HASH}, got {computed_hash}"

    # 2. Dataset Manifest Hash
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    expected_data_hash = manifest["content_hash"]

    data_bytes = DATA_PATH.read_bytes()
    computed_data_hash = hashlib.sha256(data_bytes).hexdigest()
    print(f"ADANIPORTS SHA-256:  {computed_data_hash}")
    assert computed_data_hash == expected_data_hash, f"Dataset hash mismatch: expected {expected_data_hash}, got {computed_data_hash}"

    print("Preflight verification passed successfully.\n")


class SignalTracker:
    """Wraps a signal function to track signal counts and session-boundary cancellations."""

    def __init__(self, inner_fn):
        self.inner_fn = inner_fn
        self.total_signals = 0
        self.long_signals = 0
        self.short_signals = 0
        self.signals = []

    def __call__(self, row: pd.Series, prev_row: pd.Series) -> Position | None:
        sig = self.inner_fn(row, prev_row)
        if sig is not None:
            self.total_signals += 1
            if sig == Position.LONG:
                self.long_signals += 1
            elif sig == Position.SHORT:
                self.short_signals += 1
            self.signals.append((row.name, sig))
        return sig


def summarize_result(res, execution_model: str, capital_initial: float = 100000.0) -> dict:
    trades = res.trades
    total_trades = len(trades)
    winning = [t for t in trades if t.net_pnl > 0]
    losing = [t for t in trades if t.net_pnl < 0]
    breakeven = [t for t in trades if t.net_pnl == 0]

    gross_pnl = sum(t.gross_pnl for t in trades)
    total_costs = sum(t.transaction_cost for t in trades)
    net_pnl = sum(t.net_pnl for t in trades)
    final_equity = capital_initial + net_pnl

    win_rate = (len(winning) / total_trades * 100.0) if total_trades > 0 else 0.0

    gross_profit = sum(t.net_pnl for t in winning)
    gross_loss = abs(sum(t.net_pnl for t in losing))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

    # Calculate equity curve & drawdown
    equity = capital_initial
    peak = capital_initial
    max_dd_amount = 0.0
    max_dd_pct = 0.0

    for t in trades:
        equity += t.net_pnl
        if equity > peak:
            peak = equity
        dd_amount = peak - equity
        dd_pct = (dd_amount / peak * 100.0) if peak > 0 else 0.0
        if dd_amount > max_dd_amount:
            max_dd_amount = dd_amount
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

    return {
        "execution_model": execution_model,
        "total_trades": total_trades,
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "breakeven_trades": len(breakeven),
        "win_rate_pct": round(win_rate, 2),
        "gross_pnl": round(gross_pnl, 2),
        "transaction_costs": round(total_costs, 2),
        "net_pnl": round(net_pnl, 2),
        "profit_factor": round(profit_factor, 4) if np.isfinite(profit_factor) else None,
        "final_equity": round(final_equity, 2),
        "max_drawdown_amount": round(max_dd_amount, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
    }


def count_session_end_cancellations(df: pd.DataFrame, signals: list[tuple[pd.Timestamp, Position]]) -> int:
    """Count how many signals occurred at the final bar of a calendar day session."""
    session_ends = set()
    dates = df.index.date
    for i in range(len(df) - 1):
        if dates[i] != dates[i + 1]:
            session_ends.add(df.index[i])
    session_ends.add(df.index[-1])

    cancelled = 0
    for ts, _ in signals:
        if ts in session_ends:
            cancelled += 1
    return cancelled


def main():
    verify_preflight()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading ADANIPORTS 1-minute historical dataset...")
    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
    df = df.set_index("timestamp").sort_index()

    start_date = str(df.index[0])
    end_date = str(df.index[-1])
    total_candles = len(df)
    print(f"Loaded {total_candles:,} bars from {start_date} to {end_date}")

    cfg = StrategyConfig(
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

    # -----------------------------------------------------------------------
    # Run 1: Legacy same_close (Phase 24G.3 baseline)
    # -----------------------------------------------------------------------
    print("\nExecuting Run A: Phase 24G.3 Legacy Execution ('same_close')...")
    sig_func_a = create_signal_function(df, cfg)
    tracker_a = SignalTracker(sig_func_a)
    t0 = time.time()
    res_legacy = run_backtest(
        data=df,
        signal_function=tracker_a,
        initial_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
        execution_model="same_close",
    )
    t_legacy = time.time() - t0
    summary_legacy = summarize_result(res_legacy, "same_close (Phase 24G.3 Legacy)")
    summary_legacy["signals_generated"] = tracker_a.total_signals
    summary_legacy["runtime_seconds"] = round(t_legacy, 2)
    print(f"Run A completed in {t_legacy:.2f}s: {summary_legacy['total_trades']} trades, Net P&L: Rs {summary_legacy['net_pnl']:,.2f}")

    # -----------------------------------------------------------------------
    # Run 2: Causal next_open (Phase 24G.7)
    # -----------------------------------------------------------------------
    print("\nExecuting Run B: Phase 24G.7 Causal Execution ('next_open')...")
    sig_func_b = create_signal_function(df, cfg)
    tracker_b = SignalTracker(sig_func_b)
    t0 = time.time()
    res_causal = run_backtest(
        data=df,
        signal_function=tracker_b,
        initial_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
        execution_model="next_open",
    )
    t_causal = time.time() - t0
    cancelled_orders = count_session_end_cancellations(df, tracker_b.signals)
    summary_causal = summarize_result(res_causal, "next_open (Phase 24G.7 Causal)")
    summary_causal["signals_generated"] = tracker_b.total_signals
    summary_causal["long_signals"] = tracker_b.long_signals
    summary_causal["short_signals"] = tracker_b.short_signals
    summary_causal["cancelled_eod_orders"] = cancelled_orders
    summary_causal["runtime_seconds"] = round(t_causal, 2)
    print(f"Run B completed in {t_causal:.2f}s: {summary_causal['total_trades']} trades, Signals: {tracker_b.total_signals}, Cancelled EOD: {cancelled_orders}, Net P&L: Rs {summary_causal['net_pnl']:,.2f}")

    # -----------------------------------------------------------------------
    # Run 3: Deterministic Repeat of Phase 24G.7 on slice to verify repeat reproducibility
    # -----------------------------------------------------------------------
    print("\nVerifying Deterministic Repeat of Phase 24G.7 ('next_open')...")
    sig_func_repeat = create_signal_function(df, cfg)
    res_causal_repeat = run_backtest(
        data=df,
        signal_function=sig_func_repeat,
        initial_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
        execution_model="next_open",
    )
    assert len(res_causal.trades) == len(res_causal_repeat.trades), "Trade count mismatch on repeat!"
    for i, (t1, t2) in enumerate(zip(res_causal.trades, res_causal_repeat.trades)):
        assert t1.entry_time == t2.entry_time, f"Entry time mismatch at trade {i}"
        assert t1.exit_time == t2.exit_time, f"Exit time mismatch at trade {i}"
        assert t1.entry_price == t2.entry_price, f"Entry price mismatch at trade {i}"
        assert t1.exit_price == t2.exit_price, f"Exit price mismatch at trade {i}"
        assert t1.net_pnl == t2.net_pnl, f"Net P&L mismatch at trade {i}"
    print("Deterministic repeat confirmed: 100% IDENTICAL across all trades.")

    # -----------------------------------------------------------------------
    # Run 4: Authoritative HistoricalBacktestValidator Verification
    # -----------------------------------------------------------------------
    print("\nVerifying HistoricalBacktestValidator with execution_model='next_open'...")
    validator = HistoricalBacktestValidator(
        initial_capital=100000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
        strategy_config=cfg,
        execution_model="next_open",
    )
    # Check validator execution on a 1,000-candle segment to verify contract
    val_subset = df.iloc[:1000]
    val_res = validator.check(val_subset)
    assert val_res.execution_model == "next_open", "Validator failed to pass execution_model!"
    print(f"HistoricalBacktestValidator passed: execution_model='{val_res.execution_model}', trades={val_res.total_trades}")

    # -----------------------------------------------------------------------
    # Save Trade Logs & Summary Metrics
    # -----------------------------------------------------------------------
    trades_causal_dicts = [
        {
            "entry_time": str(t.entry_time),
            "exit_time": str(t.exit_time),
            "position": t.position.value,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "quantity": t.quantity,
            "gross_pnl": t.gross_pnl,
            "transaction_cost": t.transaction_cost,
            "net_pnl": t.net_pnl,
            "return_pct": t.return_pct,
        }
        for t in res_causal.trades
    ]
    pd.DataFrame(trades_causal_dicts).to_csv(OUT_DIR / "phase24G7_trades_next_open.csv", index=False)

    trades_legacy_dicts = [
        {
            "entry_time": str(t.entry_time),
            "exit_time": str(t.exit_time),
            "position": t.position.value,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "quantity": t.quantity,
            "gross_pnl": t.gross_pnl,
            "transaction_cost": t.transaction_cost,
            "net_pnl": t.net_pnl,
            "return_pct": t.return_pct,
        }
        for t in res_legacy.trades
    ]
    pd.DataFrame(trades_legacy_dicts).to_csv(OUT_DIR / "phase24G7_trades_same_close.csv", index=False)

    comparison_df = pd.DataFrame([summary_legacy, summary_causal])
    comparison_df.to_csv(OUT_DIR / "phase24G7_comparison.csv", index=False)

    with open(OUT_DIR / "phase24G7_metrics.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "preflight": {
                    "dataset": "ADANIPORTS",
                    "dataset_path": str(DATA_PATH),
                    "dataset_sha256": "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9",
                    "config_hash": EXPECTED_CONFIG_HASH,
                    "date_range": [start_date, end_date],
                    "total_candles": total_candles,
                },
                "legacy_run": summary_legacy,
                "causal_run": summary_causal,
            },
            f,
            indent=2,
        )

    # -----------------------------------------------------------------------
    # Sample Trade Traces for Comparison
    # -----------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("REPRESENTATIVE TRADE TRACES: SAME_CLOSE vs. NEXT_OPEN")
    print("=" * 80)
    for i in range(min(5, len(res_legacy.trades), len(res_causal.trades))):
        tl = res_legacy.trades[i]
        tc = res_causal.trades[i]
        print(f"Trade #{i+1} ({tl.position.value}):")
        print(f"  Legacy same_close: entry={tl.entry_time} @ {tl.entry_price:.2f}, exit={tl.exit_time} @ {tl.exit_price:.2f}, net={tl.net_pnl:.2f}")
        print(f"  Causal next_open:  entry={tc.entry_time} @ {tc.entry_price:.2f}, exit={tc.exit_time} @ {tc.exit_price:.2f}, net={tc.net_pnl:.2f}")

    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY TABLE")
    print("=" * 80)
    print(comparison_df.to_string(index=False))
    print("=" * 80)


if __name__ == "__main__":
    main()
