"""Regression tests for causal replay/backtest parity."""

from __future__ import annotations

from datetime import datetime, time

import pandas as pd
import pytest

from src.backtest.engine import run_backtest
from src.strategy.backtest_strategy import create_signal_function
from src.paper_trading.replay_runner import PaperTradingReplayRunner


STARTING_CAPITAL = 100_000.0
TOLERANCE = 1e-9


def make_market_data() -> pd.DataFrame:
    """
    Create a deterministic two-session 1-minute market-data fixture.

    The fixture contains two valid intraday sessions:
        2026-08-25 09:15 -> 15:30
        2026-08-26 09:15 -> 15:30

    Prices trend upward so that the frozen strategy has a meaningful
    opportunity to produce signals while remaining deterministic.
    """

    sessions: list[pd.DatetimeIndex] = []

    for day in ("2026-08-25", "2026-08-26"):
        sessions.append(
            pd.date_range(
                start=f"{day} 09:15:00",
                end=f"{day} 15:30:00",
                freq="1min",
            )
        )

    index = sessions[0].append(sessions[1])

    rows: list[dict[str, float]] = []

    for i, timestamp in enumerate(index):
        close = 100.0 + (i * 0.02)

        rows.append(
            {
                "open": close - 0.01,
                "high": close + 0.05,
                "low": close - 0.05,
                "close": close,
                "volume": 1000.0,
            }
        )

    return pd.DataFrame(rows, index=index)


def _run_backtest(data: pd.DataFrame):
    """
    Run the existing backtest using the project's actual public API.

    The backtest engine requires:
        data
        signal_function
        initial_capital

    The signal function is created from the same frozen strategy used
    by the project.
    """

    signal_function = create_signal_function(data)

    return run_backtest(
        data,
        signal_function,
        STARTING_CAPITAL,
    )


def _run_causal_replay(data: pd.DataFrame):
    """Run the paper-trading replay path."""

    runner = PaperTradingReplayRunner(
        adapter_data=data,
        starting_capital=STARTING_CAPITAL,
    )

    return runner.run()


def _backtest_trade_signature(trade) -> tuple:
    """
    Return the common fields shared by backtest Trade and PaperTrade.

    Reason is intentionally excluded because the backtest Trade model
    does not contain a reason field.
    """

    return (
        trade.position,
        trade.entry_time,
        trade.exit_time,
        trade.entry_price,
        trade.exit_price,
        trade.quantity,
        trade.gross_pnl,
        trade.transaction_cost,
        trade.net_pnl,
    )


def _paper_trade_signature(trade) -> tuple:
    """Return the parity fields from a PaperTrade."""

    return (
        trade.position,
        trade.entry_time,
        trade.exit_time,
        trade.entry_price,
        trade.exit_price,
        trade.quantity,
        trade.gross_pnl,
        trade.transaction_cost,
        trade.net_pnl,
    )


def _assert_float_equal(actual: float, expected: float) -> None:
    """Assert floating-point values with a strict tolerance."""

    assert actual == pytest.approx(
        expected,
        abs=TOLERANCE,
        rel=TOLERANCE,
    )


def test_session_fixture_is_valid() -> None:
    """Fixture contains exactly two valid trading sessions."""

    data = make_market_data()

    assert len(data) == 752
    assert data.index.is_monotonic_increasing
    assert data.index.is_unique

    dates = data.index.normalize().unique()

    assert len(dates) == 2

    for timestamp in data.index:
        assert time(9, 15) <= timestamp.time() <= time(15, 30)


def test_session_fixture_is_chronological_and_unique() -> None:
    """Replay input must be strictly chronological and unique."""

    data = make_market_data()

    assert data.index.is_monotonic_increasing
    assert data.index.is_unique

    differences = data.index.to_series().diff().dropna()

    assert (differences > pd.Timedelta(0)).all()


def test_causal_replay_matches_trade_count() -> None:
    """Replay and backtest generate the same number of trades."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    assert len(backtest.trades) == replay.trade_count


def test_causal_replay_matches_trade_signatures() -> None:
    """Every replay trade matches the corresponding backtest trade."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    backtest_signatures = [
        _backtest_trade_signature(trade)
        for trade in backtest.trades
    ]

    replay_signatures = [
        _paper_trade_signature(trade)
        for trade in replay.completed_trades
    ]

    assert len(backtest_signatures) == len(replay_signatures)

    for expected, actual in zip(
        backtest_signatures,
        replay_signatures,
    ):
        assert actual[0] == expected[0]
        assert actual[1] == expected[1]
        assert actual[2] == expected[2]

        _assert_float_equal(actual[3], expected[3])
        _assert_float_equal(actual[4], expected[4])

        assert actual[5] == expected[5]

        _assert_float_equal(actual[6], expected[6])
        _assert_float_equal(actual[7], expected[7])
        _assert_float_equal(actual[8], expected[8])


