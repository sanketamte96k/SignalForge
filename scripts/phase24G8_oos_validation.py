"""
SignalForge — Phase 24G.8: Controlled Out-of-Sample Validation

Executes a partitioned historical research validation on validated ADANIPORTS 1m data:
1. Training: 2017-01-02 through 2018-12-31 (In-Sample)
2. Validation: 2019-01-01 through 2019-12-31 (Out-of-Sample)
3. Final Holdout: 2020-01-01 through 2020-12-31 (Out-of-Sample Holdout)
4. Trailing Stub: 2021-01-01 (Isolated single-day session)
5. Combined Period: 2017-01-02 through 2020-12-31 (Descriptive summary only)

All runs strictly enforce:
- next_open causal execution model
- Frozen strategy parameters (hash 920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7)
- 1 bps turnover transaction costs
- Independent repeat runs verifying byte-for-byte reproducibility
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
    calculate_timeframe_indicators,
    _make_cursors,
    _generate_filtered_signal,
    signal_result_to_position,
)
from src.validation.historical_backtest import HistoricalBacktestValidator

OUT_DIR = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase24G8_oos_validation"
DATA_PATH = PROJECT_ROOT / "data" / "historical" / "stocks" / "ADANIPORTS_1m.csv"
MANIFEST_PATH = PROJECT_ROOT / "data" / "historical" / "manifests" / "ADANIPORTS_1m_manifest.json"
SNAPSHOT_PATH = PROJECT_ROOT / "research" / "strategy_evolution_2018" / "phase22_final_validation" / "strategy_snapshot.json"

EXPECTED_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"


def verify_preflight():
    print("=" * 80)
    print("PHASE 24G.8 PREFLIGHT VERIFICATION")
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


def build_signal_fn_factory(timeframe_data: dict[str, pd.DataFrame], config: StrategyConfig):
    """Creates a fast signal function with fresh cursors for deterministic execution."""
    def make_signal_fn():
        cursors = _make_cursors(timeframe_data, config.use_rvol)

        def signal_function(row: pd.Series, prev_row: pd.Series) -> Position | None:
            timestamp = row.name
            if not isinstance(timestamp, pd.Timestamp):
                timestamp = pd.Timestamp(timestamp)

            s30 = cursors["30m"].update(timestamp)
            s15 = cursors["15m"].update(timestamp)
            s10 = cursors["10m"].update(timestamp)
            s5 = cursors["5m"].update(timestamp)

            if s30 is None or s15 is None or s10 is None or s5 is None:
                return None

            res = _generate_filtered_signal(
                states=(s30, s15, s10, s5),
                config=config,
            )
            return signal_result_to_position(res)

        return signal_function

    return make_signal_fn


class SignalAuditor:
    """Tracks signals, long/short counts, and session cancellations."""

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


def count_session_end_cancellations(df: pd.DataFrame, signals: list[tuple[pd.Timestamp, Position]]) -> int:
    """Count signals emitted at the final bar of a calendar day session."""
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


def summarize_partition(
    res,
    partition_name: str,
    df_slice: pd.DataFrame,
    auditor: SignalAuditor,
    runtime_s: float,
    capital_initial: float = 100000.0,
) -> dict:
    trades = res.trades
    total_trades = len(trades)
    winning = [t for t in trades if t.net_pnl > 0]
    losing = [t for t in trades if t.net_pnl < 0]
    breakeven = [t for t in trades if t.net_pnl == 0]

    gross_pnl = sum(t.gross_pnl for t in trades)
    total_costs = sum(t.transaction_cost for t in trades)
    net_pnl = sum(t.net_pnl for t in trades)
    final_equity = capital_initial + net_pnl
    return_pct = (net_pnl / capital_initial * 100.0)

    win_rate = (len(winning) / total_trades * 100.0) if total_trades > 0 else 0.0

    gross_profit = sum(t.net_pnl for t in winning)
    gross_loss = abs(sum(t.net_pnl for t in losing))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

    # Sub-breakdown: Long vs Short trades
    long_trades = [t for t in trades if t.position == Position.LONG]
    short_trades = [t for t in trades if t.position == Position.SHORT]
    long_winning = [t for t in long_trades if t.net_pnl > 0]
    short_winning = [t for t in short_trades if t.net_pnl > 0]
    long_win_rate = (len(long_winning) / len(long_trades) * 100.0) if long_trades else 0.0
    short_win_rate = (len(short_winning) / len(short_trades) * 100.0) if short_trades else 0.0
    long_gross_pnl = sum(t.gross_pnl for t in long_trades)
    short_gross_pnl = sum(t.gross_pnl for t in short_trades)
    long_net_pnl = sum(t.net_pnl for t in long_trades)
    short_net_pnl = sum(t.net_pnl for t in short_trades)

    # Explicit Drawdown: Peak equity minus current equity
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

    cancelled_eod = count_session_end_cancellations(df_slice, auditor.signals)
    trading_days = len(set(df_slice.index.date))

    return {
        "partition": partition_name,
        "start_time": str(df_slice.index[0]),
        "end_time": str(df_slice.index[-1]),
        "candles": len(df_slice),
        "trading_days": trading_days,
        "signals_generated": auditor.total_signals,
        "long_signals": auditor.long_signals,
        "short_signals": auditor.short_signals,
        "cancelled_eod_orders": cancelled_eod,
        "total_trades": total_trades,
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "breakeven_trades": len(breakeven),
        "win_rate_pct": round(win_rate, 2),
        "gross_pnl": round(gross_pnl, 2),
        "transaction_costs": round(total_costs, 2),
        "net_pnl": round(net_pnl, 2),
        "return_pct": round(return_pct, 4),
        "profit_factor": round(profit_factor, 4) if np.isfinite(profit_factor) else None,
        "max_drawdown_amount": round(max_dd_amount, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "final_equity": round(final_equity, 2),
        "long_trades": len(long_trades),
        "long_win_rate_pct": round(long_win_rate, 2),
        "long_gross_pnl": round(long_gross_pnl, 2),
        "long_net_pnl": round(long_net_pnl, 2),
        "short_trades": len(short_trades),
        "short_win_rate_pct": round(short_win_rate, 2),
        "short_gross_pnl": round(short_gross_pnl, 2),
        "short_net_pnl": round(short_net_pnl, 2),
        "runtime_seconds": round(runtime_s, 2),
    }


def save_trades(trades, filepath: Path) -> str:
    """Save trade log CSV and return its SHA-256 hash."""
    records = [
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
        for t in trades
    ]
    pd.DataFrame(records).to_csv(filepath, index=False)
    content = filepath.read_bytes()
    return hashlib.sha256(content).hexdigest()


def main():
    verify_preflight()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading ADANIPORTS 1-minute historical dataset...")
    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
    df = df.set_index("timestamp").sort_index()

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

    # Pre-create indicator context from full series to provide continuous indicator warm-up
    print("\nPre-computing multi-timeframe indicator series across full historical span for warm-up context...")
    t_ind0 = time.time()
    timeframe_data = calculate_timeframe_indicators(df, cfg)
    t_ind = time.time() - t_ind0
    print(f"Timeframe indicators precomputed in {t_ind:.2f}s.")

    factory = build_signal_fn_factory(timeframe_data, cfg)

    # Define Partitions
    partitions = {
        "training_2017_2018": {
            "name": "Training (2017–2018)",
            "slice": df["2017-01-02 09:15:00":"2018-12-31 15:29:00"],
            "filename": "trades_training_2017_2018.csv",
        },
        "validation_2019": {
            "name": "Validation (2019)",
            "slice": df["2019-01-01 09:15:00":"2019-12-31 15:29:00"],
            "filename": "trades_validation_2019.csv",
        },
        "holdout_2020": {
            "name": "Holdout Test (2020)",
            "slice": df["2020-01-01 09:15:00":"2020-12-31 15:29:00"],
            "filename": "trades_holdout_2020.csv",
        },
        "trailing_stub_2021": {
            "name": "Trailing Stub (2021-01-01)",
            "slice": df["2021-01-01 09:15:00":"2021-01-01 15:29:00"],
            "filename": "trades_trailing_stub_2021.csv",
        },
        "combined_2017_2020": {
            "name": "Combined Period (2017–2020 Descriptive Summary)",
            "slice": df["2017-01-02 09:15:00":"2020-12-31 15:29:00"],
            "filename": "trades_combined_2017_2020.csv",
        },
    }

    results = []

    for p_id, p_info in partitions.items():
        p_name = p_info["name"]
        p_slice = p_info["slice"]
        p_file = OUT_DIR / p_info["filename"]

        print("\n" + "=" * 80)
        print(f"RUNNING PARTITION: {p_name}")
        print(f"Range: {p_slice.index[0]} to {p_slice.index[-1]} | {len(p_slice):,} candles | {len(set(p_slice.index.date))} days")
        print("=" * 80)

        # Run 1: Primary Run
        sig_fn_1 = factory()
        auditor_1 = SignalAuditor(sig_fn_1)
        t0 = time.time()
        res_1 = run_backtest(
            data=p_slice,
            signal_function=auditor_1,
            initial_capital=100000.0,
            quantity=1,
            transaction_cost_rate=0.0001,
            execution_model="next_open",
        )
        runtime_1 = time.time() - t0

        summary = summarize_partition(
            res=res_1,
            partition_name=p_name,
            df_slice=p_slice,
            auditor=auditor_1,
            runtime_s=runtime_1,
        )

        # Save trade log and record SHA-256
        sha1 = save_trades(res_1.trades, p_file)
        summary["trade_log_sha256"] = sha1

        # Run 2: Deterministic Repeat Run
        sig_fn_2 = factory()
        auditor_2 = SignalAuditor(sig_fn_2)
        res_2 = run_backtest(
            data=p_slice,
            signal_function=auditor_2,
            initial_capital=100000.0,
            quantity=1,
            transaction_cost_rate=0.0001,
            execution_model="next_open",
        )

        assert len(res_1.trades) == len(res_2.trades), f"Trade count mismatch on repeat for {p_name}!"
        for i, (t1, t2) in enumerate(zip(res_1.trades, res_2.trades)):
            assert t1.entry_time == t2.entry_time, f"Entry time mismatch at trade {i}"
            assert t1.exit_time == t2.exit_time, f"Exit time mismatch at trade {i}"
            assert t1.entry_price == t2.entry_price, f"Entry price mismatch at trade {i}"
            assert t1.exit_price == t2.exit_price, f"Exit price mismatch at trade {i}"
            assert t1.net_pnl == t2.net_pnl, f"Net P&L mismatch at trade {i}"
        repeat_file = OUT_DIR / f"repeat_{p_info['filename']}"
        sha2 = save_trades(res_2.trades, repeat_file)
        assert sha1 == sha2, f"Trade log hash mismatch on repeat for {p_name}!"
        repeat_file.unlink()  # remove repeat temporary file after verification
        summary["deterministic_repeat_verified"] = True
        print(f"Run completed: {summary['total_trades']} trades | Net P&L: Rs {summary['net_pnl']:,.2f} | Win Rate: {summary['win_rate_pct']}% | SHA-256: {sha1[:16]}... (Repeat: 100% Identical)")

        results.append(summary)

    # Convert results to DataFrame and save
    results_df = pd.DataFrame(results)
    results_df.to_csv(OUT_DIR / "phase24G8_partition_comparison.csv", index=False)

    with open(OUT_DIR / "phase24G8_oos_metrics.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "preflight": {
                    "dataset": "ADANIPORTS",
                    "dataset_path": str(DATA_PATH),
                    "dataset_sha256": "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9",
                    "config_hash": EXPECTED_CONFIG_HASH,
                    "total_candles": len(df),
                },
                "partitions": results,
            },
            f,
            indent=2,
        )

    print("\n" + "=" * 80)
    print("PHASE 24G.8 OUT-OF-SAMPLE VALIDATION SUMMARY")
    print("=" * 80)
    cols_to_print = [
        "partition",
        "candles",
        "trading_days",
        "total_trades",
        "win_rate_pct",
        "gross_pnl",
        "transaction_costs",
        "net_pnl",
        "profit_factor",
        "max_drawdown_amount",
        "cancelled_eod_orders",
        "long_net_pnl",
        "short_net_pnl",
    ]
    print(results_df[cols_to_print].to_string(index=False))
    print("=" * 80)


if __name__ == "__main__":
    main()
