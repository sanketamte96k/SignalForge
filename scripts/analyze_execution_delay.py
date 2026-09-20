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


def create_locked_signal_function(
    data: pd.DataFrame,
):

    config = make_config()

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

        states = {}

        for timeframe in TIMEFRAMES:

            state = cursors[timeframe].update(
                timestamp
            )

            if state is None:
                return None

            states[timeframe] = state

        # ---------------------------------------------------------
        # LONG
        # ---------------------------------------------------------

        if all(
            state.close > state.ema20 > state.ema50
            for state in states.values()
        ):

            if not all(
                state.rsi >= RSI_LONG_THRESHOLD
                for state in states.values()
            ):
                return None

            if not all(
                state.atr >= config.minimum_atr
                for state in states.values()
            ):
                return None

            return Position.LONG

        # ---------------------------------------------------------
        # SHORT
        # ---------------------------------------------------------

        if all(
            state.close < state.ema20 < state.ema50
            for state in states.values()
        ):

            if not all(
                state.atr >= config.minimum_atr
                for state in states.values()
            ):
                return None

            return Position.SHORT

        return None

    return signal_function


def generate_locked_signals(
    data: pd.DataFrame,
) -> pd.Series:

    signal_function = create_locked_signal_function(
        data
    )

    signals = []

    previous_row = None

    for timestamp, row in data.iterrows():

        signal = signal_function(
            row,
            previous_row,
        )

        signals.append(signal)

        previous_row = row

    return pd.Series(
        signals,
        index=data.index,
        dtype="object",
    )


def calculate_metrics_from_trades(
    trades,
) -> dict:

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

    # -------------------------------------------------------------
    # IMPORTANT:
    # run_execution_model() returns dictionaries,
    # not Trade objects.
    # -------------------------------------------------------------

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
            gross_profit / gross_loss
        )
    else:
        profit_factor = float("inf")

    equity = INITIAL_CAPITAL
    peak = INITIAL_CAPITAL
    max_drawdown = 0.0

    for value in pnl:

        equity += value

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

            max_drawdown = max(
                max_drawdown,
                drawdown_pct,
            )

    return {
        "trades": len(pnl),
        "wins": len(wins),
        "losses": len(losses),
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
        "max_drawdown_pct": max_drawdown,
    }


