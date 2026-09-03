import json

from src.paper_trading.engine import PaperTradingEngine
from src.paper_trading.persistence import (
    load_paper_trading_report,
    save_paper_trading_report,
)
from src.paper_trading.reporting import (
    create_paper_trading_report,
)


def create_test_report():
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
        reason="Persistence test",
    )

    return create_paper_trading_report(
        engine.state
    )


def test_save_paper_trading_report(tmp_path):
    report = create_test_report()

    output_path = (
        tmp_path
        / "reports"
        / "paper"
        / "session.json"
    )

    saved_path = save_paper_trading_report(
        report,
        output_path,
    )

    assert saved_path == output_path
    assert output_path.exists()

    with output_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        payload = json.load(file)

    assert payload["starting_capital"] == 100_000.0
    assert payload["ending_equity"] == 100_010.0
    assert payload["realized_pnl"] == 10.0
    assert payload["trade_count"] == 1
    assert payload["winning_trades"] == 1
    assert payload["losing_trades"] == 0
    assert payload["long_trades"] == 1
    assert payload["short_trades"] == 0
    assert payload["net_return_pct"] == 0.01
    assert payload["win_rate_pct"] == 100.0
    assert payload["profit_factor"] == "inf"


def test_load_paper_trading_report(tmp_path):
    report = create_test_report()

    output_path = (
        tmp_path
        / "session.json"
    )

    save_paper_trading_report(
        report,
        output_path,
    )

    loaded = load_paper_trading_report(
        output_path
    )

    assert loaded["starting_capital"] == 100_000.0
    assert loaded["ending_equity"] == 100_010.0
    assert loaded["realized_pnl"] == 10.0
    assert loaded["trade_count"] == 1
    assert loaded["winning_trades"] == 1
    assert loaded["long_trades"] == 1


def test_save_creates_parent_directories(tmp_path):
    report = create_test_report()

    output_path = (
        tmp_path
        / "nested"
        / "paper"
        / "session.json"
    )

    save_paper_trading_report(
        report,
        output_path,
    )

    assert output_path.exists()
    assert output_path.parent.exists()


def test_save_rejects_invalid_report(tmp_path):
    output_path = tmp_path / "invalid.json"

    try:
        save_paper_trading_report(
            report="not a report",
            path=output_path,
        )
    except TypeError as exc:
        assert str(exc) == (
            "report must be a PaperTradingReport."
        )
    else:
        raise AssertionError(
            "Expected TypeError was not raised."
        )


def test_load_missing_report_raises(tmp_path):
    missing_path = tmp_path / "missing.json"

    try:
        load_paper_trading_report(
            missing_path
        )
    except FileNotFoundError as exc:
        assert "Report file not found" in str(exc)
    else:
        raise AssertionError(
            "Expected FileNotFoundError was not raised."
        )