"""
SignalForge — Phase 32C.6: DTP-V1 Historical Validation Runner
==============================================================
File: scripts/run_phase32c_6_dtp_v1_validation.py

Executes rigorous, causal historical validation of DTP-V1 on approved data
(INFY, RELIANCE, ICICIBANK for 2017-01-01 to 2019-12-31):
  - Strictly no look-ahead. Day T close -> Day T+1 open execution.
  - Multi-asset daily lockstep simulation.
  - Full delivery cost accounting via src/backtest/indian_delivery_costs.py.
  - Dual scenario evaluation: Baseline (Official ₹307/cr) vs Stress (Hypothetical ₹317/cr).
  - Export of all required audit ledgers and reconciliation metrics.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
import pandas as pd

from src.strategy.dtp_v1.config import (
    DTPExitReason,
    DTPRegimeState,
    DTPV1Config,
    OrderAction,
)
from src.strategy.dtp_v1.cost_integration import (
    DTPTradeCostSummary,
    calculate_dtp_roundtrip_costs,
)
from src.strategy.dtp_v1.indicators import calculate_dtp_indicators
from src.strategy.dtp_v1.market_filter import evaluate_breadth_regime
from src.strategy.dtp_v1.portfolio_rules import DTPPortfolioTracker
from src.strategy.dtp_v1.risk_manager import calculate_dtp_position_size
from src.strategy.dtp_v1.signal_engine import (
    DTPEODSignal,
    DTPPositionState,
    evaluate_exit_conditions,
    evaluate_next_open_execution,
    generate_eod_signal,
)


APPROVED_SYMBOLS = ["INFY", "RELIANCE", "ICICIBANK"]
START_DATE_STR = "2017-01-01"
END_DATE_STR = "2020-01-01"


def load_and_resample_daily_universe() -> Dict[str, pd.DataFrame]:
    """Loads approved 1m CSVs and resamples them to verified daily OHLCV bars."""
    universe: Dict[str, pd.DataFrame] = {}

    for sym in APPROVED_SYMBOLS:
        csv_path = Path(f"data/historical/stocks/{sym}_1m.csv")
        if not csv_path.exists():
            raise FileNotFoundError(f"Required approved dataset not found: {csv_path}")

        print(f"Loading {sym} from {csv_path}...")
        df_raw = pd.read_csv(csv_path, parse_dates=["timestamp"])
        df_sub = df_raw[(df_raw["timestamp"] >= START_DATE_STR) & (df_raw["timestamp"] < END_DATE_STR)].copy()

        df_sub["date"] = df_sub["timestamp"].dt.date
        daily = df_sub.groupby("date").agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )

        daily.index = pd.DatetimeIndex(daily.index)
        universe[sym] = daily
        print(f"  {sym}: {len(df_sub):,} 1m rows -> {len(daily)} daily bars ({daily.index[0].date()} to {daily.index[-1].date()})")

    return universe


def run_dtp_v1_validation(
    universe_daily: Dict[str, pd.DataFrame],
    initial_capital: float = 100000.0,
    config: Optional[DTPV1Config] = None,
    use_stress_costs: bool = False,
) -> Dict[str, Any]:
    """
    Executes chronological multi-asset simulation of DTP-V1.
    """
    if config is None:
        config = DTPV1Config()

    scenario_name = "STRESS_317" if use_stress_costs else "BASELINE_OFFICIAL"
    print(f"\n=======================================================")
    print(f"Running DTP-V1 Validation [{scenario_name}]")
    print(f"Initial Capital: ₹{initial_capital:,.2f} | Risk/Trade: {config.risk_fraction_per_trade:.1%}")
    print(f"=======================================================")

    # 1. Augment with causal indicators
    augmented_universe: Dict[str, pd.DataFrame] = {}
    for sym, df in universe_daily.items():
        aug = calculate_dtp_indicators(df, config=config)
        augmented_universe[sym] = aug

    # Common sorted trading dates
    trading_dates = sorted(list(set.intersection(*(set(df.index) for df in augmented_universe.values()))))
    print(f"Synchronized Trading Sessions: {len(trading_dates)} days ({trading_dates[0].date()} to {trading_dates[-1].date()})")

    portfolio = DTPPortfolioTracker(initial_capital, config)
    position_states: Dict[str, DTPPositionState] = {}
    pending_signals: Dict[str, DTPEODSignal] = {}

    executed_trades: List[Dict[str, Any]] = []
    rejected_signals: List[Dict[str, Any]] = []
    daily_equity_records: List[Dict[str, Any]] = []

    trade_counter = 0
    peak_equity = initial_capital

    for day_idx, current_ts in enumerate(trading_dates):
        current_dt = current_ts.date()

        # -------------------------------------------------------------------
        # Step A: Session Open (09:15 IST) - Process Pending EOD Signals
        # -------------------------------------------------------------------
        if pending_signals:
            # Sort pending signals deterministically by symbol
            for sym in sorted(list(pending_signals.keys())):
                sig = pending_signals.pop(sym)
                today_open = float(augmented_universe[sym].loc[current_ts, "open"])

                action, fill_price, action_msg = evaluate_next_open_execution(
                    signal=sig,
                    next_open_price=today_open,
                    config=config,
                )

                if action != OrderAction.ENTER_LONG:
                    rejected_signals.append(
                        {
                            "signal_date": sig.signal_date,
                            "execution_date": current_dt,
                            "symbol": sym,
                            "trigger_price": sig.entry_trigger_price,
                            "open_price": today_open,
                            "gap_pct": (today_open - sig.entry_trigger_price) / sig.entry_trigger_price,
                            "rejection_reason": action_msg,
                        }
                    )
                    continue

                # Position sizing
                curr_prices = {s: float(augmented_universe[s].loc[current_ts, "open"]) for s in APPROVED_SYMBOLS}
                equity = portfolio.get_portfolio_equity(curr_prices)
                sector = config.symbol_sector_map.get(sym, "General")
                sec_exp = portfolio.get_sector_exposure(sector, curr_prices)

                shares, size_msg = calculate_dtp_position_size(
                    equity=equity,
                    available_cash=portfolio.cash,
                    entry_price=fill_price,
                    stop_price=sig.initial_stop_price,
                    sector=sector,
                    current_sector_exposure=sec_exp,
                    config=config,
                )

                if shares <= 0:
                    rejected_signals.append(
                        {
                            "signal_date": sig.signal_date,
                            "execution_date": current_dt,
                            "symbol": sym,
                            "trigger_price": sig.entry_trigger_price,
                            "open_price": today_open,
                            "gap_pct": (today_open - sig.entry_trigger_price) / sig.entry_trigger_price,
                            "rejection_reason": f"Sizing rejected: {size_msg}",
                        }
                    )
                    continue

                can_open, gate_msg = portfolio.can_open_position(
                    symbol=sym,
                    entry_price=fill_price,
                    proposed_shares=shares,
                    sector=sector,
                    current_prices=curr_prices,
                )

                if not can_open:
                    rejected_signals.append(
                        {
                            "signal_date": sig.signal_date,
                            "execution_date": current_dt,
                            "symbol": sym,
                            "trigger_price": sig.entry_trigger_price,
                            "open_price": today_open,
                            "gap_pct": (today_open - sig.entry_trigger_price) / sig.entry_trigger_price,
                            "rejection_reason": f"Portfolio gate rejected: {gate_msg}",
                        }
                    )
                    continue

                # Open the position
                trade_counter += 1
                order_id = f"DTP_{trade_counter:04d}_BUY_{sym}_{current_dt.isoformat()}"
                active_pos = portfolio.open_position(
                    symbol=sym,
                    entry_price=fill_price,
                    shares=shares,
                    stop_price=sig.initial_stop_price,
                    r_distance=sig.r_distance,
                    entry_date=current_dt,
                    order_id=order_id,
                    sector=sector,
                )

                position_states[sym] = DTPPositionState(
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

        # -------------------------------------------------------------------
        # Step B: Intraday Session Exits (Stop loss, Chandelier, Targets)
        # -------------------------------------------------------------------
        symbols_to_close: List[Tuple[str, DTPExitReason, float, str]] = []

        for sym, pos in list(portfolio.positions.items()):
            pos_state = position_states[sym]
            bar = augmented_universe[sym].loc[current_ts]

            # In the final trading session, force liquidation to settle portfolio
            if day_idx == len(trading_dates) - 1:
                friction_rate = (config.execution_slippage_bps + config.execution_spread_bps) / 10000.0
                exit_px = float(bar["close"]) * (1.0 - friction_rate)
                symbols_to_close.append((sym, DTPExitReason.MANUAL_CLOSE, exit_px, "End of validation period liquidation"))
                continue

            reason, exit_px, exit_msg = evaluate_exit_conditions(
                pos=pos_state,
                current_high=float(bar["high"]),
                current_low=float(bar["low"]),
                current_close=float(bar["close"]),
                current_open=float(bar["open"]),
                current_atr=float(bar["atr"]),
                current_ema50=float(bar["ema_slow"]),
                current_rsi=float(bar["rsi"]),
                current_bb_upper=float(bar["bb_upper"]),
                config=config,
            )

            if reason is not None:
                symbols_to_close.append((sym, reason, exit_px, exit_msg))

        for sym, reason, exit_px, exit_msg in symbols_to_close:
            active_pos = portfolio.positions[sym]
            pos_state = position_states[sym]

            isin = config.symbol_isin_map.get(sym, "DEFAULT_ISIN")
            breakdown, cost_summary = calculate_dtp_roundtrip_costs(
                symbol=sym,
                isin=isin,
                entry_date=active_pos.entry_date,
                exit_date=current_dt,
                entry_price=active_pos.entry_price,
                exit_price=exit_px,
                quantity=active_pos.quantity,
                use_stress_profile=use_stress_costs,
                order_id_prefix=f"DTP_{trade_counter:04d}",
            )

            net_proceeds = cost_summary.sell_turnover - cost_summary.total_friction_costs
            portfolio.close_position(sym, exit_px, net_proceeds)
            position_states.pop(sym, None)

            initial_risk_amount = active_pos.quantity * active_pos.r_distance
            realized_r = cost_summary.net_pnl / initial_risk_amount if initial_risk_amount > 0 else 0.0

            executed_trades.append(
                {
                    "trade_id": active_pos.order_id,
                    "symbol": sym,
                    "sector": active_pos.sector,
                    "entry_date": active_pos.entry_date,
                    "exit_date": current_dt,
                    "holding_days": pos_state.holding_days,
                    "quantity": active_pos.quantity,
                    "entry_price": active_pos.entry_price,
                    "exit_price": exit_px,
                    "initial_stop": active_pos.initial_stop_price,
                    "exit_reason": reason.value,
                    "exit_message": exit_msg,
                    "buy_turnover": cost_summary.buy_turnover,
                    "sell_turnover": cost_summary.sell_turnover,
                    "total_turnover": cost_summary.total_turnover,
                    "gross_pnl": cost_summary.gross_pnl,
                    "total_stt": cost_summary.total_stt,
                    "total_stamp_duty": cost_summary.total_stamp_duty,
                    "exchange_charge": cost_summary.exchange_charge,
                    "ipft_charge": cost_summary.ipft_charge,
                    "sebi_turnover_fee": cost_summary.sebi_turnover_fee,
                    "total_brokerage": cost_summary.total_brokerage,
                    "total_dp_charge": cost_summary.total_dp_charge,
                    "total_gst": cost_summary.total_gst,
                    "total_execution_friction": cost_summary.total_execution_friction,
                    "total_friction_costs": cost_summary.total_friction_costs,
                    "net_pnl": cost_summary.net_pnl,
                    "net_return_pct": cost_summary.net_return_pct,
                    "breakeven_gross_pct": cost_summary.breakeven_gross_pct,
                    "initial_risk_amount": initial_risk_amount,
                    "realized_r_multiple": realized_r,
                }
            )

        # -------------------------------------------------------------------
        # Step C: Session Close (15:30 IST) - Evaluate EOD Signals
        # -------------------------------------------------------------------
        # Evaluate Universe Breadth Index (UBI) across the approved universe
        regime_state, regime_reason = evaluate_breadth_regime(augmented_universe, config=config, bar_idx=day_idx)

        # Only search for new entries if not in the final sessions
        if day_idx < len(trading_dates) - 2:
            for sym in APPROVED_SYMBOLS:
                # Do not generate duplicate signal if position is already open or pending
                if sym in portfolio.positions or sym in pending_signals:
                    continue

                sig = generate_eod_signal(
                    symbol=sym,
                    df=augmented_universe[sym],
                    market_regime=regime_state,
                    config=config,
                    bar_idx=day_idx,
                    signal_date=current_dt,
                )

                if sig is not None:
                    pending_signals[sym] = sig

        # -------------------------------------------------------------------
        # Step D: EOD Portfolio Mark-to-Market Snapshot
        # -------------------------------------------------------------------
        day_closes = {s: float(augmented_universe[s].loc[current_ts, "close"]) for s in APPROVED_SYMBOLS}
        equity_val = portfolio.get_portfolio_equity(day_closes)
        invested_val = portfolio.total_invested_capital()
        cash_val = portfolio.cash

        if equity_val > peak_equity:
            peak_equity = equity_val
        drawdown_pct = (peak_equity - equity_val) / peak_equity * 100.0 if peak_equity > 0 else 0.0

        daily_equity_records.append(
            {
                "date": current_dt,
                "cash": cash_val,
                "invested_capital": invested_val,
                "portfolio_equity": equity_val,
                "open_position_count": portfolio.position_count,
                "peak_equity": peak_equity,
                "drawdown_pct": drawdown_pct,
                "market_regime": regime_state.value,
            }
        )

    # -----------------------------------------------------------------------
    # Verification & Metrics Compilation
    # -----------------------------------------------------------------------
    final_equity = portfolio.get_portfolio_equity()
    total_net_pnl = final_equity - initial_capital
    sum_trade_net_pnl = sum(t["net_pnl"] for t in executed_trades)
    cash_reconciliation_diff = abs((portfolio.cash - initial_capital) - sum_trade_net_pnl)

    print(f"\n--- Validation Execution Summary [{scenario_name}] ---")
    print(f"Total Completed Trades: {len(executed_trades)}")
    print(f"Total Rejected Signals: {len(rejected_signals)}")
    print(f"Initial Capital:        ₹{initial_capital:,.2f}")
    print(f"Final Equity (Cash):    ₹{portfolio.cash:,.2f}")
    print(f"Total Net P&L:          ₹{total_net_pnl:,.2f} ({(total_net_pnl / initial_capital) * 100:.2f}%)")
    print(f"Sum Trade Net P&L:      ₹{sum_trade_net_pnl:,.2f}")
    print(f"Cash Reconcile Diff:    ₹{cash_reconciliation_diff:.4f} (Float vs Decimal ledger)")
    assert cash_reconciliation_diff < 0.05, f"Cash reconciliation failed: diff={cash_reconciliation_diff}"

    return {
        "scenario": scenario_name,
        "initial_capital": initial_capital,
        "final_equity": final_equity,
        "executed_trades": pd.DataFrame(executed_trades),
        "rejected_signals": pd.DataFrame(rejected_signals),
        "daily_equity": pd.DataFrame(daily_equity_records),
    }


if __name__ == "__main__":
    universe_data = load_and_resample_daily_universe()

    # 1. Run Baseline Scenario (Official ₹307/cr schedule + realistic execution)
    baseline_res = run_dtp_v1_validation(universe_data, initial_capital=100000.0, use_stress_costs=False)

    # 2. Run Stress Scenario (Hypothetical ₹317/cr schedule + 5 bps slippage)
    stress_res = run_dtp_v1_validation(universe_data, initial_capital=100000.0, use_stress_costs=True)

    # Export Baseline Dataframes
    out_dir = Path("C:/Users/Sanket Amte/.gemini/antigravity/brain/b4cd4b97-a5c7-46f6-a62b-827fcfb4102f")
    baseline_res["executed_trades"].to_csv(out_dir / "phase32c_6_dtp_v1_trade_ledger.csv", index=False)
    baseline_res["daily_equity"].to_csv(out_dir / "phase32c_6_dtp_v1_daily_equity.csv", index=False)

    rej_df = baseline_res["rejected_signals"]
    if rej_df.empty:
        rej_df = pd.DataFrame(columns=["signal_date", "execution_date", "symbol", "trigger_price", "open_price", "gap_pct", "rejection_reason"])
    rej_df.to_csv(out_dir / "phase32c_6_dtp_v1_rejected_signals.csv", index=False)

    # Generate Cost Reconciliation CSV
    cost_summary_cols = [
        "trade_id", "symbol", "entry_date", "exit_date", "quantity", "entry_price", "exit_price",
        "buy_turnover", "sell_turnover", "total_turnover", "gross_pnl",
        "total_stt", "total_stamp_duty", "exchange_charge", "ipft_charge", "sebi_turnover_fee",
        "total_brokerage", "total_dp_charge", "total_gst", "total_execution_friction",
        "total_friction_costs", "net_pnl", "breakeven_gross_pct"
    ]
    if not baseline_res["executed_trades"].empty:
        baseline_res["executed_trades"][cost_summary_cols].to_csv(
            out_dir / "phase32c_6_dtp_v1_cost_reconciliation.csv", index=False
        )

    print("\n[SUCCESS] Phase 32C.6 validation run completed and CSV deliverables generated.")
