from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Project path
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# SignalForge imports
# ---------------------------------------------------------------------------

from src.backtest.engine import run_backtest
from src.backtest.simulator import Position
from src.paper_trading.runner import PaperTradingRunner
from src.strategy.backtest_strategy import (
    StrategyConfig,
    create_signal_function,
)


# ---------------------------------------------------------------------------
# Frozen SignalForge configuration
# ---------------------------------------------------------------------------

DEFAULT_DATA_PATH = Path(
    "data/historical/nifty50_1m_signalforge.csv"
)

STARTING_CAPITAL = 100_000.0
QUANTITY = 1
TRANSACTION_COST_RATE = 0.0001

EMA_FAST_PERIOD = 20
EMA_SLOW_PERIOD = 50
RSI_PERIOD = 14
ATR_PERIOD = 14
RVOL_PERIOD = 20
MINIMUM_RVOL = 1.5
MINIMUM_ATR = 0.0
MINIMUM_LONG_RSI = 60.0

USE_RVOL = False


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_market_data(
    data_path: Path,
    start: str,
    end: str,
) -> pd.DataFrame:
    """Load and prepare historical market data."""

    if not data_path.exists():
        raise FileNotFoundError(
            f"Market data file not found: {data_path}"
        )

    data = pd.read_csv(
        data_path,
        index_col=0,
        parse_dates=True,
    )

    data = data.sort_index()

    required_columns = {
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing_columns = required_columns - set(data.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    if not isinstance(data.index, pd.DatetimeIndex):
        raise TypeError(
            "Market data index must be a DatetimeIndex."
        )

    if not data.index.is_monotonic_increasing:
        raise ValueError(
            "Market data index must be monotonically increasing."
        )

    start_timestamp = pd.Timestamp(start)
    end_timestamp = pd.Timestamp(end)

    data = data.loc[
        (data.index >= start_timestamp)
        & (data.index <= end_timestamp)
    ].copy()

    if data.empty:
        raise ValueError(
            "No market data found for the requested period."
        )

    return data


# ---------------------------------------------------------------------------
# Strategy configuration
# ---------------------------------------------------------------------------

def create_frozen_config() -> StrategyConfig:
    """Return the frozen production/research strategy configuration."""

    return StrategyConfig(
        ema_fast_period=EMA_FAST_PERIOD,
        ema_slow_period=EMA_SLOW_PERIOD,
        rsi_period=RSI_PERIOD,
        atr_period=ATR_PERIOD,
        rvol_period=RVOL_PERIOD,
        minimum_rvol=MINIMUM_RVOL,
        minimum_atr=MINIMUM_ATR,
        minimum_long_rsi=MINIMUM_LONG_RSI,
        use_rvol=USE_RVOL,
    )


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

def run_backtest_engine(
    data: pd.DataFrame,
    config: StrategyConfig,
):
    """Run the authoritative SignalForge backtest engine."""

    signal_function = create_signal_function(
        data=data,
        config=config,
    )

    return run_backtest(
        data=data,
        signal_function=signal_function,
        initial_capital=STARTING_CAPITAL,
        quantity=QUANTITY,
        transaction_cost_rate=TRANSACTION_COST_RATE,
    )


# ---------------------------------------------------------------------------
# Paper trading
# ---------------------------------------------------------------------------

def run_paper_engine(
    data: pd.DataFrame,
    config: StrategyConfig,
):
    """Run the SignalForge paper trading engine."""

    runner = PaperTradingRunner(
        starting_capital=STARTING_CAPITAL,
        quantity=QUANTITY,
        transaction_cost_rate=TRANSACTION_COST_RATE,
        strategy_config=config,
    )

    return runner.run(data)


# ---------------------------------------------------------------------------
# Trade normalization
# ---------------------------------------------------------------------------

def normalize_backtest_trades(
    trades,
) -> list[dict]:
    """Convert backtest Trade objects into comparable dictionaries."""

    normalized = []

    for trade in trades:
        normalized.append(
            {
                "position": trade.position,
                "entry_time": trade.entry_time,
                "exit_time": trade.exit_time,
                "entry_price": float(trade.entry_price),
                "exit_price": float(trade.exit_price),
                "quantity": int(trade.quantity),
                "gross_pnl": float(trade.gross_pnl),
                "transaction_cost": float(
                    trade.transaction_cost
                ),
                "net_pnl": float(trade.net_pnl),
            }
        )

    return normalized


def normalize_paper_trades(
    trades,
) -> list[dict]:
    """Convert paper PaperTrade objects into comparable dictionaries."""

    normalized = []

    for trade in trades:
        normalized.append(
            {
                "position": trade.position,
                "entry_time": trade.entry_time,
                "exit_time": trade.exit_time,
                "entry_price": float(trade.entry_price),
                "exit_price": float(trade.exit_price),
                "quantity": int(trade.quantity),
                "gross_pnl": float(trade.gross_pnl),
                "transaction_cost": float(
                    trade.transaction_cost
                ),
                "net_pnl": float(trade.net_pnl),
            }
        )

    return normalized


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

PRICE_TOLERANCE = 1e-9
PNL_TOLERANCE = 1e-9


def values_match(
    left: float,
    right: float,
    tolerance: float,
) -> bool:
    return abs(left - right) <= tolerance


def compare_trades(
    backtest_trades: list[dict],
    paper_trades: list[dict],
) -> tuple[bool, list[str]]:
    """Compare backtest and paper trades one by one."""

    differences: list[str] = []

    if len(backtest_trades) != len(paper_trades):
        differences.append(
            "Trade count mismatch: "
            f"backtest={len(backtest_trades)}, "
            f"paper={len(paper_trades)}"
        )

    common_count = min(
        len(backtest_trades),
        len(paper_trades),
    )

    for index in range(common_count):
        backtest_trade = backtest_trades[index]
        paper_trade = paper_trades[index]

        prefix = f"Trade #{index + 1}"

        if backtest_trade["position"] != paper_trade["position"]:
            differences.append(
                f"{prefix}: position mismatch: "
                f"backtest={backtest_trade['position']}, "
                f"paper={paper_trade['position']}"
            )

        if (
            backtest_trade["entry_time"]
            != paper_trade["entry_time"]
        ):
            differences.append(
                f"{prefix}: entry time mismatch: "
                f"backtest={backtest_trade['entry_time']}, "
                f"paper={paper_trade['entry_time']}"
            )

        if (
            backtest_trade["exit_time"]
            != paper_trade["exit_time"]
        ):
            differences.append(
                f"{prefix}: exit time mismatch: "
                f"backtest={backtest_trade['exit_time']}, "
                f"paper={paper_trade['exit_time']}"
            )

        if not values_match(
            backtest_trade["entry_price"],
            paper_trade["entry_price"],
            PRICE_TOLERANCE,
        ):
            differences.append(
                f"{prefix}: entry price mismatch: "
                f"backtest={backtest_trade['entry_price']}, "
                f"paper={paper_trade['entry_price']}"
            )

        if not values_match(
            backtest_trade["exit_price"],
            paper_trade["exit_price"],
            PRICE_TOLERANCE,
        ):
            differences.append(
                f"{prefix}: exit price mismatch: "
                f"backtest={backtest_trade['exit_price']}, "
                f"paper={paper_trade['exit_price']}"
            )

        if (
            backtest_trade["quantity"]
            != paper_trade["quantity"]
        ):
            differences.append(
                f"{prefix}: quantity mismatch: "
                f"backtest={backtest_trade['quantity']}, "
                f"paper={paper_trade['quantity']}"
            )

        if not values_match(
            backtest_trade["gross_pnl"],
            paper_trade["gross_pnl"],
            PNL_TOLERANCE,
        ):
            differences.append(
                f"{prefix}: gross P&L mismatch: "
                f"backtest={backtest_trade['gross_pnl']}, "
                f"paper={paper_trade['gross_pnl']}"
            )

        if not values_match(
            backtest_trade["transaction_cost"],
            paper_trade["transaction_cost"],
            PNL_TOLERANCE,
        ):
            differences.append(
                f"{prefix}: transaction cost mismatch: "
                f"backtest={backtest_trade['transaction_cost']}, "
                f"paper={paper_trade['transaction_cost']}"
            )

        if not values_match(
            backtest_trade["net_pnl"],
            paper_trade["net_pnl"],
            PNL_TOLERANCE,
        ):
            differences.append(
                f"{prefix}: net P&L mismatch: "
                f"backtest={backtest_trade['net_pnl']}, "
                f"paper={paper_trade['net_pnl']}"
            )

    return len(differences) == 0, differences


# ---------------------------------------------------------------------------
# P&L comparison
# ---------------------------------------------------------------------------

def total_net_pnl(
    trades: list[dict],
) -> float:
    return sum(
        trade["net_pnl"]
        for trade in trades
    )


def total_gross_pnl(
    trades: list[dict],
) -> float:
    return sum(
        trade["gross_pnl"]
        for trade in trades
    )


def total_transaction_cost(
    trades: list[dict],
) -> float:
    return sum(
        trade["transaction_cost"]
        for trade in trades
    )


def print_pnl_summary(
    backtest_trades: list[dict],
    paper_trades: list[dict],
) -> None:
    backtest_gross = total_gross_pnl(
        backtest_trades
    )
    paper_gross = total_gross_pnl(
        paper_trades
    )

    backtest_cost = total_transaction_cost(
        backtest_trades
    )
    paper_cost = total_transaction_cost(
        paper_trades
    )

    backtest_net = total_net_pnl(
        backtest_trades
    )
    paper_net = total_net_pnl(
        paper_trades
    )

    print()
    print("=" * 72)
    print("P&L COMPARISON")
    print("=" * 72)

    print(
        f"Backtest gross P&L:       ₹{backtest_gross:,.2f}"
    )
    print(
        f"Paper gross P&L:         ₹{paper_gross:,.2f}"
    )
    print(
        f"Gross difference:        ₹{backtest_gross - paper_gross:,.2f}"
    )

    print()

    print(
        f"Backtest transaction cost: ₹{backtest_cost:,.2f}"
    )
    print(
        f"Paper transaction cost:    ₹{paper_cost:,.2f}"
    )
    print(
        f"Cost difference:           ₹{backtest_cost - paper_cost:,.2f}"
    )

    print()

    print(
        f"Backtest net P&L:         ₹{backtest_net:,.2f}"
    )
    print(
        f"Paper net P&L:            ₹{paper_net:,.2f}"
    )
    print(
        f"Net difference:           ₹{backtest_net - paper_net:,.2f}"
    )


# ---------------------------------------------------------------------------
# Trade summary
# ---------------------------------------------------------------------------

def print_trade_summary(
    backtest_trades: list[dict],
    paper_trades: list[dict],
) -> None:
    print()
    print("=" * 72)
    print("TRADE COMPARISON")
    print("=" * 72)

    print(
        f"Backtest trades: {len(backtest_trades)}"
    )

    print(
        f"Paper trades:    {len(paper_trades)}"
    )

    common_count = min(
        len(backtest_trades),
        len(paper_trades),
    )

    print(
        f"Compared trades: {common_count}"
    )

    if backtest_trades:
        first = backtest_trades[0]
        last = backtest_trades[-1]

        print()
        print("Backtest first trade:")
        print(
            f"  {first['position']} "
            f"{first['entry_time']} → "
            f"{first['exit_time']}"
        )

        print("Backtest last trade:")
        print(
            f"  {last['position']} "
            f"{last['entry_time']} → "
            f"{last['exit_time']}"
        )

    if paper_trades:
        first = paper_trades[0]
        last = paper_trades[-1]

        print()
        print("Paper first trade:")
        print(
            f"  {first['position']} "
            f"{first['entry_time']} → "
            f"{first['exit_time']}"
        )

        print("Paper last trade:")
        print(
            f"  {last['position']} "
            f"{last['entry_time']} → "
            f"{last['exit_time']}"
        )


# ---------------------------------------------------------------------------
# Detailed mismatch reporting
# ---------------------------------------------------------------------------

def print_differences(
    differences: list[str],
) -> None:
    if not differences:
        return

    print()
    print("=" * 72)
    print("PARITY DIFFERENCES")
    print("=" * 72)

    max_display = 50

    for difference in differences[:max_display]:
        print(f"- {difference}")

    if len(differences) > max_display:
        print(
            f"... and "
            f"{len(differences) - max_display} "
            f"additional differences."
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate parity between the SignalForge "
            "backtest engine and paper trading engine."
        )
    )

    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help="Path to historical OHLCV CSV.",
    )

    parser.add_argument(
        "--start",
        required=True,
        help="Start date, e.g. 2023-01-01.",
    )

    parser.add_argument(
        "--end",
        required=True,
        help="End date, e.g. 2024-03-31.",
    )

    args = parser.parse_args()

    print("=" * 72)
    print("SIGNALFORGE PAPER/BACKTEST PARITY VALIDATION")
    print("=" * 72)

    print()
    print(f"Data:   {args.data}")
    print(f"Start:  {args.start}")
    print(f"End:    {args.end}")

    # -----------------------------------------------------------------------
    # Load data
    # -----------------------------------------------------------------------

    data = load_market_data(
        data_path=args.data,
        start=args.start,
        end=args.end,
    )

    print()
    print(
        f"Testing {len(data):,} one-minute candles."
    )

    print(
        f"Period: "
        f"{data.index.min()} → {data.index.max()}"
    )

    # -----------------------------------------------------------------------
    # Frozen strategy
    # -----------------------------------------------------------------------

    config = create_frozen_config()

    print()
    print("Frozen configuration:")
    print(
        f"  EMA: {EMA_FAST_PERIOD}/{EMA_SLOW_PERIOD}"
    )
    print(
        f"  RSI: {RSI_PERIOD}"
    )
    print(
        f"  ATR: {ATR_PERIOD}"
    )
    print(
        f"  RVOL: {RVOL_PERIOD}"
    )
    print(
        f"  Minimum long RSI: {MINIMUM_LONG_RSI}"
    )
    print(
        f"  RVOL enabled: {USE_RVOL}"
    )
    print(
        f"  Transaction cost: "
        f"{TRANSACTION_COST_RATE:.4%}"
    )

    # -----------------------------------------------------------------------
    # Backtest
    # -----------------------------------------------------------------------

    print()
    print("Running backtest...")

    backtest_result = run_backtest_engine(
        data=data,
        config=config,
    )

    backtest_trades = normalize_backtest_trades(
        backtest_result.trades
    )

    print(
        f"Backtest completed: "
        f"{len(backtest_trades)} trades."
    )

    # -----------------------------------------------------------------------
    # Paper trading
    # -----------------------------------------------------------------------

    print()
    print("Running paper trading engine...")

    paper_engine = run_paper_engine(
        data=data,
        config=config,
    )

    paper_trades = normalize_paper_trades(
        paper_engine.state.completed_trades
    )

    print(
        f"Paper trading completed: "
        f"{len(paper_trades)} trades."
    )

    # -----------------------------------------------------------------------
    # Compare
    # -----------------------------------------------------------------------

    print_trade_summary(
        backtest_trades=backtest_trades,
        paper_trades=paper_trades,
    )

    parity_passed, differences = compare_trades(
        backtest_trades=backtest_trades,
        paper_trades=paper_trades,
    )

    print_pnl_summary(
        backtest_trades=backtest_trades,
        paper_trades=paper_trades,
    )

    print_differences(differences)

    # -----------------------------------------------------------------------
    # Final result
    # -----------------------------------------------------------------------

    print()
    print("=" * 72)

    if parity_passed:
        print("PARITY RESULT: PASS")
        print(
            "Backtest and paper trading produced "
            "identical trade sequences and P&L."
        )
        print("=" * 72)

        return

    print("PARITY RESULT: FAIL")
    print(
        "Backtest and paper trading are not yet "
        "semantically identical."
    )
    print("=" * 72)

    raise SystemExit(1)


if __name__ == "__main__":
    main()