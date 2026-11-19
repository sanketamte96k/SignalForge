"""
SignalForge — Phase 32B: Strategy SEB-V1 (Squeeze Expansion Breakout)
=====================================================================
File: src/strategy/strategy_seb_v1.py

Strategy Specification:
- Execution Timeframe: 5-minute candles.
- Macro Direction: Completed 30-minute candles.
- Core Regime: Volatility Squeeze (Bollinger Bands contract inside Keltner Channel).
- Lookback / Squeeze Trigger: Squeeze occurred within the previous 6 completed 5m bars.
- Directional Trigger: 5m candle closes beyond the 20-bar Donchian channel.
  * MANDATORY CAUSALITY: Donchian boundaries strictly use shift(1) to exclude the current bar:
    Donchian_High = high.shift(1).rolling(20).max()
    Donchian_Low  = low.shift(1).rolling(20).min()
- Volume Filter: Relative Volume (RVOL) >= 1.5 against previous 20-bar volume median:
    vol_median = volume.shift(1).rolling(20).median()
    rvol = volume / vol_median >= 1.5
- Macro Confirmation: Completed 30m EMA20 > EMA50 for LONG (EMA20 < EMA50 for SHORT).
  * 30m candles must be fully completed before synchronization to 5m bars.
- Anti-Climax Guard: Breakout candle body (abs(close - open)) <= 2.0 * ATR.
- Time-of-Day Filter:
  * No entries before 09:35 IST (09:15-09:35 opening blackout).
  * No entries after 14:45 IST.
  * Mandatory EOD Square-Off at 15:15 IST.
- Daily Session Limit: Maximum 1 trade per symbol per trading session.
- Exits:
  * Initial Stop-Loss: 1.5 * ATR from entry price.
  * Target: 3.5 * ATR from entry price.
  * Trailing Logic (Frozen): Activated once price achieves +2.0 * ATR favorable excursion.
    Stop moved to max(current_stop, entry + 0.5 * ATR, high - 1.5 * ATR) for LONG.
    Stop moved to min(current_stop, entry - 0.5 * ATR, low + 1.5 * ATR) for SHORT.
  * Intrabar Collision Priority: If both stop and target are touched within the same 5m bar,
    STOP-LOSS is assumed first (conservative, zero-lookahead).
- Risk & Sizing:
  * 1% portfolio equity risk per trade, capped at 5x leverage.
  * Cost-aware sizing via calculate_cost_aware_position_size.
  * Canonical Indian transaction costs (DISCOUNT_BROKER_REALISTIC / CONSERVATIVE_STRESS).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time as dtime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

from src.backtest.capital_allocator import calculate_cost_aware_position_size
from src.backtest.indian_market_costs import (
    IntradayCostConfig,
    DISCOUNT_BROKER_REALISTIC_CONFIG,
    CONSERVATIVE_STRESS_CONFIG,
    calculate_trade_transaction_costs,
)
from src.backtest.simulator import Position, Trade, simulate_trade
from src.data.resampler import resample_ohlcv

IST_TZ = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class SEBV1Config:
    """Configuration parameters for SEB-V1 (Squeeze Expansion Breakout)."""
    name: str = "SEB-V1"
    description: str = "5m Squeeze Expansion Breakout with causal 30m EMA filter"
    bb_period: int = 20
    bb_std_mult: float = 2.0
    kc_ema_period: int = 20
    kc_atr_mult: float = 1.5
    atr_period: int = 14
    donchian_period: int = 20
    rvol_period: int = 20
    rvol_threshold: float = 1.5
    squeeze_lookback_bars: int = 6
    max_body_atr_mult: float = 2.0
    initial_stop_atr: float = 1.5
    target_atr: float = 3.5
    trailing_activation_atr: float = 2.0
    trailing_offset_atr: float = 1.5
    trailing_guarantee_atr: float = 0.5
    risk_per_trade_pct: float = 0.01
    max_leverage: float = 5.0
    opening_blackout_end: str = "09:35"
    last_entry_time: str = "14:45"
    eod_square_off_time: str = "15:15"
    max_trades_per_session: int = 1


DEFAULT_SEB_V1_CONFIG = SEBV1Config()


def calc_wilder_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Welles Wilder's Average True Range with causal smoothing."""
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def compute_seb_v1_indicators(
    df_1m: pd.DataFrame,
    config: Optional[SEBV1Config] = None,
) -> dict[str, Any]:
    """
    Computes all causal 5m and 30m indicators for SEB-V1.
    
    Guarantees:
    - 5m candles are formed strictly from complete 1-minute candles.
    - 30m candles are formed strictly from complete 1-minute candles.
    - 30m indicators are merged causally: a 30m candle spanning [T, T+30m)
      is only available at T+30m for subsequent 5m bar evaluations.
    - Donchian channels use shift(1) to prevent current-bar contamination.
    - Volume median uses shift(1).
    """
    if config is None:
        config = DEFAULT_SEB_V1_CONFIG

    # Normalize column names
    df_raw = df_1m.copy()
    df_raw.columns = [c.lower() for c in df_raw.columns]
    if "timestamp" in df_raw.columns:
        df_raw["timestamp"] = pd.to_datetime(df_raw["timestamp"])
        df_raw.set_index("timestamp", inplace=True)
    df_raw.sort_index(inplace=True)

    # 1. Resample to 5m and 30m
    df_5m = resample_ohlcv(df_raw, "5m").copy()
    df_30m = resample_ohlcv(df_raw, "30m").copy()

    # 2. Compute 5m Indicators
    df_5m["atr"] = calc_wilder_atr(df_5m, config.atr_period)
    df_5m["ema20"] = df_5m["close"].ewm(span=config.kc_ema_period, adjust=False).mean()

    # Bollinger Bands (20, 2.0 std)
    roll_mean = df_5m["close"].rolling(config.bb_period).mean()
    roll_std = df_5m["close"].rolling(config.bb_period).std()
    df_5m["bb_upper"] = roll_mean + (config.bb_std_mult * roll_std)
    df_5m["bb_lower"] = roll_mean - (config.bb_std_mult * roll_std)

    # Keltner Channels (20, 1.5 ATR)
    df_5m["kc_upper"] = df_5m["ema20"] + (config.kc_atr_mult * df_5m["atr"])
    df_5m["kc_lower"] = df_5m["ema20"] - (config.kc_atr_mult * df_5m["atr"])

    # Squeeze Condition (BB inside KC)
    df_5m["is_squeeze"] = (df_5m["bb_upper"] < df_5m["kc_upper"]) & (df_5m["bb_lower"] > df_5m["kc_lower"])
    # Squeeze in previous N completed bars (rolling window of 6 completed bars)
    df_5m["recent_squeeze"] = df_5m["is_squeeze"].rolling(config.squeeze_lookback_bars).max() >= 1

    # Donchian 20-bar Boundaries (CRITICAL: shift(1) to exclude current bar)
    df_5m["donchian_high"] = df_5m["high"].shift(1).rolling(config.donchian_period).max()
    df_5m["donchian_low"] = df_5m["low"].shift(1).rolling(config.donchian_period).min()

    # Volume Median (20 bars, shifted) & RVOL
    vol_median = df_5m["volume"].shift(1).rolling(config.rvol_period).median()
    df_5m["vol_median_20"] = vol_median
    df_5m["rvol"] = df_5m["volume"] / vol_median.replace(0, np.nan)

    # Candle body size
    df_5m["body_size"] = (df_5m["close"] - df_5m["open"]).abs()

    # 3. Compute 30m Macro Indicators
    df_30m["ema20_30m"] = df_30m["close"].ewm(span=20, adjust=False).mean()
    df_30m["ema50_30m"] = df_30m["close"].ewm(span=50, adjust=False).mean()
    df_30m["macro_bull"] = df_30m["ema20_30m"] > df_30m["ema50_30m"]
    df_30m["macro_bear"] = df_30m["ema20_30m"] < df_30m["ema50_30m"]

    # Causal availability timestamp for 30m bar: index + 30 minutes
    # A 30m candle starting at 09:15 is complete at 09:45:00
    df_30m["available_at"] = df_30m.index + pd.Timedelta(minutes=30)

    # 5m candle completion timestamp: index + 5 minutes
    df_5m["completed_at"] = df_5m.index + pd.Timedelta(minutes=5)

    # Causal asof merge: 5m bar at completed_at merges with latest available_at <= completed_at
    merged = pd.merge_asof(
        df_5m.sort_values("completed_at"),
        df_30m[["available_at", "macro_bull", "macro_bear", "ema20_30m", "ema50_30m"]].sort_values("available_at"),
        left_on="completed_at",
        right_on="available_at",
        direction="backward",
    )
    # Restore 5m index
    merged.index = df_5m.index
    df_5m["macro_bull"] = merged["macro_bull"].fillna(False)
    df_5m["macro_bear"] = merged["macro_bear"].fillna(False)

    return {
        "df_5m": df_5m,
        "df_30m": df_30m,
        "df_1m": df_raw,
    }


