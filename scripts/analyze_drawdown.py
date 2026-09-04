from __future__ import annotations

import sys
from dataclasses import dataclass
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


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "historical"
    / "nifty50_1m_signalforge.csv"
)

INITIAL_CAPITAL = 100_000.0
QUANTITY = 1
TRANSACTION_COST_RATE = 0.0001

TOP_DRAWDOWNS = 10
TOP_LOSSES = 10


# ---------------------------------------------------------------------
# Drawdown event model
# ---------------------------------------------------------------------

@dataclass
class DrawdownEvent:
    peak_trade_number: int
    trough_trade_number: int
    recovery_trade_number: int | None

    peak_time: pd.Timestamp
    trough_time: pd.Timestamp
    recovery_time: pd.Timestamp | None

    peak_equity: float
    trough_equity: float

    drawdown_amount: float
    drawdown_pct: float

    drawdown_trades: int
    recovery_trades: int | None


# ---------------------------------------------------------------------
# Load historical data
# ---------------------------------------------------------------------

def load_data() -> pd.DataFrame:
    """Load and validate the complete historical 1-minute dataset."""

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Historical data not found:\n{DATA_PATH}"
        )

    data = pd.read_csv(
        DATA_PATH,
        parse_dates=["timestamp"],
    )

    if "timestamp" not in data.columns:
        raise ValueError(
            "Dataset must contain a 'timestamp' column."
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

    required_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    missing = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
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


# ---------------------------------------------------------------------
# Frozen baseline configuration
# ---------------------------------------------------------------------

def make_config() -> StrategyConfig:
    """Return the exact frozen baseline strategy configuration."""

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


# ---------------------------------------------------------------------
# Baseline signal function
# ---------------------------------------------------------------------

def create_baseline_signal_function(
    data: pd.DataFrame,
    config: StrategyConfig,
):
    """
    Create the same frozen baseline signal function used in 7.1/7.2.

    Indicator history is calculated across the complete dataset.
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


# ---------------------------------------------------------------------
# Run complete chronological backtest
# ---------------------------------------------------------------------

def run_baseline_backtest(
    data: pd.DataFrame,
    config: StrategyConfig,
):
    """Run one continuous chronological baseline backtest."""

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


# ---------------------------------------------------------------------
# Build equity curve
# ---------------------------------------------------------------------

def build_equity_curve(trades):
    """
    Build the realized trade-by-trade equity curve.

    Each point represents equity after a completed trade.
    """

    rows = []

    equity = INITIAL_CAPITAL

    rows.append(
        {
            "trade_number": 0,
            "time": pd.Timestamp.min,
            "equity": equity,
        }
    )

    for trade_number, trade in enumerate(
        trades,
        start=1,
    ):
        equity += float(trade.net_pnl)

        rows.append(
            {
                "trade_number": trade_number,
                "time": pd.Timestamp(trade.exit_time),
                "equity": equity,
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------
# Detect drawdown events
# ---------------------------------------------------------------------

def detect_drawdowns(
    trades,
) -> list[DrawdownEvent]:
    """
    Detect every peak-to-trough drawdown and its recovery.

    A drawdown begins after equity falls below a prior equity high.

    Recovery occurs when equity returns to or exceeds the previous
    peak.
    """

    if not trades:
        return []

    equity = INITIAL_CAPITAL
    peak_equity = INITIAL_CAPITAL

    peak_trade_number = 0
    peak_time = pd.Timestamp.min

    current_drawdown = None
    events = []

    for trade_number, trade in enumerate(
        trades,
        start=1,
    ):
        exit_time = pd.Timestamp(
            trade.exit_time
        )

        equity += float(trade.net_pnl)

        # -------------------------------------------------------------
        # New equity high / recovery
        # -------------------------------------------------------------

        if equity >= peak_equity:

            if current_drawdown is not None:

                trough = current_drawdown

                recovery_trades = (
                    trade_number
                    - trough["trough_trade_number"]
                )

                events.append(
                    DrawdownEvent(
                        peak_trade_number=(
                            trough["peak_trade_number"]
                        ),
                        trough_trade_number=(
                            trough["trough_trade_number"]
                        ),
                        recovery_trade_number=(
                            trade_number
                        ),
                        peak_time=trough["peak_time"],
                        trough_time=trough["trough_time"],
                        recovery_time=exit_time,
                        peak_equity=trough["peak_equity"],
                        trough_equity=trough["trough_equity"],
                        drawdown_amount=(
                            trough["peak_equity"]
                            - trough["trough_equity"]
                        ),
                        drawdown_pct=(
                            (
                                trough["peak_equity"]
                                - trough["trough_equity"]
                            )
                            / trough["peak_equity"]
                            * 100.0
                        ),
                        drawdown_trades=(
                            trough["trough_trade_number"]
                            - trough["peak_trade_number"]
                        ),
                        recovery_trades=recovery_trades,
                    )
                )

                current_drawdown = None

            peak_equity = equity
            peak_trade_number = trade_number
            peak_time = exit_time

            continue

        # -------------------------------------------------------------
        # Currently below equity peak
        # -------------------------------------------------------------

        if current_drawdown is None:

            current_drawdown = {
                "peak_trade_number": peak_trade_number,
                "peak_time": peak_time,
                "peak_equity": peak_equity,
                "trough_trade_number": trade_number,
                "trough_time": exit_time,
                "trough_equity": equity,
            }

        elif equity < current_drawdown["trough_equity"]:

            current_drawdown["trough_trade_number"] = (
                trade_number
            )

            current_drawdown["trough_time"] = (
                exit_time
            )

            current_drawdown["trough_equity"] = (
                equity
            )

    # -------------------------------------------------------------
    # Unrecovered final drawdown
    # -------------------------------------------------------------

    if current_drawdown is not None:

        trough = current_drawdown

        events.append(
            DrawdownEvent(
                peak_trade_number=(
                    trough["peak_trade_number"]
                ),
                trough_trade_number=(
                    trough["trough_trade_number"]
                ),
                recovery_trade_number=None,
                peak_time=trough["peak_time"],
                trough_time=trough["trough_time"],
                recovery_time=None,
                peak_equity=trough["peak_equity"],
                trough_equity=trough["trough_equity"],
                drawdown_amount=(
                    trough["peak_equity"]
                    - trough["trough_equity"]
                ),
                drawdown_pct=(
                    (
                        trough["peak_equity"]
                        - trough["trough_equity"]
                    )
                    / trough["peak_equity"]
                    * 100.0
                ),
                drawdown_trades=(
                    trough["trough_trade_number"]
                    - trough["peak_trade_number"]
                ),
                recovery_trades=None,
            )
        )

    return events


# ---------------------------------------------------------------------
# Global drawdown statistics
# ---------------------------------------------------------------------

def calculate_global_drawdown_metrics(
    trades,
    drawdowns,
):
    """Calculate overall drawdown statistics."""

    if not trades:
        return {
            "final_equity": INITIAL_CAPITAL,
            "net_pnl": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "max_drawdown_event": None,
            "longest_drawdown_trades": 0,
            "longest_recovery_trades": 0,
            "drawdown_count": 0,
            "unrecovered_drawdowns": 0,
        }

    equity = INITIAL_CAPITAL
    peak_equity = INITIAL_CAPITAL
    max_drawdown = 0.0
    max_drawdown_pct = 0.0

    for trade in trades:

        equity += float(trade.net_pnl)

        peak_equity = max(
            peak_equity,
            equity,
        )

        drawdown = (
            peak_equity
            - equity
        )

        drawdown_pct = (
            drawdown / peak_equity * 100.0
            if peak_equity > 0
            else 0.0
        )

        max_drawdown = max(
            max_drawdown,
            drawdown,
        )

        max_drawdown_pct = max(
            max_drawdown_pct,
            drawdown_pct,
        )

    longest_drawdown_trades = max(
        (
            event.drawdown_trades
            for event in drawdowns
        ),
        default=0,
    )

    longest_recovery_trades = max(
        (
            event.recovery_trades
            for event in drawdowns
            if event.recovery_trades is not None
        ),
        default=0,
    )

    unrecovered_drawdowns = sum(
        event.recovery_trade_number is None
        for event in drawdowns
    )

    max_drawdown_event = (
        max(
            drawdowns,
            key=lambda event: event.drawdown_amount,
        )
        if drawdowns
        else None
    )

    return {
        "final_equity": equity,
        "net_pnl": equity - INITIAL_CAPITAL,
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown_pct,
        "max_drawdown_event": max_drawdown_event,
        "longest_drawdown_trades": longest_drawdown_trades,
        "longest_recovery_trades": longest_recovery_trades,
        "drawdown_count": len(drawdowns),
        "unrecovered_drawdowns": unrecovered_drawdowns,
    }


# ---------------------------------------------------------------------
# Losing streak
# ---------------------------------------------------------------------

def calculate_losing_streak(trades):
    """Calculate worst consecutive losing-trade streak."""

    current = 0
    worst = 0

    for trade in trades:

        if float(trade.net_pnl) < 0:

            current += 1

            worst = max(
                worst,
                current,
            )

        else:
            current = 0

    return worst


# ---------------------------------------------------------------------
# Top individual losses
# ---------------------------------------------------------------------

def get_top_losses(
    trades,
    limit: int,
):
    """Return the largest individual losing trades."""

    losses = [
        trade
        for trade in trades
        if float(trade.net_pnl) < 0
    ]

    losses.sort(
        key=lambda trade: float(
            trade.net_pnl
        )
    )

    return losses[:limit]


# ---------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------

def print_drawdown_event(
    rank: int,
    event: DrawdownEvent,
):
    """Print one drawdown event."""

    recovery_text = (
        str(event.recovery_time)
        if event.recovery_time is not None
        else "NOT RECOVERED"
    )

    recovery_trades_text = (
        str(event.recovery_trades)
        if event.recovery_trades is not None
        else "N/A"
    )

    print(
        f"{rank:>2}. "
        f"Peak {event.peak_time} "
        f"-> Trough {event.trough_time} "
        f"-> Recovery {recovery_text}"
    )

    print(
        f"    Drawdown: "
        f"{event.drawdown_amount:.2f} "
        f"({event.drawdown_pct:.2f}%)"
    )

    print(
        f"    Peak equity: "
        f"{event.peak_equity:.2f}"
    )

    print(
        f"    Trough equity: "
        f"{event.trough_equity:.2f}"
    )

    print(
        f"    Peak trade #: "
        f"{event.peak_trade_number}"
    )

    print(
        f"    Trough trade #: "
        f"{event.trough_trade_number}"
    )

    print(
        f"    Drawdown length: "
        f"{event.drawdown_trades} trades"
    )

    print(
        f"    Recovery length: "
        f"{recovery_trades_text} trades"
    )


def print_top_losses(
    trades,
    limit: int,
):
    """Print largest individual losing trades."""

    top_losses = get_top_losses(
        trades,
        limit,
    )

    print()
    print("TOP INDIVIDUAL LOSSES")
    print("-" * 110)

    if not top_losses:
        print("No losing trades.")

        return

    for rank, trade in enumerate(
        top_losses,
        start=1,
    ):

        print(
            f"{rank:>2}. "
            f"{pd.Timestamp(trade.entry_time)} "
            f"-> "
            f"{pd.Timestamp(trade.exit_time)} "
            f"| P&L: {float(trade.net_pnl):+.2f}"
        )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():

    print("=" * 110)
    print(
        "SIGNALFORGE - PHASE 7.3 "
        "DRAWDOWN ANALYSIS"
    )
    print("=" * 110)

    # -------------------------------------------------------------
    # Load data
    # -------------------------------------------------------------

    print()
    print("Loading complete historical dataset...")

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
    # Configuration
    # -------------------------------------------------------------

    config = make_config()

    print()
    print("Frozen baseline configuration:")
    print(
        f"  EMA: "
        f"{config.ema_fast_period} / "
        f"{config.ema_slow_period}"
    )

    print(
        f"  RSI period: "
        f"{config.rsi_period}"
    )

    print(
        f"  ATR period: "
        f"{config.atr_period}"
    )

    print(
        f"  RVOL period: "
        f"{config.rvol_period}"
    )

    print(
        f"  Minimum RVOL: "
        f"{config.minimum_rvol}"
    )

    print(
        f"  Minimum ATR: "
        f"{config.minimum_atr}"
    )

    print(
        f"  RVOL enabled: "
        f"{config.use_rvol}"
    )

    # -------------------------------------------------------------
    # Backtest
    # -------------------------------------------------------------

    print()
    print(
        "Running one continuous chronological "
        "backtest..."
    )

    result = run_baseline_backtest(
        data,
        config,
    )

    trades = list(result.trades)

    print(
        f"Completed trades: "
        f"{len(trades):,}"
    )

    if not trades:
        raise RuntimeError(
            "Backtest produced no completed trades."
        )

    # -------------------------------------------------------------
    # Equity curve
    # -------------------------------------------------------------

    print()
    print(
        "Building realized equity curve..."
    )

    equity_curve = build_equity_curve(
        trades
    )

    print(
        f"Final equity: "
        f"{equity_curve.iloc[-1]['equity']:.2f}"
    )

    # -------------------------------------------------------------
    # Drawdown detection
    # -------------------------------------------------------------

    print()
    print(
        "Detecting drawdown periods..."
    )

    drawdowns = detect_drawdowns(
        trades
    )

    metrics = calculate_global_drawdown_metrics(
        trades,
        drawdowns,
    )

    # -------------------------------------------------------------
    # Overall statistics
    # -------------------------------------------------------------

    wins = sum(
        float(trade.net_pnl) > 0
        for trade in trades
    )

    losses = sum(
        float(trade.net_pnl) < 0
        for trade in trades
    )

    win_rate = (
        wins / len(trades) * 100.0
    )

    worst_losing_streak = (
        calculate_losing_streak(
            trades
        )
    )

    # -------------------------------------------------------------
    # Main report
    # -------------------------------------------------------------

    print()
    print("=" * 110)
    print("OVERALL DRAWdown STATISTICS")
    print("=" * 110)

    print(
        f"Completed trades       : "
        f"{len(trades)}"
    )

    print(
        f"Wins                   : "
        f"{wins}"
    )

    print(
        f"Losses                 : "
        f"{losses}"
    )

    print(
        f"Win rate               : "
        f"{win_rate:.2f}%"
    )

    print(
        f"Net P&L                : "
        f"{metrics['net_pnl']:+.2f}"
    )

    print(
        f"Final equity           : "
        f"{metrics['final_equity']:.2f}"
    )

    print(
        f"Maximum drawdown       : "
        f"{metrics['max_drawdown']:.2f}"
    )

    print(
        f"Maximum drawdown %     : "
        f"{metrics['max_drawdown_pct']:.2f}%"
    )

    print(
        f"Drawdown periods       : "
        f"{metrics['drawdown_count']}"
    )

    print(
        f"Unrecovered drawdowns  : "
        f"{metrics['unrecovered_drawdowns']}"
    )

    print(
        f"Longest drawdown       : "
        f"{metrics['longest_drawdown_trades']} trades"
    )

    print(
        f"Longest recovery       : "
        f"{metrics['longest_recovery_trades']} trades"
    )

    print(
        f"Worst losing streak    : "
        f"{worst_losing_streak} trades"
    )

    # -------------------------------------------------------------
    # Maximum drawdown event
    # -------------------------------------------------------------

    max_event = metrics[
        "max_drawdown_event"
    ]

    if max_event is not None:

        print()
        print("=" * 110)
        print("MAXIMUM DRAWDOWN EVENT")
        print("=" * 110)

        print_drawdown_event(
            1,
            max_event,
        )

    # -------------------------------------------------------------
    # Top drawdown periods
    # -------------------------------------------------------------

    print()
    print("=" * 110)
    print(
        f"TOP {TOP_DRAWDOWNS} "
        "DRAWDOWN PERIODS"
    )
    print("=" * 110)

    sorted_drawdowns = sorted(
        drawdowns,
        key=lambda event: event.drawdown_amount,
        reverse=True,
    )

    for rank, event in enumerate(
        sorted_drawdowns[:TOP_DRAWDOWNS],
        start=1,
    ):

        print_drawdown_event(
            rank,
            event,
        )

    # -------------------------------------------------------------
    # Longest drawdown periods
    # -------------------------------------------------------------

    print()
    print("=" * 110)
    print(
        f"TOP {TOP_DRAWDOWNS} "
        "LONGEST DRAWDOWN PERIODS"
    )
    print("=" * 110)

    longest_drawdowns = sorted(
        drawdowns,
        key=lambda event: event.drawdown_trades,
        reverse=True,
    )

    for rank, event in enumerate(
        longest_drawdowns[:TOP_DRAWDOWNS],
        start=1,
    ):

        recovery_text = (
            f"{event.recovery_trades} trades"
            if event.recovery_trades is not None
            else "NOT RECOVERED"
        )

        print(
            f"{rank:>2}. "
            f"{event.peak_time} "
            f"-> "
            f"{event.trough_time} "
            f"| DD: "
            f"{event.drawdown_amount:.2f} "
            f"({event.drawdown_pct:.2f}%) "
            f"| Length: "
            f"{event.drawdown_trades} trades "
            f"| Recovery: "
            f"{recovery_text}"
        )

    # -------------------------------------------------------------
    # Recovery analysis
    # -------------------------------------------------------------

    recovered = [
        event
        for event in drawdowns
        if event.recovery_trades is not None
    ]

    if recovered:

        recovery_values = np.array(
            [
                event.recovery_trades
                for event in recovered
            ],
            dtype=float,
        )

        print()
        print("=" * 110)
        print("RECOVERY ANALYSIS")
        print("=" * 110)

        print(
            f"Recovered drawdowns    : "
            f"{len(recovered)}"
        )

        print(
            f"Average recovery       : "
            f"{np.mean(recovery_values):.2f} trades"
        )

        print(
            f"Median recovery        : "
            f"{np.median(recovery_values):.2f} trades"
        )

        print(
            f"Maximum recovery       : "
            f"{np.max(recovery_values):.0f} trades"
        )

    # -------------------------------------------------------------
    # Top individual losses
    # -------------------------------------------------------------

    print_top_losses(
        trades,
        TOP_LOSSES,
    )

    # -------------------------------------------------------------
    # Final research interpretation
    # -------------------------------------------------------------

    print()
    print("=" * 110)
    print("RESEARCH CHECK")
    print("=" * 110)

    print(
        "This analysis uses the frozen baseline strategy only."
    )

    print(
        "No parameter optimization or candidate strategy "
        "comparison was performed."
    )

    print(
        "Drawdown is measured on the complete chronological "
        "trade sequence."
    )

    print(
        "Quantity remains fixed at 1, so the reported P&L/DD "
        "is not a position-sizing recommendation."
    )

    print()
    print("=" * 110)
    print(
        "PHASE 7.3 DRAWDOWN ANALYSIS COMPLETE"
    )
    print("=" * 110)


if __name__ == "__main__":
    main()