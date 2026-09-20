from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------
# SignalForge imports
# ---------------------------------------------------------------------

from src.backtest.engine import Position, run_backtest
from src.signals.signal_engine import generate_signal
from src.strategy.backtest_strategy import (
    StrategyConfig,
    _make_cursors,
    calculate_timeframe_indicators,
)


# =====================================================================
# CONFIGURATION
# =====================================================================

DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "historical"
    / "nifty50_1m_signalforge.csv"
)

INITIAL_CAPITAL = 100_000.0
QUANTITY = 1
TRANSACTION_COST_RATE = 0.0001

TIMEFRAMES = (
    "30m",
    "15m",
    "10m",
    "5m",
)

# ---------------------------------------------------------------------
# Causal regime definitions
#
# Direction:
#   previous completed session return >= +0.50% -> TREND_UP
#   previous completed session return <= -0.50% -> TREND_DOWN
#   otherwise -> SIDEWAYS
#
# Volatility:
#   previous completed session realized volatility is compared with
#   the trailing median of earlier completed sessions.
#
# The regime used for a trade is therefore known BEFORE the entry
# session begins.
# ---------------------------------------------------------------------

DIRECTION_THRESHOLD_PCT = 0.50

VOLATILITY_MEDIAN_WINDOW = 60
VOLATILITY_MIN_PERIODS = 20


# =====================================================================
# DATA
# =====================================================================

