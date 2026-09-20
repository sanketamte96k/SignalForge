from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.engine import Position
from src.strategy.backtest_strategy import (
    StrategyConfig,
    _make_cursors,
    calculate_timeframe_indicators,
)


# =====================================================================
# CONFIG
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

RSI_LONG_THRESHOLD = 60.0

TIMEFRAMES = (
    "30m",
    "15m",
    "10m",
    "5m",
)

PERIODS = {
    "Development": ("2015-01-01", "2020-12-31"),
    "Validation": ("2021-01-01", "2022-12-31"),
    "OOS": ("2023-01-01", "2024-03-31"),
}


# =====================================================================
# DATA
# =====================================================================

def load_data() -> pd.DataFrame:

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

    return data


# =====================================================================
# LOCKED STRATEGY
# =====================================================================

def make_config() -> StrategyConfig:

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


def generate_locked_signals(
    data: pd.DataFrame,
) -> pd.Series:

    config = make_config()

    timeframe_data = (
        calculate_timeframe_indicators(
            data,
            config,
        )
    )

    cursors = _make_cursors(
        timeframe_data,
        config.use_rvol,
    )

    signals = []

    for timestamp, row in data.iterrows():

        states = {}

        for timeframe in TIMEFRAMES:

            state = cursors[timeframe].update(
                pd.Timestamp(timestamp)
            )

            if state is None:
                states = {}
                break

            states[timeframe] = state

        if len(states) != 4:

            signals.append(None)
            continue

        # ---------------------------------------------------------
        # LONG
        # ---------------------------------------------------------

        if all(
            state.close > state.ema20 > state.ema50
            for state in states.values()
        ):

            if all(
                state.rsi >= RSI_LONG_THRESHOLD
                for state in states.values()
            ):

                signals.append(
                    Position.LONG
                )

                continue

        # ---------------------------------------------------------
        # SHORT
        # ---------------------------------------------------------

        if all(
            state.close < state.ema20 < state.ema50
            for state in states.values()
        ):

            signals.append(
                Position.SHORT
            )

            continue

        signals.append(None)

    return pd.Series(
        signals,
        index=data.index,
        dtype="object",
    )


# =====================================================================
# CAUSAL REAL-TIME FEATURES
# =====================================================================

