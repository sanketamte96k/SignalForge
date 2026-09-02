"""Development-only LONG RSI filter experiment."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.backtest.engine import run_backtest
from src.signals.signal_engine import (
    Signal,
    generate_signal,
)
from src.strategy.backtest_strategy import (
    StrategyConfig,
    _completed_state,
    _make_cursors,
    calculate_timeframe_indicators,
    signal_result_to_position,
)


DEVELOPMENT_START = "2015-01-01"
DEVELOPMENT_END = "2020-12-31"

RSI_THRESHOLDS = [50, 52, 55, 58, 60]

INITIAL_CAPITAL = 100_000.0
QUANTITY = 1
TRANSACTION_COST_RATE = 0.0001


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Test LONG-side RSI thresholds on "
            "the 2015-2020 development period."
        )
    )

    parser.add_argument(
        "--data",
        type=Path,
        required=True,
        help="Path to SignalForge historical CSV.",
    )

    return parser.parse_args()


def load_data(data_path: Path) -> pd.DataFrame:
    """Load historical SignalForge market data."""

    if not data_path.exists():
        raise FileNotFoundError(
            f"Historical dataset not found: {data_path}"
        )

    data = pd.read_csv(
        data_path,
        index_col=0,
        parse_dates=True,
    ).sort_index()

    if data.empty:
        raise ValueError(
            "Historical dataset is empty."
        )

    return data


def get_development_data(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Return only the 2015-2020 development period."""

    start = pd.Timestamp(DEVELOPMENT_START)

    end = (
        pd.Timestamp(DEVELOPMENT_END)
        + pd.Timedelta(days=1)
    )

    development_data = data.loc[
        (data.index >= start)
        & (data.index < end)
    ].copy()

    if development_data.empty:
        raise ValueError(
            "No data found for the development period."
        )

    return development_data