@dataclass
class SEBV1BacktestResult:
    """Detailed results from SEB-V1 simulation."""
    symbol: str
    strategy_name: str
    trades: list[Trade]
    initial_capital: float
    ending_capital: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    gross_pnl: float
    total_costs: float
    brokerage_costs: float
    statutory_costs: float
    slippage_and_spread_costs: float
    net_pnl: float
    gross_profit_factor: float
    net_profit_factor: float
    net_expectancy: float
    avg_win: float
    avg_loss: float
    payoff_ratio: float
    max_drawdown_inr: float
    max_drawdown_pct: float
    max_consecutive_losses: int
    total_turnover: float
    turnover_ratio: float
    avg_holding_duration_mins: float
    bootstrap_ci_95: tuple[float, float]
    trades_df: pd.DataFrame = field(default_factory=pd.DataFrame)


def run_seb_v1_backtest(
    df_1m: pd.DataFrame,
    symbol: str,
    initial_capital: float = 100000.0,
    cost_config: Optional[IntradayCostConfig] = None,
    config: Optional[SEBV1Config] = None,
) -> SEBV1BacktestResult:
    """
    Executes a strict, zero-lookahead backtest for SEB-V1.
    
    Execution semantics:
    - Signal generated at close of 5m bar T.
    - Order executes at Open of 5m bar T+1 (next_open fill).
    - Stop-loss and Target evaluated intrabar on subsequent bars.
    - If stop and target both touched in the same bar, Stop-Loss triggers first.
    - Trailing logic updates stop causally once +2 ATR excursion is reached.
    - Mandatory square-off at 15:15 IST.
    - Sizing: 1% risk per trade, 5x leverage cap, cost-aware.
    """
    if config is None:
        config = DEFAULT_SEB_V1_CONFIG
    if cost_config is None:
        cost_config = DISCOUNT_BROKER_REALISTIC_CONFIG

    features = compute_seb_v1_indicators(df_1m, config)
    df_5m = features["df_5m"]

    capital = float(initial_capital)
    trades: list[Trade] = []

    # Parse blackout and cutoffs
    bh_h, bh_m = [int(x) for x in config.opening_blackout_end.split(":")]
    blackout_end = dtime(bh_h, bh_m)
    le_h, le_m = [int(x) for x in config.last_entry_time.split(":")]
    last_entry = dtime(le_h, le_m)
    eod_h, eod_m = [int(x) for x in config.eod_square_off_time.split(":")]
    eod_square_off = dtime(eod_h, eod_m)

    # Active position tracking
    active_position: Optional[Position] = None
    entry_price = 0.0
    entry_time: Optional[pd.Timestamp] = None
    quantity = 0
    current_stop = 0.0
    current_target = 0.0
    atr_at_entry = 0.0
    trailing_activated = False
    highest_since_entry = 0.0
    lowest_since_entry = 0.0
    capital_before_entry = 0.0

    # Session tracking for 1-trade-per-session limit
    session_trades_count = 0
    current_session_date = None

    n_bars = len(df_5m)
    timestamps = df_5m.index

    for i in range(n_bars):
        cur_ts = timestamps[i]
        cur_date = cur_ts.date()
        cur_time = cur_ts.time()

        # New session reset
        if cur_date != current_session_date:
            current_session_date = cur_date
            session_trades_count = 0

        bar = df_5m.iloc[i]
        b_open = float(bar["open"])
        b_high = float(bar["high"])
        b_low = float(bar["low"])
        b_close = float(bar["close"])

        # -------------------------------------------------------------
        # 1. Manage Active Position
        # -------------------------------------------------------------
        if active_position is not None:
            exit_triggered = False
            exit_price = 0.0
            exit_reason = ""

            # Check EOD Square-Off
            if cur_time >= eod_square_off:
                exit_triggered = True
                exit_price = b_open
                exit_reason = "EOD_SQUARE_OFF"
            else:
                if active_position == Position.LONG:
                    highest_since_entry = max(highest_since_entry, b_high)
                    hit_stop = b_low <= current_stop
                    hit_target = b_high >= current_target

                    if hit_stop and hit_target:
                        # Collision: Stop First
                        exit_triggered = True
                        exit_price = current_stop
                        exit_reason = "STOP_LOSS"
                    elif hit_stop:
                        exit_triggered = True
                        exit_price = current_stop
                        exit_reason = "STOP_LOSS"
                    elif hit_target:
                        exit_triggered = True
                        exit_price = current_target
                        exit_reason = "TARGET"
                    else:
                        # Trailing Update
                        if not trailing_activated and (b_high >= entry_price + (config.trailing_activation_atr * atr_at_entry)):
                            trailing_activated = True
                        if trailing_activated:
                            trail_stop = highest_since_entry - (config.trailing_offset_atr * atr_at_entry)
                            guarantee_stop = entry_price + (config.trailing_guarantee_atr * atr_at_entry)
                            current_stop = max(current_stop, guarantee_stop, trail_stop)

                elif active_position == Position.SHORT:
                    lowest_since_entry = min(lowest_since_entry, b_low)
                    hit_stop = b_high >= current_stop
                    hit_target = b_low <= current_target

                    if hit_stop and hit_target:
                        # Collision: Stop First
                        exit_triggered = True
                        exit_price = current_stop
                        exit_reason = "STOP_LOSS"
                    elif hit_stop:
                        exit_triggered = True
                        exit_price = current_stop
                        exit_reason = "STOP_LOSS"
                    elif hit_target:
                        exit_triggered = True
                        exit_price = current_target
                        exit_reason = "TARGET"
                    else:
                        # Trailing Update
                        if not trailing_activated and (b_low <= entry_price - (config.trailing_activation_atr * atr_at_entry)):
                            trailing_activated = True
                        if trailing_activated:
                            trail_stop = lowest_since_entry + (config.trailing_offset_atr * atr_at_entry)
                            guarantee_stop = entry_price - (config.trailing_guarantee_atr * atr_at_entry)
                            current_stop = min(current_stop, guarantee_stop, trail_stop)

            if exit_triggered:
                trade = simulate_trade(
                    position=active_position,
                    entry_time=entry_time,
                    exit_time=cur_ts,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=quantity,
                    cost_config=cost_config,
                    symbol=symbol,
                    exit_reason=exit_reason,
                    capital_before=capital_before_entry,
                    capital_after=capital + (exit_price - entry_price if active_position == Position.LONG else entry_price - exit_price) * quantity,
                    atr=atr_at_entry,
                    stop_distance=abs(entry_price - current_stop),
                )
                trades.append(trade)
                capital += trade.net_pnl

                # Reset position state
                active_position = None
                entry_price = 0.0
                entry_time = None
                quantity = 0
                current_stop = 0.0
                current_target = 0.0
                atr_at_entry = 0.0
                trailing_activated = False

        # -------------------------------------------------------------
        # 2. Evaluate Signals at Candle Close (if no active position)
        # -------------------------------------------------------------
        if active_position is None and session_trades_count < config.max_trades_per_session:
            # Check timing filters
            if cur_time < blackout_end or cur_time > last_entry:
                continue

            # Check indicators availability
            atr = bar["atr"]
            if pd.isna(atr) or atr <= 0.0:
                continue
            dh = bar["donchian_high"]
            dl = bar["donchian_low"]
            if pd.isna(dh) or pd.isna(dl):
                continue
            rvol = bar["rvol"]
            if pd.isna(rvol):
                continue

            recent_sq = bool(bar["recent_squeeze"])
            macro_bull = bool(bar["macro_bull"])
            macro_bear = bool(bar["macro_bear"])
            body_size = float(bar["body_size"])
            max_body = config.max_body_atr_mult * atr

            sig_side: Optional[PositionSide] = None

            # LONG Squeeze Breakout Condition
            if recent_sq and (b_close > dh) and (rvol >= config.rvol_threshold) and macro_bull and (body_size <= max_body):
                sig_side = Position.LONG
            # SHORT Squeeze Breakout Condition
            elif recent_sq and (b_close < dl) and (rvol >= config.rvol_threshold) and macro_bear and (body_size <= max_body):
                sig_side = Position.SHORT

            # If signal fired, fill at Next Bar Open (i+1)
            if sig_side is not None and (i + 1 < n_bars):
                next_bar = df_5m.iloc[i + 1]
                next_ts = timestamps[i + 1]

                # Ensure next bar is in same trading day or early next day
                if next_ts.date() == cur_date and next_ts.time() < eod_square_off:
                    fill_price = float(next_bar["open"])
                    stop_dist = config.initial_stop_atr * atr
                    planned_stop = fill_price - stop_dist if sig_side == Position.LONG else fill_price + stop_dist

                    # Calculate cost-aware size
                    qty, _, _ = calculate_cost_aware_position_size(
                        entry_price=fill_price,
                        stop_loss=planned_stop,
                        capital=capital,
                        risk_per_trade_pct=config.risk_per_trade_pct,
                        max_leverage=config.max_leverage,
                        side=sig_side,
                        cost_config=cost_config,
                        include_costs_in_sizing=True,
                    )

                    if qty > 0:
                        active_position = sig_side
                        entry_price = fill_price
                        entry_time = next_ts
                        quantity = qty
                        atr_at_entry = atr
                        current_stop = planned_stop
                        current_target = fill_price + (config.target_atr * atr) if sig_side == Position.LONG else fill_price - (config.target_atr * atr)
                        highest_since_entry = fill_price
                        lowest_since_entry = fill_price
                        trailing_activated = False
                        capital_before_entry = capital
                        session_trades_count += 1

    # -------------------------------------------------------------
    # 3. Post-Backtest Metrics Aggregation
    # -------------------------------------------------------------
    return _aggregate_backtest_results(
        symbol=symbol,
        strategy_name=config.name,
        initial_capital=initial_capital,
        ending_capital=capital,
        trades=trades,
    )


