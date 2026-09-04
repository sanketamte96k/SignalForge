from __future__ import annotations

import pandas as pd

from src.backtest.simulator import (
    Position,
    simulate_trade,
)
from src.validation.cost_slippage import (
    CostSlippageValidator,
)


def make_market_data(
    rows: int = 300,
) -> pd.DataFrame:
    """Create deterministic 1-minute OHLCV data."""

    index = pd.date_range(
        "2024-01-02 09:15:00",
        periods=rows,
        freq="min",
    )

    values = [
        100.0 + position * 0.10
        for position in range(rows)
    ]

    return pd.DataFrame(
        {
            "open": values,
            "high": [
                value + 1.0
                for value in values
            ],
            "low": [
                value - 1.0
                for value in values
            ],
            "close": values,
            "volume": [1000.0] * rows,
        },
        index=index,
    )


def make_trades(
    transaction_cost_rate: float = 0.0,
):
    """Create deterministic completed trades."""

    return [
        simulate_trade(
            position=Position.LONG,
            entry_time=pd.Timestamp(
                "2024-01-02 10:00:00"
            ),
            exit_time=pd.Timestamp(
                "2024-01-02 10:10:00"
            ),
            entry_price=100.0,
            exit_price=110.0,
            quantity=1,
            transaction_cost_rate=(
                transaction_cost_rate
            ),
        ),
        simulate_trade(
            position=Position.LONG,
            entry_time=pd.Timestamp(
                "2024-01-02 11:00:00"
            ),
            exit_time=pd.Timestamp(
                "2024-01-02 11:10:00"
            ),
            entry_price=110.0,
            exit_price=105.0,
            quantity=1,
            transaction_cost_rate=(
                transaction_cost_rate
            ),
        ),
    ]


def test_cost_slippage_validator_rejects_invalid_data():
    validator = CostSlippageValidator()

    result = validator.check("invalid")

    assert result.passed is False
    assert result.scenarios_checked == 0
    assert not result.has_evidence
    assert any(
        "pandas DataFrame" in issue
        for issue in result.issues
    )


def test_cost_slippage_validator_rejects_missing_columns():
    data = make_market_data()

    data = data.drop(
        columns=["volume"]
    )

    validator = CostSlippageValidator()

    result = validator.check(data)

    assert result.passed is False
    assert result.scenarios_checked == 0
    assert any(
        "missing required columns" in issue
        for issue in result.issues
    )


def test_cost_slippage_validator_rejects_duplicate_timestamps():
    data = make_market_data()

    duplicate = data.iloc[[10]].copy()

    data = pd.concat(
        [
            data.iloc[:20],
            duplicate,
            data.iloc[20:],
        ]
    )

    validator = CostSlippageValidator()

    result = validator.check(data)

    assert result.passed is False
    assert result.scenarios_checked == 0
    assert any(
        "duplicate timestamps" in issue
        for issue in result.issues
    )


def test_cost_slippage_validator_rejects_empty_data():
    data = make_market_data().iloc[0:0]

    validator = CostSlippageValidator()

    result = validator.check(data)

    assert result.passed is False
    assert result.total_candles == 0
    assert result.scenarios_checked == 0
    assert not result.has_evidence


def test_cost_slippage_validator_evaluates_all_scenarios(
    monkeypatch,
):
    data = make_market_data()

    trades_by_cost = {
        0.0: make_trades(0.0),
        0.0001: make_trades(0.0001),
    }

    def fake_run_backtest(
        data,
        signal_function,
        initial_capital,
        quantity,
        transaction_cost_rate,
    ):
        class FakeResult:
            def __init__(self, trades):
                self.trades = trades

        return FakeResult(
            trades_by_cost[
                transaction_cost_rate
            ]
        )

    import src.validation.cost_slippage as module

    monkeypatch.setattr(
        module,
        "run_backtest",
        fake_run_backtest,
    )

    validator = CostSlippageValidator(
        transaction_cost_rates=(
            0.0,
            0.0001,
        ),
        slippage_rates=(
            0.0,
            0.0001,
            0.0002,
        ),
        minimum_trades_required=1,
        selected_transaction_cost_rate=0.0001,
        selected_slippage_rate=0.0001,
    )

    result = validator.check(data)

    assert result.has_evidence
    assert result.scenarios_checked == 6
    assert len(result.scenarios) == 6


def test_cost_slippage_keeps_trade_count_constant(
    monkeypatch,
):
    data = make_market_data()

    trades_by_cost = {
        0.0: make_trades(0.0),
        0.0001: make_trades(0.0001),
        0.0002: make_trades(0.0002),
    }

    def fake_run_backtest(
        data,
        signal_function,
        initial_capital,
        quantity,
        transaction_cost_rate,
    ):
        class FakeResult:
            def __init__(self, trades):
                self.trades = trades

        return FakeResult(
            trades_by_cost[
                transaction_cost_rate
            ]
        )

    import src.validation.cost_slippage as module

    monkeypatch.setattr(
        module,
        "run_backtest",
        fake_run_backtest,
    )

    validator = CostSlippageValidator(
        transaction_cost_rates=(
            0.0,
            0.0001,
            0.0002,
        ),
        slippage_rates=(
            0.0,
            0.0001,
        ),
    )

    result = validator.check(data)

    assert result.has_evidence
    assert result.baseline_trades == 2

    assert all(
        scenario.trades
        == result.baseline_trades
        for scenario in result.scenarios
    )


