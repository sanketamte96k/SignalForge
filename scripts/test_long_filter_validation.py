"""Validation test for the development-selected LONG RSI filter."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.backtest.engine import run_backtest
from src.signals.signal_engine import Signal, generate_signal
from src.strategy.backtest_strategy import (
    StrategyConfig,
    calculate_timeframe_indicators,
    signal_result_to_position,
    _make_cursors,
)


VALIDATION_START = "2021-01-01"
VALIDATION_END = "2022-12-31"

LONG_RSI_THRESHOLD = 60

INITIAL_CAPITAL = 100_000.0
QUANTITY = 1
TRANSACTION_COST_RATE = 0.0001


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the LONG RSI >= 60 candidate "
            "on the untouched 2021-2022 period."
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
    """Load historical SignalForge data."""

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


def get_validation_data(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Return only the untouched 2021-2022 validation period."""

    start = pd.Timestamp(VALIDATION_START)

    end = (
        pd.Timestamp(VALIDATION_END)
        + pd.Timedelta(days=1)
    )

    validation_data = data.loc[
        (data.index >= start)
        & (data.index < end)
    ].copy()

    if validation_data.empty:
        raise ValueError(
            "No data found for validation period."
        )

    return validation_data


def create_signal_function(
    data: pd.DataFrame,
    config: StrategyConfig,
    long_rsi_threshold: int | None,
):
    """
    Create either:

    - baseline strategy when long_rsi_threshold is None
    - LONG RSI filtered strategy otherwise

    SHORT rules remain unchanged.
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
        timestamp = row.name

        if not isinstance(timestamp, pd.Timestamp):
            timestamp = pd.Timestamp(timestamp)

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
            timeframe_30m=state_30m,
            timeframe_15m=state_15m,
            timeframe_10m=state_10m,
            timeframe_5m=state_5m,
            minimum_rvol=config.minimum_rvol,
            minimum_atr=config.minimum_atr,
            use_rvol=config.use_rvol,
        )

        # ----------------------------------------------------
        # Baseline: no additional LONG filter.
        # ----------------------------------------------------

        if long_rsi_threshold is None:
            return signal_result_to_position(result)

        # ----------------------------------------------------
        # Candidate: LONG RSI >= 60.
        # ----------------------------------------------------

        if result.signal == Signal.BUY:

            rsi_values = [
                state_30m.rsi,
                state_15m.rsi,
                state_10m.rsi,
                state_5m.rsi,
            ]

            if any(
                rsi < long_rsi_threshold
                for rsi in rsi_values
            ):
                return None

        # SHORT remains exactly unchanged.
        return signal_result_to_position(result)

    return signal_function


def run_test(
    data: pd.DataFrame,
    config: StrategyConfig,
    long_rsi_threshold: int | None,
):
    """Run one validation backtest."""

    signal_function = create_signal_function(
        data=data,
        config=config,
        long_rsi_threshold=long_rsi_threshold,
    )

    return run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=INITIAL_CAPITAL,
        quantity=QUANTITY,
        transaction_cost_rate=TRANSACTION_COST_RATE,
    )


def calculate_metrics(result):
    """Calculate validation metrics."""

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
        pnl for pnl in pnl_values
        if pnl > 0
    ]

    losses = [
        pnl for pnl in pnl_values
        if pnl < 0
    ]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else float("inf")
    )

    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (
            len(wins) / len(trades) * 100
        ),
        "pnl": sum(pnl_values),
        "avg_trade": (
            sum(pnl_values) / len(pnl_values)
        ),
        "profit_factor": profit_factor,
    }


def print_metrics(
    label: str,
    metrics: dict,
) -> None:
    """Print one result block."""

    print()
    print(label)
    print("-" * 50)

    print(
        f"Trades:        "
        f"{metrics['trades']}"
    )

    print(
        f"Winning:       "
        f"{metrics['wins']}"
    )

    print(
        f"Losing:        "
        f"{metrics['losses']}"
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


def main() -> None:
    args = parse_args()

    print("=" * 72)
    print("SignalForge - LONG RSI Validation")
    print("=" * 72)

    print()
    print(f"Data: {args.data}")

    data = load_data(args.data)

    print()
    print("Full dataset:")
    print(f"Rows:  {len(data):,}")
    print(f"Start: {data.index.min()}")
    print(f"End:   {data.index.max()}")

    validation_data = get_validation_data(data)

    print()
    print("Validation period:")
    print(
        f"{VALIDATION_START} -> "
        f"{VALIDATION_END}"
    )

    print(
        f"Rows:  {len(validation_data):,}"
    )

    print(
        f"Start: {validation_data.index.min()}"
    )

    print(
        f"End:   {validation_data.index.max()}"
    )

    # --------------------------------------------------------
    # Same configuration as baseline.
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
    print("Strategy configuration:")
    print("EMA:       20 / 50")
    print("RSI:       14")
    print("ATR:       14")
    print("RVOL:      disabled")
    print("Costs:     0.0001")

    # --------------------------------------------------------
    # Baseline
    # --------------------------------------------------------

    print()
    print("=" * 72)
    print("1. BASELINE")
    print("=" * 72)

    baseline_result = run_test(
        data=validation_data,
        config=strategy_config,
        long_rsi_threshold=None,
    )

    baseline_metrics = calculate_metrics(
        baseline_result
    )

    print_metrics(
        "Original strategy",
        baseline_metrics,
    )

    # --------------------------------------------------------
    # RSI 60 candidate
    # --------------------------------------------------------

    print()
    print("=" * 72)
    print("2. LONG RSI >= 60 CANDIDATE")
    print("=" * 72)

    candidate_result = run_test(
        data=validation_data,
        config=strategy_config,
        long_rsi_threshold=LONG_RSI_THRESHOLD,
    )

    candidate_metrics = calculate_metrics(
        candidate_result
    )

    print_metrics(
        "LONG RSI >= 60",
        candidate_metrics,
    )

    # --------------------------------------------------------
    # Comparison
    # --------------------------------------------------------

    pnl_difference = (
        candidate_metrics["pnl"]
        - baseline_metrics["pnl"]
    )

    avg_trade_difference = (
        candidate_metrics["avg_trade"]
        - baseline_metrics["avg_trade"]
    )

    win_rate_difference = (
        candidate_metrics["win_rate"]
        - baseline_metrics["win_rate"]
    )

    pf_difference = (
        candidate_metrics["profit_factor"]
        - baseline_metrics["profit_factor"]
    )

    trade_difference = (
        candidate_metrics["trades"]
        - baseline_metrics["trades"]
    )

    print()
    print("=" * 72)
    print("VALIDATION COMPARISON")
    print("=" * 72)

    print()

    print(
        f"{'Metric':<22}"
        f"{'Baseline':>15}"
        f"{'RSI >= 60':>15}"
        f"{'Difference':>15}"
    )

    print("-" * 67)

    print(
        f"{'Trades':<22}"
        f"{baseline_metrics['trades']:>15}"
        f"{candidate_metrics['trades']:>15}"
        f"{trade_difference:>15}"
    )

    print(
        f"{'Win rate %':<22}"
        f"{baseline_metrics['win_rate']:>15.2f}"
        f"{candidate_metrics['win_rate']:>15.2f}"
        f"{win_rate_difference:>15.2f}"
    )

    print(
        f"{'P&L':<22}"
        f"{baseline_metrics['pnl']:>15.2f}"
        f"{candidate_metrics['pnl']:>15.2f}"
        f"{pnl_difference:>15.2f}"
    )

    print(
        f"{'Avg trade':<22}"
        f"{baseline_metrics['avg_trade']:>15.2f}"
        f"{candidate_metrics['avg_trade']:>15.2f}"
        f"{avg_trade_difference:>15.2f}"
    )

    print(
        f"{'Profit factor':<22}"
        f"{baseline_metrics['profit_factor']:>15.3f}"
        f"{candidate_metrics['profit_factor']:>15.3f}"
        f"{pf_difference:>15.3f}"
    )

    # --------------------------------------------------------
    # Interpretation
    # --------------------------------------------------------

    print()
    print("=" * 72)
    print("VALIDATION INTERPRETATION")
    print("=" * 72)

    print()

    if (
        candidate_metrics["pnl"]
        > baseline_metrics["pnl"]
        and candidate_metrics["profit_factor"]
        > baseline_metrics["profit_factor"]
    ):
        print(
            "RESULT: RSI >= 60 improves both P&L "
            "and profit factor versus baseline."
        )
    else:
        print(
            "RESULT: RSI >= 60 does NOT improve both "
            "P&L and profit factor versus baseline."
        )

    print()
    print(
        "This validation result must NOT be used to "
        "retune the threshold."
    )

    print(
        "The 2023-2024 period remains untouched OOS data."
    )

    print()
    print(
        "Production SignalForge strategy was NOT modified."
    )

    print("=" * 72)


if __name__ == "__main__":
    main()