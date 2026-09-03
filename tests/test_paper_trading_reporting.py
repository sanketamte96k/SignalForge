from src.paper_trading.engine import PaperTradingEngine
from src.paper_trading.reporting import create_paper_trading_report


def test_empty_paper_trading_report():
    engine = PaperTradingEngine(
        starting_capital=100_000.0,
        quantity=1,
        transaction_cost_rate=0.0001,
    )

    report = create_paper_trading_report(engine.state)

    assert report.starting_capital == 100_000.0
    assert report.ending_equity == 100_000.0
    assert report.realized_pnl == 0.0
    assert report.total_transaction_cost == 0.0

    assert report.trade_count == 0
    assert report.winning_trades == 0
    assert report.losing_trades == 0

    assert report.gross_profit == 0.0
    assert report.gross_loss == 0.0

    assert report.long_trades == 0
    assert report.short_trades == 0

    assert report.net_return_pct == 0.0
    assert report.win_rate_pct == 0.0
    assert report.profit_factor == 0.0


def test_paper_trading_report_metrics():
    engine = PaperTradingEngine(
        starting_capital=100_000.0,
        quantity=1,
        transaction_cost_rate=0.0,
    )

    engine.open_long(
        price=100.0,
        timestamp=None,
    )

    engine.close_position(
        price=110.0,
        timestamp=None,
        reason="Test profit",
    )

    engine.open_short(
        price=200.0,
        timestamp=None,
    )

    engine.close_position(
        price=190.0,
        timestamp=None,
        reason="Test profit",
    )

    engine.open_long(
        price=300.0,
        timestamp=None,
    )

    engine.close_position(
        price=295.0,
        timestamp=None,
        reason="Test loss",
    )

    report = create_paper_trading_report(engine.state)

    assert report.trade_count == 3

    assert report.winning_trades == 2
    assert report.losing_trades == 1

    assert report.long_trades == 2
    assert report.short_trades == 1

    assert report.gross_profit == 20.0
    assert report.gross_loss == -5.0

    assert report.realized_pnl == 15.0
    assert report.ending_equity == 100_015.0

    assert report.net_return_pct == 0.015

    assert abs(
        report.win_rate_pct - 66.6666666667
    ) < 1e-9

    assert report.profit_factor == 4.0


def test_paper_trading_report_includes_transaction_costs():
    engine = PaperTradingEngine(
        starting_capital=100_000.0,
        quantity=1,
        transaction_cost_rate=0.001,
    )

    engine.open_long(
        price=100.0,
        timestamp=None,
    )

    engine.close_position(
        price=110.0,
        timestamp=None,
        reason="Test cost",
    )

    report = create_paper_trading_report(engine.state)

    assert report.trade_count == 1

    expected_cost = (
        (100.0 + 110.0)
        * 0.001
    )

    expected_net_pnl = 10.0 - expected_cost

    assert abs(
        report.total_transaction_cost
        - expected_cost
    ) < 1e-9

    assert abs(
        report.realized_pnl
        - expected_net_pnl
    ) < 1e-9

    assert abs(
        report.ending_equity
        - (100_000.0 + expected_net_pnl)
    ) < 1e-9

    assert report.gross_profit == report.realized_pnl
    assert report.gross_loss == 0.0

    assert report.winning_trades == 1
    assert report.losing_trades == 0

    assert report.long_trades == 1
    assert report.short_trades == 0