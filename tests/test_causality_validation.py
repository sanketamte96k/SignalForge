from __future__ import annotations

import pandas as pd

from src.validation.causality import (
    CausalityValidator,
)


def make_market_data(
    rows: int = 120,
) -> pd.DataFrame:
    """Create deterministic 1-minute OHLCV data."""

    index = pd.date_range(
        "2024-01-02 09:15:00",
        periods=rows,
        freq="min",
    )

    values = [
        100.0 + position * 0.25
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


def test_causality_passes_for_causal_strategy():
    data = make_market_data()

    validator = CausalityValidator(
        minimum_observations=10,
        observation_step=5,
    )

    result = validator.check(data)

    assert result.passed
    assert result.has_evidence
    assert result.causal
    assert result.mismatches == 0
    assert result.first_mismatch_timestamp is None
    assert result.observations_checked >= 10


def test_causality_detects_future_dependent_strategy(
    monkeypatch,
):
    import src.validation.causality as causality_module

    original_create_signal_function = (
        causality_module.create_signal_function
    )

    def future_dependent_strategy(data):
        strategy = original_create_signal_function(
            data
        )

        def wrapped_strategy(
            current_row,
            previous_row,
        ):
            future_exists = (
                current_row.name < data.index[-1]
            )

            if future_exists:
                return "BUY"

            return strategy(
                current_row,
                previous_row,
            )

        return wrapped_strategy

    monkeypatch.setattr(
        causality_module,
        "create_signal_function",
        future_dependent_strategy,
    )

    data = make_market_data()

    validator = CausalityValidator(
        minimum_observations=1,
        observation_step=1,
        minimum_history_candles=50,
    )

    result = validator.check(data)

    assert result.passed is False
    assert result.mismatches > 0
    assert result.first_mismatch_timestamp is not None
    assert (
        result.first_mismatch_timestamp
        == data.index[50]
    )


def test_causality_rejects_duplicate_timestamps():
    data = make_market_data()

    duplicate = data.iloc[[10]].copy()

    data = pd.concat(
        [
            data.iloc[:20],
            duplicate,
            data.iloc[20:],
        ]
    )

    validator = CausalityValidator()

    result = validator.check(data)

    assert not result.passed
    assert result.observations_checked == 0
    assert any(
        "duplicate timestamps" in issue
        for issue in result.issues
    )


def test_causality_rejects_missing_columns():
    data = make_market_data()

    data = data.drop(columns=["volume"])

    validator = CausalityValidator()

    result = validator.check(data)

    assert not result.passed
    assert result.observations_checked == 0
    assert any(
        "missing required columns" in issue
        for issue in result.issues
    )


def test_causality_rejects_empty_data():
    data = make_market_data().iloc[0:0]

    validator = CausalityValidator()

    result = validator.check(data)

    assert not result.passed
    assert result.total_candles == 0
    assert not result.has_evidence


def test_causality_requires_previous_candle():
    data = make_market_data(rows=1)

    validator = CausalityValidator()

    result = validator.check(data)

    assert not result.passed
    assert not result.has_evidence
    assert any(
        "insufficient historical candles" in issue
        for issue in result.issues
    )


def test_causality_observation_step_controls_sampling():
    data = make_market_data(rows=100)

    validator = CausalityValidator(
        minimum_observations=1,
        observation_step=10,
    )

    result = validator.check(data)

    assert result.passed
    assert result.observations_checked == 5


def test_invalid_validator_configuration():
    try:
        CausalityValidator(
            minimum_observations=0,
        )
        assert False
    except ValueError:
        pass

    try:
        CausalityValidator(
            observation_step=0,
        )
        assert False
    except ValueError:
        pass

    try:
        CausalityValidator(
            minimum_history_candles=1,
        )
        assert False
    except ValueError:
        pass