def test_causal_replay_matches_positions() -> None:
    """Long/short direction remains identical."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    backtest_positions = [
        trade.position
        for trade in backtest.trades
    ]

    replay_positions = [
        trade.position
        for trade in replay.completed_trades
    ]

    assert replay_positions == backtest_positions


def test_causal_replay_matches_entry_times() -> None:
    """Entry timestamps remain identical."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    expected = [
        trade.entry_time
        for trade in backtest.trades
    ]

    actual = [
        trade.entry_time
        for trade in replay.completed_trades
    ]

    assert actual == expected


def test_causal_replay_matches_exit_times() -> None:
    """Exit timestamps remain identical."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    expected = [
        trade.exit_time
        for trade in backtest.trades
    ]

    actual = [
        trade.exit_time
        for trade in replay.completed_trades
    ]

    assert actual == expected


def test_causal_replay_matches_entry_prices() -> None:
    """Entry prices remain identical."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    expected = [
        trade.entry_price
        for trade in backtest.trades
    ]

    actual = [
        trade.entry_price
        for trade in replay.completed_trades
    ]

    assert actual == pytest.approx(expected)


def test_causal_replay_matches_exit_prices() -> None:
    """Exit prices remain identical."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    expected = [
        trade.exit_price
        for trade in backtest.trades
    ]

    actual = [
        trade.exit_price
        for trade in replay.completed_trades
    ]

    assert actual == pytest.approx(expected)


def test_causal_replay_matches_quantity() -> None:
    """Position quantities remain identical."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    expected = [
        trade.quantity
        for trade in backtest.trades
    ]

    actual = [
        trade.quantity
        for trade in replay.completed_trades
    ]

    assert actual == expected


def test_causal_replay_matches_gross_pnl() -> None:
    """Every trade preserves gross P&L."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    expected = [
        trade.gross_pnl
        for trade in backtest.trades
    ]

    actual = [
        trade.gross_pnl
        for trade in replay.completed_trades
    ]

    assert actual == pytest.approx(expected)


def test_causal_replay_matches_transaction_costs() -> None:
    """Every trade preserves transaction costs."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    expected = [
        trade.transaction_cost
        for trade in backtest.trades
    ]

    actual = [
        trade.transaction_cost
        for trade in replay.completed_trades
    ]

    assert actual == pytest.approx(expected)


def test_causal_replay_matches_net_pnl() -> None:
    """Every trade preserves net P&L."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    expected = [
        trade.net_pnl
        for trade in backtest.trades
    ]

    actual = [
        trade.net_pnl
        for trade in replay.completed_trades
    ]

    assert actual == pytest.approx(expected)


def test_causal_replay_matches_realized_pnl() -> None:
    """Total realized P&L is identical."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    expected = sum(
        trade.net_pnl
        for trade in backtest.trades
    )

    _assert_float_equal(
        replay.realized_pnl,
        expected,
    )


def test_causal_replay_matches_transaction_cost_total() -> None:
    """Total transaction costs are identical."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    expected = sum(
        trade.transaction_cost
        for trade in backtest.trades
    )

    _assert_float_equal(
        replay.total_transaction_cost,
        expected,
    )


def test_causal_replay_matches_ending_equity() -> None:
    """Ending equity is identical."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    expected = STARTING_CAPITAL + sum(
        trade.net_pnl
        for trade in backtest.trades
    )

    _assert_float_equal(
        replay.ending_equity,
        expected,
    )


def test_causal_replay_matches_report_trade_count() -> None:
    """Paper report trade count matches backtest."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    assert replay.trade_count == len(backtest.trades)


def test_causal_replay_matches_report_pnl() -> None:
    """Paper report preserves realized P&L."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    expected = sum(
        trade.net_pnl
        for trade in backtest.trades
    )

    _assert_float_equal(
        replay.realized_pnl,
        expected,
    )


def test_causal_replay_matches_report_transaction_costs() -> None:
    """Paper report preserves transaction costs."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    expected = sum(
        trade.transaction_cost
        for trade in backtest.trades
    )

    _assert_float_equal(
        replay.total_transaction_cost,
        expected,
    )


def test_causal_replay_matches_report_ending_equity() -> None:
    """Paper report preserves ending equity."""

    data = make_market_data()

    backtest = _run_backtest(data)
    replay = _run_causal_replay(data)

    expected = STARTING_CAPITAL + sum(
        trade.net_pnl
        for trade in backtest.trades
    )

    _assert_float_equal(
        replay.ending_equity,
        expected,
    )


def test_causal_replay_processes_candles_chronologically() -> None:
    """The causal strategy context processes candles in order."""

    data = make_market_data()

    runner = PaperTradingReplayRunner(
        adapter_data=data,
        starting_capital=STARTING_CAPITAL,
    )

    runner.run()

    context = runner.strategy_context

    assert context.processed_count > 0
    assert context.last_timestamp is not None
    assert context.last_timestamp == data.index[-1]


def test_causal_replay_does_not_leave_position_open() -> None:
    """Replay must finish with no open position."""

    data = make_market_data()

    runner = PaperTradingReplayRunner(
        adapter_data=data,
        starting_capital=STARTING_CAPITAL,
    )

    report = runner.run()

    assert report.trade_count == len(
        runner.engine.state.completed_trades
    )

    assert runner.engine.state.open_position is None