def _aggregate_backtest_results(
    symbol: str,
    strategy_name: str,
    initial_capital: float,
    ending_capital: float,
    trades: list[Trade],
) -> SEBV1BacktestResult:
    """Computes all required performance, cost, and statistical metrics."""
    total_trades = len(trades)
    if total_trades == 0:
        return SEBV1BacktestResult(
            symbol=symbol,
            strategy_name=strategy_name,
            trades=[],
            initial_capital=initial_capital,
            ending_capital=initial_capital,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate_pct=0.0,
            gross_pnl=0.0,
            total_costs=0.0,
            brokerage_costs=0.0,
            statutory_costs=0.0,
            slippage_and_spread_costs=0.0,
            net_pnl=0.0,
            gross_profit_factor=0.0,
            net_profit_factor=0.0,
            net_expectancy=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            payoff_ratio=0.0,
            max_drawdown_inr=0.0,
            max_drawdown_pct=0.0,
            max_consecutive_losses=0,
            total_turnover=0.0,
            turnover_ratio=0.0,
            avg_holding_duration_mins=0.0,
            bootstrap_ci_95=(0.0, 0.0),
            trades_df=pd.DataFrame(),
        )

    records = []
    wins = 0
    losses = 0
    gross_wins = 0.0
    gross_losses = 0.0
    net_wins = 0.0
    net_losses = 0.0
    total_brokerage = 0.0
    total_statutory = 0.0
    total_slippage_spread = 0.0
    total_turnover = 0.0
    durations = []

    for t in trades:
        records.append({
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "position": t.position.value,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "quantity": t.quantity,
            "gross_pnl": t.gross_pnl,
            "transaction_cost": t.transaction_cost,
            "brokerage": t.brokerage,
            "statutory_fees": t.statutory_fees,
            "slippage_and_spread": t.slippage,
            "net_pnl": t.net_pnl,
            "exit_reason": t.exit_reason,
            "turnover": (t.entry_price + t.exit_price) * t.quantity,
            "holding_mins": (pd.Timestamp(t.exit_time) - pd.Timestamp(t.entry_time)).total_seconds() / 60.0,
        })

        if t.net_pnl > 0:
            wins += 1
            net_wins += t.net_pnl
        else:
            losses += 1
            net_losses += abs(t.net_pnl)

        if t.gross_pnl > 0:
            gross_wins += t.gross_pnl
        else:
            gross_losses += abs(t.gross_pnl)

        total_brokerage += t.brokerage
        total_statutory += t.statutory_fees
        total_slippage_spread += t.slippage
        total_turnover += (t.entry_price + t.exit_price) * t.quantity
        durations.append((pd.Timestamp(t.exit_time) - pd.Timestamp(t.entry_time)).total_seconds() / 60.0)

    trades_df = pd.DataFrame(records)

    gross_pnl = sum(t.gross_pnl for t in trades)
    total_costs = sum(t.transaction_cost for t in trades)
    net_pnl = sum(t.net_pnl for t in trades)

    win_rate_pct = (wins / total_trades) * 100.0
    gross_pf = (gross_wins / gross_losses) if gross_losses > 0 else (99.0 if gross_wins > 0 else 0.0)
    net_pf = (net_wins / net_losses) if net_losses > 0 else (99.0 if net_wins > 0 else 0.0)
    net_expectancy = net_pnl / total_trades

    avg_win = (net_wins / wins) if wins > 0 else 0.0
    avg_loss = (net_losses / losses) if losses > 0 else 0.0
    payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

    # Drawdown calculation
    equity_curve = [initial_capital]
    peak = initial_capital
    max_dd_inr = 0.0
    max_dd_pct = 0.0

    consecutive_losses = 0
    max_consecutive_losses = 0

    for t in trades:
        equity_curve.append(equity_curve[-1] + t.net_pnl)
        eq = equity_curve[-1]
        if eq > peak:
            peak = eq
        dd = peak - eq
        dd_pct = (dd / peak) * 100.0 if peak > 0 else 0.0
        if dd > max_dd_inr:
            max_dd_inr = dd
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

        if t.net_pnl <= 0:
            consecutive_losses += 1
            if consecutive_losses > max_consecutive_losses:
                max_consecutive_losses = consecutive_losses
        else:
            consecutive_losses = 0

    turnover_ratio = total_turnover / initial_capital
    avg_duration = float(np.mean(durations)) if durations else 0.0

    # Bootstrap 95% Confidence Interval for Net Expectancy (1,000 resamples)
    net_pnls = np.array([t.net_pnl for t in trades])
    np.random.seed(42)
    boot_means = []
    for _ in range(1000):
        resample = np.random.choice(net_pnls, size=total_trades, replace=True)
        boot_means.append(float(np.mean(resample)))
    ci_lower = float(np.percentile(boot_means, 2.5))
    ci_upper = float(np.percentile(boot_means, 97.5))

    return SEBV1BacktestResult(
        symbol=symbol,
        strategy_name=strategy_name,
        trades=trades,
        initial_capital=initial_capital,
        ending_capital=ending_capital,
        total_trades=total_trades,
        winning_trades=wins,
        losing_trades=losses,
        win_rate_pct=round(win_rate_pct, 2),
        gross_pnl=round(gross_pnl, 2),
        total_costs=round(total_costs, 2),
        brokerage_costs=round(total_brokerage, 2),
        statutory_costs=round(total_statutory, 2),
        slippage_and_spread_costs=round(total_slippage_spread, 2),
        net_pnl=round(net_pnl, 2),
        gross_profit_factor=round(gross_pf, 2),
        net_profit_factor=round(net_pf, 2),
        net_expectancy=round(net_expectancy, 2),
        avg_win=round(avg_win, 2),
        avg_loss=round(avg_loss, 2),
        payoff_ratio=round(payoff_ratio, 2),
        max_drawdown_inr=round(max_dd_inr, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
        max_consecutive_losses=max_consecutive_losses,
        total_turnover=round(total_turnover, 2),
        turnover_ratio=round(turnover_ratio, 2),
        avg_holding_duration_mins=round(avg_duration, 1),
        bootstrap_ci_95=(round(ci_lower, 2), round(ci_upper, 2)),
        trades_df=trades_df,
    )
