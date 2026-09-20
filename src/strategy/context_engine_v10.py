"""SignalForge — Phase 10: Relative Market Context & Cross-Asset Signal Engine.

Vectorized, past-only computation of:
1. Macro Benchmark Context (NIFTY 50)
2. Relative Strength (RS_15, RS_60, Relative RSI)
3. Cross-Sectional Ranking (Ranks 1..5 across tracked symbols)
4. Context Buckets (9 interpretable macro/stock interaction categories)
5. 8 Explicit Hypotheses (H1 to H8)
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict
import pandas as pd

REGIMES = ["TREND_UP", "TREND_DOWN", "RANGE", "HIGH_VOLATILITY", "LOW_VOLATILITY"]

CONTEXT_BUCKETS = [
    "STRONG MARKET + STRONG STOCK",
    "STRONG MARKET + WEAK STOCK",
    "WEAK MARKET + STRONG STOCK",
    "WEAK MARKET + WEAK STOCK",
    "NEUTRAL MARKET",
    "STRONG RELATIVE STRENGTH",
    "WEAK RELATIVE STRENGTH",
    "EXTREME RELATIVE STRENGTH",
    "EXTREME RELATIVE WEAKNESS",
]


def load_benchmark_data(path: str | Path, year: int = 2018) -> pd.DataFrame:
    """Load and causally process 1-minute benchmark data (e.g., NIFTY 50)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Benchmark file not found: {p}")

    df = pd.read_csv(p)
    # Parse Date and Time format: e.g., '09-01-2015' and '9:15:00'
    df["datetime"] = pd.to_datetime(df["Date"] + " " + df["Time"], format="mixed", dayfirst=True)
    df = df[(df["datetime"] >= f"{year}-01-01") & (df["datetime"] <= f"{year}-12-31 23:59:59")].copy()
    df = df.sort_values("datetime").reset_index(drop=True)
    df.set_index("datetime", inplace=True)

    # Standardize column casing
    col_map = {c: c.capitalize() for c in df.columns}
    df.rename(columns=col_map, inplace=True)

    # Precompute causal benchmark indicators
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    # Rolling returns
    df["bm_ret_5"] = close.pct_change(5).fillna(0.0)
    df["bm_ret_15"] = close.pct_change(15).fillna(0.0)
    df["bm_ret_60"] = close.pct_change(60).fillna(0.0)

    # EMAs
    df["bm_ema_20"] = close.ewm(span=20, adjust=False).mean()
    df["bm_ema_50"] = close.ewm(span=50, adjust=False).mean()
    df["bm_ema_dist"] = (close - df["bm_ema_20"]) / df["bm_ema_20"]

    # ATR 14
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["bm_atr_14"] = tr.rolling(14).mean().bfill()
    bm_atr_ma60 = df["bm_atr_14"].rolling(60).mean().bfill()

    # RSI 14
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean().replace(0.0, 1e-9)
    rs = avg_gain / avg_loss
    df["bm_rsi_14"] = (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)

    # Benchmark Market Regime
    cond_up = (df["bm_ema_20"] > df["bm_ema_50"]) & (df["bm_ret_15"] > 0.0002)
    cond_down = (df["bm_ema_20"] < df["bm_ema_50"]) & (df["bm_ret_15"] < -0.0002)
    cond_hvol = df["bm_atr_14"] > (bm_atr_ma60 * 1.25)
    cond_lvol = df["bm_atr_14"] < (bm_atr_ma60 * 0.75)

    regimes = pd.Series("RANGE", index=df.index)
    regimes[cond_hvol] = "HIGH_VOLATILITY"
    regimes[cond_lvol] = "LOW_VOLATILITY"
    regimes[cond_up] = "TREND_UP"
    regimes[cond_down] = "TREND_DOWN"
    df["bm_regime"] = regimes

    return df


def precompute_stock_features(df_stock: pd.DataFrame, df_bm: pd.DataFrame) -> pd.DataFrame:
    """Compute causal stock features and align with benchmark data."""
    df = df_stock.copy()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    # Stock returns
    df["stock_ret_5"] = close.pct_change(5).fillna(0.0)
    df["stock_ret_15"] = close.pct_change(15).fillna(0.0)
    df["stock_ret_60"] = close.pct_change(60).fillna(0.0)

    # Stock EMAs
    df["stock_ema_20"] = close.ewm(span=20, adjust=False).mean()
    df["stock_ema_50"] = close.ewm(span=50, adjust=False).mean()
    df["stock_ema_dist"] = (close - df["stock_ema_20"]) / df["stock_ema_20"]

    # ATR 14
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["stock_atr_14"] = tr.rolling(14).mean().bfill()

    # RSI 14
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean().replace(0.0, 1e-9)
    rs = avg_gain / avg_loss
    df["stock_rsi_14"] = (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)

    # Align benchmark features onto stock datetime index
    bm_cols = ["Close", "bm_ret_5", "bm_ret_15", "bm_ret_60", "bm_ema_20", "bm_ema_50", "bm_atr_14", "bm_rsi_14", "bm_regime"]
    aligned_bm = df_bm[bm_cols].reindex(df.index).ffill()
    aligned_bm.rename(columns={"Close": "bm_close"}, inplace=True)

    for c in aligned_bm.columns:
        df[c] = aligned_bm[c]

    # Relative Strength Metrics
    df["rs_5"] = df["stock_ret_5"] - df["bm_ret_5"]
    df["rs_15"] = df["stock_ret_15"] - df["bm_ret_15"]
    df["rs_60"] = df["stock_ret_60"] - df["bm_ret_60"]
    df["rel_rsi"] = df["stock_rsi_14"] - df["bm_rsi_14"]

    return df


