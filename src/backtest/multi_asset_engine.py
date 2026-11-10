"""
SignalForge — Multi-Asset Synchronized Intraday Execution Engine.
================================================================
Processes multiple stocks during the same trading session while maintaining:
1. Independent positions per stock.
2. One shared portfolio accounting ledger (PortfolioManager).
3. One shared capital allocation controller (CapitalAllocator).
4. One aggregate portfolio risk budget.
5. One portfolio-wide capital protection floor mechanism.
6. Deterministic timestamp-synchronized execution ordering.
7. Explicit missing-candle handling and stale-price protection.
8. Accurate canonical transaction-cost accounting (Phase 27B).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd

from src.backtest.capital_allocator import (
    AllocationDecision,
    CapitalAllocationConfig,
    CapitalAllocator,
    TradeOpportunity,
)
from src.backtest.engine import IST_TIMEZONE, is_in_opening_cooldown
from src.backtest.indian_market_costs import (
    DISCOUNT_BROKER_REALISTIC_CONFIG,
    IntradayCostConfig,
    calculate_trade_transaction_costs,
    get_cost_config,
)
from src.backtest.metrics import PerformanceMetrics, calculate_metrics
from src.backtest.portfolio import OpenPosition, PortfolioManager
from src.backtest.simulator import Position, Trade, simulate_trade


@dataclass
class MultiAssetEngineConfig:
    """
    Configuration for multi-asset synchronized intraday backtesting.

    Parameters
    ----------
    initial_capital:
        Starting account equity in rupees (default 100,000.0).
    risk_per_trade_pct:
        Risk percentage per trade (default 1.0% = 0.01).
    max_stock_allocation_pct:
        Max fraction of equity encumbered as margin collateral per stock (default 35.0% = 0.35).
    max_portfolio_risk_pct:
        Maximum aggregate open portfolio risk percentage (default 3.0% = 0.03).
    reserve_capital_pct:
        Percentage of equity reserved as liquidity buffer (default 15.0% = 0.15).
    max_leverage:
        SignalForge internal simulation software ceiling (default 5.0x).
    stop_loss_atr:
        ATR multiplier for stop-loss distance (default 1.5x).
    take_profit_atr:
        ATR multiplier for take-profit distance (default 3.0x).
    session_end_time:
        Intraday square-off cutoff time formatted as 'HH:MM' (default '15:15').
    enforce_eod_square_off:
        Whether to enforce end-of-day square-off (default True, zero overnight exposure).
    execution_model:
        Execution contract: 'next_open' (default) or 'same_close'.
    gap_execution:
        Whether adverse gap openings through stop/target fill at bar open (default True).
    conservative_same_candle:
        Deterministic collision policy: STOP evaluated before TARGET on same-candle hits (default True).
    capital_protection_floor:
        Absolute equity floor in rupees below which all trading halts.
    overall_loss_limit:
        Maximum permitted loss from initial capital in rupees.
    cost_config:
        Canonical Phase 27B IntradayCostConfig schedule.
    include_estimated_round_trip_costs_in_sizing:
        Whether to account for estimated round-trip transaction costs in position sizing (default True).
    min_trade_quantity:
        Minimum allowable trade quantity (default 1).
    min_free_capital:
        Minimum unencumbered cash required in portfolio (default 0.0).
    brokerage_per_trade:
        Fixed brokerage per leg for legacy compatibility (default 0.0).
    slippage_rate:
        Proportional slippage rate for legacy compatibility (default 0.0).
    statutory_fee_rate:
        Statutory fee rate for legacy compatibility (default 0.0).
    transaction_cost_rate:
        Linear transaction cost rate for legacy compatibility (default 0.0).
    """

    initial_capital: float = 100_000.0
    risk_per_trade_pct: float = 0.01
    max_stock_allocation_pct: float = 0.35
    max_portfolio_risk_pct: float = 0.03
    reserve_capital_pct: float = 0.15
    max_leverage: float = 5.0
    stop_loss_atr: float = 1.5
    take_profit_atr: float = 3.0
    session_end_time: str = "15:15"
    enforce_eod_square_off: bool = True
    execution_model: str = "next_open"
    gap_execution: bool = True
    conservative_same_candle: bool = True
    capital_protection_floor: Optional[float] = None
    overall_loss_limit: Optional[float] = None
    cost_config: Optional[IntradayCostConfig] = None
    include_estimated_round_trip_costs_in_sizing: bool = True
    min_trade_quantity: int = 1
    min_free_capital: float = 0.0
    brokerage_per_trade: float = 0.0
    slippage_rate: float = 0.0
    statutory_fee_rate: float = 0.0
    transaction_cost_rate: float = 0.0
    opening_cooldown_minutes: int = 10
    market_open_time: str = "09:15"

    def __post_init__(self) -> None:
        if not isinstance(self.initial_capital, (int, float)) or isinstance(self.initial_capital, bool):
            raise TypeError("initial_capital must be numeric.")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be greater than zero.")

        if self.execution_model not in ("same_close", "next_open"):
            raise ValueError(
                f"Unsupported execution_model: '{self.execution_model}'. Supported: 'same_close', 'next_open'."
            )

        if not isinstance(self.risk_per_trade_pct, (int, float)) or isinstance(self.risk_per_trade_pct, bool):
            raise TypeError("risk_per_trade_pct must be numeric.")
        if not (0.0 < self.risk_per_trade_pct <= 1.0):
            raise ValueError("risk_per_trade_pct must be between 0.0 and 1.0.")

        if not isinstance(self.max_stock_allocation_pct, (int, float)) or isinstance(self.max_stock_allocation_pct, bool):
            raise TypeError("max_stock_allocation_pct must be numeric.")
        if not (0.0 < self.max_stock_allocation_pct <= 1.0):
            raise ValueError("max_stock_allocation_pct must be between 0.0 and 1.0.")

        if not isinstance(self.max_portfolio_risk_pct, (int, float)) or isinstance(self.max_portfolio_risk_pct, bool):
            raise TypeError("max_portfolio_risk_pct must be numeric.")
        if not (0.0 < self.max_portfolio_risk_pct <= 1.0):
            raise ValueError("max_portfolio_risk_pct must be between 0.0 and 1.0.")

        if self.max_portfolio_risk_pct < self.risk_per_trade_pct:
            raise ValueError("max_portfolio_risk_pct cannot be less than risk_per_trade_pct.")

        if self.stop_loss_atr <= 0:
            raise ValueError("stop_loss_atr must be greater than zero.")
        if self.take_profit_atr <= 0:
            raise ValueError("take_profit_atr must be greater than zero.")

        if not isinstance(self.opening_cooldown_minutes, int) or isinstance(self.opening_cooldown_minutes, bool):
            raise TypeError("opening_cooldown_minutes must be an integer.")
        if self.opening_cooldown_minutes < 0:
            raise ValueError("opening_cooldown_minutes cannot be negative.")

        try:
            open_t = pd.Timestamp(self.market_open_time).time()
            session_end_t = pd.Timestamp(self.session_end_time).time()
        except Exception as e:
            raise ValueError(f"Invalid time format in market_open_time or session_end_time: {e}")

        if open_t >= session_end_t:
            raise ValueError("market_open_time must be earlier than session_end_time.")

        cooldown_end_dt = datetime.combine(datetime.today().date(), open_t) + pd.Timedelta(minutes=self.opening_cooldown_minutes)
        if cooldown_end_dt.time() > session_end_t:
            raise ValueError("opening_cooldown_minutes cannot extend past session_end_time.")

        if self.cost_config is None:
            self.cost_config = DISCOUNT_BROKER_REALISTIC_CONFIG

    def is_in_opening_cooldown(self, current_time: Union[pd.Timestamp, datetime]) -> bool:
        """Check if timestamp falls strictly within the opening market cooldown period."""
        return is_in_opening_cooldown(
            current_time,
            self.opening_cooldown_minutes,
            self.market_open_time,
        )

    @property
    def effective_protection_floor(self) -> Optional[float]:
        """Calculate effective rupee protection floor."""
        if self.capital_protection_floor is not None:
            return float(self.capital_protection_floor)
        if self.overall_loss_limit is not None:
            return max(0.0, float(self.initial_capital) - float(self.overall_loss_limit))
        return None

    def to_capital_allocation_config(self) -> CapitalAllocationConfig:
        """Generate a corresponding CapitalAllocationConfig instance."""
        return CapitalAllocationConfig(
            risk_per_trade_pct=self.risk_per_trade_pct,
            max_stock_allocation_pct=self.max_stock_allocation_pct,
            max_portfolio_risk_pct=self.max_portfolio_risk_pct,
            reserve_capital_pct=self.reserve_capital_pct,
            max_leverage=self.max_leverage,
            min_trade_quantity=self.min_trade_quantity,
            min_free_capital=self.min_free_capital,
            include_estimated_round_trip_costs_in_sizing=self.include_estimated_round_trip_costs_in_sizing,
            cost_config=self.cost_config,
        )


@dataclass(frozen=True)
class MultiAssetBacktestResult:
    """Complete result returned by the multi-asset synchronized backtest engine."""

    trades: list[Trade]
    portfolio: PortfolioManager
    metrics: PerformanceMetrics
    symbol_metrics: dict[str, dict[str, Any]]
    equity_curve: pd.DataFrame
    allocations: list[AllocationDecision]
    missing_candle_stats: dict[str, int]
    stale_price_events: int
    stale_notional_exposure: float
    unresolved_positions: list[OpenPosition] = field(default_factory=list)
    unresolved_liquidation_exposure: float = 0.0
    opening_cooldown_minutes: int = 10
    bankruptcy_reason: Optional[str] = None
    cost_model_info: Optional[dict[str, Any]] = None
    indeterminate_valuation_events: int = 0


def _normalize_symbol_dataframe(symbol: str, data: pd.DataFrame) -> pd.DataFrame:
    """
    Validate, clean, and standardize an individual stock candle DataFrame.
    Guarantees standard columns: Open, High, Low, Close, Volume, and ATR.
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError(f"Data for symbol '{symbol}' must be a pandas DataFrame.")
    if data.empty:
        raise ValueError(f"Data for symbol '{symbol}' cannot be empty.")

    df = data.copy()

    # Normalize datetime index
    if not isinstance(df.index, pd.DatetimeIndex):
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date", drop=False)
        elif "date" in df.columns:
            df["Date"] = pd.to_datetime(df["date"])
            df = df.set_index("Date", drop=False)
        else:
            raise TypeError(f"Data for '{symbol}' must have a DatetimeIndex or Date column.")

    if not df.index.is_monotonic_increasing:
        df = df.sort_index()

    if df.index.has_duplicates:
        df = df[~df.index.duplicated(keep="last")]

    # Case-insensitive column map
    col_map = {str(c).lower(): c for c in df.columns}
    for req in ("open", "high", "low", "close"):
        if req not in col_map:
            raise ValueError(f"Symbol '{symbol}' data missing required column: {req}")

    df["Open"] = df[col_map["open"]].astype(float)
    df["High"] = df[col_map["high"]].astype(float)
    df["Low"] = df[col_map["low"]].astype(float)
    df["Close"] = df[col_map["close"]].astype(float)

    if "volume" in col_map:
        df["Volume"] = df[col_map["volume"]].astype(float)
    else:
        df["Volume"] = 100_000.0

    # Ensure ATR column exists using causal Wilder's smoothed ATR(14)
    if "atr" in col_map:
        df["ATR"] = df[col_map["atr"]].astype(float)
    else:
        prev_close = df["Close"].shift(1)
        tr1 = df["High"] - df["Low"]
        tr2 = (df["High"] - prev_close).abs()
        tr3 = (df["Low"] - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["ATR"] = tr.ewm(alpha=1.0 / 14.0, adjust=False, min_periods=14).mean()
        # Backfill any leading NaNs with simple true range or 1.0% of close
        df["ATR"] = df["ATR"].bfill().fillna(df["Close"] * 0.01)

    return df


def _resolve_raw_signal(
    sym: str,
    current_time: pd.Timestamp,
    bar: pd.Series,
    sym_df: pd.DataFrame,
    signals_by_symbol: Optional[dict[str, Any]],
    signal_generator: Optional[Callable],
) -> Union[TradeOpportunity, Position, None]:
    """Extract candidate signal for symbol at timestamp."""
    val: Any = None

    if signals_by_symbol and sym in signals_by_symbol:
        sig_src = signals_by_symbol[sym]
        if isinstance(sig_src, pd.Series):
            if current_time in sig_src.index:
                val = sig_src.loc[current_time]
        elif isinstance(sig_src, (list, np.ndarray)):
            if current_time in sym_df.index:
                pos_idx = sym_df.index.get_loc(current_time)
                if pos_idx < len(sig_src):
                    val = sig_src[pos_idx]
        elif callable(sig_src):
            val = sig_src(sym, current_time, bar)
    elif signal_generator is not None:
        val = signal_generator(sym, current_time, bar)
    elif "signal" in bar.index:
        val = bar["signal"]

    if isinstance(val, TradeOpportunity):
        return val

    pos = _parse_signal_value(val)
    return pos


def _calculate_symbol_metrics(trades: list[Trade], symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Calculate granular performance breakdown by individual symbol."""
    sym_trades: dict[str, list[Trade]] = {s: [] for s in symbols}
    for t in trades:
        sym = getattr(t, "symbol", "UNKNOWN")
        if sym not in sym_trades:
            sym_trades[sym] = []
        sym_trades[sym].append(t)

    metrics_by_sym: dict[str, dict[str, Any]] = {}
    for s, t_list in sym_trades.items():
        count = len(t_list)
        if count == 0:
            metrics_by_sym[s] = {
                "trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "net_pnl": 0.0,
                "gross_pnl": 0.0,
                "total_transaction_costs": 0.0,
                "win_rate_pct": 0.0,
                "profit_factor": 0.0,
            }
            continue

        wins = sum(1 for t in t_list if t.net_pnl > 0)
        losses = sum(1 for t in t_list if t.net_pnl < 0)
        net_pnl = sum(t.net_pnl for t in t_list)
        gross_pnl = sum(t.gross_pnl for t in t_list)
        costs = sum(t.transaction_cost for t in t_list)
        win_rate = (wins / count) * 100.0 if count > 0 else 0.0

        gross_win = sum(t.gross_pnl for t in t_list if t.gross_pnl > 0)
        gross_loss = abs(sum(t.gross_pnl for t in t_list if t.gross_pnl < 0))
        pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)

        metrics_by_sym[s] = {
            "trades": count,
            "winning_trades": wins,
            "losing_trades": losses,
            "net_pnl": round(net_pnl, 2),
            "gross_pnl": round(gross_pnl, 2),
            "total_transaction_costs": round(costs, 2),
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": round(pf, 2) if not math.isinf(pf) else "inf",
        }

    return metrics_by_sym


def run_multi_asset_backtest(
    data_by_symbol: dict[str, pd.DataFrame],
    signals_by_symbol: Optional[dict[str, Any]] = None,
    config: Optional[MultiAssetEngineConfig] = None,
    signal_generator: Optional[Callable] = None,
) -> MultiAssetBacktestResult:
    """
    Run a synchronized multi-asset intraday backtest across multiple stocks.

    Deterministic Processing Sequence at Each Timestamp:
    ----------------------------------------------------
    1. Load valid market events for timestamp t across all symbols.
    2. Identify missing candles; update valid prices for active positions.
    3. Recalculate portfolio MTM equity and drawdown.
    4. Evaluate exits for active open positions (session cutoff, stop-loss, take-profit).
       Exits release margin and update realized cash immediately.
    5. Check portfolio bankruptcy and capital protection floor breach.
    6. Identify candidate entry signals for timestamp t (or execute pending next-open signals).
    7. Rank candidate opportunities deterministically (quality desc, R:R desc, rvol desc, symbol asc).
    8. Allocate capital and size entries using CapitalAllocator with cost awareness.
    9. Execute accepted entries: reserve margin collateral, register open position in PortfolioManager.
    10. Record portfolio snapshot / equity curve at timestamp t.

    Parameters
    ----------
    data_by_symbol:
        Dictionary mapping stock symbol to its 1-minute OHLCV DataFrame.
    signals_by_symbol:
        Optional dictionary mapping symbol to a list/Series of signals (Position.LONG, Position.SHORT, None).
    config:
        MultiAssetEngineConfig containing risk, capital, leverage, and execution settings.
    signal_generator:
        Optional callable generator f(symbol, timestamp, row, history) returning Position/TradeOpportunity.

    Returns
    -------
    MultiAssetBacktestResult
    """
    if config is None:
        config = MultiAssetEngineConfig()

    if not isinstance(data_by_symbol, dict) or not data_by_symbol:
        raise ValueError("data_by_symbol must be a non-empty dictionary of DataFrames.")

    # 1. Normalize and validate each symbol's data
    normalized_data: dict[str, pd.DataFrame] = {}
    symbols = sorted([str(s).strip().upper() for s in data_by_symbol.keys()])

    for sym in symbols:
        df_raw = data_by_symbol.get(sym)
        if df_raw is None:
            # Check case-insensitive
            for k, v in data_by_symbol.items():
                if str(k).strip().upper() == sym:
                    df_raw = v
                    break
        normalized_data[sym] = _normalize_symbol_dataframe(sym, df_raw)

    # 2. Build global synchronized chronological timeline
    all_timestamps_set: Set[pd.Timestamp] = set()
    for df in normalized_data.values():
        all_timestamps_set.update(df.index)

    timeline = sorted(list(all_timestamps_set))
    if not timeline:
        raise ValueError("No valid timestamps found across supplied symbol data.")

    # 3. Initialize Shared PortfolioManager and CapitalAllocator
    portfolio = PortfolioManager(
        initial_capital=config.initial_capital,
        max_leverage=config.max_leverage,
        reserve_capital_pct=config.reserve_capital_pct,
        capital_protection_floor=config.capital_protection_floor,
        overall_loss_limit=config.overall_loss_limit,
        max_stock_allocation_pct=config.max_stock_allocation_pct,
    )

    allocator_config = config.to_capital_allocation_config()
    allocator = CapitalAllocator(allocator_config)

    # Tracking containers
    all_allocations: list[AllocationDecision] = []
    missing_candle_stats: dict[str, int] = {s: 0 for s in symbols}
    stale_price_events: int = 0
    stale_notional_exposure: float = 0.0
    indeterminate_events: int = 0
    equity_snapshots: list[dict[str, Any]] = []

    # Pending signals for next_open execution model
    # Key: symbol, Value: TradeOpportunity produced at previous bar close
    pending_next_open_signals: dict[str, TradeOpportunity] = {}

    session_end_t = pd.Timestamp(config.session_end_time).time()
    prev_date: Optional[object] = None
    prev_timestamp: Optional[pd.Timestamp] = None

    # Pre-extract row indexers for rapid timestamp access
    symbol_index_map: dict[str, set] = {s: set(df.index) for s, df in normalized_data.items()}

    # ------------------------------------------------------------------------
    # SYNCHRONIZED TIMELINE LOOP
    # ------------------------------------------------------------------------
    for t_idx, current_time in enumerate(timeline):
        current_date = current_time.date()

        # --------------------------------------------------------------------
        # 1. SESSION BOUNDARY ENFORCEMENT (Date Rollover)
        # --------------------------------------------------------------------
        if prev_date is not None and current_date != prev_date:
            if portfolio.open_position_count > 0:
                # Force close remaining positions at previous candle's close
                portfolio.close_all_positions(
                    exit_time=prev_timestamp,
                    exit_reason="EOD",
                    cost_config=config.cost_config,
                    brokerage=config.brokerage_per_trade,
                    slippage_rate=config.slippage_rate,
                    statutory_fee_rate=config.statutory_fee_rate,
                    transaction_cost_rate=config.transaction_cost_rate,
                )
            pending_next_open_signals.clear()

        prev_date = current_date
        prev_timestamp = current_time

        # --------------------------------------------------------------------
        # 2. LOAD ACTIVE MARKET EVENTS & DETECT MISSING CANDLES
        # --------------------------------------------------------------------
        active_bars: dict[str, pd.Series] = {}
        missing_syms_with_positions: list[str] = []
        for sym in symbols:
            if current_time in symbol_index_map[sym]:
                active_bars[sym] = normalized_data[sym].loc[current_time]
            else:
                missing_candle_stats[sym] += 1
                # Check if position open in missing symbol (stale mark)
                if sym in portfolio.open_positions:
                    stale_price_events += 1
                    pos = portfolio.open_positions[sym]
                    stale_notional_exposure += pos.notional_value
                    missing_syms_with_positions.append(sym)

        if missing_syms_with_positions:
            indeterminate_events += 1
            cannot_form_mark = any(
                portfolio.open_positions[s].current_price is None or portfolio.open_positions[s].current_price <= 0
                for s in missing_syms_with_positions
            )
            if cannot_form_mark:
                portfolio.has_indeterminate_valuation = True
                portfolio.indeterminate_valuation_reason = (
                    f"Current mark cannot be formed from authentic data for: {', '.join(sorted(missing_syms_with_positions))} at {current_time}"
                )
            else:
                portfolio.has_indeterminate_valuation = False
                portfolio.indeterminate_valuation_reason = None
        elif not portfolio.has_unresolved_liquidations:
            portfolio.has_indeterminate_valuation = False
            portfolio.indeterminate_valuation_reason = None

        # --------------------------------------------------------------------
        # 3. PROCESS PENDING LIQUIDATIONS (Authentic executable bar arrival)
        # --------------------------------------------------------------------
        if portfolio.has_unresolved_liquidations:
            for pos in list(portfolio.unresolved_liquidation_positions):
                sym = pos.symbol
                if sym in active_bars:
                    # Valid market data arrived! Execute liquidation without synthetic fabrication
                    bar_exec_p = (
                        float(active_bars[sym]["Open"])
                        if config.execution_model == "next_open"
                        else float(active_bars[sym]["Close"])
                    )
                    pos.pending_liquidation = False
                    portfolio.close_position(
                        symbol=sym,
                        exit_time=current_time,
                        exit_price=bar_exec_p,
                        exit_reason=pos.pending_liquidation_reason or "EMERGENCY_LIQUIDATION",
                        cost_config=config.cost_config,
                        brokerage=config.brokerage_per_trade,
                        slippage_rate=config.slippage_rate,
                        statutory_fee_rate=config.statutory_fee_rate,
                        transaction_cost_rate=config.transaction_cost_rate,
                    )

        # --------------------------------------------------------------------
        # 4. EXECUTION LIFECYCLE BY MODEL
        # --------------------------------------------------------------------
        if config.execution_model == "next_open":
            # ================================================================
            # MODEL: NEXT_OPEN (Causal execution at bar Open)
            # ================================================================

            # 4A. Evaluate Opening-Gap Protection at t Open (Priority 1)
            eff_floor = portfolio.effective_protection_floor
            if eff_floor is not None and portfolio.open_positions:
                open_unrealized = 0.0
                for sym, pos in portfolio.open_positions.items():
                    # Include every open position, including pending_liquidation, using authentic mark
                    p_mark = float(active_bars[sym]["Open"]) if sym in active_bars else pos.current_price
                    if pos.side == Position.LONG:
                        open_unrealized += (p_mark - pos.entry_price) * pos.quantity
                    else:
                        open_unrealized += (pos.entry_price - p_mark) * pos.quantity
                open_equity = portfolio.cash + open_unrealized
                if open_equity <= eff_floor or open_equity <= 0:
                    portfolio.is_bankrupt = True
                    if portfolio.bankruptcy_reason is None:
                        portfolio.bankruptcy_reason = "CAPITAL_EXHAUSTED" if open_equity <= 0 else "PROTECTION_FLOOR"

            # Emergency Liquidation at t Open if Opening-Gap breached protection
            if portfolio.is_bankrupt:
                open_syms = sorted(list(portfolio.open_positions.keys()))
                for sym in open_syms:
                    if sym not in portfolio.open_positions:
                        continue
                    if sym in active_bars:
                        portfolio.close_position(
                            symbol=sym,
                            exit_time=current_time,
                            exit_price=float(active_bars[sym]["Open"]),
                            exit_reason=portfolio.bankruptcy_reason or "PROTECTION_FLOOR",
                            cost_config=config.cost_config,
                            brokerage=config.brokerage_per_trade,
                            slippage_rate=config.slippage_rate,
                            statutory_fee_rate=config.statutory_fee_rate,
                            transaction_cost_rate=config.transaction_cost_rate,
                        )
                    else:
                        portfolio.mark_pending_liquidation(sym, portfolio.bankruptcy_reason or "PROTECTION_FLOOR")
                pending_next_open_signals.clear()

            # 4B. Evaluate Opening-Gap Stop/Target Exits at t Open (Priority 2)
            if not portfolio.is_bankrupt:
                open_syms = sorted(list(portfolio.open_positions.keys()))
                for sym in open_syms:
                    if sym not in portfolio.open_positions or sym not in active_bars:
                        continue
                    pos = portfolio.open_positions[sym]
                    if pos.pending_liquidation:
                        continue

                    bar = active_bars[sym]
                    bar_open = float(bar["Open"])
                    gap_exit_price = None
                    gap_exit_reason = None

                    if pos.side == Position.LONG:
                        if config.gap_execution and bar_open <= pos.stop_price:
                            gap_exit_price = bar_open
                            gap_exit_reason = "STOP"
                        elif config.gap_execution and bar_open >= pos.target_price:
                            gap_exit_price = bar_open
                            gap_exit_reason = "TARGET"
                    elif pos.side == Position.SHORT:
                        if config.gap_execution and bar_open >= pos.stop_price:
                            gap_exit_price = bar_open
                            gap_exit_reason = "STOP"
                        elif config.gap_execution and bar_open <= pos.target_price:
                            gap_exit_price = bar_open
                            gap_exit_reason = "TARGET"

                    if gap_exit_price is not None and gap_exit_reason is not None:
                        portfolio.close_position(
                            symbol=sym,
                            exit_time=current_time,
                            exit_price=gap_exit_price,
                            exit_reason=gap_exit_reason,
                            cost_config=config.cost_config,
                            brokerage=config.brokerage_per_trade,
                            slippage_rate=config.slippage_rate,
                            statutory_fee_rate=config.statutory_fee_rate,
                            transaction_cost_rate=config.transaction_cost_rate,
                        )

            # 4C. Execute New Entries at t Open (from pending t-1 signals)
            # Available margin includes margin released by Opening-Gap exits,
            # but strictly EXCLUDES positions that only exit later intrabar.
            is_in_cooldown = config.is_in_opening_cooldown(current_time)
            is_trading_active = (
                not portfolio.is_bankrupt
                and not portfolio.has_unresolved_liquidations
                and not portfolio.has_indeterminate_valuation
                and not (config.enforce_eod_square_off and current_time.time() >= session_end_t)
            )

            if is_in_cooldown:
                # During Opening Cooldown: discard pending signals, block new entries
                pending_next_open_signals.clear()
            elif is_trading_active and pending_next_open_signals:
                candidate_opportunities = []
                for sym, opp in list(pending_next_open_signals.items()):
                    if sym in active_bars and sym not in portfolio.open_positions:
                        bar = active_bars[sym]
                        bar_open = float(bar["Open"])
                        bar_atr = float(opp.atr) if opp.atr > 0 else float(bar["ATR"])

                        stop_dist = bar_atr * config.stop_loss_atr
                        target_dist = bar_atr * config.take_profit_atr

                        if opp.side == Position.LONG:
                            stop_p = bar_open - stop_dist
                            target_p = bar_open + target_dist
                        else:
                            stop_p = bar_open + stop_dist
                            target_p = bar_open - target_dist

                        reanchored_opp = TradeOpportunity(
                            symbol=sym,
                            side=opp.side,
                            entry_price=bar_open,
                            stop_loss=stop_p,
                            target_price=target_p,
                            requested_quantity=opp.requested_quantity,
                            signal_quality=opp.signal_quality,
                            reward_risk_ratio=opp.reward_risk_ratio,
                            relative_volume=opp.relative_volume,
                            is_tradeable=True,
                            timestamp=current_time,
                            atr=bar_atr,
                        )
                        candidate_opportunities.append(reanchored_opp)

                pending_next_open_signals.clear()

                if candidate_opportunities and not portfolio.is_bankrupt:
                    decisions = allocator.allocate_batch(candidate_opportunities, portfolio)
                    all_allocations.extend(decisions)

                    for dec in decisions:
                        if dec.accepted and dec.allocated_quantity > 0:
                            opp_match = next((o for o in candidate_opportunities if o.symbol == dec.symbol), None)
                            if opp_match is not None:
                                portfolio.open_position(
                                    symbol=dec.symbol,
                                    side=opp_match.side,
                                    entry_time=current_time,
                                    entry_price=dec.entry_price,
                                    quantity=dec.allocated_quantity,
                                    stop_price=dec.stop_loss,
                                    target_price=opp_match.target_price,
                                    risk_amount=dec.estimated_risk,
                                    atr=opp_match.atr,
                                    stop_distance=abs(dec.entry_price - dec.stop_loss),
                                    leverage=config.max_leverage,
                                    risk_based_quantity=dec.allocated_quantity,
                                    max_allowed_quantity=dec.allocated_quantity,
                                )

            # 4D. Evaluate Intrabar & Close Exits for Bar t
            # Intrabar exits release margin for FUTURE bars (t+1 Open), NOT retroactively at t Open.

            # Step 4D-1: Intrabar Individual Stop-Loss Exits (Priority 3)
            open_syms = sorted(list(portfolio.open_positions.keys()))
            for sym in open_syms:
                if sym not in portfolio.open_positions or sym not in active_bars:
                    continue
                pos = portfolio.open_positions[sym]
                if pos.pending_liquidation:
                    continue

                bar = active_bars[sym]
                bar_low = float(bar["Low"])
                bar_high = float(bar["High"])

                stop_hit = False
                if pos.side == Position.LONG:
                    if bar_low <= pos.stop_price and bar_high >= pos.target_price and config.conservative_same_candle:
                        stop_hit = True
                    elif bar_low <= pos.stop_price:
                        stop_hit = True
                elif pos.side == Position.SHORT:
                    if bar_high >= pos.stop_price and bar_low <= pos.target_price and config.conservative_same_candle:
                        stop_hit = True
                    elif bar_high >= pos.stop_price:
                        stop_hit = True

                if stop_hit:
                    portfolio.close_position(
                        symbol=sym,
                        exit_time=current_time,
                        exit_price=pos.stop_price,
                        exit_reason="STOP",
                        cost_config=config.cost_config,
                        brokerage=config.brokerage_per_trade,
                        slippage_rate=config.slippage_rate,
                        statutory_fee_rate=config.statutory_fee_rate,
                        transaction_cost_rate=config.transaction_cost_rate,
                    )

            # Step 4D-2: Aggregate Portfolio Protection (Intrabar & Close) (Priority 4)
            eff_floor = portfolio.effective_protection_floor
            if eff_floor is not None and portfolio.open_positions:
                # 1. Adverse intrabar excursion across all remaining open positions (including pending_liquidation)
                adv_unrealized = 0.0
                for s, p in portfolio.open_positions.items():
                    if s in active_bars:
                        p_adv = float(active_bars[s]["Low"]) if p.side == Position.LONG else float(active_bars[s]["High"])
                    else:
                        p_adv = p.current_price
                    if p.side == Position.LONG:
                        adv_unrealized += (p_adv - p.entry_price) * p.quantity
                    else:
                        adv_unrealized += (p.entry_price - p_adv) * p.quantity
                adv_equity = portfolio.cash + adv_unrealized

                # 2. Close equity across all remaining open positions
                close_unrealized = 0.0
                for s, p in portfolio.open_positions.items():
                    if s in active_bars:
                        p_cls = float(active_bars[s]["Close"])
                    else:
                        p_cls = p.current_price
                    if p.side == Position.LONG:
                        close_unrealized += (p_cls - p.entry_price) * p.quantity
                    else:
                        close_unrealized += (p.entry_price - p_cls) * p.quantity
                close_equity = portfolio.cash + close_unrealized

                if adv_equity <= eff_floor or close_equity <= eff_floor or adv_equity <= 0 or close_equity <= 0:
                    portfolio.is_bankrupt = True
                    if portfolio.bankruptcy_reason is None:
                        portfolio.bankruptcy_reason = "CAPITAL_EXHAUSTED" if (adv_equity <= 0 or close_equity <= 0) else "PROTECTION_FLOOR"

            # Emergency Liquidation if aggregate protection breached
            if portfolio.is_bankrupt:
                open_syms = sorted(list(portfolio.open_positions.keys()))
                for sym in open_syms:
                    if sym not in portfolio.open_positions:
                        continue
                    if sym in active_bars:
                        pos = portfolio.open_positions[sym]
                        # Conservative liquidation at authentic adverse price, never awarding post-breach recovery
                        exit_p = float(active_bars[sym]["Low"]) if pos.side == Position.LONG else float(active_bars[sym]["High"])
                        portfolio.close_position(
                            symbol=sym,
                            exit_time=current_time,
                            exit_price=exit_p,
                            exit_reason=portfolio.bankruptcy_reason or "PROTECTION_FLOOR",
                            cost_config=config.cost_config,
                            brokerage=config.brokerage_per_trade,
                            slippage_rate=config.slippage_rate,
                            statutory_fee_rate=config.statutory_fee_rate,
                            transaction_cost_rate=config.transaction_cost_rate,
                        )
                    else:
                        portfolio.mark_pending_liquidation(sym, portfolio.bankruptcy_reason or "PROTECTION_FLOOR")
                pending_next_open_signals.clear()

            # Step 4D-3: Intrabar Individual Target Exits (Priority 5)
            # Only awarded if portfolio did not breach protection floor!
            if not portfolio.is_bankrupt:
                open_syms = sorted(list(portfolio.open_positions.keys()))
                for sym in open_syms:
                    if sym not in portfolio.open_positions or sym not in active_bars:
                        continue
                    pos = portfolio.open_positions[sym]
                    if pos.pending_liquidation:
                        continue

                    bar = active_bars[sym]
                    bar_high = float(bar["High"])
                    bar_low = float(bar["Low"])

                    target_hit = False
                    if pos.side == Position.LONG:
                        if bar_high >= pos.target_price:
                            target_hit = True
                    elif pos.side == Position.SHORT:
                        if bar_low <= pos.target_price:
                            target_hit = True

                    if target_hit:
                        portfolio.close_position(
                            symbol=sym,
                            exit_time=current_time,
                            exit_price=pos.target_price,
                            exit_reason="TARGET",
                            cost_config=config.cost_config,
                            brokerage=config.brokerage_per_trade,
                            slippage_rate=config.slippage_rate,
                            statutory_fee_rate=config.statutory_fee_rate,
                            transaction_cost_rate=config.transaction_cost_rate,
                        )

            # Step 4D-4: End-of-Day Square-Off (Priority 6)
            if not portfolio.is_bankrupt and config.enforce_eod_square_off and current_time.time() >= session_end_t:
                open_syms = sorted(list(portfolio.open_positions.keys()))
                for sym in open_syms:
                    if sym not in portfolio.open_positions:
                        continue
                    if sym in active_bars:
                        portfolio.close_position(
                            symbol=sym,
                            exit_time=current_time,
                            exit_price=float(active_bars[sym]["Close"]),
                            exit_reason="EOD",
                            cost_config=config.cost_config,
                            brokerage=config.brokerage_per_trade,
                            slippage_rate=config.slippage_rate,
                            statutory_fee_rate=config.statutory_fee_rate,
                            transaction_cost_rate=config.transaction_cost_rate,
                        )
                    else:
                        portfolio.mark_pending_liquidation(sym, "EOD")

            # 4E. Update MTM Prices & Drawdown at Bar t Close
            current_prices = {}
            for sym, bar in active_bars.items():
                current_prices[sym] = float(bar["Close"])
            portfolio.update_market_prices(current_prices)

            # 4F. Detect New Signals at Bar t Close for t+1 Open
            if (
                is_trading_active
                and not portfolio.is_bankrupt
                and not portfolio.has_unresolved_liquidations
                and not portfolio.has_indeterminate_valuation
            ):
                for sym, bar in active_bars.items():
                    if sym in portfolio.open_positions:
                        continue

                    raw_sig = _resolve_raw_signal(
                        sym=sym,
                        current_time=current_time,
                        bar=bar,
                        sym_df=normalized_data[sym],
                        signals_by_symbol=signals_by_symbol,
                        signal_generator=signal_generator,
                    )

                    if isinstance(raw_sig, TradeOpportunity):
                        pending_next_open_signals[sym] = raw_sig
                    elif isinstance(raw_sig, Position):
                        bar_atr = float(bar["ATR"])
                        pending_next_open_signals[sym] = TradeOpportunity(
                            symbol=sym,
                            side=raw_sig,
                            entry_price=float(bar["Close"]),
                            stop_loss=0.0,
                            target_price=0.0,
                            signal_quality=1.0,
                            relative_volume=1.0,
                            is_tradeable=True,
                            timestamp=current_time,
                            atr=bar_atr,
                        )

        elif config.execution_model == "same_close":
            # ================================================================
            # MODEL: SAME_CLOSE (Synchronous evaluation and execution at Close)
            # ================================================================

            # Step 4A: Opening-Gap Protection at t Open (Priority 1)
            eff_floor = portfolio.effective_protection_floor
            if eff_floor is not None and portfolio.open_positions:
                open_unrealized = 0.0
                for sym, pos in portfolio.open_positions.items():
                    p_mark = float(active_bars[sym]["Open"]) if sym in active_bars else pos.current_price
                    if pos.side == Position.LONG:
                        open_unrealized += (p_mark - pos.entry_price) * pos.quantity
                    else:
                        open_unrealized += (pos.entry_price - p_mark) * pos.quantity
                open_equity = portfolio.cash + open_unrealized
                if open_equity <= eff_floor or open_equity <= 0:
                    portfolio.is_bankrupt = True
                    if portfolio.bankruptcy_reason is None:
                        portfolio.bankruptcy_reason = "CAPITAL_EXHAUSTED" if open_equity <= 0 else "PROTECTION_FLOOR"

            # Emergency Liquidation at t Open if Opening-Gap breached protection
            if portfolio.is_bankrupt:
                open_syms = sorted(list(portfolio.open_positions.keys()))
                for sym in open_syms:
                    if sym not in portfolio.open_positions:
                        continue
                    if sym in active_bars:
                        portfolio.close_position(
                            symbol=sym,
                            exit_time=current_time,
                            exit_price=float(active_bars[sym]["Open"]),
                            exit_reason=portfolio.bankruptcy_reason or "PROTECTION_FLOOR",
                            cost_config=config.cost_config,
                            brokerage=config.brokerage_per_trade,
                            slippage_rate=config.slippage_rate,
                            statutory_fee_rate=config.statutory_fee_rate,
                            transaction_cost_rate=config.transaction_cost_rate,
                        )
                    else:
                        portfolio.mark_pending_liquidation(sym, portfolio.bankruptcy_reason or "PROTECTION_FLOOR")

            # Step 4B: Opening-Gap Stop/Target Exits at t Open (Priority 2)
            if not portfolio.is_bankrupt:
                open_syms = sorted(list(portfolio.open_positions.keys()))
                for sym in open_syms:
                    if sym not in portfolio.open_positions or sym not in active_bars:
                        continue
                    pos = portfolio.open_positions[sym]
                    if pos.pending_liquidation:
                        continue

                    bar = active_bars[sym]
                    bar_open = float(bar["Open"])
                    gap_exit_price = None
                    gap_exit_reason = None

                    if pos.side == Position.LONG:
                        if config.gap_execution and bar_open <= pos.stop_price:
                            gap_exit_price = bar_open
                            gap_exit_reason = "STOP"
                        elif config.gap_execution and bar_open >= pos.target_price:
                            gap_exit_price = bar_open
                            gap_exit_reason = "TARGET"
                    elif pos.side == Position.SHORT:
                        if config.gap_execution and bar_open >= pos.stop_price:
                            gap_exit_price = bar_open
                            gap_exit_reason = "STOP"
                        elif config.gap_execution and bar_open <= pos.target_price:
                            gap_exit_price = bar_open
                            gap_exit_reason = "TARGET"

                    if gap_exit_price is not None and gap_exit_reason is not None:
                        portfolio.close_position(
                            symbol=sym,
                            exit_time=current_time,
                            exit_price=gap_exit_price,
                            exit_reason=gap_exit_reason,
                            cost_config=config.cost_config,
                            brokerage=config.brokerage_per_trade,
                            slippage_rate=config.slippage_rate,
                            statutory_fee_rate=config.statutory_fee_rate,
                            transaction_cost_rate=config.transaction_cost_rate,
                        )

            # Step 4C: Intrabar Individual Stop-Loss Exits (Priority 3)
            if not portfolio.is_bankrupt:
                open_syms = sorted(list(portfolio.open_positions.keys()))
                for sym in open_syms:
                    if sym not in portfolio.open_positions or sym not in active_bars:
                        continue
                    pos = portfolio.open_positions[sym]
                    if pos.pending_liquidation:
                        continue

                    bar = active_bars[sym]
                    bar_low = float(bar["Low"])
                    bar_high = float(bar["High"])

                    stop_hit = False
                    if pos.side == Position.LONG:
                        if bar_low <= pos.stop_price and bar_high >= pos.target_price and config.conservative_same_candle:
                            stop_hit = True
                        elif bar_low <= pos.stop_price:
                            stop_hit = True
                    elif pos.side == Position.SHORT:
                        if bar_high >= pos.stop_price and bar_low <= pos.target_price and config.conservative_same_candle:
                            stop_hit = True
                        elif bar_high >= pos.stop_price:
                            stop_hit = True

                    if stop_hit:
                        portfolio.close_position(
                            symbol=sym,
                            exit_time=current_time,
                            exit_price=pos.stop_price,
                            exit_reason="STOP",
                            cost_config=config.cost_config,
                            brokerage=config.brokerage_per_trade,
                            slippage_rate=config.slippage_rate,
                            statutory_fee_rate=config.statutory_fee_rate,
                            transaction_cost_rate=config.transaction_cost_rate,
                        )

            # Step 4D: Aggregate Portfolio Protection (Intrabar & Close) (Priority 4)
            eff_floor = portfolio.effective_protection_floor
            if eff_floor is not None and portfolio.open_positions:
                adv_unrealized = 0.0
                for s, p in portfolio.open_positions.items():
                    if s in active_bars:
                        p_adv = float(active_bars[s]["Low"]) if p.side == Position.LONG else float(active_bars[s]["High"])
                    else:
                        p_adv = p.current_price
                    if p.side == Position.LONG:
                        adv_unrealized += (p_adv - p.entry_price) * p.quantity
                    else:
                        adv_unrealized += (p.entry_price - p_adv) * p.quantity
                adv_equity = portfolio.cash + adv_unrealized

                close_unrealized = 0.0
                for s, p in portfolio.open_positions.items():
                    if s in active_bars:
                        p_cls = float(active_bars[s]["Close"])
                    else:
                        p_cls = p.current_price
                    if p.side == Position.LONG:
                        close_unrealized += (p_cls - p.entry_price) * p.quantity
                    else:
                        close_unrealized += (p.entry_price - p_cls) * p.quantity
                close_equity = portfolio.cash + close_unrealized

                if adv_equity <= eff_floor or close_equity <= eff_floor or adv_equity <= 0 or close_equity <= 0:
                    portfolio.is_bankrupt = True
                    if portfolio.bankruptcy_reason is None:
                        portfolio.bankruptcy_reason = "CAPITAL_EXHAUSTED" if (adv_equity <= 0 or close_equity <= 0) else "PROTECTION_FLOOR"

            # Emergency Liquidation if aggregate protection breached
            if portfolio.is_bankrupt:
                open_syms = sorted(list(portfolio.open_positions.keys()))
                for sym in open_syms:
                    if sym not in portfolio.open_positions:
                        continue
                    if sym in active_bars:
                        pos = portfolio.open_positions[sym]
                        exit_p = float(active_bars[sym]["Low"]) if pos.side == Position.LONG else float(active_bars[sym]["High"])
                        portfolio.close_position(
                            symbol=sym,
                            exit_time=current_time,
                            exit_price=exit_p,
                            exit_reason=portfolio.bankruptcy_reason or "PROTECTION_FLOOR",
                            cost_config=config.cost_config,
                            brokerage=config.brokerage_per_trade,
                            slippage_rate=config.slippage_rate,
                            statutory_fee_rate=config.statutory_fee_rate,
                            transaction_cost_rate=config.transaction_cost_rate,
                        )
                    else:
                        portfolio.mark_pending_liquidation(sym, portfolio.bankruptcy_reason or "PROTECTION_FLOOR")

            # Step 4E: Intrabar Targets (Priority 5)
            if not portfolio.is_bankrupt:
                open_syms = sorted(list(portfolio.open_positions.keys()))
                for sym in open_syms:
                    if sym not in portfolio.open_positions or sym not in active_bars:
                        continue
                    pos = portfolio.open_positions[sym]
                    if pos.pending_liquidation:
                        continue

                    bar = active_bars[sym]
                    bar_high = float(bar["High"])
                    bar_low = float(bar["Low"])

                    target_hit = False
                    if pos.side == Position.LONG:
                        if bar_high >= pos.target_price:
                            target_hit = True
                    elif pos.side == Position.SHORT:
                        if bar_low <= pos.target_price:
                            target_hit = True

                    if target_hit:
                        portfolio.close_position(
                            symbol=sym,
                            exit_time=current_time,
                            exit_price=pos.target_price,
                            exit_reason="TARGET",
                            cost_config=config.cost_config,
                            brokerage=config.brokerage_per_trade,
                            slippage_rate=config.slippage_rate,
                            statutory_fee_rate=config.statutory_fee_rate,
                            transaction_cost_rate=config.transaction_cost_rate,
                        )

            # Step 4F: End-of-Day Square-Off (Priority 6)
            if not portfolio.is_bankrupt and config.enforce_eod_square_off and current_time.time() >= session_end_t:
                open_syms = sorted(list(portfolio.open_positions.keys()))
                for sym in open_syms:
                    if sym not in portfolio.open_positions:
                        continue
                    if sym in active_bars:
                        portfolio.close_position(
                            symbol=sym,
                            exit_time=current_time,
                            exit_price=float(active_bars[sym]["Close"]),
                            exit_reason="EOD",
                            cost_config=config.cost_config,
                            brokerage=config.brokerage_per_trade,
                            slippage_rate=config.slippage_rate,
                            statutory_fee_rate=config.statutory_fee_rate,
                            transaction_cost_rate=config.transaction_cost_rate,
                        )
                    else:
                        portfolio.mark_pending_liquidation(sym, "EOD")

            # Step 4G: Update MTM Prices with Bar t Close
            current_prices = {}
            for sym, bar in active_bars.items():
                current_prices[sym] = float(bar["Close"])
            portfolio.update_market_prices(current_prices)

            # Step 4H: Generate & Execute New Candidate Entries at Bar t Close
            is_in_cooldown = config.is_in_opening_cooldown(current_time)
            is_trading_active = (
                not portfolio.is_bankrupt
                and not portfolio.has_unresolved_liquidations
                and not portfolio.has_indeterminate_valuation
                and not (config.enforce_eod_square_off and current_time.time() >= session_end_t)
            )

            if not is_in_cooldown and is_trading_active:
                candidate_opportunities = []
                for sym, bar in active_bars.items():
                    if sym in portfolio.open_positions:
                        continue

                    raw_sig = _resolve_raw_signal(
                        sym=sym,
                        current_time=current_time,
                        bar=bar,
                        sym_df=normalized_data[sym],
                        signals_by_symbol=signals_by_symbol,
                        signal_generator=signal_generator,
                    )

                    if isinstance(raw_sig, TradeOpportunity):
                        candidate_opportunities.append(raw_sig)
                    elif isinstance(raw_sig, Position):
                        bar_close = float(bar["Close"])
                        bar_atr = float(bar["ATR"])
                        stop_dist = bar_atr * config.stop_loss_atr
                        target_dist = bar_atr * config.take_profit_atr

                        if raw_sig == Position.LONG:
                            stop_p = bar_close - stop_dist
                            target_p = bar_close + target_dist
                        else:
                            stop_p = bar_close + stop_dist
                            target_p = bar_close - target_dist

                        opp = TradeOpportunity(
                            symbol=sym,
                            side=raw_sig,
                            entry_price=bar_close,
                            stop_loss=stop_p,
                            target_price=target_p,
                            signal_quality=1.0,
                            reward_risk_ratio=target_dist / stop_dist if stop_dist > 0 else 2.0,
                            relative_volume=1.0,
                            is_tradeable=True,
                            timestamp=current_time,
                            atr=bar_atr,
                        )
                        candidate_opportunities.append(opp)

                if candidate_opportunities and not portfolio.is_bankrupt:
                    decisions = allocator.allocate_batch(candidate_opportunities, portfolio)
                    all_allocations.extend(decisions)

                    for dec in decisions:
                        if dec.accepted and dec.allocated_quantity > 0:
                            opp_match = next((o for o in candidate_opportunities if o.symbol == dec.symbol), None)
                            if opp_match is not None:
                                portfolio.open_position(
                                    symbol=dec.symbol,
                                    side=opp_match.side,
                                    entry_time=current_time,
                                    entry_price=dec.entry_price,
                                    quantity=dec.allocated_quantity,
                                    stop_price=dec.stop_loss,
                                    target_price=opp_match.target_price,
                                    risk_amount=dec.estimated_risk,
                                    atr=opp_match.atr,
                                    stop_distance=abs(dec.entry_price - dec.stop_loss),
                                    leverage=config.max_leverage,
                                    risk_based_quantity=dec.allocated_quantity,
                                    max_allowed_quantity=dec.allocated_quantity,
                                )

        # --------------------------------------------------------------------
        # 5. RECORD PORTFOLIO SNAPSHOT AT TIMESTAMP t
        # --------------------------------------------------------------------
        equity_snapshots.append(
            {
                "timestamp": current_time,
                "cash": round(portfolio.cash, 2),
                "unrealized_pnl": round(portfolio.unrealized_pnl, 2),
                "equity": round(portfolio.equity, 2),
                "allocated_margin": round(portfolio.allocated_margin, 2),
                "available_margin": round(portfolio.available_margin, 2),
                "reserved_capital": round(portfolio.reserved_capital, 2),
                "gross_exposure": round(portfolio.gross_exposure, 2),
                "effective_leverage": round(portfolio.effective_leverage, 2),
                "current_drawdown_pct": round(portfolio.current_drawdown, 2),
                "open_positions_count": portfolio.open_position_count,
            }
        )

    # ------------------------------------------------------------------------
    # FINAL CLEANUP AT END OF SIMULATION
    # ------------------------------------------------------------------------
    # Close any positions remaining open at the final candle if executable candle exists
    if portfolio.open_position_count > 0:
        final_time = timeline[-1]
        final_active_bars = active_bars
        for sym in list(portfolio.open_positions.keys()):
            pos = portfolio.open_positions[sym]
            if sym in final_active_bars:
                portfolio.close_position(
                    symbol=sym,
                    exit_time=final_time,
                    exit_price=float(final_active_bars[sym]["Close"]),
                    exit_reason="EOD",
                    cost_config=config.cost_config,
                    brokerage=config.brokerage_per_trade,
                    slippage_rate=config.slippage_rate,
                    statutory_fee_rate=config.statutory_fee_rate,
                    transaction_cost_rate=config.transaction_cost_rate,
                )
            else:
                # Missing from final candle: do NOT fabricate fill! Mark pending liquidation.
                pos.pending_liquidation = True
                pos.pending_liquidation_reason = "EOD"

    unresolved_positions = portfolio.unresolved_liquidation_positions
    unresolved_liquidation_exposure = sum(p.notional_value for p in unresolved_positions)

    # Build equity curve DataFrame
    equity_df = pd.DataFrame(equity_snapshots)
    if not equity_df.empty:
        equity_df.set_index("timestamp", inplace=True)

    # Calculate overall metrics
    metrics = calculate_metrics(
        trades=portfolio.trades,
        initial_capital=config.initial_capital,
        max_drawdown_pct=portfolio.max_drawdown,
    )

    # Calculate per-symbol metrics
    sym_metrics = _calculate_symbol_metrics(portfolio.trades, symbols)

    cost_model_info = {
        "profile_name": config.cost_config.name if config.cost_config else "CUSTOM",
        "include_in_sizing": config.include_estimated_round_trip_costs_in_sizing,
    }

    return MultiAssetBacktestResult(
        trades=portfolio.trades,
        portfolio=portfolio,
        metrics=metrics,
        symbol_metrics=sym_metrics,
        equity_curve=equity_df,
        allocations=all_allocations,
        missing_candle_stats=missing_candle_stats,
        stale_price_events=stale_price_events,
        stale_notional_exposure=round(stale_notional_exposure, 2),
        unresolved_positions=unresolved_positions,
        unresolved_liquidation_exposure=round(unresolved_liquidation_exposure, 2),
        opening_cooldown_minutes=config.opening_cooldown_minutes,
        bankruptcy_reason=portfolio.bankruptcy_reason,
        cost_model_info=cost_model_info,
        indeterminate_valuation_events=indeterminate_events,
    )


def _parse_signal_value(val: Any) -> Optional[Position]:
    """Parse various signal representations into a Position enum or None."""
    if val is None or val is False:
        return None
    if isinstance(val, Position):
        return val
    if isinstance(val, str):
        v = val.strip().upper()
        if v in ("LONG", "BUY", "1"):
            return Position.LONG
        elif v in ("SHORT", "SELL", "-1"):
            return Position.SHORT
        return None
    if isinstance(val, (int, float)):
        if val > 0:
            return Position.LONG
        elif val < 0:
            return Position.SHORT
    return None
