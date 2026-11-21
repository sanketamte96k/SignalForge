"""
Unit tests for Phase 32H.1: Monthly Performance Analytics
=========================================================
Tests verify:
1. Complete 48-month calendar coverage (2017-01 to 2020-12).
2. Exact 55-trade reconciliation.
3. Accurate zero-trade month handling (23 months with 0 trades, 0 P&L, 0 costs).
4. Monthly gross - costs == net P&L equality across all months.
5. Official schedule P&L reconciliation against annual baseline figures.
6. Stress schedule P&L reconciliation against annual baseline figures.
7. Cost stress premium monotonicity and sizing floor explanations.
8. Illustrative proportional ₹10,000 scaling validity.
9. Deliverable existence and integrity.
"""

from pathlib import Path
import pytest
import pandas as pd


@pytest.fixture(scope="module")
def monthly_df():
    path = Path("reports/phase32h_1/monthly_pnl.csv")
    assert path.exists(), f"Deliverable missing: {path}"
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def cost_comp_df():
    path = Path("reports/phase32h_1/monthly_cost_comparison.csv")
    assert path.exists(), f"Deliverable missing: {path}"
    return pd.read_csv(path)


@pytest.fixture(scope="module")
def yearly_df():
    path = Path("reports/phase32h_1/monthly_yearly_summary.csv")
    assert path.exists(), f"Deliverable missing: {path}"
    return pd.read_csv(path)


# -----------------------------------------------------------------------------
# 1. Calendar Months and Trade Count Integrity
# -----------------------------------------------------------------------------

def test_calendar_months_coverage(monthly_df):
    """Verify exactly 48 calendar months from 2017-01 to 2020-12 exist in order."""
    assert len(monthly_df) == 48
    expected_months = [str(m) for m in pd.period_range("2017-01", "2020-12", freq="M")]
    assert list(monthly_df["month"]) == expected_months


def test_total_trade_count_sums_to_55(monthly_df):
    """Verify total trade count sums to exactly 55."""
    assert monthly_df["trades"].sum() == 55


def test_active_and_zero_trade_months_partition(monthly_df):
    """Verify partition into 25 active months and 23 zero-trade months."""
    active_months = monthly_df[monthly_df["trades"] > 0]
    zero_months = monthly_df[monthly_df["trades"] == 0]

    assert len(active_months) == 25
    assert len(zero_months) == 23
    assert len(active_months) + len(zero_months) == 48


def test_zero_trade_months_invariants(monthly_df, cost_comp_df):
    """Verify that zero-trade months have exactly 0 P&L, 0 costs, and 0 return."""
    zero_m = monthly_df[monthly_df["trades"] == 0]
    for _, row in zero_m.iterrows():
        assert row["official_gross_pnl"] == 0.0
        assert row["official_costs"] == 0.0
        assert row["official_net_pnl"] == 0.0
        assert row["official_return_pct"] == 0.0
        assert row["official_wins"] == 0
        assert row["official_losses"] == 0

    zero_cost = cost_comp_df[cost_comp_df["trades"] == 0]
    for _, row in zero_cost.iterrows():
        assert row["stress_gross_pnl"] == 0.0
        assert row["stress_costs"] == 0.0
        assert row["stress_net_pnl"] == 0.0
        assert row["cost_stress_premium"] == 0.0


# -----------------------------------------------------------------------------
# 2. P&L Math and Reconciliation
# -----------------------------------------------------------------------------

def test_gross_minus_costs_equals_net(monthly_df, cost_comp_df):
    """Verify gross realized P&L minus costs equals net realized P&L for every single month."""
    for _, row in monthly_df.iterrows():
        calc_net = round(row["official_gross_pnl"] - row["official_costs"], 2)
        assert calc_net == pytest.approx(row["official_net_pnl"], abs=0.01)

    for _, row in cost_comp_df.iterrows():
        calc_str_net = round(row["stress_gross_pnl"] - row["stress_costs"], 2)
        assert calc_str_net == pytest.approx(row["stress_net_pnl"], abs=0.01)


