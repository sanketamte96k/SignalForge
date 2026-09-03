from src.paper_trading.engine import PaperTradingEngine
from src.paper_trading.runner import PaperTradingRunner


def test_runner_exposes_report():
    runner = PaperTradingRunner(
        starting_capital=100_000.0,
        quantity=1,
        transaction_cost_rate=0.0,
    )

    report = runner.report

    assert report.starting_capital == 100_000.0
    assert report.ending_equity == 100_000.0
    assert report.trade_count == 0
    assert report.realized_pnl == 0.0
    assert report.total_transaction_cost == 0.0


def test_runner_report_updates_after_trading():
    runner = PaperTradingRunner(
        starting_capital=100_000.0,
        quantity=1,
        transaction_cost_rate=0.0,
    )

    runner.engine.open_long(
        price=100.0,
        timestamp=None,
    )

    report_before_close = runner.report

    assert report_before_close.trade_count == 0
    assert report_before_close.realized_pnl == 0.0
    assert report_before_close.ending_equity == 100_000.0

    runner.engine.close_position(
        price=110.0,
        timestamp=None,
        reason="Test",
    )

    report_after_close = runner.report

    assert report_after_close.trade_count == 1
    assert report_after_close.realized_pnl == 10.0
    assert report_after_close.ending_equity == 100_010.0
    assert report_after_close.winning_trades == 1
    assert report_after_close.losing_trades == 0
    assert report_after_close.win_rate_pct == 100.0


def test_runner_report_after_initialization():
    runner = PaperTradingRunner(
        starting_capital=100_000.0,
        quantity=1,
        transaction_cost_rate=0.0,
    )

    report = runner.report

    assert report.starting_capital == 100_000.0
    assert report.trade_count == 0
    assert report.winning_trades == 0
    assert report.losing_trades == 0
    assert report.realized_pnl == 0.0
    assert report.total_transaction_cost == 0.0
    assert report.ending_equity == 100_000.0
    assert report.net_return_pct == 0.0
    assert report.win_rate_pct == 0.0
    assert report.profit_factor == 0.0