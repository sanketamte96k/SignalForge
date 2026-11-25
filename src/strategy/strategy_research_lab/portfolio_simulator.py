"""
SignalForge — Phase 33A: Portfolio Simulator & Performance Metrics Engine
========================================================================
File: src/strategy/strategy_research_lab/portfolio_simulator.py

Simulates realistic cash equity swing trading with:
  - Max 2 concurrent open positions across the universe
  - E1 (1%), E2 (2%), E3 (3%) risk-based integer position sizing
  - Cash equity accounting (no margin, no shorting, no leverage)
  - Next-open execution with 5 bps slippage per leg
  - Certified Indian delivery transaction costs (Official ₹307/cr vs Stress ₹317/cr)
  - Full monthly, yearly, and trade-level accounting
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.strategy.dtp_v3.cost_integration import calculate_dtp_roundtrip_costs
from src.strategy.strategy_research_lab.config import (
    DEFAULT_STRATEGY_CONFIGS,
    ExitReason,
    RiskTier,
    StrategyCandidateConfig,
    StrategyID,
    StrategyLabConfig,
)
from src.strategy.strategy_research_lab.signal_engines import (
    CandidateSignal,
    evaluate_candidate_exit,
    generate_candidate_signals,
)


def to_py_date(dt: Any) -> date:
    """Converts a datetime/Timestamp or date to a pure python datetime.date object."""
    if hasattr(dt, "date") and callable(getattr(dt, "date")):
        return dt.date()
    return dt


@dataclass
class ActivePosition:
    """Represents an open swing position in the portfolio."""
    trade_id: int
    strategy_id: StrategyID
    symbol: str
    sector: str
    isin: str
    entry_date: date
    entry_price: float
    quantity: int
    stop_loss_price: float
    profit_target_price: Optional[float]
    trailing_exit_level: Optional[float]
    max_hold_bars: int
    bars_held: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompletedTrade:
    """Full forensic ledger record for a completed trade."""
    trade_id: int
    strategy_id: str
    symbol: str
    sector: str
    entry_date: date
    exit_date: date
    bars_held: int
    quantity: int
    raw_entry_price: float
    raw_exit_price: float
    effective_entry_price: float
    effective_exit_price: float
    buy_turnover: float
    sell_turnover: float
    total_turnover: float
    gross_pnl: float
    brokerage: float
    stt: float
    exchange_turnover: float
    stamp_duty: float
    gst: float
    sebi_charges: float
    dp_charges: float
    slippage: float
    total_costs: float
    net_pnl: float
    net_return_pct: float
    exit_reason: str
    exit_notes: str


@dataclass
class PortfolioSimulationResult:
    """Complete backtest output across single or combined strategies."""
    strategy_id: str
    risk_tier: str
    cost_schedule: str
    initial_capital: float
    final_equity: float
    total_net_pnl: float
    total_gross_pnl: float
    total_costs: float
    roi_pct: float
    cagr_pct: float
    completed_trades: int
    wins: int
    losses: int
    win_rate: float
    profit_factor: float
    payoff_ratio: float
    max_drawdown_pct: float
    max_drawdown_inr: float
    trades: List[CompletedTrade]
    daily_equity: pd.Series
    monthly_profitability: pd.DataFrame
    yearly_profitability: pd.DataFrame
    top_3_trades_contribution: float
    ex_top_3_net_pnl: float
    profitable_months: int
    losing_months: int
    profitable_months_pct: float
    profitable_years: int
    losing_years: int
    longest_consecutive_losses: int
    longest_consecutive_losing_months: int


def calculate_performance_tables(
    trades: List[CompletedTrade],
    daily_equity: pd.Series,
    initial_capital: float,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Calculates granular monthly and yearly profitability breakdowns."""
    if not trades:
        empty_monthly = pd.DataFrame(
            columns=[
                "year_month", "trades", "wins", "losses", "gross_profit", "gross_loss",
                "costs", "net_pnl", "return_pct", "max_drawdown", "profit_factor"
            ]
        )
        empty_yearly = pd.DataFrame(
            columns=[
                "year", "trades", "win_rate", "gross_profit", "costs", "net_pnl",
                "annual_return_pct", "cagr_pct", "max_drawdown_pct", "profit_factor", "payoff_ratio"
            ]
        )
        return empty_monthly, empty_yearly, {
            "profitable_months": 0, "losing_months": 0, "profitable_months_pct": 0.0,
            "profitable_years": 0, "losing_years": 0, "longest_consec_losing_months": 0,
            "longest_consec_losing_trades": 0, "top_3_contribution": 0.0, "ex_top3_net_pnl": 0.0
        }

    df_trades = pd.DataFrame([t.__dict__ for t in trades])
    df_trades["exit_date"] = pd.to_datetime(df_trades["exit_date"])
    df_trades["year"] = df_trades["exit_date"].dt.year
    df_trades["year_month"] = df_trades["exit_date"].dt.to_period("M").astype(str)

    # Monthly aggregation
    monthly_records = []
    # Build complete calendar months between start and end
    all_months = sorted(list(df_trades["year_month"].unique()))
    
    for ym in all_months:
        sub = df_trades[df_trades["year_month"] == ym]
        n_trades = len(sub)
        n_wins = int((sub["net_pnl"] > 0).sum())
        n_losses = int((sub["net_pnl"] <= 0).sum())
        gp = float(sub[sub["gross_pnl"] > 0]["gross_pnl"].sum())
        gl = float(abs(sub[sub["gross_pnl"] < 0]["gross_pnl"].sum()))
        costs = float(sub["total_costs"].sum())
        net_pnl = float(sub["net_pnl"].sum())

        # Net profit factor
        pos_net = float(sub[sub["net_pnl"] > 0]["net_pnl"].sum())
        neg_net = float(abs(sub[sub["net_pnl"] < 0]["net_pnl"].sum()))
        pf = (pos_net / neg_net) if neg_net > 0 else (99.0 if pos_net > 0 else 0.0)

        # Drawdown during month
        sub_dates = sub["exit_date"].dt.date.tolist()
        m_start = min(sub_dates)
        m_end = max(sub_dates)
        eq_sub = daily_equity.loc[m_start:m_end] if m_start in daily_equity.index and m_end in daily_equity.index else pd.Series()
        if len(eq_sub) > 0:
            m_peak = eq_sub.cummax()
            m_dd = float(((eq_sub - m_peak) / m_peak).min() * 100.0)
        else:
            m_dd = 0.0

        ret_pct = (net_pnl / initial_capital) * 100.0

        monthly_records.append({
            "year_month": ym,
            "trades": n_trades,
            "wins": n_wins,
            "losses": n_losses,
            "gross_profit": round(gp, 2),
            "gross_loss": round(gl, 2),
            "costs": round(costs, 2),
            "net_pnl": round(net_pnl, 2),
            "return_pct": round(ret_pct, 2),
            "max_drawdown": round(m_dd, 2),
            "profit_factor": round(pf, 2),
        })

    df_monthly = pd.DataFrame(monthly_records)

    # Yearly aggregation
    yearly_records = []
    years = sorted(list(df_trades["year"].unique()))
    for y in years:
        sub_y = df_trades[df_trades["year"] == y]
        n_trades = len(sub_y)
        n_wins = int((sub_y["net_pnl"] > 0).sum())
        win_rate = (n_wins / n_trades * 100.0) if n_trades > 0 else 0.0
        gp = float(sub_y[sub_y["gross_pnl"] > 0]["gross_pnl"].sum())
        costs = float(sub_y["total_costs"].sum())
        net_pnl = float(sub_y["net_pnl"].sum())
        ret_pct = (net_pnl / initial_capital) * 100.0

        pos_net = float(sub_y[sub_y["net_pnl"] > 0]["net_pnl"].sum())
        neg_net = float(abs(sub_y[sub_y["net_pnl"] < 0]["net_pnl"].sum()))
        pf = (pos_net / neg_net) if neg_net > 0 else (99.0 if pos_net > 0 else 0.0)

        # Payoff ratio
        avg_win = float(sub_y[sub_y["net_pnl"] > 0]["net_pnl"].mean()) if n_wins > 0 else 0.0
        avg_loss = float(abs(sub_y[sub_y["net_pnl"] < 0]["net_pnl"].mean())) if (n_trades - n_wins) > 0 else 0.0
        payoff = (avg_win / avg_loss) if avg_loss > 0 else (99.0 if avg_win > 0 else 0.0)

        yearly_records.append({
            "year": y,
            "trades": n_trades,
            "win_rate": round(win_rate, 2),
            "gross_profit": round(gp, 2),
            "costs": round(costs, 2),
            "net_pnl": round(net_pnl, 2),
            "annual_return_pct": round(ret_pct, 2),
            "cagr_pct": round(ret_pct, 2),
            "profit_factor": round(pf, 2),
            "payoff_ratio": round(payoff, 2),
        })

    df_yearly = pd.DataFrame(yearly_records)

    # Summary statistics
    prof_months = int((df_monthly["net_pnl"] > 0).sum())
    loss_months = int((df_monthly["net_pnl"] <= 0).sum())
    prof_months_pct = (prof_months / len(df_monthly) * 100.0) if len(df_monthly) > 0 else 0.0

    prof_years = int((df_yearly["net_pnl"] > 0).sum())
    loss_years = int((df_yearly["net_pnl"] <= 0).sum())

    # Longest consecutive losing months
    max_consec_losing_months = 0
    cur_consec_m = 0
    for pnl in df_monthly["net_pnl"]:
        if pnl <= 0:
            cur_consec_m += 1
            max_consec_losing_months = max(max_consec_losing_months, cur_consec_m)
        else:
            cur_consec_m = 0

    # Longest consecutive losing trades
    max_consec_losing_trades = 0
    cur_consec_t = 0
    for pnl in df_trades["net_pnl"]:
        if pnl <= 0:
            cur_consec_t += 1
            max_consec_losing_trades = max(max_consec_losing_trades, cur_consec_t)
        else:
            cur_consec_t = 0

    # Top 3 trade concentration
    sorted_pnls = sorted(df_trades["net_pnl"].tolist(), reverse=True)
    top_3_sum = sum(sorted_pnls[:3]) if len(sorted_pnls) >= 3 else sum(sorted_pnls)
    tot_net_pnl = float(df_trades["net_pnl"].sum())
    top_3_contrib_pct = (top_3_sum / tot_net_pnl * 100.0) if tot_net_pnl > 0 else 0.0
    ex_top3_pnl = tot_net_pnl - top_3_sum

    stats = {
        "profitable_months": prof_months,
        "losing_months": loss_months,
        "profitable_months_pct": round(prof_months_pct, 2),
        "profitable_years": prof_years,
        "losing_years": loss_years,
        "longest_consec_losing_months": max_consec_losing_months,
        "longest_consec_losing_trades": max_consec_losing_trades,
        "top_3_contribution": round(top_3_contrib_pct, 2),
        "ex_top3_net_pnl": round(ex_top3_pnl, 2),
    }

    return df_monthly, df_yearly, stats


