from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.backtest.engine import run_backtest
from src.paper_trading.runner import PaperTradingRunner
from src.strategy.backtest_strategy import (
    StrategyConfig,
    create_signal_function,
)


# ---------------------------------------------------------------------------
# Test configuration
# ---------------------------------------------------------------------------

DATA_PATH = Path(
    "data/historical/nifty50_1m_signalforge.csv"
)

START_DATE = "2023-01-01"
END_DATE = "2024-03-31"

STARTING_CAPITAL = 100_000.0
QUANTITY = 1
TRANSACTION_COST_RATE = 0.0001

PRICE_TOLERANCE = 1e-9
PNL_TOLERANCE = 1e-9


# ---------------------------------------------------------------------------
# Frozen strategy configuration
# ---------------------------------------------------------------------------

def create_frozen_config() -> StrategyConfig:
    return StrategyConfig(
        ema_fast_period=20,
        ema_slow_period=50,
        rsi_period=14,
        atr_period=14,
        rvol_period=20,
        minimum_rvol=1.5,
        minimum_atr=0.0,
        minimum_long_rsi=60.0,
        use_rvol=False,
    )


# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def market_data() -> pd.DataFrame:
    """Load the authoritative OOS dataset used for parity validation."""

    if not DATA_PATH.exists():
        pytest.skip(
            f"Historical parity dataset not available: {DATA_PATH}"
        )

    data = pd.read_csv(
        DATA_PATH,
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
        pytest.fail(
            f"Parity dataset is missing columns: "
            f"{sorted(missing_columns)}"
        )

    data = data.loc[
        (data.index >= pd.Timestamp(START_DATE))
        & (data.index <= pd.Timestamp(END_DATE))
    ].copy()

    if data.empty:
        pytest.fail(
            "Parity dataset contains no candles "
            "for the requested OOS period."
        )

    return data


# ---------------------------------------------------------------------------
# Trade normalization
# ---------------------------------------------------------------------------

def normalize_backtest_trades(trades) -> list[dict]:
    return [
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
        for trade in trades
    ]


def normalize_paper_trades(trades) -> list[dict]:
    return [
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
        for trade in trades
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def assert_float_equal(
    actual: float,
    expected: float,
    label: str,
) -> None:
    assert abs(actual - expected) <= PNL_TOLERANCE, (
        f"{label} mismatch: "
        f"actual={actual}, expected={expected}"
    )


# ---------------------------------------------------------------------------
# Main parity test
# ---------------------------------------------------------------------------

def test_paper_trading_matches_backtest(
    market_data: pd.DataFrame,
) -> None:
    """
    Verify that paper trading and backtesting produce
    identical trades and P&L on the frozen OOS dataset.
    """

    config = create_frozen_config()

    # -----------------------------------------------------------------------
    # Backtest
    # -----------------------------------------------------------------------

    backtest_signal_function = create_signal_function(
        data=market_data,
        config=config,
    )

    backtest_result = run_backtest(
        data=market_data,
        signal_function=backtest_signal_function,
        initial_capital=STARTING_CAPITAL,
        quantity=QUANTITY,
        transaction_cost_rate=TRANSACTION_COST_RATE,
    )

    backtest_trades = normalize_backtest_trades(
        backtest_result.trades
    )

    # -----------------------------------------------------------------------
    # Paper trading
    # -----------------------------------------------------------------------

    paper_runner = PaperTradingRunner(
        starting_capital=STARTING_CAPITAL,
        quantity=QUANTITY,
        transaction_cost_rate=TRANSACTION_COST_RATE,
        strategy_config=config,
    )

    paper_engine = paper_runner.run(
        market_data
    )

    paper_trades = normalize_paper_trades(
        paper_engine.state.completed_trades
    )

    # -----------------------------------------------------------------------
    # Trade count
    # -----------------------------------------------------------------------

    assert len(paper_trades) == len(backtest_trades), (
        "Trade count mismatch: "
        f"paper={len(paper_trades)}, "
        f"backtest={len(backtest_trades)}"
    )

    # -----------------------------------------------------------------------
    # Trade-by-trade parity
    # -----------------------------------------------------------------------

    for index, (
        backtest_trade,
        paper_trade,
    ) in enumerate(
        zip(backtest_trades, paper_trades),
        start=1,
    ):
        prefix = f"Trade #{index}"

        assert paper_trade["position"] == backtest_trade["position"], (
            f"{prefix} position mismatch: "
            f"paper={paper_trade['position']}, "
            f"backtest={backtest_trade['position']}"
        )

        assert paper_trade["entry_time"] == backtest_trade["entry_time"], (
            f"{prefix} entry time mismatch: "
            f"paper={paper_trade['entry_time']}, "
            f"backtest={backtest_trade['entry_time']}"
        )

        assert paper_trade["exit_time"] == backtest_trade["exit_time"], (
            f"{prefix} exit time mismatch: "
            f"paper={paper_trade['exit_time']}, "
            f"backtest={backtest_trade['exit_time']}"
        )

        assert_float_equal(
            paper_trade["entry_price"],
            backtest_trade["entry_price"],
            f"{prefix} entry price",
        )

        assert_float_equal(
            paper_trade["exit_price"],
            backtest_trade["exit_price"],
            f"{prefix} exit price",
        )

        assert paper_trade["quantity"] == backtest_trade["quantity"], (
            f"{prefix} quantity mismatch: "
            f"paper={paper_trade['quantity']}, "
            f"backtest={backtest_trade['quantity']}"
        )

        assert_float_equal(
            paper_trade["gross_pnl"],
            backtest_trade["gross_pnl"],
            f"{prefix} gross P&L",
        )

        assert_float_equal(
            paper_trade["transaction_cost"],
            backtest_trade["transaction_cost"],
            f"{prefix} transaction cost",
        )

        assert_float_equal(
            paper_trade["net_pnl"],
            backtest_trade["net_pnl"],
            f"{prefix} net P&L",
        )

    # -----------------------------------------------------------------------
    # Aggregate P&L parity
    # -----------------------------------------------------------------------

    backtest_net_pnl = sum(
        trade["net_pnl"]
        for trade in backtest_trades
    )

    paper_net_pnl = sum(
        trade["net_pnl"]
        for trade in paper_trades
    )

    assert_float_equal(
        paper_net_pnl,
        backtest_net_pnl,
        "Total net P&L",
    )

    # -----------------------------------------------------------------------
    # Aggregate transaction-cost parity
    # -----------------------------------------------------------------------

    backtest_cost = sum(
        trade["transaction_cost"]
        for trade in backtest_trades
    )

    paper_cost = sum(
        trade["transaction_cost"]
        for trade in paper_trades
    )

    assert_float_equal(
        paper_cost,
        backtest_cost,
        "Total transaction cost",
    )