def create_experiment_signal_function(
    data: pd.DataFrame,
    config: StrategyConfig,
    long_rsi_threshold: float,
):
    """
    Create the LONG RSI experiment signal function.

    Existing SignalForge rules remain unchanged.

    Only BUY/LONG signals receive an additional filter:

        RSI >= long_rsi_threshold

    SHORT signals are left completely unchanged.
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
        previous_row: pd.Series,
    ):
        """Generate one experimental signal."""

        timestamp = row.name

        if not isinstance(timestamp, pd.Timestamp):
            timestamp = pd.Timestamp(timestamp)

        # ----------------------------------------------------
        # Use EXACTLY the same cursor/state logic as the
        # production strategy.
        # ----------------------------------------------------

        state_30m = cursors["30m"].update(
            timestamp
        )

        state_15m = cursors["15m"].update(
            timestamp
        )

        state_10m = cursors["10m"].update(
            timestamp
        )

        state_5m = cursors["5m"].update(
            timestamp
        )

        if (
            state_30m is None
            or state_15m is None
            or state_10m is None
            or state_5m is None
        ):
            return None

        # ----------------------------------------------------
        # Run the EXISTING SignalForge signal engine.
        # ----------------------------------------------------

        result = generate_signal(
            timeframe_30m=state_30m,
            timeframe_15m=state_15m,
            timeframe_10m=state_10m,
            timeframe_5m=state_5m,
            minimum_rvol=config.minimum_rvol,
            minimum_atr=config.minimum_atr,
            use_rvol=config.use_rvol,
        )

        # ----------------------------------------------------
        # Only modify BUY/LONG signals.
        # ----------------------------------------------------

        if result.signal == Signal.BUY:

            rsi_values = [
                state_30m.rsi,
                state_15m.rsi,
                state_10m.rsi,
                state_5m.rsi,
            ]

            # All four timeframes must satisfy the
            # experimental LONG RSI threshold.
            if any(
                rsi < long_rsi_threshold
                for rsi in rsi_values
            ):
                return None

        # ----------------------------------------------------
        # SHORT and accepted LONG signals are converted using
        # the existing SignalForge adapter.
        # ----------------------------------------------------

        return signal_result_to_position(result)

    return signal_function


def run_experiment(
    data: pd.DataFrame,
    config: StrategyConfig,
    threshold: float,
):
    """Run one LONG RSI threshold experiment."""

    signal_function = create_experiment_signal_function(
        data=data,
        config=config,
        long_rsi_threshold=threshold,
    )

    return run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=INITIAL_CAPITAL,
        quantity=QUANTITY,
        transaction_cost_rate=TRANSACTION_COST_RATE,
    )


def calculate_metrics(result):
    """Calculate experiment performance metrics."""

    trades = result.trades

    if not trades:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "pnl": 0.0,
            "avg_trade": 0.0,
            "profit_factor": 0.0,
        }

    pnl_values = [
        float(trade.net_pnl)
        for trade in trades
    ]

    wins = [
        pnl
        for pnl in pnl_values
        if pnl > 0
    ]

    losses = [
        pnl
        for pnl in pnl_values
        if pnl < 0
    ]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    if gross_loss > 0:
        profit_factor = (
            gross_profit / gross_loss
        )
    else:
        profit_factor = float("inf")

    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (
            len(wins)
            / len(trades)
            * 100
        ),
        "pnl": sum(pnl_values),
        "avg_trade": (
            sum(pnl_values)
            / len(pnl_values)
        ),
        "profit_factor": profit_factor,
    }


def main() -> None:
    """Run all LONG RSI development experiments."""

    args = parse_args()

    print("=" * 72)
    print("SignalForge - LONG RSI Filter Experiment")
    print("=" * 72)

    # --------------------------------------------------------
    # Load full dataset
    # --------------------------------------------------------

    print()
    print(f"Data: {args.data}")

    data = load_data(args.data)

    print()
    print("Full dataset:")
    print(f"Rows:  {len(data):,}")
    print(f"Start: {data.index.min()}")
    print(f"End:   {data.index.max()}")

    # --------------------------------------------------------
    # Development period
    # --------------------------------------------------------

    development_data = get_development_data(
        data
    )

    print()
    print("Development period:")
    print(
        f"{DEVELOPMENT_START} -> "
        f"{DEVELOPMENT_END}"
    )

    print(
        f"Rows:  {len(development_data):,}"
    )

    print(
        f"Start: {development_data.index.min()}"
    )

    print(
        f"End:   {development_data.index.max()}"
    )

    # --------------------------------------------------------
    # Base configuration
    # --------------------------------------------------------

    strategy_config = StrategyConfig(
        ema_fast_period=20,
        ema_slow_period=50,
        rsi_period=14,
        atr_period=14,
        rvol_period=20,
        minimum_rvol=1.5,
        minimum_atr=0.0,
        use_rvol=False,
    )

    print()
    print("Base strategy:")
    print(
        f"EMA:       "
        f"{strategy_config.ema_fast_period} / "
        f"{strategy_config.ema_slow_period}"
    )

    print(
        f"RSI:       "
        f"{strategy_config.rsi_period}"
    )

    print(
        f"ATR:       "
        f"{strategy_config.atr_period}"
    )

    print(
        f"RVOL:      "
        f"{strategy_config.rvol_period}"
    )

    print(
        f"Use RVOL:  "
        f"{strategy_config.use_rvol}"
    )

    print()
    print(
        f"LONG RSI thresholds: "
        f"{RSI_THRESHOLDS}"
    )

    print(
        "SHORT rules: unchanged"
    )

    # --------------------------------------------------------
    # Run experiments
    # --------------------------------------------------------

    results = []

    print()
    print("=" * 72)
    print("RUNNING DEVELOPMENT EXPERIMENTS")
    print("=" * 72)

    for threshold in RSI_THRESHOLDS:

        print()
        print(
            f"Testing LONG RSI >= {threshold}"
        )

        result = run_experiment(
            data=development_data,
            config=strategy_config,
            threshold=threshold,
        )

        metrics = calculate_metrics(
            result
        )

        results.append(
            {
                "LONG_RSI": threshold,
                **metrics,
            }
        )

        print(
            f"Trades:        "
            f"{metrics['trades']}"
        )

        print(
            f"Win rate:      "
            f"{metrics['win_rate']:.2f}%"
        )

        print(
            f"P&L:           "
            f"{metrics['pnl']:.2f}"
        )

        print(
            f"Avg trade:     "
            f"{metrics['avg_trade']:.2f}"
        )

        print(
            f"Profit factor: "
            f"{metrics['profit_factor']:.3f}"
        )

    # --------------------------------------------------------
    # Results table
    # --------------------------------------------------------

    results_df = pd.DataFrame(
        results
    )

    print()
    print("=" * 72)
    print("DEVELOPMENT RESULTS")
    print("=" * 72)

    print()

    print(
        results_df.to_string(
            index=False,
            formatters={
                "win_rate": "{:.2f}".format,
                "pnl": "{:.2f}".format,
                "avg_trade": "{:.2f}".format,
                "profit_factor": "{:.3f}".format,
            },
        )
    )

    # --------------------------------------------------------
    # Ranking
    # --------------------------------------------------------

    ranked = results_df.sort_values(
        by="pnl",
        ascending=False,
    ).reset_index(drop=True)

    print()
    print("=" * 72)
    print("RANKING BY DEVELOPMENT P&L")
    print("=" * 72)

    print()

    print(
        ranked.to_string(
            index=False,
            formatters={
                "win_rate": "{:.2f}".format,
                "pnl": "{:.2f}".format,
                "avg_trade": "{:.2f}".format,
                "profit_factor": "{:.3f}".format,
            },
        )
    )

    # --------------------------------------------------------
    # Candidate
    # --------------------------------------------------------

    if not ranked.empty:

        best = ranked.iloc[0]

        print()
        print("=" * 72)
        print("BEST DEVELOPMENT CANDIDATE")
        print("=" * 72)

        print()

        print(
            f"LONG RSI threshold: "
            f"{int(best['LONG_RSI'])}"
        )

        print(
            f"Development P&L:    "
            f"{best['pnl']:.2f}"
        )

        print(
            f"Trades:              "
            f"{int(best['trades'])}"
        )

        print(
            f"Win rate:            "
            f"{best['win_rate']:.2f}%"
        )

        print(
            f"Profit factor:       "
            f"{best['profit_factor']:.3f}"
        )

    # --------------------------------------------------------
    # Research warning
    # --------------------------------------------------------

    print()
    print("=" * 72)
    print("RESEARCH NOTE")
    print("=" * 72)

    print()
    print(
        "Development-only experiment."
    )

    print(
        "Production SignalForge strategy was NOT modified."
    )

    print(
        "The candidate must pass the untouched "
        "2021-2022 validation period before "
        "any OOS test."
    )

    print("=" * 72)


if __name__ == "__main__":
    main()