def compute_cross_sectional_ranks(stock_dfs: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Compute strictly causal cross-sectional ranks (1 to 5) across symbols at each timestamp."""
    # Build a combined table of rolling 15m return across symbols
    ret_dict = {}
    for sym, df in stock_dfs.items():
        ret_dict[sym] = df["stock_ret_15"]

    df_rets = pd.DataFrame(ret_dict)

    # Rank ascending=False: highest return gets rank 1, lowest gets rank 5
    ranks = df_rets.rank(axis=1, ascending=False, method="first")
    pct_ranks = (5.0 - ranks) / 4.0  # 1.0 for rank 1, 0.0 for rank 5

    out_dfs = {}
    for sym, df in stock_dfs.items():
        df_out = df.copy()
        df_out["cs_rank"] = ranks[sym]
        df_out["cs_pct"] = pct_ranks[sym]
        out_dfs[sym] = df_out

    return out_dfs


def classify_context_bucket(stock_ret_15: float, bm_ret_15: float, rs_15: float) -> str:
    """Map causal metrics at timestamp T into one of 9 interpretable context buckets."""
    # Extreme RS checks first
    if rs_15 > 0.005:
        return "EXTREME RELATIVE STRENGTH"
    if rs_15 < -0.005:
        return "EXTREME RELATIVE WEAKNESS"
    if rs_15 > 0.002:
        return "STRONG RELATIVE STRENGTH"
    if rs_15 < -0.002:
        return "WEAK RELATIVE STRENGTH"

    # Neutral market check
    if abs(bm_ret_15) < 0.0004:
        return "NEUTRAL MARKET"

    # Market direction vs Stock direction
    if bm_ret_15 >= 0.0004:
        if stock_ret_15 >= 0.0004:
            return "STRONG MARKET + STRONG STOCK"
        else:
            return "STRONG MARKET + WEAK STOCK"
    else:
        if stock_ret_15 >= 0.0004:
            return "WEAK MARKET + STRONG STOCK"
        else:
            return "WEAK MARKET + WEAK STOCK"


def evaluate_hypotheses_for_trade(
    direction: str,
    stock_ret_15: float,
    bm_ret_15: float,
    rs_15: float,
    bm_regime: str,
    bm_ema_20: float,
    bm_ema_50: float,
    stock_ema_dist: float,
    cs_rank: float,
) -> Dict[str, bool]:
    """Evaluate candidate trade against 8 explicit, interpretable hypotheses."""
    is_long = direction == "LONG"

    # H1: Stock setup + Relative Strength Confirmation
    # LONG requires positive relative strength; SHORT requires negative relative strength
    h1 = (rs_15 > 0.0) if is_long else (rs_15 < 0.0)

    # H2: Stock setup + Market Trend Agreement
    # Market trending in trade direction (NIFTY EMA20 > EMA50 for LONG, EMA20 < EMA50 for SHORT)
    h2 = (bm_ema_20 > bm_ema_50 and bm_ret_15 > 0.0) if is_long else (bm_ema_20 < bm_ema_50 and bm_ret_15 < 0.0)

    # H3: Dual Alignment (Market Agreement + Relative Strength)
    h3 = h1 and h2

    # H4: Cross-Sectional Leaders (Rank 1-2 for LONG, Rank 4-5 for SHORT)
    h4 = (cs_rank <= 2.0) if is_long else (cs_rank >= 4.0)

    # H5: Extreme Relative Strength Divergence / Mean-Reversion
    # Stock oversold relative to strong market, or stock overbought relative to weak market
    h5 = (rs_15 < -0.003 and bm_ret_15 > 0.0005) if is_long else (rs_15 > 0.003 and bm_ret_15 < -0.0005)

    # H6: Market Agreement + Pullback Confirmation
    # Market aligned, and stock has pulled back near its EMA (small distance from EMA20)
    h6 = h2 and (abs(stock_ema_dist) < 0.0025)

    # H7: Strong RS + Favorable Market Regime (Non-choppy trend regime in market)
    h7 = h1 and (bm_regime in ["TREND_UP", "TREND_DOWN"])

    # H8: Full Consensus Signal (Market Agreement + Top/Bottom CS Rank + Positive RS)
    h8 = h1 and h2 and h4

    return {
        "H1_RS_CONFIRMATION": bool(h1),
        "H2_MARKET_AGREEMENT": bool(h2),
        "H3_DUAL_ALIGNMENT": bool(h3),
        "H4_CS_LEADERS": bool(h4),
        "H5_RS_DIVERGENCE": bool(h5),
        "H6_MARKET_PULLBACK": bool(h6),
        "H7_REGIME_RS": bool(h7),
        "H8_FULL_CONSENSUS": bool(h8),
    }
