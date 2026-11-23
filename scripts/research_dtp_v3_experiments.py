"""
SignalForge — Phase 32I: DTP-V3 Strategy Research & Hypothesis Testing
Explores systematic improvements to DTP-V2 on the authorized 2017-2019 dataset.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_phase32d_3_dtp_v1_expanded_validation import (
    load_and_resample_21_universe,
    APPROVED_21_SYMBOLS,
    EXPANDED_SECTOR_MAP,
    EXPANDED_ISIN_MAP,
)
from src.strategy.dtp_v2.config import DTPV2Config, DTPRegimeState, DTPExitReason, OrderAction
from src.strategy.dtp_v2.cost_integration import calculate_dtp_roundtrip_costs
from src.strategy.dtp_v2.market_filter import evaluate_breadth_regime

# Calculate Choppiness Index
def calculate_choppiness_index(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    sum_tr = tr.rolling(window=period).sum()
    max_hi = high.rolling(window=period).max()
    min_lo = low.rolling(window=period).min()
    range_hl = (max_hi - min_lo).replace(0.0, np.nan)
    ci = 100.0 * np.log10(sum_tr / range_hl) / np.log10(period)
    return ci.fillna(50.0)

# Precompute indicators with additional candidate indicators
def prepare_indicators(df: pd.DataFrame, cfg: DTPV2Config) -> pd.DataFrame:
    df = df.copy()
    c = df["close"]
    h = df["high"]
    l = df["low"]
    v = df["volume"]

    df["ema_fast"] = c.ewm(span=cfg.ema_fast_period, adjust=False).mean()
    df["ema_slow"] = c.ewm(span=cfg.ema_slow_period, adjust=False).mean()
    df["sma_trend"] = c.rolling(window=cfg.sma_trend_period).mean()

    # TR & ATR
    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    df["tr"] = tr
    df["atr"] = tr.ewm(alpha=1.0 / cfg.atr_period, adjust=False).mean()

    # RSI
    delta = c.diff()
    gain = delta.clip(lower=0.0).ewm(alpha=1.0 / cfg.rsi_period, adjust=False).mean()
    loss = (-delta).clip(lower=0.0).ewm(alpha=1.0 / cfg.rsi_period, adjust=False).mean()
    rs = gain / loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.fillna(100.0)
    rsi.loc[(gain == 0.0) & (loss == 0.0)] = 50.0
    df["rsi"] = rsi

    # ADX
    up_move = h - h.shift(1)
    down_move = l.shift(1) - l
    plus_dm = np.where((up_move > down_move) & (up_move > 0.0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0.0), down_move, 0.0)
    p_dm_s = pd.Series(plus_dm, index=df.index).ewm(alpha=1.0 / cfg.adx_period, adjust=False).mean()
    m_dm_s = pd.Series(minus_dm, index=df.index).ewm(alpha=1.0 / cfg.adx_period, adjust=False).mean()
    plus_di = 100.0 * (p_dm_s / df["atr"].replace(0.0, np.nan))
    minus_di = 100.0 * (m_dm_s / df["atr"].replace(0.0, np.nan))
    di_sum = (plus_di + minus_di).replace(0.0, np.nan)
    dx = 100.0 * ((plus_di - minus_di).abs() / di_sum).fillna(0.0)
    df["adx"] = dx.ewm(alpha=1.0 / cfg.adx_period, adjust=False).mean()
    df["plus_di"] = plus_di
    df["minus_di"] = minus_di

    # Volume SMA & RVOL
    df["volume_sma"] = v.rolling(window=cfg.volume_sma_period).mean()

    # Bollinger Bands
    sma20 = c.rolling(window=cfg.bb_period).mean()
    std20 = c.rolling(window=cfg.bb_period).std()
    df["bb_upper"] = sma20 + (cfg.bb_std_mult * std20)
    df["bb_lower"] = sma20 - (cfg.bb_std_mult * std20)

    # Swings
    df["swing_high_20"] = h.rolling(window=20).max()
    df["swing_low_20"] = l.rolling(window=20).min()

    # Choppiness Index
    df["chop_index"] = calculate_choppiness_index(h, l, c, period=14)

    # Relative strength (proxy: momentum vs 20-day return)
    ret20 = c.pct_change(periods=20).fillna(0.0)
    df["relative_strength"] = ret20

    return df

print("Module research_dtp_v3_experiments ready.")

from dataclasses import dataclass

@dataclass
class ExperimentConfig:
    name: str
    risk_pct: float = 0.01
    adx_min: float = 20.0
    use_chop_filter: bool = False
    max_chop_index: float = 58.0
    ema20_proximity_pct: float = 0.010
    pullback_window_days: int = 3
    require_upper_half_close: bool = False
    adaptive_stop: bool = False
    min_stop_atr: float = 1.5
    breakeven_r: float = 1.0
    trailing_r: float = 1.5
    trailing_atr_mult: float = 2.0
    profit_target_r: float = 3.0
    max_holding_sessions: int = 10
    dynamic_time_exit: bool = False
    max_concurrent_positions: int = 3
    max_position_allocation_pct: float = 0.333
    use_stress_costs: bool = False
    initial_capital: float = 100000.0

@dataclass
class PosState:
    symbol: str
    entry_date: Any
    entry_price: float
    quantity: int
    initial_stop_price: float
    current_stop_price: float
    r_distance: float
    highest_high: float
    highest_close: float
    holding_days: int = 0
    is_breakeven_activated: bool = False
    is_trailing_activated: bool = False
    consecutive_closes_below_ema50: int = 0

def run_experiment(
    exp: ExperimentConfig,
    universe_daily: Dict[str, pd.DataFrame],
    trading_dates: List[pd.Timestamp],
) -> Dict[str, Any]:
    cfg = DTPV2Config(
        risk_fraction_per_trade=exp.risk_pct,
        max_concurrent_positions=exp.max_concurrent_positions,
        max_position_allocation_pct=exp.max_position_allocation_pct,
        symbol_sector_map=EXPANDED_SECTOR_MAP,
        symbol_isin_map=EXPANDED_ISIN_MAP,
    )

    positions: Dict[str, PosState] = {}
    pending_signals: Dict[str, Any] = {}
    trades: List[Dict[str, Any]] = []
    cash = exp.initial_capital
    portfolio_equity = exp.initial_capital
    daily_records: List[Dict[str, Any]] = []
    peak_equity = exp.initial_capital
    max_drawdown = 0.0

    # Sector mapping
    sector_map = EXPANDED_SECTOR_MAP
    isin_map = EXPANDED_ISIN_MAP

    trade_id = 0

    for day_idx, current_ts in enumerate(trading_dates):
        current_dt = current_ts.date()

        # Step A: Next-Day Open Execution
        if pending_signals:
            # Deterministic sort: lowest risk distance first, then symbol
            sorted_pending = sorted(pending_signals.items(), key=lambda x: (x[1]["r_distance"], x[0]))

            for sym, sig in sorted_pending:
                bar = universe_daily[sym].loc[current_ts]
                today_open = float(bar["open"])

                # Check gap up
                trigger = sig["entry_trigger_price"]
                if today_open > trigger * (1.0 + cfg.max_gap_up_pct):
                    continue
                # Check gap down below stop
                if today_open <= sig["initial_stop_price"]:
                    continue

                friction_rate = (cfg.execution_slippage_bps + cfg.execution_spread_bps) / 10000.0
                fill_price = today_open * (1.0 + friction_rate)

                # Current equity
                curr_prices = {s: float(universe_daily[s].loc[current_ts, "open"]) for s in APPROVED_21_SYMBOLS}
                pos_val = sum(positions[s].quantity * curr_prices[s] for s in positions)
                equity = cash + pos_val

                # Portfolio constraints
                if len(positions) >= exp.max_concurrent_positions:
                    continue
                if sym in positions:
                    continue

                sector = sector_map.get(sym, "General")
                sec_val = sum(positions[s].quantity * curr_prices[s] for s in positions if sector_map.get(s, "General") == sector)
                if (sec_val / equity) >= cfg.max_sector_exposure_pct:
                    continue

                # Position sizing based on risk
                risk_amt = equity * exp.risk_pct
                stop_dist = max(fill_price - sig["initial_stop_price"], 0.01)
                raw_shares = risk_amt / stop_dist

                # Max position allocation cap
                max_notional = equity * exp.max_position_allocation_pct
                shares_cap = max_notional / fill_price
                shares = int(min(raw_shares, shares_cap))

                # Cash affordability
                cost_est = shares * fill_price * 1.002
                if cost_est > cash:
                    shares = int((cash * 0.99) / fill_price)

                if shares <= 0:
                    continue

                trade_notional = shares * fill_price
                if trade_notional < cfg.min_trade_notional:
                    continue

                # Execute entry
                cash -= trade_notional
                trade_id += 1
                positions[sym] = PosState(
                    symbol=sym,
                    entry_date=current_dt,
                    entry_price=fill_price,
                    quantity=shares,
                    initial_stop_price=sig["initial_stop_price"],
                    current_stop_price=sig["initial_stop_price"],
                    r_distance=sig["r_distance"],
                    highest_high=fill_price,
                    highest_close=fill_price,
                )

            pending_signals.clear()

        # Step B: Session Exits
        full_exits = []
        for sym, pos in list(positions.items()):
            bar = universe_daily[sym].loc[current_ts]
            high = float(bar["high"])
            low = float(bar["low"])
            close = float(bar["close"])
            open_px = float(bar["open"])
            atr = float(bar["atr"])
            ema50 = float(bar["ema_slow"])
            rsi = float(bar["rsi"])
            bb_upper = float(bar["bb_upper"])

            pos.holding_days += 1
            friction_rate = (cfg.execution_slippage_bps + cfg.execution_spread_bps) / 10000.0

            if high > pos.highest_high:
                pos.highest_high = high
            if close > pos.highest_close:
                pos.highest_close = close

            # Last day liquidation
            if day_idx == len(trading_dates) - 1:
                exit_px = close * (1.0 - friction_rate)
                full_exits.append((sym, "MANUAL_CLOSE", exit_px))
                continue

            # 1. Stop loss
            if low <= pos.current_stop_price:
                raw_exit = min(open_px, pos.current_stop_price)
                exit_px = raw_exit * (1.0 - friction_rate)
                reason = "STOP_LOSS"
                if pos.is_trailing_activated:
                    reason = "TRAILING_STOP"
                elif pos.is_breakeven_activated:
                    reason = "BREAKEVEN_STOP"
                full_exits.append((sym, reason, exit_px))
                continue

            # 2. Advance Trailing Stops
            excursion_r = (pos.highest_high - pos.entry_price) / pos.r_distance

            # Breakeven
            if excursion_r >= exp.breakeven_r and not pos.is_breakeven_activated:
                pos.is_breakeven_activated = True
                be_stop = pos.entry_price * 1.005
                pos.current_stop_price = max(pos.current_stop_price, be_stop)

            # Chandelier trailing
            if excursion_r >= exp.trailing_r:
                pos.is_trailing_activated = True
                chand_stop = pos.highest_high - (exp.trailing_atr_mult * atr)
                pos.current_stop_price = max(pos.current_stop_price, chand_stop)

            # 3. Full Profit Target
            target_px = pos.entry_price + (exp.profit_target_r * pos.r_distance)
            if high >= target_px:
                exit_px = target_px * (1.0 - friction_rate)
                full_exits.append((sym, "PROFIT_TARGET", exit_px))
                continue

            # 4. Overbought Blowoff
            if rsi >= cfg.rsi_overbought_threshold and high >= bb_upper:
                exit_px = close * (1.0 - friction_rate)
                full_exits.append((sym, "DYNAMIC_OVERBOUGHT", exit_px))
                continue

            # 5. Trend Breakdown
            if close < ema50:
                pos.consecutive_closes_below_ema50 += 1
            else:
                pos.consecutive_closes_below_ema50 = 0

            if pos.consecutive_closes_below_ema50 >= cfg.consecutive_breakdown_bars:
                exit_px = close * (1.0 - friction_rate)
                full_exits.append((sym, "TREND_BREAKDOWN", exit_px))
                continue

            # 6. Time limit exit
            if exp.dynamic_time_exit:
                # Dynamic: session 10 exit only if excursion < 1.0R and close < entry
                # If profitable and above EMA20, allow up to 15 sessions
                if pos.holding_days >= exp.max_holding_sessions:
                    if excursion_r < 1.0 and close <= pos.entry_price:
                        exit_px = close * (1.0 - friction_rate)
                        full_exits.append((sym, "TIME_LIMIT", exit_px))
                        continue
                    elif pos.holding_days >= 15:
                        exit_px = close * (1.0 - friction_rate)
                        full_exits.append((sym, "TIME_LIMIT", exit_px))
                        continue
            else:
                if pos.holding_days >= exp.max_holding_sessions and excursion_r < exp.trailing_r:
                    exit_px = close * (1.0 - friction_rate)
                    full_exits.append((sym, "TIME_LIMIT", exit_px))
                    continue

        # Process exits
        for sym, reason, exit_px in full_exits:
            pos = positions.pop(sym)
            isin = isin_map.get(sym, "INE000000000")
            breakdown, c_summary = calculate_dtp_roundtrip_costs(
                symbol=sym,
                isin=isin,
                entry_date=pos.entry_date,
                exit_date=current_dt,
                entry_price=pos.entry_price,
                exit_price=exit_px,
                quantity=pos.quantity,
                use_stress_profile=exp.use_stress_costs,
            )

            gross_pnl = (exit_px - pos.entry_price) * pos.quantity
            tot_costs = float(c_summary.total_friction_costs)
            net_pnl = gross_pnl - tot_costs
            cash += float(c_summary.sell_turnover) - float(c_summary.total_friction_costs)

            trades.append({
                "symbol": sym,
                "entry_date": pos.entry_date,
                "exit_date": current_dt,
                "entry_price": pos.entry_price,
                "exit_price": exit_px,
                "quantity": pos.quantity,
                "holding_days": pos.holding_days,
                "exit_reason": reason,
                "gross_pnl": gross_pnl,
                "total_costs": tot_costs,
                "net_pnl": net_pnl,
            })

        # Step C: EOD Signal Evaluation for Bar T
        # Market regime
        regime = evaluate_breadth_regime(universe_daily, bar_idx=day_idx, config=cfg)
        if regime != DTPRegimeState.BEARISH and regime != DTPRegimeState.UNKNOWN:
            for sym in APPROVED_21_SYMBOLS:
                if sym in positions:
                    continue
                df_sym = universe_daily[sym]
                if day_idx < max(cfg.ema_slow_period, exp.pullback_window_days + 1):
                    continue

                row = df_sym.iloc[day_idx]
                c = float(row["close"])
                o = float(row["open"])
                h = float(row["high"])
                l = float(row["low"])
                atr = float(row["atr"])
                ema20 = float(row["ema_fast"])
                ema50 = float(row["ema_slow"])
                adx = float(row["adx"])
                chop = float(row.get("chop_index", 50.0))

                # Trend Alignment
                if "sma_trend" in row and pd.notna(row["sma_trend"]) and c < row["sma_trend"]:
                    continue
                if ema20 <= ema50:
                    continue
                # EMA 50 slope
                lookback = max(0, day_idx - 5)
                if ema50 <= df_sym["ema_slow"].iloc[lookback]:
                    continue
                if adx < exp.adx_min:
                    continue
                if "relative_strength" in row and pd.notna(row["relative_strength"]) and row["relative_strength"] < 0.0:
                    continue

                # Choppiness Filter
                if exp.use_chop_filter and chop > exp.max_chop_index:
                    continue

                # Pullback identification
                rsi = float(row["rsi"])
                if rsi < cfg.rsi_pullback_min or rsi > cfg.rsi_pullback_max:
                    continue

                # EMA20 proximity
                ema_dist = abs(l - ema20) / ema20
                if ema_dist > exp.ema20_proximity_pct and l > ema20:
                    continue

                # Fibonacci retrace
                if "swing_high_20" in row and "swing_low_20" in row:
                    sh = row["swing_high_20"]
                    sl = row["swing_low_20"]
                    if pd.notna(sh) and pd.notna(sl) and sh > sl:
                        retrace = (sh - l) / (sh - sl)
                        if retrace > cfg.max_retracement_depth:
                            continue

                # Volume contraction on pullback
                vol = float(row["volume"])
                vol_sma = float(row["volume_sma"])
                if pd.notna(vol_sma) and vol_sma > 0:
                    if vol > vol_sma * cfg.volume_contraction_ratio:
                        continue

                # Reversal candle check
                is_bullish = c > o
                body = abs(c - o)
                lower_wick = min(o, c) - l
                candle_range = h - l
                is_hammer = (lower_wick >= 2.0 * body) and (candle_range > 0) if body > 0 else False
                if not (is_bullish or is_hammer):
                    continue

                # Optional: upper half close filter
                if exp.require_upper_half_close and candle_range > 0:
                    if (c - l) / candle_range < 0.50:
                        continue

                # Reclaim 20 EMA
                if c < ema20:
                    continue

                # Expanding volume
                prev_vol = float(df_sym["volume"].iloc[day_idx - 1]) if day_idx > 0 else vol
                vol_ok = (vol > prev_vol) or (pd.notna(vol_sma) and vol >= vol_sma * cfg.volume_expansion_ratio)
                if not vol_ok:
                    continue

                # Stop calculation
                w_start = max(0, day_idx - exp.pullback_window_days)
                lowest_low = float(df_sym["low"].iloc[w_start : day_idx + 1].min())

                if exp.adaptive_stop:
                    # Adaptive stop: ensure stop is at least 1.5 * ATR below close, and lowest_low buffered
                    atr_stop = c - (2.0 * atr)
                    buff_low = lowest_low - (0.2 * atr)
                    initial_stop = min(buff_low, atr_stop)
                    # Floor at 1.5 * ATR
                    if (c - initial_stop) < exp.min_stop_atr * atr:
                        initial_stop = c - (exp.min_stop_atr * atr)
                else:
                    atr_stop = c - (cfg.initial_stop_atr_mult * atr)
                    initial_stop = min(lowest_low, atr_stop)

                # Cap stop at 3.0 * ATR
                if (c - initial_stop) > cfg.max_stop_atr_mult * atr:
                    initial_stop = c - (cfg.max_stop_atr_mult * atr)

                r_dist = c - initial_stop
                if r_dist <= 0:
                    continue

                pending_signals[sym] = {
                    "entry_trigger_price": c,
                    "initial_stop_price": initial_stop,
                    "r_distance": r_dist,
                }

        # Track daily equity
        curr_eod_px = {s: float(universe_daily[s].loc[current_ts, "close"]) for s in APPROVED_21_SYMBOLS}
        pos_val_eod = sum(positions[s].quantity * curr_eod_px[s] for s in positions)
        eod_equity = cash + pos_val_eod
        if eod_equity > peak_equity:
            peak_equity = eod_equity
        dd = (peak_equity - eod_equity) / peak_equity
        if dd > max_drawdown:
            max_drawdown = dd

    # Summary metrics
    n_trades = len(trades)
    df_t = pd.DataFrame(trades) if n_trades > 0 else pd.DataFrame(columns=["net_pnl", "gross_pnl", "total_costs", "holding_days", "entry_date"])
    net_pnl = float(df_t["net_pnl"].sum()) if n_trades > 0 else 0.0
    gross_pnl = float(df_t["gross_pnl"].sum()) if n_trades > 0 else 0.0
    tot_costs = float(df_t["total_costs"].sum()) if n_trades > 0 else 0.0
    wins = len(df_t[df_t["net_pnl"] > 0]) if n_trades > 0 else 0
    losses = len(df_t[df_t["net_pnl"] <= 0]) if n_trades > 0 else 0
    wr = (wins / n_trades * 100.0) if n_trades > 0 else 0.0
    g_wins = float(df_t[df_t["net_pnl"] > 0]["net_pnl"].sum()) if wins > 0 else 0.0
    g_loss = float(abs(df_t[df_t["net_pnl"] <= 0]["net_pnl"].sum())) if losses > 0 else 0.0
    pf = round(g_wins / g_loss, 2) if g_loss > 0 else 999.0
    avg_win = g_wins / wins if wins > 0 else 0.0
    avg_loss = g_loss / losses if losses > 0 else 0.0
    payoff = round(avg_win / avg_loss, 2) if avg_loss > 0 else 999.0
    cagr = round(((eod_equity / exp.initial_capital) ** (1.0 / 3.0) - 1.0) * 100.0, 2)
    avg_hold = round(float(df_t["holding_days"].mean()), 1) if n_trades > 0 else 0.0

    # Yearly breakdown
    yearly = {}
    if n_trades > 0:
        df_t["year"] = pd.to_datetime(df_t["exit_date"]).dt.year
        for yr, grp in df_t.groupby("year"):
            yearly[yr] = {
                "trades": len(grp),
                "net_pnl": round(float(grp["net_pnl"].sum()), 2),
                "wr": round(len(grp[grp["net_pnl"] > 0]) / len(grp) * 100.0, 1),
            }

    return {
        "name": exp.name,
        "risk_pct": exp.risk_pct,
        "trades": n_trades,
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(wr, 2),
        "gross_pnl": round(gross_pnl, 2),
        "total_costs": round(tot_costs, 2),
        "net_pnl": round(net_pnl, 2),
        "net_pf": pf,
        "payoff": payoff,
        "max_dd_pct": round(max_drawdown * 100.0, 2),
        "cagr_pct": cagr,
        "avg_hold": avg_hold,
        "yearly": yearly,
        "final_equity": round(eod_equity, 2),
    }


def main():
    print("=" * 80)
    print("Loading 2017-2019 Universe for Research Experiments...")
    print("=" * 80)
    raw_universe = load_and_resample_21_universe()
    cfg_default = DTPV2Config(symbol_sector_map=EXPANDED_SECTOR_MAP, symbol_isin_map=EXPANDED_ISIN_MAP)

    universe_augmented = {}
    for sym in APPROVED_21_SYMBOLS:
        universe_augmented[sym] = prepare_indicators(raw_universe[sym], cfg_default)

    trading_dates = list(raw_universe[APPROVED_21_SYMBOLS[0]].index)
    print(f"Loaded {len(universe_augmented)} symbols across {len(trading_dates)} trading sessions.")

    experiments = [
        # Baseline: Exact DTP-V2 logic
        ExperimentConfig(name="01_Baseline_DTP_V2_1pct", risk_pct=0.01),

        # Exp A: Choppiness Filter only
        ExperimentConfig(name="02_Chop_Filter_CI58", risk_pct=0.01, use_chop_filter=True, max_chop_index=58.0),
        ExperimentConfig(name="03_Chop_Filter_CI60", risk_pct=0.01, use_chop_filter=True, max_chop_index=60.0),

        # Exp B: Adaptive Stop Loss only
        ExperimentConfig(name="04_Adaptive_Stop_1.5ATR", risk_pct=0.01, adaptive_stop=True, min_stop_atr=1.5),

        # Exp C: Entry confirmation (Upper half close)
        ExperimentConfig(name="05_Upper_Half_Close", risk_pct=0.01, require_upper_half_close=True),

        # Exp D: Pullback Proximity & Window (Frequency improvement)
        ExperimentConfig(name="06_Pullback_Prox_1.8pct", risk_pct=0.01, ema20_proximity_pct=0.018),
        ExperimentConfig(name="07_Pullback_Window_4days", risk_pct=0.01, pullback_window_days=4),

        # Exp E: Exit Management (Dynamic time exit + BE at 1.2R)
        ExperimentConfig(name="08_Dynamic_Time_Exit_BE1.2R", risk_pct=0.01, dynamic_time_exit=True, breakeven_r=1.2),

        # Exp F: Combined candidates (DTP-V3 Prototype at 1% risk)
        ExperimentConfig(
            name="09_Combined_V3_Prototype_1pct",
            risk_pct=0.01,
            adx_min=18.0,
            use_chop_filter=True,
            max_chop_index=60.0,
            ema20_proximity_pct=0.018,
            pullback_window_days=4,
            adaptive_stop=True,
            min_stop_atr=1.5,
            breakeven_r=1.2,
            dynamic_time_exit=True,
        ),

        # Exp G: Combined Prototype at 2% risk
        ExperimentConfig(
            name="10_Combined_V3_Prototype_2pct",
            risk_pct=0.02,
            adx_min=18.0,
            use_chop_filter=True,
            max_chop_index=60.0,
            ema20_proximity_pct=0.018,
            pullback_window_days=4,
            adaptive_stop=True,
            min_stop_atr=1.5,
            breakeven_r=1.2,
            dynamic_time_exit=True,
        ),

        # Exp H: Combined Prototype at 3% risk
        ExperimentConfig(
            name="11_Combined_V3_Prototype_3pct",
            risk_pct=0.03,
            adx_min=18.0,
            use_chop_filter=True,
            max_chop_index=60.0,
            ema20_proximity_pct=0.018,
            pullback_window_days=4,
            adaptive_stop=True,
            min_stop_atr=1.5,
            breakeven_r=1.2,
            dynamic_time_exit=True,
        ),
    ]

    print("\nRunning research experiments...")
    results = []
    for exp in experiments:
        res = run_experiment(exp, universe_augmented, trading_dates)
        results.append(res)
        print(f"\n[{res['name']}]")
        print(f"  Trades: {res['trades']} | WinRate: {res['win_rate_pct']}% | Net PnL: ₹{res['net_pnl']:,.2f} | PF: {res['net_pf']} | Payoff: {res['payoff']} | MaxDD: {res['max_dd_pct']}% | CAGR: {res['cagr_pct']}%")
        print(f"  Yearly: {res['yearly']}")

if __name__ == "__main__":
    main()