def run_execution_model(
    data: pd.DataFrame,
    signals: pd.Series,
    entry_delay: int,
    exit_delay: int,
):
    """
    Research-only execution simulator.

    Signal generated at candle t.

    Entry:
        signal at t -> execute after entry_delay minutes.

    Exit:
        opposite signal at t -> execute after exit_delay minutes.

    Execution price:
        close of the delayed minute.

    This models execution timing only.
    It does not modify the underlying strategy.
    """

    position = None
    entry_price = None
    entry_time = None

    trades = []

    timestamps = list(data.index)

    for i, timestamp in enumerate(timestamps):

        signal = signals.iloc[i]

        # ---------------------------------------------------------
        # Ignore no-trade signals.
        # ---------------------------------------------------------

        if signal is None:
            continue

        # ---------------------------------------------------------
        # No open position -> potential entry.
        # ---------------------------------------------------------

        if position is None:

            execution_index = (
                i + entry_delay
            )

            if execution_index >= len(data):
                continue

            execution_time = timestamps[
                execution_index
            ]

            # Never carry an entry across sessions.
            if (
                execution_time.date()
                != timestamp.date()
            ):
                continue

            execution_price = float(
                data.iloc[
                    execution_index
                ]["close"]
            )

            position = signal
            entry_price = execution_price
            entry_time = execution_time

            continue

        # ---------------------------------------------------------
        # LONG -> SHORT reversal.
        # ---------------------------------------------------------

        if (
            position == Position.LONG
            and signal == Position.SHORT
        ):

            execution_index = (
                i + exit_delay
            )

            if execution_index >= len(data):
                continue

            execution_time = timestamps[
                execution_index
            ]

            if (
                execution_time.date()
                != timestamp.date()
            ):
                continue

            exit_price = float(
                data.iloc[
                    execution_index
                ]["close"]
            )

            gross_pnl = (
                exit_price
                - entry_price
            ) * QUANTITY

            transaction_cost = (
                (
                    entry_price
                    + exit_price
                )
                * QUANTITY
                * TRANSACTION_COST_RATE
            )

            net_pnl = (
                gross_pnl
                - transaction_cost
            )

            trades.append(
                {
                    "position": "LONG",
                    "entry_time": entry_time,
                    "exit_time": execution_time,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "net_pnl": net_pnl,
                }
            )

            # Reverse into SHORT at exit execution.
            position = Position.SHORT
            entry_price = exit_price
            entry_time = execution_time

            continue

        # ---------------------------------------------------------
        # SHORT -> LONG reversal.
        # ---------------------------------------------------------

        if (
            position == Position.SHORT
            and signal == Position.LONG
        ):

            execution_index = (
                i + exit_delay
            )

            if execution_index >= len(data):
                continue

            execution_time = timestamps[
                execution_index
            ]

            if (
                execution_time.date()
                != timestamp.date()
            ):
                continue

            exit_price = float(
                data.iloc[
                    execution_index
                ]["close"]
            )

            gross_pnl = (
                entry_price
                - exit_price
            ) * QUANTITY

            transaction_cost = (
                (
                    entry_price
                    + exit_price
                )
                * QUANTITY
                * TRANSACTION_COST_RATE
            )

            net_pnl = (
                gross_pnl
                - transaction_cost
            )

            trades.append(
                {
                    "position": "SHORT",
                    "entry_time": entry_time,
                    "exit_time": execution_time,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "net_pnl": net_pnl,
                }
            )

            # Reverse into LONG at exit execution.
            position = Position.LONG
            entry_price = exit_price
            entry_time = execution_time

    # -------------------------------------------------------------
    # Close final open position.
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

        transaction_cost = (
            (
                entry_price
                + final_price
            )
            * QUANTITY
            * TRANSACTION_COST_RATE
        )

        net_pnl = (
            gross_pnl
            - transaction_cost
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


def print_metrics(
    label: str,
    metrics: dict,
):

    pf = metrics["profit_factor"]

    if pf == float("inf"):
        pf_text = "INF"
    else:
        pf_text = f"{pf:.3f}"

    print(
        f"{label:<18}"
        f"Trades={metrics['trades']:>4}  "
        f"Win={metrics['win_rate']:>6.2f}%  "
        f"P&L={metrics['net_pnl']:>+10.2f}  "
        f"Avg={metrics['avg_trade']:>+8.2f}  "
        f"PF={pf_text:>6}  "
        f"DD={metrics['max_drawdown_pct']:>5.2f}%"
    )


def main():

    print("=" * 78)
    print(
        "SIGNALFORGE — EXECUTION DELAY REALISM TEST"
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

    data = load_data()

    print(
        f"\nRows: {len(data):,}"
    )

    print(
        f"Range: {data.index.min()} "
        f"→ {data.index.max()}"
    )

    for period_name, (
        start,
        end,
    ) in PERIODS.items():

        period_data = data[
            (data.index >= pd.Timestamp(start))
            & (data.index <= pd.Timestamp(end))
        ].copy()

        if period_data.empty:
            continue

        print("\n" + "-" * 78)

        print(
            f"{period_name}: "
            f"{start} → {end}"
        )

        print("-" * 78)

        print(
            "\nGenerating locked strategy signals..."
        )

        signals = generate_locked_signals(
            period_data
        )

        print(
            f"Signals generated: "
            f"{len(signals):,}"
        )

        print("\nExecution scenarios:")

        # ---------------------------------------------------------
        # Baseline
        # ---------------------------------------------------------

        baseline_trades = run_execution_model(
            period_data,
            signals,
            entry_delay=0,
            exit_delay=0,
        )

        baseline_metrics = (
            calculate_metrics_from_trades(
                baseline_trades
            )
        )

        print_metrics(
            "0/0 baseline",
            baseline_metrics,
        )

        # ---------------------------------------------------------
        # Entry delay
        # ---------------------------------------------------------

        for delay in (1, 2):

            trades = run_execution_model(
                period_data,
                signals,
                entry_delay=delay,
                exit_delay=0,
            )

            metrics = (
                calculate_metrics_from_trades(
                    trades
                )
            )

            print_metrics(
                f"Entry +{delay}m",
                metrics,
            )

        # ---------------------------------------------------------
        # Exit delay
        # ---------------------------------------------------------

        for delay in (1, 2):

            trades = run_execution_model(
                period_data,
                signals,
                entry_delay=0,
                exit_delay=delay,
            )

            metrics = (
                calculate_metrics_from_trades(
                    trades
                )
            )

            print_metrics(
                f"Exit +{delay}m",
                metrics,
            )

        # ---------------------------------------------------------
        # Entry + exit delay
        # ---------------------------------------------------------

        for delay in (1, 2):

            trades = run_execution_model(
                period_data,
                signals,
                entry_delay=delay,
                exit_delay=delay,
            )

            metrics = (
                calculate_metrics_from_trades(
                    trades
                )
            )

            print_metrics(
                f"Both +{delay}m",
                metrics,
            )

    print("\n" + "=" * 78)

    print(
        "EXECUTION DELAY TEST COMPLETE"
    )

    print("=" * 78)

    print(
        "\nInterpretation:"
        "\n  PASS        = edge survives realistic small delays"
        "\n  CONDITIONAL = edge survives some delays but weakens"
        "\n  FAIL        = edge disappears under small delays"
    )


if __name__ == "__main__":
    main()