def run_strategy_simulation(
    strategy_id: StrategyID,
    augmented_universe: Dict[str, pd.DataFrame],
    risk_tier: RiskTier = RiskTier.E2,
    use_stress_costs: bool = False,
    config: Optional[StrategyLabConfig] = None,
    candidate_config: Optional[StrategyCandidateConfig] = None,
    nifty_df: Optional[pd.DataFrame] = None,
) -> PortfolioSimulationResult:
    """
    Simulates a single strategy candidate across the entire 2017-2019 dataset.
    """
    if config is None:
        config = StrategyLabConfig()
    if candidate_config is None:
        candidate_config = DEFAULT_STRATEGY_CONFIGS[strategy_id]

    # Trading calendar from first symbol
    symbols = sorted(list(augmented_universe.keys()))
    trading_dates = sorted(list(augmented_universe[symbols[0]].index))
    n_days = len(trading_dates)

    cash = config.initial_capital
    active_positions: Dict[str, ActivePosition] = {}
    completed_trades: List[CompletedTrade] = []
    trade_counter = 0

    equity_records = {}

    pending_signals: List[CandidateSignal] = []

    for day_idx in range(n_days):
        current_dt = trading_dates[day_idx]
        is_final_bar = (day_idx == n_days - 1)

        # -------------------------------------------------------------
        # STEP 1: EXECUTE PENDING SIGNALS FROM PREVIOUS EOD AT TODAY'S OPEN
        # -------------------------------------------------------------
        if pending_signals and not is_final_bar:
            for sig in pending_signals:
                if len(active_positions) >= config.max_concurrent_positions:
                    break
                if sig.symbol in active_positions:
                    continue

                bar = augmented_universe[sig.symbol].loc[current_dt]
                raw_open = float(bar["open"])
                slippage_factor = (config.execution_slippage_bps + config.execution_spread_bps) / 10000.0
                exec_open = raw_open * (1.0 + slippage_factor)

                # Current portfolio equity
                current_equity = cash + sum(
                    p.quantity * float(augmented_universe[p.symbol].loc[current_dt]["open"])
                    for p in active_positions.values()
                )

                # Risk sizing
                risk_budget = current_equity * risk_tier.risk_fraction
                stop_dist = max(0.50, exec_open - sig.stop_loss_price)
                raw_shares = int(risk_budget / stop_dist)
                max_cash_shares = int(cash / exec_open)
                shares = min(raw_shares, max_cash_shares)

                if shares < 1:
                    continue  # Ineffective size or insufficient cash

                cost_required = shares * exec_open
                if cost_required > cash:
                    continue

                trade_counter += 1
                sector = config.symbol_sector_map.get(sig.symbol, "Diversified")
                isin = config.symbol_isin_map.get(sig.symbol, f"INE_{sig.symbol}_CANONICAL")

                active_pos = ActivePosition(
                    trade_id=trade_counter,
                    strategy_id=sig.strategy_id,
                    symbol=sig.symbol,
                    sector=sector,
                    isin=isin,
                    entry_date=to_py_date(current_dt),
                    entry_price=exec_open,
                    quantity=shares,
                    stop_loss_price=sig.stop_loss_price,
                    profit_target_price=sig.profit_target_price,
                    trailing_exit_level=sig.trailing_exit_level,
                    max_hold_bars=sig.max_hold_bars,
                    bars_held=0,
                    metadata={"raw_entry_open": raw_open, **sig.metadata},
                )
                active_positions[sig.symbol] = active_pos
                cash -= cost_required

            pending_signals = []

        # -------------------------------------------------------------
        # STEP 2: EVALUATE EXITS ON CURRENT BAR FOR ACTIVE POSITIONS
        # -------------------------------------------------------------
        symbols_to_exit: List[Tuple[str, float, ExitReason, str]] = []
        for sym, pos in list(active_positions.items()):
            pos.bars_held += 1
            bar = augmented_universe[sym].loc[current_dt]

            exit_eval = evaluate_candidate_exit(
                strategy_id=pos.strategy_id,
                bar=bar,
                entry_price=pos.entry_price,
                stop_loss_price=pos.stop_loss_price,
                bars_held=pos.bars_held,
                max_hold_bars=pos.max_hold_bars,
                is_final_bar=is_final_bar,
                profit_target_price=pos.profit_target_price,
                trailing_exit_level=pos.trailing_exit_level,
                cfg=candidate_config,
            )

            if exit_eval is not None:
                raw_exit_px, exit_reason, exit_notes = exit_eval
                symbols_to_exit.append((sym, raw_exit_px, exit_reason, exit_notes))

        # Process exits
        for sym, raw_exit_px, exit_reason, exit_notes in symbols_to_exit:
            pos = active_positions.pop(sym)
            friction_factor = (config.execution_slippage_bps + config.execution_spread_bps) / 10000.0
            effective_exit_px = raw_exit_px * (1.0 - friction_factor)

            e_date = to_py_date(pos.entry_date)
            x_date = to_py_date(current_dt)

            # Certified delivery cost calculation
            cost_bd, cost_sum = calculate_dtp_roundtrip_costs(
                symbol=pos.symbol,
                isin=pos.isin,
                entry_date=e_date,
                exit_date=x_date,
                entry_price=pos.entry_price,
                exit_price=effective_exit_px,
                quantity=pos.quantity,
                use_stress_profile=use_stress_costs,
            )

            cash += (pos.quantity * effective_exit_px) - (cost_sum.total_friction_costs - cost_sum.total_execution_friction)

            entry_raw = pos.metadata.get("raw_entry_open", pos.entry_price)
            comp_trade = CompletedTrade(
                trade_id=pos.trade_id,
                strategy_id=pos.strategy_id.value,
                symbol=pos.symbol,
                sector=pos.sector,
                entry_date=e_date,
                exit_date=x_date,
                bars_held=pos.bars_held,
                quantity=pos.quantity,
                raw_entry_price=round(entry_raw, 2),
                raw_exit_price=round(raw_exit_px, 2),
                effective_entry_price=round(pos.entry_price, 2),
                effective_exit_price=round(effective_exit_px, 2),
                buy_turnover=round(cost_sum.buy_turnover, 2),
                sell_turnover=round(cost_sum.sell_turnover, 2),
                total_turnover=round(cost_sum.total_turnover, 2),
                gross_pnl=round(cost_sum.gross_pnl, 2),
                brokerage=round(cost_sum.total_brokerage, 2),
                stt=round(cost_sum.total_stt, 2),
                exchange_turnover=round(cost_sum.exchange_charge, 2),
                stamp_duty=round(cost_sum.total_stamp_duty, 2),
                gst=round(cost_sum.total_gst, 2),
                sebi_charges=round(cost_sum.sebi_turnover_fee, 2),
                dp_charges=round(cost_sum.total_dp_charge, 2),
                slippage=round(cost_sum.total_execution_friction, 2),
                total_costs=round(cost_sum.total_friction_costs, 2),
                net_pnl=round(cost_sum.net_pnl, 2),
                net_return_pct=round(cost_sum.net_return_pct, 2),
                exit_reason=exit_reason.value,
                exit_notes=exit_notes,
            )
            completed_trades.append(comp_trade)

        # -------------------------------------------------------------
        # STEP 3: EOD EQUITY SNAPSHOT & SIGNAL GENERATION
        # -------------------------------------------------------------
        eod_equity = cash + sum(
            p.quantity * float(augmented_universe[p.symbol].loc[current_dt]["close"])
            for p in active_positions.values()
        )
        equity_records[current_dt] = eod_equity

        if day_idx < n_days - 1:
            next_dt = trading_dates[day_idx + 1]
            new_sigs = generate_candidate_signals(
                strategy_id=strategy_id,
                augmented_universe=augmented_universe,
                day_idx=day_idx,
                current_dt=current_dt,
                next_dt=next_dt,
                nifty_df=nifty_df,
                cfg=candidate_config,
            )
            pending_signals = new_sigs

    daily_eq_series = pd.Series(equity_records)
    final_eq = float(daily_eq_series.iloc[-1])
    tot_net_pnl = round(final_eq - config.initial_capital, 2)
    tot_gross = round(sum(t.gross_pnl for t in completed_trades), 2)
    tot_costs = round(sum(t.total_costs for t in completed_trades), 2)
    roi_pct = round((tot_net_pnl / config.initial_capital) * 100.0, 2)

    # 3-year CAGR
    years_elapsed = 3.0
    cagr_pct = round(((final_eq / config.initial_capital) ** (1.0 / years_elapsed) - 1.0) * 100.0, 2)

    # Drawdown
    peak_eq = daily_eq_series.cummax()
    dd_series = (daily_eq_series - peak_eq) / peak_eq * 100.0
    max_dd_pct = round(abs(float(dd_series.min())), 2)
    max_dd_inr = round(float((peak_eq - daily_eq_series).max()), 2)

    n_trades = len(completed_trades)
    wins = sum(1 for t in completed_trades if t.net_pnl > 0)
    losses = sum(1 for t in completed_trades if t.net_pnl <= 0)
    win_rate = round((wins / n_trades * 100.0), 2) if n_trades > 0 else 0.0

    pos_pnl = sum(t.net_pnl for t in completed_trades if t.net_pnl > 0)
    neg_pnl = abs(sum(t.net_pnl for t in completed_trades if t.net_pnl < 0))
    pf = round(pos_pnl / neg_pnl, 2) if neg_pnl > 0 else (99.0 if pos_pnl > 0 else 0.0)

    avg_win = (pos_pnl / wins) if wins > 0 else 0.0
    avg_loss = (neg_pnl / losses) if losses > 0 else 0.0
    payoff = round(avg_win / avg_loss, 2) if avg_loss > 0 else (99.0 if avg_win > 0 else 0.0)

    # Granular monthly & yearly
    df_monthly, df_yearly, stats = calculate_performance_tables(
        completed_trades, daily_eq_series, config.initial_capital
    )

    cost_str = "Stress (₹317/cr)" if use_stress_costs else "Official (₹307/cr)"
    return PortfolioSimulationResult(
        strategy_id=strategy_id.value,
        risk_tier=risk_tier.value,
        cost_schedule=cost_str,
        initial_capital=config.initial_capital,
        final_equity=final_eq,
        total_net_pnl=tot_net_pnl,
        total_gross_pnl=tot_gross,
        total_costs=tot_costs,
        roi_pct=roi_pct,
        cagr_pct=cagr_pct,
        completed_trades=n_trades,
        wins=wins,
        losses=losses,
        win_rate=win_rate,
        profit_factor=pf,
        payoff_ratio=payoff,
        max_drawdown_pct=max_dd_pct,
        max_drawdown_inr=max_dd_inr,
        trades=completed_trades,
        daily_equity=daily_eq_series,
        monthly_profitability=df_monthly,
        yearly_profitability=df_yearly,
        top_3_trades_contribution=stats["top_3_contribution"],
        ex_top_3_net_pnl=stats["ex_top3_net_pnl"],
        profitable_months=stats["profitable_months"],
        losing_months=stats["losing_months"],
        profitable_months_pct=stats["profitable_months_pct"],
        profitable_years=stats["profitable_years"],
        losing_years=stats["losing_years"],
        longest_consecutive_losses=stats["longest_consec_losing_trades"],
        longest_consecutive_losing_months=stats["longest_consec_losing_months"],
    )