def test_annual_and_combined_official_reconciliation(yearly_df):
    """Verify official annual P&L figures reconcile exactly to Phase 32G baselines."""
    # 2017: Net ₹6,450.82
    y2017 = yearly_df[yearly_df["year"] == "2017"].iloc[0]
    assert y2017["total_trades"] == 13
    assert y2017["official_gross_pnl"] == pytest.approx(8414.62, abs=0.01)
    assert y2017["official_costs"] == pytest.approx(1963.80, abs=0.01)
    assert y2017["official_net_pnl"] == pytest.approx(6450.82, abs=0.01)

    # 2018: Net ₹5,038.29
    y2018 = yearly_df[yearly_df["year"] == "2018"].iloc[0]
    assert y2018["total_trades"] == 12
    assert y2018["official_gross_pnl"] == pytest.approx(6779.90, abs=0.01)
    assert y2018["official_costs"] == pytest.approx(1741.61, abs=0.01)
    assert y2018["official_net_pnl"] == pytest.approx(5038.29, abs=0.01)

    # 2019: Net -₹3,635.27
    y2019 = yearly_df[yearly_df["year"] == "2019"].iloc[0]
    assert y2019["total_trades"] == 18
    assert y2019["official_gross_pnl"] == pytest.approx(-1150.64, abs=0.01)
    assert y2019["official_costs"] == pytest.approx(2484.63, abs=0.01)
    assert y2019["official_net_pnl"] == pytest.approx(-3635.27, abs=0.01)

    # 2020: Net ₹13,027.93
    y2020 = yearly_df[yearly_df["year"] == "2020"].iloc[0]
    assert y2020["total_trades"] == 12
    assert y2020["official_gross_pnl"] == pytest.approx(14491.10, abs=0.01)
    assert y2020["official_costs"] == pytest.approx(1463.17, abs=0.01)
    assert y2020["official_net_pnl"] == pytest.approx(13027.93, abs=0.01)

    # Combined: Net ₹20,881.77
    comb = yearly_df[yearly_df["year"] == "Combined (2017-2020)"].iloc[0]
    assert comb["total_trades"] == 55
    assert comb["official_gross_pnl"] == pytest.approx(28534.98, abs=0.01)
    assert comb["official_costs"] == pytest.approx(7653.21, abs=0.01)
    assert comb["official_net_pnl"] == pytest.approx(20881.77, abs=0.01)


def test_annual_and_combined_stress_reconciliation(yearly_df):
    """Verify stress annual P&L figures reconcile exactly to Phase 32G baselines."""
    # 2017: Net ₹6,145.70
    y2017 = yearly_df[yearly_df["year"] == "2017"].iloc[0]
    assert y2017["stress_net_pnl"] == pytest.approx(6145.70, abs=0.01)
    assert y2017["stress_costs"] == pytest.approx(2268.92, abs=0.01)

    # 2018: Net ₹4,768.81
    y2018 = yearly_df[yearly_df["year"] == "2018"].iloc[0]
    assert y2018["stress_net_pnl"] == pytest.approx(4768.81, abs=0.01)
    assert y2018["stress_costs"] == pytest.approx(2011.09, abs=0.01)

    # 2019: Net -₹4,022.52
    y2019 = yearly_df[yearly_df["year"] == "2019"].iloc[0]
    assert y2019["stress_net_pnl"] == pytest.approx(-4022.52, abs=0.01)
    assert y2019["stress_costs"] == pytest.approx(2850.22, abs=0.01)

    # 2020: Net ₹12,837.40
    y2020 = yearly_df[yearly_df["year"] == "2020"].iloc[0]
    assert y2020["stress_net_pnl"] == pytest.approx(12837.40, abs=0.01)
    assert y2020["stress_costs"] == pytest.approx(1653.70, abs=0.01)

    # Combined: Net ₹19,729.39
    comb = yearly_df[yearly_df["year"] == "Combined (2017-2020)"].iloc[0]
    assert comb["stress_gross_pnl"] == pytest.approx(28513.32, abs=0.01)
    assert comb["stress_costs"] == pytest.approx(8783.93, abs=0.01)
    assert comb["stress_net_pnl"] == pytest.approx(19729.39, abs=0.01)


def test_stress_cost_premium_positivity(cost_comp_df):
    """Verify that stress costs are greater than official costs for all active months."""
    active = cost_comp_df[cost_comp_df["trades"] > 0]
    for _, row in active.iterrows():
        assert row["cost_stress_premium"] > 0.0
        assert row["stress_costs"] > row["official_costs"]


def test_best_and_worst_month_identification(monthly_df):
    """Verify the identity of the best and worst performing months."""
    best_row = monthly_df.loc[monthly_df["official_net_pnl"].idxmax()]
    worst_row = monthly_df.loc[monthly_df["official_net_pnl"].idxmin()]

    assert best_row["month"] == "2020-11"
    assert best_row["official_net_pnl"] == pytest.approx(6426.63, abs=0.01)

    assert worst_row["month"] == "2019-01"
    assert worst_row["official_net_pnl"] == pytest.approx(-2159.23, abs=0.01)


def test_illustrative_10k_proportional_scaling(monthly_df):
    """Verify illustrative proportional ₹10,000 scaling is exactly 10% of ₹100,000."""
    for _, row in monthly_df.iterrows():
        expected_p10k_net = round(row["official_net_pnl"] * 0.10, 2)
        assert row["p10k_illustrative_official_net"] == pytest.approx(expected_p10k_net, abs=0.01)
        assert row["p10k_illustrative_official_return_pct"] == pytest.approx(row["official_return_pct"], abs=0.01)


def test_all_deliverables_exist():
    """Verify that all 8 deliverables specified in Section 8 are generated and non-empty."""
    base_dir = Path("reports/phase32h_1")
    expected_files = [
        "monthly_pnl.csv",
        "monthly_yearly_summary.csv",
        "monthly_cost_comparison.csv",
        "monthly_pnl_chart.png",
        "monthly_cumulative_pnl_chart.png",
        "monthly_return_chart.png",
    ]
    for fn in expected_files:
        fp = base_dir / fn
        assert fp.exists(), f"Missing deliverable: {fp}"
        assert fp.stat().st_size > 0, f"Empty deliverable: {fp}"
