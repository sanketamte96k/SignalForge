import pandas as pd
import pytest

from src.backtest.engine import (
    BacktestResult,
    run_backtest,
)
from src.backtest.report import (
    BacktestReport,
    build_drawdown_curve,
    build_equity_curve,
    build_report,
)
from src.backtest.simulator import Position


def make_data():
    index = pd.date_range(
        "2026-08-31 09:15",
        periods=5,
        freq="min",
    )

    return pd.DataFrame(
        {
            "close": [
                100,
                110,
                105,
                115,
                110,
            ]
        },
        index=index,
    )


def make_result():
    data = make_data()

    def signal(row, previous_row):
        if row.name == data.index[0]:
            return Position.LONG

        if row.name == data.index[2]:
            return Position.SHORT

        return None

    return run_backtest(
        data=data,
        signal_function=signal,
        initial_capital=100000,
        quantity=1,
    )


def test_build_equity_curve_returns_series():
    result = make_result()

    curve = build_equity_curve(result)

    assert isinstance(
        curve,
        pd.Series,
    )


def test_equity_curve_starts_with_initial_capital():
    result = make_result()

    curve = build_equity_curve(result)

    assert curve.iloc[0] == 100000


def test_equity_curve_contains_initial_plus_trades():
    result = make_result()

    curve = build_equity_curve(result)

    assert len(curve) == (
        len(result.trades) + 1
    )


def test_equity_curve_tracks_trade_pnl():
    result = make_result()

    curve = build_equity_curve(result)

    expected = [
        100000,
        100005,
        100000,
    ]

    assert curve.tolist() == expected


def test_equity_curve_name():
    result = make_result()

    curve = build_equity_curve(result)

    assert curve.name == "equity"


def test_empty_backtest_equity_curve():
    data = make_data()

    result = run_backtest(
        data=data,
        signal_function=lambda row, previous: None,
        initial_capital=100000,
    )

    curve = build_equity_curve(result)

    assert len(curve) == 1
    assert curve.iloc[0] == 100000


def test_drawdown_curve_returns_series():
    result = make_result()

    curve = build_drawdown_curve(result)

    assert isinstance(
        curve,
        pd.Series,
    )


def test_drawdown_curve_starts_at_zero():
    result = make_result()

    curve = build_drawdown_curve(result)

    assert curve.iloc[0] == 0


def test_drawdown_after_equity_decline():
    result = make_result()

    curve = build_drawdown_curve(result)

    assert curve.iloc[2] == pytest.approx(
        (
            (100005 - 100000)
            / 100005
        ) * 100
    )


def test_drawdown_curve_name():
    result = make_result()

    curve = build_drawdown_curve(result)

    assert curve.name == "drawdown_pct"


def test_drawdown_never_negative():
    result = make_result()

    curve = build_drawdown_curve(result)

    assert (curve >= 0).all()


def test_report_returns_backtest_report():
    result = make_result()

    report = build_report(result)

    assert isinstance(
        report,
        BacktestReport,
    )


def test_report_initial_capital():
    result = make_result()

    report = build_report(result)

    assert report.initial_capital == 100000


def test_report_final_equity():
    result = make_result()

    report = build_report(result)

    assert report.final_equity == 100000


def test_report_total_pnl():
    result = make_result()

    report = build_report(result)

    assert report.total_pnl == 0


def test_report_total_return():
    result = make_result()

    report = build_report(result)

    assert report.total_return_pct == pytest.approx(
        0.0
    )


def test_report_trade_count():
    result = make_result()

    report = build_report(result)

    assert report.total_trades == 2


def test_report_win_loss_counts():
    result = make_result()

    report = build_report(result)

    assert report.winning_trades == 1
    assert report.losing_trades == 1


def test_report_win_rate():
    result = make_result()

    report = build_report(result)

    assert report.win_rate_pct == pytest.approx(
        50
    )


def test_report_profit_factor():
    result = make_result()

    report = build_report(result)

    assert report.profit_factor == pytest.approx(
        1.0
    )


def test_report_expectancy():
    result = make_result()

    report = build_report(result)

    assert report.expectancy == pytest.approx(
        0.0
    )


def test_report_drawdown():
    result = make_result()

    report = build_report(result)

    assert report.max_drawdown_pct == pytest.approx(
        (
            (100005 - 100000)
            / 100005
        ) * 100
    )


def test_invalid_result_for_equity_curve():
    with pytest.raises(TypeError):
        build_equity_curve("invalid")


def test_invalid_result_for_drawdown():
    with pytest.raises(TypeError):
        build_drawdown_curve("invalid")


def test_invalid_result_for_report():
    with pytest.raises(TypeError):
        build_report("invalid")