def run_combined_portfolio_simulation(
    selected_strategies: List[StrategyID],
    augmented_universe: Dict[str, pd.DataFrame],
    risk_tier: RiskTier = RiskTier.E2,
    use_stress_costs: bool = False,
    config: Optional[StrategyLabConfig] = None,
    candidate_configs: Optional[Dict[StrategyID, StrategyCandidateConfig]] = None,
    nifty_df: Optional[pd.DataFrame] = None,
) -> PortfolioSimulationResult:
    """
    Simulates a combined portfolio of up to 3 selected strategies competing for the same
    2 concurrent position slots with unified capital management.
    """
    if config is None:
        config = StrategyLabConfig()
    if candidate_configs is None:
        candidate_configs = DEFAULT_STRATEGY_CONFIGS

    symbols = sorted(list(augmented_universe.keys()))
    trading_dates = sorted(list(augmented_universe[symbols[0]].index))
    n_days = len(trading_dates)

    cash = config.initial_capital
    active_positions: Dict[str, ActivePosition] = {}
    completed_trades: List[CompletedTrade] = []
    trade_counter = 0

    equity_records = {}
    pending_signals: List[CandidateSignal] = []

    for day_idx in range(n_days):
        current_dt = trading_dates[day_idx]
        is_final_bar = (day_idx == n_days - 1)

        # Execute signals at Open
        if pending_signals and not is_final_bar:
            for sig in pending_signals:
                if len(active_positions) >= config.max_concurrent_positions:
                    break
                if sig.symbol in active_positions:
                    continue

                bar = augmented_universe[sig.symbol].loc[current_dt]
                raw_open = float(bar["open"])
                slippage_factor = (config.execution_slippage_bps + config.execution_spread_bps) / 10000.0
                exec_open = raw_open * (1.0 + slippage_factor)

                current_equity = cash + sum(
                    p.quantity * float(augmented_universe[p.symbol].loc[current_dt]["open"])
                    for p in active_positions.values()
                )

                risk_budget = current_equity * risk_tier.risk_fraction
                stop_dist = max(0.50, exec_open - sig.stop_loss_price)
                raw_shares = int(risk_budget / stop_dist)
                max_cash_shares = int(cash / exec_open)
                shares = min(raw_shares, max_cash_shares)

                if shares < 1:
                    continue

                cost_required = shares * exec_open
                if cost_required > cash:
                    continue

                trade_counter += 1
                sector = config.symbol_sector_map.get(sig.symbol, "Diversified")
                isin = config.symbol_isin_map.get(sig.symbol, f"INE_{sig.symbol}_CANONICAL")

                active_pos = ActivePosition(
                    trade_id=trade_counter,
                    strategy_id=sig.strategy_id,
                    symbol=sig.symbol,
                    sector=sector,
                    isin=isin,
                    entry_date=to_py_date(current_dt),
                    entry_price=exec_open,
                    quantity=shares,
                    stop_loss_price=sig.stop_loss_price,
                    profit_target_price=sig.profit_target_price,
                    trailing_exit_level=sig.trailing_exit_level,
                    max_hold_bars=sig.max_hold_bars,
                    bars_held=0,
                    metadata={"raw_entry_open": raw_open, **sig.metadata},
                )
                active_positions[sig.symbol] = active_pos
                cash -= cost_required

            pending_signals = []

        # Evaluate exits
        symbols_to_exit = []
        for sym, pos in list(active_positions.items()):
            pos.bars_held += 1
            bar = augmented_universe[sym].loc[current_dt]
            cfg = candidate_configs[pos.strategy_id]

            exit_eval = evaluate_candidate_exit(
                strategy_id=pos.strategy_id,
                bar=bar,
                entry_price=pos.entry_price,
                stop_loss_price=pos.stop_loss_price,
                bars_held=pos.bars_held,
                max_hold_bars=pos.max_hold_bars,
                is_final_bar=is_final_bar,
                profit_target_price=pos.profit_target_price,
                trailing_exit_level=pos.trailing_exit_level,
                cfg=cfg,
            )

            if exit_eval is not None:
                raw_exit_px, exit_reason, exit_notes = exit_eval
                symbols_to_exit.append((sym, raw_exit_px, exit_reason, exit_notes))

        for sym, raw_exit_px, exit_reason, exit_notes in symbols_to_exit:
            pos = active_positions.pop(sym)
            friction_factor = (config.execution_slippage_bps + config.execution_spread_bps) / 10000.0
            effective_exit_px = raw_exit_px * (1.0 - friction_factor)

            e_date = to_py_date(pos.entry_date)
            x_date = to_py_date(current_dt)

            cost_bd, cost_sum = calculate_dtp_roundtrip_costs(
                symbol=pos.symbol,
                isin=pos.isin,
                entry_date=e_date,
                exit_date=x_date,
                entry_price=pos.entry_price,
                exit_price=effective_exit_px,
                quantity=pos.quantity,
                use_stress_profile=use_stress_costs,
            )

            cash += (pos.quantity * effective_exit_px) - (cost_sum.total_friction_costs - cost_sum.total_execution_friction)
            entry_raw = pos.metadata.get("raw_entry_open", pos.entry_price)

            completed_trades.append(
                CompletedTrade(
                    trade_id=pos.trade_id,
                    strategy_id=pos.strategy_id.value,
                    symbol=pos.symbol,
                    sector=pos.sector,
                    entry_date=e_date,
                    exit_date=x_date,
                    bars_held=pos.bars_held,
                    quantity=pos.quantity,
                    raw_entry_price=round(entry_raw, 2),
                    raw_exit_price=round(raw_exit_px, 2),
                    effective_entry_price=round(pos.entry_price, 2),
                    effective_exit_price=round(effective_exit_px, 2),
                    buy_turnover=round(cost_sum.buy_turnover, 2),
                    sell_turnover=round(cost_sum.sell_turnover, 2),
                    total_turnover=round(cost_sum.total_turnover, 2),
                    gross_pnl=round(cost_sum.gross_pnl, 2),
                    brokerage=round(cost_sum.total_brokerage, 2),
                    stt=round(cost_sum.total_stt, 2),
                    exchange_turnover=round(cost_sum.exchange_charge, 2),
                    stamp_duty=round(cost_sum.total_stamp_duty, 2),
                    gst=round(cost_sum.total_gst, 2),
                    sebi_charges=round(cost_sum.sebi_turnover_fee, 2),
                    dp_charges=round(cost_sum.total_dp_charge, 2),
                    slippage=round(cost_sum.total_execution_friction, 2),
                    total_costs=round(cost_sum.total_friction_costs, 2),
                    net_pnl=round(cost_sum.net_pnl, 2),
                    net_return_pct=round(cost_sum.net_return_pct, 2),
                    exit_reason=exit_reason.value,
                    exit_notes=exit_notes,
                )
            )

        eod_equity = cash + sum(
            p.quantity * float(augmented_universe[p.symbol].loc[current_dt]["close"])
            for p in active_positions.values()
        )
        equity_records[current_dt] = eod_equity

        if day_idx < n_days - 1:
            next_dt = trading_dates[day_idx + 1]
            all_sigs = []
            for st_id in selected_strategies:
                cfg = candidate_configs[st_id]
                st_sigs = generate_candidate_signals(
                    strategy_id=st_id,
                    augmented_universe=augmented_universe,
                    day_idx=day_idx,
                    current_dt=current_dt,
                    next_dt=next_dt,
                    nifty_df=nifty_df,
                    cfg=cfg,
                )
                all_sigs.extend(st_sigs)

            # Prioritize signals
            all_sigs.sort(key=lambda s: s.priority_score, reverse=True)
            pending_signals = all_sigs

    daily_eq_series = pd.Series(equity_records)
    final_eq = float(daily_eq_series.iloc[-1])
    tot_net_pnl = round(final_eq - config.initial_capital, 2)
    tot_gross = round(sum(t.gross_pnl for t in completed_trades), 2)
    tot_costs = round(sum(t.total_costs for t in completed_trades), 2)
    roi_pct = round((tot_net_pnl / config.initial_capital) * 100.0, 2)
    cagr_pct = round(((final_eq / config.initial_capital) ** (1.0 / 3.0) - 1.0) * 100.0, 2)

    peak_eq = daily_eq_series.cummax()
    dd_series = (daily_eq_series - peak_eq) / peak_eq * 100.0
    max_dd_pct = round(abs(float(dd_series.min())), 2)
    max_dd_inr = round(float((peak_eq - daily_eq_series).max()), 2)

    n_trades = len(completed_trades)
    wins = sum(1 for t in completed_trades if t.net_pnl > 0)
    losses = sum(1 for t in completed_trades if t.net_pnl <= 0)
    win_rate = round((wins / n_trades * 100.0), 2) if n_trades > 0 else 0.0

    pos_pnl = sum(t.net_pnl for t in completed_trades if t.net_pnl > 0)
    neg_pnl = abs(sum(t.net_pnl for t in completed_trades if t.net_pnl < 0))
    pf = round(pos_pnl / neg_pnl, 2) if neg_pnl > 0 else (99.0 if pos_pnl > 0 else 0.0)

    avg_win = (pos_pnl / wins) if wins > 0 else 0.0
    avg_loss = (neg_pnl / losses) if losses > 0 else 0.0
    payoff = round(avg_win / avg_loss, 2) if avg_loss > 0 else (99.0 if avg_win > 0 else 0.0)

    df_monthly, df_yearly, stats = calculate_performance_tables(
        completed_trades, daily_eq_series, config.initial_capital
    )

    combined_name = "Combined Portfolio: " + " + ".join([s.value.split("—")[0].strip() for s in selected_strategies])
    cost_str = "Stress (₹317/cr)" if use_stress_costs else "Official (₹307/cr)"

    return PortfolioSimulationResult(
        strategy_id=combined_name,
        risk_tier=risk_tier.value,
        cost_schedule=cost_str,
        initial_capital=config.initial_capital,
        final_equity=final_eq,
        total_net_pnl=tot_net_pnl,
        total_gross_pnl=tot_gross,
        total_costs=tot_costs,
        roi_pct=roi_pct,
        cagr_pct=cagr_pct,
        completed_trades=n_trades,
        wins=wins,
        losses=losses,
        win_rate=win_rate,
        profit_factor=pf,
        payoff_ratio=payoff,
        max_drawdown_pct=max_dd_pct,
        max_drawdown_inr=max_dd_inr,
        trades=completed_trades,
        daily_equity=daily_eq_series,
        monthly_profitability=df_monthly,
        yearly_profitability=df_yearly,
        top_3_trades_contribution=stats["top_3_contribution"],
        ex_top_3_net_pnl=stats["ex_top3_net_pnl"],
        profitable_months=stats["profitable_months"],
        losing_months=stats["losing_months"],
        profitable_months_pct=stats["profitable_months_pct"],
        profitable_years=stats["profitable_years"],
        losing_years=stats["losing_years"],
        longest_consecutive_losses=stats["longest_consec_losing_trades"],
        longest_consecutive_losing_months=stats["longest_consec_losing_months"],
    )