def calculate_realtime_features(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate only information available at each minute.

    No future session close/high/low is used.
    """

    features = pd.DataFrame(
        index=data.index
    )

    session_dates = pd.Series(
        data.index.date,
        index=data.index,
    )

    # -------------------------------------------------------------
    # Current-day return.
    #
    # At time t:
    # current close / today's first open.
    # -------------------------------------------------------------

    day_open = (
        data["open"]
        .groupby(session_dates)
        .transform("first")
    )

    features["day_return_pct"] = (
        data["close"]
        / day_open
        - 1.0
    ) * 100.0

    # -------------------------------------------------------------
    # Opening range.
    #
    # First 30 minutes:
    # 09:15 -> 09:44
    #
    # We only use the completed opening range after 09:45.
    # -------------------------------------------------------------

    features["opening_range_high"] = float("nan")
    features["opening_range_low"] = float("nan")

    for session_date, session in data.groupby(
        data.index.date
    ):

        session_indices = session.index

        if len(session) < 30:
            continue

        opening_range = session.iloc[:30]

        opening_high = float(
            opening_range["high"].max()
        )

        opening_low = float(
            opening_range["low"].min()
        )

        # First 30 minutes are deliberately left
        # without an opening-range signal.
        usable_indices = session_indices[30:]

        features.loc[
            usable_indices,
            "opening_range_high"
        ] = opening_high

        features.loc[
            usable_indices,
            "opening_range_low"
        ] = opening_low

    # -------------------------------------------------------------
    # Opening-range position.
    #
    # +1 = above opening range
    # -1 = below opening range
    #  0 = inside
    # -------------------------------------------------------------

    features["opening_range_direction"] = 0

    above = (
        data["close"]
        > features["opening_range_high"]
    )

    below = (
        data["close"]
        < features["opening_range_low"]
    )

    features.loc[
        above,
        "opening_range_direction"
    ] = 1

    features.loc[
        below,
        "opening_range_direction"
    ] = -1

    # -------------------------------------------------------------
    # Current 30-minute EMA direction.
    #
    # Uses the latest COMPLETED 30m candle only.
    # -------------------------------------------------------------

    config = make_config()

    timeframe_data = (
        calculate_timeframe_indicators(
            data,
            config,
        )
    )

    thirty = timeframe_data["30m"]

    ema_direction = pd.Series(
        0,
        index=data.index,
        dtype="int64",
    )

    for timestamp in data.index:

        completed_position = (
            thirty.index.searchsorted(
                timestamp,
                side="left",
            )
            - 1
        )

        if completed_position < 0:
            continue

        state = thirty.iloc[
            completed_position
        ]

        if pd.isna(state["ema20"]) or pd.isna(
            state["ema50"]
        ):
            continue

        if (
            state["close"]
            > state["ema20"]
            > state["ema50"]
        ):

            ema_direction.loc[
                timestamp
            ] = 1

        elif (
            state["close"]
            < state["ema20"]
            < state["ema50"]
        ):

            ema_direction.loc[
                timestamp
            ] = -1

    features["ema30_direction"] = (
        ema_direction
    )

    return features


# =====================================================================
# FILTER LOGIC
# =====================================================================

def apply_filter(
    signal,
    features: pd.Series,
    filter_name: str,
):

    if signal is None:
        return None

    # -------------------------------------------------------------
    # BASELINE
    # -------------------------------------------------------------

    if filter_name == "BASELINE":
        return signal

    # -------------------------------------------------------------
    # FILTER 1:
    # Current-day return agrees with trade direction.
    #
    # Zero means no directional information yet.
    # -------------------------------------------------------------

    if filter_name == "DAY_DIRECTION":

        day_return = (
            features["day_return_pct"]
        )

        if signal == Position.LONG:

            if day_return > 0:
                return signal

            return None

        if signal == Position.SHORT:

            if day_return < 0:
                return signal

            return None

        return None

    # -------------------------------------------------------------
    # FILTER 2:
    # Price agrees with completed opening range.
    # -------------------------------------------------------------

    if filter_name == "OPENING_RANGE":

        direction = (
            features[
                "opening_range_direction"
            ]
        )

        if signal == Position.LONG:

            if direction == 1:
                return signal

            return None

        if signal == Position.SHORT:

            if direction == -1:
                return signal

            return None

        return None

    # -------------------------------------------------------------
    # FILTER 3:
    # Completed 30m EMA structure agrees.
    # -------------------------------------------------------------

    if filter_name == "EMA_30M":

        direction = (
            features[
                "ema30_direction"
            ]
        )

        if signal == Position.LONG:

            if direction == 1:
                return signal

            return None

        if signal == Position.SHORT:

            if direction == -1:
                return signal

            return None

        return None

    raise ValueError(
        f"Unknown filter: {filter_name}"
    )


# =====================================================================
# EXECUTION
# =====================================================================

def run_execution(
    data: pd.DataFrame,
    signals: pd.Series,
    features: pd.DataFrame,
    filter_name: str,
):

    position = None
    entry_price = None
    entry_time = None

    trades = []

    timestamps = list(data.index)

    for i, timestamp in enumerate(timestamps):

        row = data.iloc[i]

        signal = signals.iloc[i]

        filtered_signal = apply_filter(
            signal,
            features.iloc[i],
            filter_name,
        )

        # ---------------------------------------------------------
        # Session boundary.
        # ---------------------------------------------------------

        if i > 0:

            previous_timestamp = (
                timestamps[i - 1]
            )

            if (
                timestamp.date()
                != previous_timestamp.date()
            ):

                if (
                    position is not None
                    and entry_price is not None
                ):

                    exit_price = float(
                        data.iloc[i - 1]["close"]
                    )

                    exit_time = timestamps[
                        i - 1
                    ]

                    if position == Position.LONG:

                        gross_pnl = (
                            exit_price
                            - entry_price
                        ) * QUANTITY

                    else:

                        gross_pnl = (
                            entry_price
                            - exit_price
                        ) * QUANTITY

                    cost = (
                        (
                            entry_price
                            + exit_price
                        )
                        * QUANTITY
                        * TRANSACTION_COST_RATE
                    )

                    net_pnl = (
                        gross_pnl
                        - cost
                    )

                    trades.append(
                        {
                            "position": position.value,
                            "entry_time": entry_time,
                            "exit_time": exit_time,
                            "entry_price": entry_price,
                            "exit_price": exit_price,
                            "net_pnl": net_pnl,
                        }
                    )

                    position = None
                    entry_price = None
                    entry_time = None

        if filtered_signal is None:
            continue

        # ---------------------------------------------------------
        # Open.
        # ---------------------------------------------------------

        if position is None:

            position = filtered_signal
            entry_price = float(
                row["close"]
            )
            entry_time = timestamp

            continue

        # ---------------------------------------------------------
        # Same direction.
        # ---------------------------------------------------------

        if filtered_signal == position:
            continue

        # ---------------------------------------------------------
        # Reverse.
        # ---------------------------------------------------------

        exit_price = float(
            row["close"]
        )

        exit_time = timestamp

        if position == Position.LONG:

            gross_pnl = (
                exit_price
                - entry_price
            ) * QUANTITY

        else:

            gross_pnl = (
                entry_price
                - exit_price
            ) * QUANTITY

        cost = (
            (
                entry_price
                + exit_price
            )
            * QUANTITY
            * TRANSACTION_COST_RATE
        )

        net_pnl = (
            gross_pnl
            - cost
        )

        trades.append(
            {
                "position": position.value,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "net_pnl": net_pnl,
            }
        )

        position = filtered_signal
        entry_price = exit_price
        entry_time = exit_time

    # -------------------------------------------------------------
    # Final position.
    # -------------------------------------------------------------

    if (
        position is not None
        and entry_price is not None
    ):

        final_time = timestamps[-1]

        final_price = float(
            data.iloc[-1]["close"]
        )

        if position == Position.LONG:

            gross_pnl = (
                final_price
                - entry_price
            ) * QUANTITY

        else:

            gross_pnl = (
                entry_price
                - final_price
            ) * QUANTITY

        cost = (
            (
                entry_price
                + final_price
            )
            * QUANTITY
            * TRANSACTION_COST_RATE
        )

        net_pnl = (
            gross_pnl
            - cost
        )

        trades.append(
            {
                "position": position.value,
                "entry_time": entry_time,
                "exit_time": final_time,
                "entry_price": entry_price,
                "exit_price": final_price,
                "net_pnl": net_pnl,
            }
        )

    return trades


# =====================================================================
# METRICS
# =====================================================================

def calculate_metrics(
    trades,
) -> dict:

    if not trades:

        return {
            "trades": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "avg_trade": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
        }

    pnl = [
        float(trade["net_pnl"])
        for trade in trades
    ]

    wins = [
        value
        for value in pnl
        if value > 0
    ]

    losses = [
        value
        for value in pnl
        if value < 0
    ]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    if gross_loss > 0:

        profit_factor = (
            gross_profit
            / gross_loss
        )

    else:

        profit_factor = float("inf")

    equity = INITIAL_CAPITAL
    peak = INITIAL_CAPITAL
    max_dd = 0.0

    for value in pnl:

        equity += value

        peak = max(
            peak,
            equity,
        )

        if peak > 0:

            dd = (
                (peak - equity)
                / peak
                * 100.0
            )

            max_dd = max(
                max_dd,
                dd,
            )

    return {
        "trades": len(pnl),
        "win_rate": (
            len(wins)
            / len(pnl)
            * 100.0
        ),
        "net_pnl": sum(pnl),
        "avg_trade": (
            sum(pnl)
            / len(pnl)
        ),
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_dd,
    }


def print_metrics(
    label: str,
    metrics: dict,
):

    pf = metrics["profit_factor"]

    pf_text = (
        "INF"
        if pf == float("inf")
        else f"{pf:.3f}"
    )

    print(
        f"{label:<20}"
        f"Trades={metrics['trades']:>4}  "
        f"Win={metrics['win_rate']:>6.2f}%  "
        f"P&L={metrics['net_pnl']:>+10.2f}  "
        f"Avg={metrics['avg_trade']:>+8.2f}  "
        f"PF={pf_text:>6}  "
        f"DD={metrics['max_drawdown_pct']:>5.2f}%"
    )


# =====================================================================
# MAIN
# =====================================================================

def main():

    print("=" * 78)
    print(
        "SIGNALFORGE — REAL-TIME REGIME FILTER RESEARCH"
    )
    print("=" * 78)

    print(
        "\nLocked strategy:"
        "\n  EMA = 20 / 50"
        "\n  RSI period = 14"
        "\n  LONG RSI >= 60"
        "\n  ATR period = 14"
        "\n  MTF = 30m / 15m / 10m / 5m"
        "\n  RVOL = disabled"
    )

    print(
        f"\nTransaction cost: "
        f"{TRANSACTION_COST_RATE * 100:.2f}%"
    )

    print(
        "\nCandidate causal filters:"
        "\n  BASELINE"
        "\n  DAY_DIRECTION"
        "\n  OPENING_RANGE"
        "\n  EMA_30M"
    )

    data = load_data()

    print(
        f"\nRows: {len(data):,}"
    )

    print(
        f"Range: {data.index.min()} "
        f"→ {data.index.max()}"
    )

    print(
        "\nCalculating real-time features..."
    )

    features = calculate_realtime_features(
        data
    )

    print(
        "Generating locked strategy signals..."
    )

    signals = generate_locked_signals(
        data
    )

    filter_names = (
        "BASELINE",
        "DAY_DIRECTION",
        "OPENING_RANGE",
        "EMA_30M",
    )

    for period_name, (
        start,
        end,
    ) in PERIODS.items():

        period_mask = (
            (data.index >= pd.Timestamp(start))
            & (data.index <= pd.Timestamp(end))
        )

        period_data = data.loc[
            period_mask
        ].copy()

        period_signals = signals.loc[
            period_mask
        ]

        period_features = features.loc[
            period_mask
        ]

        if period_data.empty:
            continue

        print("\n" + "-" * 78)

        print(
            f"{period_name}: "
            f"{start} → {end}"
        )

        print("-" * 78)

        for filter_name in filter_names:

            trades = run_execution(
                period_data,
                period_signals,
                period_features,
                filter_name,
            )

            metrics = calculate_metrics(
                trades
            )

            print_metrics(
                filter_name,
                metrics,
            )

    print("\n" + "=" * 78)
    print(
        "REAL-TIME REGIME FILTER RESEARCH COMPLETE"
    )
    print("=" * 78)

    print(
        "\nIMPORTANT:"
        "\nThese filters are research candidates only."
        "\nDo not add any filter to production based on this test alone."
        "\nThe next step is validation of any promising causal filter."
    )


if __name__ == "__main__":
    main()