def load_data() -> pd.DataFrame:
    """Load and validate the complete historical dataset."""

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Historical data not found:\n{DATA_PATH}"
        )

    data = pd.read_csv(
        DATA_PATH,
        parse_dates=["timestamp"],
    )

    required = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    missing = [
        column
        for column in required
        if column not in data.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    data = (
        data
        .set_index("timestamp")
        .sort_index()
    )

    if data.empty:
        raise ValueError(
            "Historical dataset is empty."
        )

    if data.index.has_duplicates:
        raise ValueError(
            "Historical dataset contains duplicate timestamps."
        )

    if not data.index.is_monotonic_increasing:
        raise ValueError(
            "Historical dataset must be chronologically ordered."
        )

    return data


# =====================================================================
# FROZEN BASELINE STRATEGY
# =====================================================================

def make_config() -> StrategyConfig:
    """Return the exact frozen baseline configuration."""

    return StrategyConfig(
        ema_fast_period=20,
        ema_slow_period=50,
        rsi_period=14,
        atr_period=14,
        rvol_period=20,
        minimum_rvol=1.5,
        minimum_atr=0.0,
        use_rvol=False,
    )


def create_baseline_signal_function(
    data: pd.DataFrame,
    config: StrategyConfig,
):
    """
    Create the same baseline signal path used in Phase 7.1 and 7.2.

    No parameter optimization or candidate strategy is used.
    """

    timeframe_data = calculate_timeframe_indicators(
        data,
        config,
    )

    cursors = _make_cursors(
        timeframe_data,
        config.use_rvol,
    )

    def signal_function(
        row: pd.Series,
        previous_row: pd.Series | None,
    ) -> Position | None:

        timestamp = pd.Timestamp(row.name)

        state_30m = cursors["30m"].update(timestamp)
        state_15m = cursors["15m"].update(timestamp)
        state_10m = cursors["10m"].update(timestamp)
        state_5m = cursors["5m"].update(timestamp)

        if (
            state_30m is None
            or state_15m is None
            or state_10m is None
            or state_5m is None
        ):
            return None

        result = generate_signal(
            state_30m,
            state_15m,
            state_10m,
            state_5m,
            minimum_rvol=config.minimum_rvol,
            minimum_atr=config.minimum_atr,
            use_rvol=config.use_rvol,
        )

        if result.signal.value == "BUY":
            return Position.LONG

        if result.signal.value == "SELL":
            return Position.SHORT

        return None

    return signal_function


# =====================================================================
# CAUSAL SESSION FEATURES
# =====================================================================

def calculate_session_features(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate completed-session features.

    The resulting regime labels are shifted before being used for
    trades, preventing current-session information from leaking into
    the classification.
    """

    rows = []

    grouped = data.groupby(
        data.index.date
    )

    for session_date, session in grouped:

        if session.empty:
            continue

        first_open = float(
            session["open"].iloc[0]
        )

        last_close = float(
            session["close"].iloc[-1]
        )

        session_high = float(
            session["high"].max()
        )

        session_low = float(
            session["low"].min()
        )

        if first_open <= 0:
            continue

        session_return = (
            last_close / first_open - 1.0
        ) * 100.0

        session_range = (
            session_high
            - session_low
        ) / first_open * 100.0

        minute_returns = (
            session["close"]
            .pct_change()
            .dropna()
        )

        if minute_returns.empty:
            realized_vol = 0.0
        else:
            realized_vol = (
                minute_returns.std()
                * np.sqrt(len(minute_returns))
                * 100.0
            )

        rows.append(
            {
                "date": pd.Timestamp(session_date),
                "session_return_pct": session_return,
                "session_range_pct": session_range,
                "realized_vol_pct": realized_vol,
            }
        )

    features = pd.DataFrame(rows)

    if features.empty:
        raise ValueError(
            "Unable to calculate session features."
        )

    features = (
        features
        .set_index("date")
        .sort_index()
    )

    # -------------------------------------------------------------
    # Prior-session volatility benchmark.
    #
    # The shift ensures the current completed session is not included
    # in the benchmark used for its own classification.
    # -------------------------------------------------------------

    historical_vol = (
        features["realized_vol_pct"]
        .shift(1)
    )

    features["vol_median"] = (
        historical_vol
        .rolling(
            VOLATILITY_MEDIAN_WINDOW,
            min_periods=VOLATILITY_MIN_PERIODS,
        )
        .median()
    )

    # -------------------------------------------------------------
    # Direction regime.
    # -------------------------------------------------------------

    features["direction"] = np.select(
        [
            features["session_return_pct"]
            >= DIRECTION_THRESHOLD_PCT,

            features["session_return_pct"]
            <= -DIRECTION_THRESHOLD_PCT,
        ],
        [
            "TREND_UP",
            "TREND_DOWN",
        ],
        default="SIDEWAYS",
    )

    # -------------------------------------------------------------
    # Volatility regime.
    # -------------------------------------------------------------

    features["volatility"] = np.select(
        [
            features["realized_vol_pct"]
            > features["vol_median"],
        ],
        [
            "HIGH_VOL",
        ],
        default="LOW_VOL",
    )

    # -------------------------------------------------------------
    # Shift the labels one full session.
    #
    # Trading day D uses information from day D-1.
    # -------------------------------------------------------------

    causal = features[
        [
            "direction",
            "volatility",
        ]
    ].shift(1)

    causal["feature_date"] = (
        features.index.to_series()
        .shift(1)
    )

    return causal


def attach_regimes(
    data: pd.DataFrame,
    session_features: pd.DataFrame,
) -> pd.DataFrame:
    """
    Attach the previous-session regime to every minute.
    """

    session_dates = pd.Series(
        pd.to_datetime(data.index.date),
        index=data.index,
    )

    direction_map = (
        session_features["direction"]
        .to_dict()
    )

    volatility_map = (
        session_features["volatility"]
        .to_dict()
    )

    feature_date_map = (
        session_features["feature_date"]
        .to_dict()
    )

    direction = session_dates.map(
        direction_map
    )

    volatility = session_dates.map(
        volatility_map
    )

    feature_date = session_dates.map(
        feature_date_map
    )

    return pd.DataFrame(
        {
            "direction": direction.values,
            "volatility": volatility.values,
            "feature_date": feature_date.values,
        },
        index=data.index,
    )


# =====================================================================
# BASELINE BACKTEST
# =====================================================================

def run_baseline_backtest(
    data: pd.DataFrame,
    config: StrategyConfig,
):
    """
    Run one continuous chronological baseline backtest.
    """

    signal_function = create_baseline_signal_function(
        data,
        config,
    )

    return run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=INITIAL_CAPITAL,
        quantity=QUANTITY,
        transaction_cost_rate=TRANSACTION_COST_RATE,
    )


# =====================================================================
# TRADE CLASSIFICATION
# =====================================================================

def classify_trades(
    trades,
    data: pd.DataFrame,
    regimes: pd.DataFrame,
) -> list[dict]:
    """
    Classify each completed trade using the causal regime present at
    the trade's entry timestamp.
    """

    classified = []

    for trade in trades:

        entry_time = pd.Timestamp(
            trade.entry_time
        )

        if entry_time not in data.index:
            raise ValueError(
                f"Trade entry timestamp not found: "
                f"{entry_time}"
            )

        regime_row = regimes.loc[
            entry_time
        ]

        direction = regime_row["direction"]
        volatility = regime_row["volatility"]
        feature_date = regime_row["feature_date"]

        # Early history does not have sufficient prior-session
        # volatility information.
        if (
            pd.isna(direction)
            or pd.isna(volatility)
            or pd.isna(feature_date)
        ):
            continue

        classified.append(
            {
                "position": trade.position.value,
                "entry_time": entry_time,
                "exit_time": pd.Timestamp(
                    trade.exit_time
                ),
                "net_pnl": float(
                    trade.net_pnl
                ),
                "direction_regime": str(
                    direction
                ),
                "volatility_regime": str(
                    volatility
                ),
                "feature_date": pd.Timestamp(
                    feature_date
                ),
            }
        )

    return classified


# =====================================================================
# METRICS
# =====================================================================

def calculate_metrics(
    trades: list[dict],
) -> dict:
    """Calculate standard performance metrics."""

    if not trades:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "avg_trade": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
        }

    pnl = np.array(
        [
            float(trade["net_pnl"])
            for trade in trades
        ],
        dtype=float,
    )

    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]

    gross_profit = float(
        wins.sum()
    )

    gross_loss = abs(
        float(losses.sum())
    )

    if gross_loss > 0:
        profit_factor = (
            gross_profit
            / gross_loss
        )
    else:
        profit_factor = float("inf")

    equity = INITIAL_CAPITAL
    peak = INITIAL_CAPITAL
    max_drawdown_pct = 0.0

    for value in pnl:

        equity += float(value)

        peak = max(
            peak,
            equity,
        )

        if peak > 0:

            drawdown_pct = (
                (peak - equity)
                / peak
                * 100.0
            )

            max_drawdown_pct = max(
                max_drawdown_pct,
                drawdown_pct,
            )

    return {
        "trades": len(pnl),
        "wins": int(len(wins)),
        "losses": int(len(losses)),
        "win_rate": (
            len(wins)
            / len(pnl)
            * 100.0
        ),
        "net_pnl": float(
            pnl.sum()
        ),
        "avg_trade": float(
            pnl.mean()
        ),
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_drawdown_pct,
    }


def print_metrics(
    label: str,
    metrics: dict,
):
    """Print metrics in a compact format."""

    pf = metrics["profit_factor"]

    pf_text = (
        "INF"
        if pf == float("inf")
        else f"{pf:.3f}"
    )

    print(
        f"{label:<34}"
        f"Trades={metrics['trades']:>4}  "
        f"Win={metrics['win_rate']:>6.2f}%  "
        f"P&L={metrics['net_pnl']:>+10.2f}  "
        f"Avg={metrics['avg_trade']:>+8.2f}  "
        f"PF={pf_text:>6}  "
        f"DD={metrics['max_drawdown_pct']:>5.2f}%"
    )


# =====================================================================
# REGIME REPORT
# =====================================================================

def print_regime_report(
    trades: list[dict],
):
    """Print performance across causal market regimes."""

    # -------------------------------------------------------------
    # Direction
    # -------------------------------------------------------------

    print()
    print("=" * 105)
    print("PERFORMANCE BY MARKET DIRECTION REGIME")
    print("=" * 105)

    for regime in (
        "TREND_UP",
        "TREND_DOWN",
        "SIDEWAYS",
    ):

        selected = [
            trade
            for trade in trades
            if trade["direction_regime"] == regime
        ]

        metrics = calculate_metrics(
            selected
        )

        print_metrics(
            regime,
            metrics,
        )

    # -------------------------------------------------------------
    # Volatility
    # -------------------------------------------------------------

    print()
    print("=" * 105)
    print("PERFORMANCE BY VOLATILITY REGIME")
    print("=" * 105)

    for regime in (
        "HIGH_VOL",
        "LOW_VOL",
    ):

        selected = [
            trade
            for trade in trades
            if trade["volatility_regime"] == regime
        ]

        metrics = calculate_metrics(
            selected
        )

        print_metrics(
            regime,
            metrics,
        )

    # -------------------------------------------------------------
    # Direction × volatility
    # -------------------------------------------------------------

    print()
    print("=" * 105)
    print("PERFORMANCE BY DIRECTION × VOLATILITY")
    print("=" * 105)

    for direction in (
        "TREND_UP",
        "TREND_DOWN",
        "SIDEWAYS",
    ):

        for volatility in (
            "HIGH_VOL",
            "LOW_VOL",
        ):

            selected = [
                trade
                for trade in trades
                if (
                    trade["direction_regime"]
                    == direction
                    and
                    trade["volatility_regime"]
                    == volatility
                )
            ]

            metrics = calculate_metrics(
                selected
            )

            label = (
                f"{direction}/{volatility}"
            )

            print_metrics(
                label,
                metrics,
            )

    # -------------------------------------------------------------
    # Position × direction
    # -------------------------------------------------------------

    print()
    print("=" * 105)
    print("PERFORMANCE BY POSITION × MARKET DIRECTION")
    print("=" * 105)

    for position in (
        "LONG",
        "SHORT",
    ):

        for regime in (
            "TREND_UP",
            "TREND_DOWN",
            "SIDEWAYS",
        ):

            selected = [
                trade
                for trade in trades
                if (
                    trade["position"]
                    == position
                    and
                    trade["direction_regime"]
                    == regime
                )
            ]

            metrics = calculate_metrics(
                selected
            )

            label = (
                f"{position}/{regime}"
            )

            print_metrics(
                label,
                metrics,
            )

    # -------------------------------------------------------------
    # Position × volatility
    # -------------------------------------------------------------

    print()
    print("=" * 105)
    print("PERFORMANCE BY POSITION × VOLATILITY")
    print("=" * 105)

    for position in (
        "LONG",
        "SHORT",
    ):

        for volatility in (
            "HIGH_VOL",
            "LOW_VOL",
        ):

            selected = [
                trade
                for trade in trades
                if (
                    trade["position"]
                    == position
                    and
                    trade["volatility_regime"]
                    == volatility
                )
            ]

            metrics = calculate_metrics(
                selected
            )

            label = (
                f"{position}/{volatility}"
            )

            print_metrics(
                label,
                metrics,
            )


# =====================================================================
# REGIME DISTRIBUTION
# =====================================================================

def print_regime_distribution(
    trades: list[dict],
):
    """Show the number and percentage of trades in each regime."""

    print()
    print("=" * 105)
    print("REGIME TRADE DISTRIBUTION")
    print("=" * 105)

    total = len(trades)

    if total == 0:
        print("No classified trades.")
        return

    combinations = [
        ("TREND_UP", "HIGH_VOL"),
        ("TREND_UP", "LOW_VOL"),
        ("TREND_DOWN", "HIGH_VOL"),
        ("TREND_DOWN", "LOW_VOL"),
        ("SIDEWAYS", "HIGH_VOL"),
        ("SIDEWAYS", "LOW_VOL"),
    ]

    for direction, volatility in combinations:

        count = sum(
            (
                trade["direction_regime"]
                == direction
                and
                trade["volatility_regime"]
                == volatility
            )
            for trade in trades
        )

        share = (
            count
            / total
            * 100.0
        )

        print(
            f"{direction:<12}"
            f"{volatility:<10}"
            f"Trades={count:>5}  "
            f"Share={share:>6.2f}%"
        )


# =====================================================================
# CAUSALITY CHECK
# =====================================================================

def run_causality_check(
    trades: list[dict],
):
    """
    Verify that every regime feature date is strictly before the
    trade entry date.
    """

    violations = []

    for trade in trades:

        entry_date = (
            trade["entry_time"].normalize()
        )

        feature_date = (
            trade["feature_date"].normalize()
        )

        if feature_date >= entry_date:

            violations.append(
                (
                    trade["entry_time"],
                    feature_date,
                )
            )

    if violations:

        raise RuntimeError(
            "Causality violation detected: "
            f"{violations[:5]}"
        )

    print()
    print(
        f"Causality check: PASS "
        f"({len(trades):,} classified trades)"
    )


# =====================================================================
# MAIN
# =====================================================================

def main():

    print("=" * 105)
    print(
        "SIGNALFORGE - PHASE 7.4 MARKET-REGIME ANALYSIS"
    )
    print("=" * 105)

    print()
    print("Frozen baseline:")
    print("  EMA = 20 / 50")
    print("  RSI = 14")
    print("  ATR = 14")
    print("  RVOL = 20")
    print("  RVOL enabled = False")
    print("  MTF = 30m / 15m / 10m / 5m")
    print("  Minimum ATR = 0.0")
    print("  Minimum RVOL = 1.5")

    print()
    print("Causal regime definitions:")
    print(
        f"  TREND_UP   = previous session return "
        f">= +{DIRECTION_THRESHOLD_PCT:.2f}%"
    )
    print(
        f"  TREND_DOWN = previous session return "
        f"<= -{DIRECTION_THRESHOLD_PCT:.2f}%"
    )
    print(
        f"  SIDEWAYS   = previous session return "
        f"inside +/-{DIRECTION_THRESHOLD_PCT:.2f}%"
    )
    print(
        "  HIGH_VOL   = previous session volatility "
        "above prior trailing median"
    )
    print(
        "  LOW_VOL    = previous session volatility "
        "at/below prior trailing median"
    )

    print()
    print(
        "Regime information is shifted by one session "
        "to prevent lookahead."
    )

    # -------------------------------------------------------------
    # Load data.
    # -------------------------------------------------------------

    print()
    print("Loading historical data...")

    data = load_data()

    print(
        f"Rows: {len(data):,}"
    )

    print(
        f"Range: "
        f"{data.index.min()} "
        f"-> "
        f"{data.index.max()}"
    )

    # -------------------------------------------------------------
    # Calculate causal regimes.
    # -------------------------------------------------------------

    print()
    print(
        "Calculating causal session regime features..."
    )

    session_features = calculate_session_features(
        data
    )

    regimes = attach_regimes(
        data,
        session_features,
    )

    print(
        f"Completed sessions: "
        f"{len(session_features):,}"
    )

    # -------------------------------------------------------------
    # Run frozen baseline.
    # -------------------------------------------------------------

    config = make_config()

    print()
    print(
        "Running one continuous chronological "
        "baseline backtest..."
    )

    result = run_baseline_backtest(
        data,
        config,
    )

    trades = list(result.trades)

    print(
        f"Completed baseline trades: "
        f"{len(trades):,}"
    )

    if not trades:
        raise RuntimeError(
            "Baseline backtest produced no trades."
        )

    # -------------------------------------------------------------
    # Classify.
    # -------------------------------------------------------------

    print()
    print(
        "Classifying trades using pre-entry regimes..."
    )

    classified_trades = classify_trades(
        trades,
        data,
        regimes,
    )

    skipped = (
        len(trades)
        - len(classified_trades)
    )

    print(
        f"Classified trades: "
        f"{len(classified_trades):,}"
    )

    print(
        f"Early trades without sufficient causal "
        f"regime history: {skipped:,}"
    )

    if not classified_trades:
        raise RuntimeError(
            "No trades could be classified."
        )

    # -------------------------------------------------------------
    # Causality validation.
    # -------------------------------------------------------------

    run_causality_check(
        classified_trades
    )

    # -------------------------------------------------------------
    # Overall classified baseline.
    # -------------------------------------------------------------

    overall = calculate_metrics(
        classified_trades
    )

    print()
    print("=" * 105)
    print("CLASSIFIED BASELINE CROSS-CHECK")
    print("=" * 105)

    print_metrics(
        "CLASSIFIED BASELINE",
        overall,
    )

    # -------------------------------------------------------------
    # Reports.
    # -------------------------------------------------------------

    print_regime_report(
        classified_trades
    )

    print_regime_distribution(
        classified_trades
    )

    # -------------------------------------------------------------
    # Research rules.
    # -------------------------------------------------------------

    print()
    print("=" * 105)
    print("RESEARCH RULES")
    print("=" * 105)

    print(
        "1. Diagnostic analysis only."
    )

    print(
        "2. Trading strategy remains frozen."
    )

    print(
        "3. No regime filter is added."
    )

    print(
        "4. No parameters are optimized."
    )

    print(
        "5. Regime labels use only prior-session information."
    )

    print(
        "6. Regime observations must be tested for persistence "
        "before any strategy modification."
    )

    print()
    print("=" * 105)
    print(
        "PHASE 7.4 MARKET-REGIME ANALYSIS COMPLETE"
    )
    print("=" * 105)


if __name__ == "__main__":
    main()