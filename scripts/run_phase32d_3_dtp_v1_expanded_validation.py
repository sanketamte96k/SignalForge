"""
SignalForge — Phase 32D.3: DTP-V1 Expanded Universe Historical Validation Runner
================================================================================
File: scripts/run_phase32d_3_dtp_v1_expanded_validation.py

Executes rigorous, causal historical validation of DTP-V1 across the approved
21-stock Primary NSE cash-equity universe (2017-01-01 to 2019-12-31):
  - Strictly no look-ahead: Day T EOD close evaluation -> Day T+1 open execution.
  - Multi-asset daily lockstep simulation across 739 synchronized sessions.
  - Full statutory delivery cost accounting via src/backtest/indian_delivery_costs.py.
  - Deterministic signal priority: S_trend descending, S_pullback ascending, alphabetical tie-breaker.
  - Portfolio exposure gates: <=3 concurrent positions, <=40% sector cap, 1% risk/trade, 33.3% pos cap.
  - Dual scenario evaluation: Baseline (Official ₹307/cr) vs Stress (Groww UI ₹317/cr).
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

# Approved 21-stock primary research universe
APPROVED_21_SYMBOLS = [
    "INFY", "RELIANCE", "ICICIBANK", "HDFCBANK", "AXISBANK",
    "KOTAKBANK", "SBIN", "MARUTI", "M&M", "BAJAJ-AUTO",
    "ITC", "ASIANPAINT", "SUNPHARMA", "CIPLA", "DRREDDY",
    "HCLTECH", "LT", "BPCL", "POWERGRID", "NTPC", "COALINDIA"
]

EXPANDED_SECTOR_MAP: Dict[str, str] = {
    "INFY": "Information Technology",
    "RELIANCE": "Oil, Gas & Consumable Fuels",
    "ICICIBANK": "Financial Services (Banking)",
    "HDFCBANK": "Financial Services (Banking)",
    "AXISBANK": "Financial Services (Banking)",
    "KOTAKBANK": "Financial Services (Banking)",
    "SBIN": "Financial Services (Banking)",
    "MARUTI": "Automobile",
    "M&M": "Automobile",
    "BAJAJ-AUTO": "Automobile",
    "ITC": "Fast Moving Consumer Goods",
    "ASIANPAINT": "Consumer Durables",
    "SUNPHARMA": "Healthcare & Pharmaceuticals",
    "CIPLA": "Healthcare & Pharmaceuticals",
    "DRREDDY": "Healthcare & Pharmaceuticals",
    "HCLTECH": "Information Technology",
    "LT": "Construction & Capital Goods",
    "BPCL": "Oil, Gas & Consumable Fuels",
    "POWERGRID": "Power",
    "NTPC": "Power",
    "COALINDIA": "Oil, Gas & Consumable Fuels",
}

EXPANDED_ISIN_MAP: Dict[str, str] = {
    "INFY": "INE009A01021",
    "RELIANCE": "INE002A01018",
    "ICICIBANK": "INE090A01021",
    "HDFCBANK": "INE040A01034",
    "AXISBANK": "INE238A01034",
    "KOTAKBANK": "INE237A01028",
    "SBIN": "INE062A01020",
    "MARUTI": "INE585B01010",
    "M&M": "INE101A01026",
    "BAJAJ-AUTO": "INE917I01010",
    "ITC": "INE154A01025",
    "ASIANPAINT": "INE021A01026",
    "SUNPHARMA": "INE044A01036",
    "CIPLA": "INE059A01026",
    "DRREDDY": "INE089A01023",
    "HCLTECH": "INE860A01027",
    "LT": "INE018A01030",
    "BPCL": "INE029A01011",
    "POWERGRID": "INE752E01010",
    "NTPC": "INE733E01010",
    "COALINDIA": "INE522F01014",
}

START_DATE_STR = "2017-01-01"
END_DATE_STR = "2020-01-01"


def load_and_resample_21_universe() -> Dict[str, pd.DataFrame]:
    """Loads approved 21 canonical 1m CSVs and resamples them to synchronized daily OHLCV bars."""
    universe: Dict[str, pd.DataFrame] = {}

    for sym in APPROVED_21_SYMBOLS:
        csv_path = Path(f"data/historical/stocks/{sym}_1m.csv")
        if not csv_path.exists():
            raise FileNotFoundError(f"Required approved canonical dataset not found: {csv_path}")

        print(f"Loading {sym:12} from {csv_path}...")
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
        print(f"  {sym:12}: {len(df_sub):,} 1m rows -> {len(daily)} daily bars ({daily.index[0].date()} to {daily.index[-1].date()})")

    return universe


def calculate_signal_priority(sig: DTPEODSignal, bar: pd.Series) -> Tuple[float, float, str]:
    """
    Computes deterministic sort tuple for signal prioritization:
      Key 1: S_trend (descending -> sort by -S_trend)
             S_trend = ((Close - SMA200) / SMA200) * (ADX / 20.0)
      Key 2: S_pullback (ascending -> sort by S_pullback)
             S_pullback = abs(Close - EMA20) / EMA20
      Key 3: Symbol alphabetical order (ascending)
    """
    close = float(bar["close"])
    sma200 = float(bar["sma_trend"]) if "sma_trend" in bar and bar["sma_trend"] > 0 else close
    adx = float(bar["adx"]) if "adx" in bar else 20.0
    ema20 = float(bar["ema_fast"]) if "ema_fast" in bar and bar["ema_fast"] > 0 else close

    s_trend = ((close - sma200) / sma200) * (adx / 20.0)
    s_pullback = abs(close - ema20) / ema20

    # Negative s_trend so that higher trend strength sorts first
    return (-s_trend, s_pullback, sig.symbol)


def run_dtp_v1_expanded_validation(
    universe_daily: Dict[str, pd.DataFrame],
    initial_capital: float = 100000.0,
    config: Optional[DTPV1Config] = None,
    use_stress_costs: bool = False,
) -> Dict[str, Any]:
    """
    Executes chronological multi-asset lockstep simulation of DTP-V1 across 21 stocks.
    """
    if config is None:
        config = DTPV1Config(
            symbol_sector_map=EXPANDED_SECTOR_MAP,
            symbol_isin_map=EXPANDED_ISIN_MAP
        )

    scenario_name = "STRESS_317" if use_stress_costs else "BASELINE_OFFICIAL"
    print(f"\n=======================================================")
    print(f"Running DTP-V1 21-Stock Expanded Validation [{scenario_name}]")
    print(f"Universe: {len(universe_daily)} Equities | Initial Capital: ₹{initial_capital:,.2f}")
    print(f"Risk/Trade: {config.risk_fraction_per_trade:.1%} | Max Positions: {config.max_concurrent_positions}")
    print(f"=======================================================")

    # 1. Augment with causal indicators
    augmented_universe: Dict[str, pd.DataFrame] = {}
    for sym, df in universe_daily.items():
        aug = calculate_dtp_indicators(df, config=config)
        augmented_universe[sym] = aug

    # Synchronized trading dates
    trading_dates = sorted(list(set.intersection(*(set(df.index) for df in augmented_universe.values()))))
    print(f"Synchronized Trading Sessions: {len(trading_dates)} days ({trading_dates[0].date()} to {trading_dates[-1].date()})")

    portfolio = DTPPortfolioTracker(initial_capital, config)
    position_states: Dict[str, DTPPositionState] = {}
    pending_signals: Dict[str, Tuple[DTPEODSignal, Tuple[float, float, str]]] = {}

    executed_trades: List[Dict[str, Any]] = []
    rejected_signals: List[Dict[str, Any]] = []
    daily_equity_records: List[Dict[str, Any]] = []

    trade_counter = 0
    peak_equity = initial_capital

    for day_idx, current_ts in enumerate(trading_dates):
        current_dt = current_ts.date()
        opening_cash = portfolio.cash

        # -------------------------------------------------------------------
        # Step A: Session Open (09:15 IST) - Process Pending EOD Signals
        # -------------------------------------------------------------------
        if pending_signals:
            # Sort pending signals deterministically using locked priority tuple
            # Priority tuple: (-s_trend, s_pullback, symbol)
            sorted_pending = sorted(pending_signals.items(), key=lambda item: item[1][1])

            for sym, (sig, prio_tuple) in sorted_pending:
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
                            "sector": config.symbol_sector_map.get(sym, "General"),
                            "priority_rank": str(prio_tuple),
                            "trigger_price": sig.entry_trigger_price,
                            "open_price": today_open,
                            "gap_pct": (today_open - sig.entry_trigger_price) / sig.entry_trigger_price,
                            "rejection_reason": action_msg,
                            "available_cash": portfolio.cash,
                            "current_positions": portfolio.position_count,
                            "sector_limit_pct": config.max_sector_exposure_pct,
                        }
                    )
                    continue

                # Position sizing
                curr_prices = {s: float(augmented_universe[s].loc[current_ts, "open"]) for s in APPROVED_21_SYMBOLS}
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
                            "sector": sector,
                            "priority_rank": str(prio_tuple),
                            "trigger_price": sig.entry_trigger_price,
                            "open_price": today_open,
                            "gap_pct": (today_open - sig.entry_trigger_price) / sig.entry_trigger_price,
                            "rejection_reason": f"Sizing rejected: {size_msg}",
                            "available_cash": portfolio.cash,
                            "current_positions": portfolio.position_count,
                            "sector_limit_pct": config.max_sector_exposure_pct,
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
                            "sector": sector,
                            "priority_rank": str(prio_tuple),
                            "trigger_price": sig.entry_trigger_price,
                            "open_price": today_open,
                            "gap_pct": (today_open - sig.entry_trigger_price) / sig.entry_trigger_price,
                            "rejection_reason": f"Portfolio gate rejected: {gate_msg}",
                            "available_cash": portfolio.cash,
                            "current_positions": portfolio.position_count,
                            "sector_limit_pct": config.max_sector_exposure_pct,
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

            # Clear pending signals
            pending_signals.clear()

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

            # Calculate separate sub-totals
            taxes_and_statutory = (
                cost_summary.total_stt +
                cost_summary.exchange_charge +
                cost_summary.ipft_charge +
                cost_summary.sebi_turnover_fee +
                cost_summary.total_stamp_duty +
                cost_summary.total_gst
            )
            brokerage = cost_summary.total_brokerage
            depository_charges = cost_summary.total_dp_charge
            friction_cost = cost_summary.total_execution_friction

            executed_trades.append(
                {
                    "trade_id": active_pos.order_id,
                    "symbol": sym,
                    "sector": active_pos.sector,
                    "entry_date": active_pos.entry_date,
                    "entry_price": active_pos.entry_price,
                    "exit_date": current_dt,
                    "exit_price": exit_px,
                    "quantity": active_pos.quantity,
                    "gross_pnl": cost_summary.gross_pnl,
                    "brokerage": brokerage,
                    "taxes_and_statutory": taxes_and_statutory,
                    "depository_charges": depository_charges,
                    "execution_friction": friction_cost,
                    "total_costs": cost_summary.total_friction_costs,
                    "net_pnl": cost_summary.net_pnl,
                    "holding_days": pos_state.holding_days,
                    "exit_reason": reason.value,
                    "exit_message": exit_msg,
                    "realized_r": realized_r,
                }
            )

        # -------------------------------------------------------------------
        # Step C: Session Close (15:30 IST) - Evaluate Market Regime & EOD Signals
        # -------------------------------------------------------------------
        regime_state, regime_reason = evaluate_breadth_regime(augmented_universe, config=config, bar_idx=day_idx)

        # Generate signals for Day T+1 (only up to 2 days before final session)
        if day_idx < len(trading_dates) - 2:
            for sym in APPROVED_21_SYMBOLS:
                if sym in portfolio.positions:
                    continue  # Pyramiding forbidden

                sig = generate_eod_signal(
                    symbol=sym,
                    df=augmented_universe[sym],
                    market_regime=regime_state,
                    config=config,
                    bar_idx=day_idx,
                    signal_date=current_dt,
                )

                if sig is not None:
                    bar = augmented_universe[sym].iloc[day_idx]
                    prio = calculate_signal_priority(sig, bar)
                    pending_signals[sym] = (sig, prio)

        # -------------------------------------------------------------------
        # Step D: EOD Portfolio Mark-to-Market Valuation
        # -------------------------------------------------------------------
        eod_prices = {s: float(augmented_universe[s].loc[current_ts, "close"]) for s in APPROVED_21_SYMBOLS}
        portfolio_equity = portfolio.get_portfolio_equity(eod_prices)
        invested_capital = portfolio.total_invested_capital()
        closing_cash = portfolio.cash
        exposure_pct = (invested_capital / portfolio_equity) if portfolio_equity > 0 else 0.0

        if portfolio_equity > peak_equity:
            peak_equity = portfolio_equity
        drawdown_pct = (portfolio_equity - peak_equity) / peak_equity if peak_equity > 0 else 0.0

        prev_equity = daily_equity_records[-1]["total_equity"] if daily_equity_records else initial_capital
        daily_return = (portfolio_equity - prev_equity) / prev_equity if prev_equity > 0 else 0.0

        daily_equity_records.append(
            {
                "date": current_dt,
                "opening_cash": opening_cash,
                "closing_cash": closing_cash,
                "open_position_value": invested_capital,
                "total_equity": portfolio_equity,
                "daily_return": daily_return,
                "drawdown": drawdown_pct,
                "exposure_pct": exposure_pct,
                "open_positions": portfolio.position_count,
                "peak_equity": peak_equity,
                "market_regime": regime_state.value,
            }
        )



    # -----------------------------------------------------------------------
    # Portfolio Performance & Verification Metrics
    # -----------------------------------------------------------------------
    df_trades = pd.DataFrame(executed_trades)
    df_daily = pd.DataFrame(daily_equity_records)
    df_rejected = pd.DataFrame(rejected_signals)

    ending_equity = float(df_daily["total_equity"].iloc[-1])
    total_net_pnl = ending_equity - initial_capital
    net_return_pct = total_net_pnl / initial_capital

    days_elapsed = (trading_dates[-1].date() - trading_dates[0].date()).days
    years_elapsed = days_elapsed / 365.25
    cagr = ((ending_equity / initial_capital) ** (1.0 / years_elapsed)) - 1.0 if ending_equity > 0 else -1.0

    max_dd = float(df_daily["drawdown"].min())
    total_trades_count = len(df_trades)

    if total_trades_count > 0:
        win_trades = df_trades[df_trades["net_pnl"] > 0]
        loss_trades = df_trades[df_trades["net_pnl"] <= 0]

        win_rate = len(win_trades) / total_trades_count
        gross_wins = float(win_trades["net_pnl"].sum())
        gross_losses = float(abs(loss_trades["net_pnl"].sum()))

        profit_factor = gross_wins / gross_losses if gross_losses > 0 else 999.0
        avg_win = float(win_trades["net_pnl"].mean()) if len(win_trades) > 0 else 0.0
        avg_loss = float(abs(loss_trades["net_pnl"].mean())) if len(loss_trades) > 0 else 0.0
        payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 999.0

        total_gross_pnl = float(df_trades["gross_pnl"].sum())
        total_costs = float(df_trades["total_costs"].sum())
        cost_ratio = (total_costs / total_gross_pnl) if total_gross_pnl > 0 else 0.0
        avg_holding_days = float(df_trades["holding_days"].mean())
    else:
        win_rate = 0.0
        profit_factor = 0.0
        payoff_ratio = 0.0
        avg_win = 0.0
        avg_loss = 0.0
        total_gross_pnl = 0.0
        total_costs = 0.0
        cost_ratio = 0.0
        avg_holding_days = 0.0

    avg_utilization = float(df_daily["exposure_pct"].mean())

    metrics = {
        "scenario": scenario_name,
        "initial_capital": initial_capital,
        "ending_equity": round(ending_equity, 2),
        "total_net_pnl": round(total_net_pnl, 2),
        "net_return_pct": round(net_return_pct * 100.0, 2),
        "cagr_pct": round(cagr * 100.0, 2),
        "profit_factor": round(profit_factor, 2),
        "win_rate_pct": round(win_rate * 100.0, 2),
        "max_drawdown_pct": round(abs(max_dd) * 100.0, 2),
        "payoff_ratio": round(payoff_ratio, 2),
        "total_trades": total_trades_count,
        "avg_holding_days": round(avg_holding_days, 1),
        "total_gross_pnl": round(total_gross_pnl, 2),
        "total_friction_costs": round(total_costs, 2),
        "cost_to_gross_profit_pct": round(cost_ratio * 100.0, 2),
        "avg_capital_utilization_pct": round(avg_utilization * 100.0, 2),
        "rejected_signals_count": len(df_rejected),
    }

    return {
        "metrics": metrics,
        "trades_df": df_trades,
        "daily_df": df_daily,
        "rejected_df": df_rejected,
    }


def main():
    artifact_dir = Path("C:/Users/Sanket Amte/.gemini/antigravity/brain/b4cd4b97-a5c7-46f6-a62b-827fcfb4102f")

    # 1. Load universe
    universe_daily = load_and_resample_21_universe()

    # 2. Run Baseline Scenario (Official ₹307/cr)
    baseline_result = run_dtp_v1_expanded_validation(
        universe_daily=universe_daily,
        initial_capital=100000.0,
        use_stress_costs=False,
    )

    # 3. Run Stress Scenario (Groww Discrepancy ₹317/cr)
    stress_result = run_dtp_v1_expanded_validation(
        universe_daily=universe_daily,
        initial_capital=100000.0,
        use_stress_costs=True,
    )

    # 4. Print Summary Comparison
    b_met = baseline_result["metrics"]
    s_met = stress_result["metrics"]

    print("\n=======================================================")
    print("DTP-V1 21-STOCK EXPANDED VALIDATION RESULTS SUMMARY")
    print("=======================================================")
    print(f"{'Metric':<32} | {'Baseline (Official ₹307)':<22} | {'Stress (+₹10 Discrepancy)':<22}")
    print("-" * 82)
    for k in b_met.keys():
        if k == "scenario":
            continue
        print(f"{k:<32} | {str(b_met[k]):<22} | {str(s_met[k]):<22}")
    print("=======================================================\n")

    # 5. Export Baseline Audit Ledgers
    b_trades = baseline_result["trades_df"]
    b_daily = baseline_result["daily_df"]
    b_rejected = baseline_result["rejected_df"]

    trade_ledger_path = artifact_dir / "phase32d_3_trade_ledger.csv"
    b_trades.to_csv(trade_ledger_path, index=False)
    print(f"Exported: {trade_ledger_path} ({len(b_trades)} trades)")

    daily_equity_path = artifact_dir / "phase32d_3_daily_equity.csv"
    b_daily.to_csv(daily_equity_path, index=False)
    print(f"Exported: {daily_equity_path} ({len(b_daily)} sessions)")

    rejected_path = artifact_dir / "phase32d_3_rejected_signals.csv"
    b_rejected.to_csv(rejected_path, index=False)
    print(f"Exported: {rejected_path} ({len(b_rejected)} rejected signals)")

    # 6. Export Cost Reconciliation Ledger comparing Baseline vs Stress
    s_trades = stress_result["trades_df"]
    reconciliation_rows = []
    for idx in range(len(b_trades)):
        bt = b_trades.iloc[idx]
        st = s_trades.iloc[idx]
        reconciliation_rows.append(
            {
                "trade_id": bt["trade_id"],
                "symbol": bt["symbol"],
                "sector": bt["sector"],
                "entry_date": bt["entry_date"],
                "exit_date": bt["exit_date"],
                "quantity": bt["quantity"],
                "gross_pnl": bt["gross_pnl"],
                "baseline_brokerage": bt["brokerage"],
                "baseline_taxes_and_statutory": bt["taxes_and_statutory"],
                "baseline_depository_charges": bt["depository_charges"],
                "baseline_execution_friction": bt["execution_friction"],
                "baseline_total_costs": bt["total_costs"],
                "baseline_net_pnl": bt["net_pnl"],
                "stress_taxes_and_statutory": st["taxes_and_statutory"],
                "stress_total_costs": st["total_costs"],
                "stress_net_pnl": st["net_pnl"],
                "cost_delta_inr": round(st["total_costs"] - bt["total_costs"], 4),
                "net_pnl_delta_inr": round(st["net_pnl"] - bt["net_pnl"], 4),
            }
        )

    cost_rec_df = pd.DataFrame(reconciliation_rows)
    cost_rec_path = artifact_dir / "phase32d_3_cost_reconciliation.csv"
    cost_rec_df.to_csv(cost_rec_path, index=False)
    print(f"Exported: {cost_rec_path} ({len(cost_rec_df)} reconciled trades)")


if __name__ == "__main__":
    main()