def test_slippage_reduces_net_pnl():
    validator = CostSlippageValidator(
        transaction_cost_rates=(0.0,),
        slippage_rates=(
            0.0,
            0.0001,
        ),
        minimum_trades_required=1,
        selected_transaction_cost_rate=0.0,
        selected_slippage_rate=0.0001,
    )

    trades = make_trades(0.0)

    baseline = validator._build_scenario(
        trades=trades,
        transaction_cost_rate=0.0,
        slippage_rate=0.0,
    )

    slippage = validator._build_scenario(
        trades=trades,
        transaction_cost_rate=0.0,
        slippage_rate=0.0001,
    )

    assert baseline.trades == 2
    assert slippage.trades == 2
    assert slippage.slippage_cost > 0.0
    assert slippage.net_pnl < baseline.net_pnl


def test_transaction_cost_reduces_net_pnl():
    validator = CostSlippageValidator(
        transaction_cost_rates=(
            0.0,
            0.0001,
        ),
        slippage_rates=(0.0,),
        minimum_trades_required=1,
        selected_transaction_cost_rate=0.0001,
        selected_slippage_rate=0.0,
    )

    baseline_trades = make_trades(0.0)
    cost_trades = make_trades(0.0001)

    baseline = validator._build_scenario(
        trades=baseline_trades,
        transaction_cost_rate=0.0,
        slippage_rate=0.0,
    )

    cost_scenario = validator._build_scenario(
        trades=cost_trades,
        transaction_cost_rate=0.0001,
        slippage_rate=0.0,
    )

    assert baseline.trades == 2
    assert cost_scenario.trades == 2
    assert cost_scenario.transaction_cost > 0.0
    assert cost_scenario.net_pnl < baseline.net_pnl


def test_selected_profitable_scenario_can_pass(
    monkeypatch,
):
    data = make_market_data()

    trades = make_trades(0.0)

    def fake_run_backtest(
        data,
        signal_function,
        initial_capital,
        quantity,
        transaction_cost_rate,
    ):
        class FakeResult:
            def __init__(self):
                self.trades = trades

        return FakeResult()

    import src.validation.cost_slippage as module

    monkeypatch.setattr(
        module,
        "run_backtest",
        fake_run_backtest,
    )

    validator = CostSlippageValidator(
        transaction_cost_rates=(0.0,),
        slippage_rates=(0.0,),
        minimum_trades_required=1,
        selected_transaction_cost_rate=0.0,
        selected_slippage_rate=0.0,
    )

    result = validator.check(data)

    assert result.selected_scenario is not None
    assert result.selected_scenario.net_pnl > 0.0
    assert result.friction_resistant
    assert result.passed


def test_selected_scenario_can_fail_when_friction_is_too_high(
    monkeypatch,
):
    data = make_market_data()

    trades = make_trades(0.0)

    def fake_run_backtest(
        data,
        signal_function,
        initial_capital,
        quantity,
        transaction_cost_rate,
    ):
        class FakeResult:
            def __init__(self):
                self.trades = trades

        return FakeResult()

    import src.validation.cost_slippage as module

    monkeypatch.setattr(
        module,
        "run_backtest",
        fake_run_backtest,
    )

    validator = CostSlippageValidator(
        transaction_cost_rates=(0.0,),
        slippage_rates=(
            0.0,
            1.0,
        ),
        minimum_trades_required=1,
        selected_transaction_cost_rate=0.0,
        selected_slippage_rate=1.0,
    )

    result = validator.check(data)

    assert result.selected_scenario is not None
    assert result.selected_scenario.net_pnl <= 0.0
    assert result.friction_resistant is False
    assert result.passed is False
    assert any(
        "not profitable" in issue
        for issue in result.issues
    )


def test_minimum_trade_requirement_can_fail(
    monkeypatch,
):
    data = make_market_data()

    trades = make_trades(0.0)

    def fake_run_backtest(
        data,
        signal_function,
        initial_capital,
        quantity,
        transaction_cost_rate,
    ):
        class FakeResult:
            def __init__(self):
                self.trades = trades

        return FakeResult()

    import src.validation.cost_slippage as module

    monkeypatch.setattr(
        module,
        "run_backtest",
        fake_run_backtest,
    )

    validator = CostSlippageValidator(
        transaction_cost_rates=(0.0,),
        slippage_rates=(0.0,),
        minimum_trades_required=10_000,
        selected_transaction_cost_rate=0.0,
        selected_slippage_rate=0.0,
    )

    result = validator.check(data)

    assert result.passed is False
    assert any(
        "insufficient baseline trades" in issue
        for issue in result.issues
    )


def test_invalid_validator_configuration():
    try:
        CostSlippageValidator(
            transaction_cost_rates=(),
        )
        assert False
    except ValueError:
        pass

    try:
        CostSlippageValidator(
            slippage_rates=(),
        )
        assert False
    except ValueError:
        pass

    try:
        CostSlippageValidator(
            transaction_cost_rates=(-0.0001,),
        )
        assert False
    except ValueError:
        pass

    try:
        CostSlippageValidator(
            slippage_rates=(-0.0001,),
        )
        assert False
    except ValueError:
        pass

    try:
        CostSlippageValidator(
            initial_capital=0.0,
        )
        assert False
    except ValueError:
        pass

    try:
        CostSlippageValidator(
            quantity=0.0,
        )
        assert False
    except ValueError:
        pass

    try:
        CostSlippageValidator(
            quantity=1.5,
        )
        assert False
    except ValueError:
        pass

    try:
        CostSlippageValidator(
            minimum_trades_required=0,
        )
        assert False
    except ValueError:
        pass

    try:
        CostSlippageValidator(
            transaction_cost_rates=(0.0,),
            selected_transaction_cost_rate=0.0001,
        )
        assert False
    except ValueError:
        pass

    try:
        CostSlippageValidator(
            slippage_rates=(0.0,),
            selected_slippage_rate=0.0001,
        )
        assert False
    except ValueError:
        pass
