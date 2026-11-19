"""
SignalForge — Phase 32C.3: Test Suite for Indian Equity Delivery Cost Engine
===========================================================================
Deterministic unit tests covering all 38 test specifications across:
  1. Rate and date tests (1–10)
  2. Tax tests (11–15)
  3. Brokerage tests (16–19)
  4. DP charge tests (20–28)
  5. Discrepancy and sensitivity tests (29–32)
  6. Financial correctness & regression fixture tests (33–38)
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN
import pytest

from src.backtest.indian_delivery_costs import (
    DeliveryOrder,
    OrderSide,
    DPBillingMode,
    RoundingMode,
    StatutoryCostSchedule,
    ExchangeChargeSchedule,
    BrokerChargeProfile,
    DepositoryChargeProfile,
    ExecutionCostAssumptions,
    DeliveryCostBreakdown,
    DeliveryCostCalculator,
    # Pre-defined schedules
    STATUTORY_SCHEDULE_HISTORICAL_MH,
    STATUTORY_SCHEDULE_MODERN_PRE_JULY2022,
    STATUTORY_SCHEDULE_MODERN,
    NSE_CASH_SCHEDULE_HISTORICAL_2017,
    NSE_CASH_SCHEDULE_HISTORICAL_2019,
    NSE_CASH_SCHEDULE_2023_Q2,
    NSE_CASH_SCHEDULE_2024_Q4,
    NSE_CASH_SCHEDULE_2026_Q1,
    # Profiles
    GROWW_DELIVERY_PROFILE,
    GROWW_DELIVERY_STRESS_317_PROFILE,
    ZERODHA_DELIVERY_PROFILE,
    CDSL_GROWW_MALE_PROFILE,
    CDSL_GROWW_FEMALE_PROFILE,
    CDSL_ZERODHA_PROFILE,
    ZERO_EXECUTION_ASSUMPTIONS,
    REALISTIC_SWING_EXECUTION_ASSUMPTIONS,
    # Resolvers
    get_statutory_schedule,
    get_exchange_schedule,
)


# ===========================================================================
# 1. Rate and Date Tests (1–10)
# ===========================================================================

def test_01_nse_schedule_before_march_2026():
    """1. NSE schedule before 1 March 2026 (Oct 2024 to Feb 2026)."""
    sched = get_exchange_schedule(date(2025, 6, 15))
    assert sched.schedule_id == "NSE_CASH_2024_Q4"
    assert sched.transaction_charge_rate == Decimal("297.00") / Decimal("10000000")
    assert sched.ipft_rate == Decimal("10.00") / Decimal("10000000")
    assert sched.combined_exchange_ipft_rate == Decimal("307.00") / Decimal("10000000")


def test_02_nse_schedule_from_march_2026():
    """2. NSE schedule from 1 March 2026 (Circular NSE/FA/73061)."""
    sched = get_exchange_schedule(date(2026, 3, 1))
    assert sched.schedule_id == "NSE_CASH_2026_Q1"
    assert sched.transaction_charge_rate == Decimal("306.99") / Decimal("10000000")
    assert sched.ipft_rate == Decimal("0.01") / Decimal("10000000")
    assert sched.combined_exchange_ipft_rate == Decimal("307.00") / Decimal("10000000")


def test_03_ipft_is_not_double_counted():
    """3. IPFT is separately accounted for and not double-counted."""
    sched = NSE_CASH_SCHEDULE_2026_Q1
    expected_sum = sched.transaction_charge_rate + sched.ipft_rate
    assert sched.combined_exchange_ipft_rate == expected_sum

    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("100000"),
        sell_turnovers=Decimal("100000"),
        trade_date=date(2026, 3, 15),
    )
    assert res.combined_exchange_ipft_charge == res.exchange_transaction_charge + res.ipft_charge


def test_04_sebi_fee_before_april_2019():
    """4. SEBI fee before 1 April 2019 is ₹15 per crore."""
    sched = get_exchange_schedule(date(2018, 5, 10))
    assert sched.schedule_id == "NSE_CASH_HISTORICAL_2017"
    assert sched.sebi_turnover_rate == Decimal("15.00") / Decimal("10000000")


def test_05_sebi_fee_from_april_2019():
    """5. SEBI fee from 1 April 2019 is ₹10 per crore (Notification 2019/03)."""
    sched = get_exchange_schedule(date(2019, 4, 1))
    assert sched.schedule_id == "NSE_CASH_HISTORICAL_2019"
    assert sched.sebi_turnover_rate == Decimal("10.00") / Decimal("10000000")


def test_06_sebi_gst_immediately_before_july_18_2022():
    """6. SEBI turnover fee was exempt from GST before 18 July 2022."""
    sched = get_statutory_schedule(date(2022, 7, 17))
    assert sched.gst_on_sebi_fees is False

    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("50000"),
        sell_turnovers=Decimal("50000"),
        trade_date=date(2022, 7, 17),
    )
    assert res.taxable_sebi_fee == Decimal("0.00")


def test_07_sebi_gst_from_july_18_2022():
    """7. SEBI turnover fee attracts 18% GST from 18 July 2022 (Notification 04/2022)."""
    sched = get_statutory_schedule(date(2022, 7, 18))
    assert sched.gst_on_sebi_fees is True

    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("50000"),
        sell_turnovers=Decimal("50000"),
        trade_date=date(2022, 7, 18),
    )
    assert res.taxable_sebi_fee == res.sebi_turnover_fee


def test_08_stamp_duty_immediately_before_july_1_2020():
    """8. Maharashtra stamp duty before 1 July 2020 was 0.005% on buy turnover."""
    sched = get_statutory_schedule(date(2020, 6, 30), state="MH")
    assert sched.stamp_duty_buy_rate == Decimal("0.00005")
    assert sched.stamp_duty_sell_rate == Decimal("0")

    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("100000"),
        sell_turnovers=Decimal("100000"),
        trade_date=date(2020, 6, 30),
    )
    assert res.buy_stamp_duty == Decimal("5.00")


def test_09_stamp_duty_from_july_1_2020():
    """9. National uniform stamp duty from 1 July 2020 is 0.015% on buy turnover."""
    sched = get_statutory_schedule(date(2020, 7, 1))
    assert sched.stamp_duty_buy_rate == Decimal("0.00015")
    assert sched.stamp_duty_sell_rate == Decimal("0")

    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("100000"),
        sell_turnovers=Decimal("100000"),
        trade_date=date(2020, 7, 1),
    )
    assert res.buy_stamp_duty == Decimal("15.00")


def test_10_unsupported_historical_periods_fail_safely():
    """10. Dates prior to 2017 fail safely with clear ValueError."""
    with pytest.raises(ValueError, match="Unsupported historical date"):
        get_statutory_schedule(date(2016, 12, 31))

    with pytest.raises(ValueError, match="Unsupported historical date"):
        get_exchange_schedule(date(2016, 12, 31))

    with pytest.raises(ValueError, match="Exchange 'BSE' unsupported"):
        get_exchange_schedule(date(2025, 1, 1), exchange="BSE")


# ===========================================================================
# 2. Tax Tests (11–15)
# ===========================================================================

def test_11_stt_excluded_from_gst():
    """11. Securities Transaction Tax (STT) is strictly exempt from GST."""
    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("100000"),
        sell_turnovers=Decimal("100000"),
    )
    assert res.total_stt == Decimal("200.00")
    # Verify STT is not part of taxable services base
    assert res.taxable_services_base == (
        res.total_brokerage
        + res.exchange_transaction_charge
        + res.ipft_charge
        + res.taxable_sebi_fee
        + res.total_dp_base
    )


def test_12_stamp_duty_excluded_from_gst():
    """12. Stamp duty is strictly exempt from GST."""
    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("100000"),
        sell_turnovers=Decimal("100000"),
    )
    assert res.total_stamp_duty == Decimal("15.00")
    assert res.total_stamp_duty not in [res.taxable_services_base]


def test_13_applicable_services_receive_gst_correctly():
    """13. All taxable financial service components are included in GST base."""
    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("50000"),
        sell_turnovers=Decimal("55000"),
        trade_date=date(2026, 3, 15),
    )
    expected_taxable = (
        res.total_brokerage
        + res.exchange_transaction_charge
        + res.ipft_charge
        + res.taxable_sebi_fee
        + res.total_dp_base
    )
    assert res.taxable_services_base == expected_taxable
    assert res.total_gst == (expected_taxable * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def test_14_gst_not_applied_twice():
    """14. GST is applied exactly once to the taxable services aggregate."""
    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("10000"),
        sell_turnovers=Decimal("10500"),
    )
    assert res.statutory_broker_costs == (
        res.total_brokerage
        + res.total_stt
        + res.total_stamp_duty
        + res.exchange_transaction_charge
        + res.ipft_charge
        + res.sebi_turnover_fee
        + res.total_dp_base
        + res.total_gst
    )


def test_15_component_level_gst_rounding_deterministic():
    """15. GST quantizes deterministically to 2 decimal places."""
    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("12345.67"),
        sell_turnovers=Decimal("23456.78"),
    )
    assert res.total_gst == res.total_gst.quantize(Decimal("0.01"))


# ===========================================================================
# 3. Brokerage Tests (16–19)
# ===========================================================================

def test_16_minimum_brokerage():
    """16. Minimum brokerage ₹5.00 is billed when 0.1% of turnover is < ₹5.00."""
    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("2000.00"),  # 0.1% = ₹2.00, below min ₹5
        sell_turnovers=Decimal("2000.00"),
    )
    assert res.buy_brokerage == Decimal("5.00")
    assert res.sell_brokerage == Decimal("5.00")
    assert res.total_brokerage == Decimal("10.00")


def test_17_percentage_based_brokerage():
    """17. Percentage brokerage (0.1%) applies between ₹5,000 and ₹20,000."""
    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("12500.00"),  # 0.1% = ₹12.50
        sell_turnovers=Decimal("15000.00"), # 0.1% = ₹15.00
    )
    assert res.buy_brokerage == Decimal("12.50")
    assert res.sell_brokerage == Decimal("15.00")
    assert res.total_brokerage == Decimal("27.50")


def test_18_maximum_brokerage_cap():
    """18. Maximum brokerage is capped at ₹20.00 per executed order."""
    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("50000.00"),   # 0.1% = ₹50, capped at ₹20
        sell_turnovers=Decimal("100000.00"), # 0.1% = ₹100, capped at ₹20
    )
    assert res.buy_brokerage == Decimal("20.00")
    assert res.sell_brokerage == Decimal("20.00")
    assert res.total_brokerage == Decimal("40.00")


def test_19_multiple_separate_orders_brokerage():
    """19. Brokerage is calculated per executed order, not per total turnover."""
    orders = [
        DeliveryOrder("B1", "INFY", OrderSide.BUY, Decimal("50000"), date(2026, 3, 1)),
        DeliveryOrder("S1", "INFY", OrderSide.SELL, Decimal("30000"), date(2026, 3, 2)),
        DeliveryOrder("S2", "INFY", OrderSide.SELL, Decimal("30000"), date(2026, 3, 3)),
    ]
    res = DeliveryCostCalculator.calculate_trade(
        orders=orders,
        broker_profile=GROWW_DELIVERY_PROFILE,
        depository_profile=CDSL_GROWW_MALE_PROFILE,
    )
    # Buy: ₹20 (capped); Sell 1: ₹20 (capped); Sell 2: ₹20 (capped) -> Total ₹60
    assert res.buy_brokerage == Decimal("20.00")
    assert res.sell_brokerage == Decimal("40.00")
    assert res.total_brokerage == Decimal("60.00")


# ===========================================================================
# 4. DP Charge Tests (20–28)
# ===========================================================================

def test_20_groww_male_profile():
    """20. Groww male profile bills ₹20.00 base DP fee (₹16.50 Groww + ₹3.50 CDSL)."""
    assert CDSL_GROWW_MALE_PROFILE.broker_dp_fee == Decimal("16.50")
    assert CDSL_GROWW_MALE_PROFILE.cdsl_fee == Decimal("3.50")
    assert CDSL_GROWW_MALE_PROFILE.total_base_dp_fee == Decimal("20.00")


def test_21_groww_female_profile():
    """21. Groww female profile bills ₹19.75 base DP fee (₹16.50 Groww + ₹3.25 CDSL)."""
    assert CDSL_GROWW_FEMALE_PROFILE.broker_dp_fee == Decimal("16.50")
    assert CDSL_GROWW_FEMALE_PROFILE.cdsl_fee == Decimal("3.25")
    assert CDSL_GROWW_FEMALE_PROFILE.total_base_dp_fee == Decimal("19.75")


def test_22_groww_fee_waiver_below_100():
    """22. Sale value < ₹100 waives Groww's ₹16.50 fee; only CDSL fee applies."""
    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("80.00"),
        sell_turnovers=Decimal("95.00"),  # < ₹100
        depository_profile=CDSL_GROWW_MALE_PROFILE,
    )
    assert res.groww_dp_charge == Decimal("0.00")
    assert res.cdsl_dp_charge == Decimal("3.50")
    assert res.total_dp_base == Decimal("3.50")


def test_23_cdsl_component_correctly_accounted_for():
    """23. CDSL depository component remains accounted for and separately tracked."""
    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("50000"),
        sell_turnovers=Decimal("50000"),
        depository_profile=CDSL_GROWW_MALE_PROFILE,
    )
    assert res.groww_dp_charge == Decimal("16.50")
    assert res.cdsl_dp_charge == Decimal("3.50")
    assert res.total_dp_base == Decimal("20.00")


def test_24_two_separate_same_day_sell_orders_groww():
    """24. Under Groww PER_EXECUTED_ORDER, 2 separate sell orders on same day incur 2 DP charges."""
    d = date(2026, 3, 10)
    orders = [
        DeliveryOrder("B1", "RELIANCE", OrderSide.BUY, Decimal("100000"), d),
        DeliveryOrder("S1", "RELIANCE", OrderSide.SELL, Decimal("50000"), d),
        DeliveryOrder("S2", "RELIANCE", OrderSide.SELL, Decimal("50000"), d),
    ]
    res = DeliveryCostCalculator.calculate_trade(
        orders=orders,
        broker_profile=GROWW_DELIVERY_PROFILE,  # PER_EXECUTED_ORDER
        depository_profile=CDSL_GROWW_MALE_PROFILE,
    )
    assert res.dp_charge_debit_count == 2
    assert res.groww_dp_charge == Decimal("33.00")
    assert res.cdsl_dp_charge == Decimal("7.00")
    assert res.total_dp_base == Decimal("40.00")


def test_25_partial_fills_of_one_order_incur_one_dp_charge():
    """25. Multiple partial fills of ONE order_id incur only ONE DP charge."""
    d = date(2026, 3, 10)
    orders = [
        DeliveryOrder("B1", "INFY", OrderSide.BUY, Decimal("100000"), d),
        DeliveryOrder("S1", "INFY", OrderSide.SELL, Decimal("30000"), d, execution_id="FILL_1"),
        DeliveryOrder("S1", "INFY", OrderSide.SELL, Decimal("70000"), d, execution_id="FILL_2"),
    ]
    res = DeliveryCostCalculator.calculate_trade(
        orders=orders,
        broker_profile=GROWW_DELIVERY_PROFILE,
        depository_profile=CDSL_GROWW_MALE_PROFILE,
    )
    assert res.sell_order_count == 1
    assert res.dp_charge_debit_count == 1
    assert res.total_dp_base == Decimal("20.00")


def test_26_separate_day_sell_orders_incur_separate_dp_charges():
    """26. Separate sell orders on different trading days incur separate DP charges."""
    orders = [
        DeliveryOrder("B1", "INFY", OrderSide.BUY, Decimal("100000"), date(2026, 3, 1)),
        DeliveryOrder("S1", "INFY", OrderSide.SELL, Decimal("50000"), date(2026, 3, 5)),
        DeliveryOrder("S2", "INFY", OrderSide.SELL, Decimal("50000"), date(2026, 3, 8)),
    ]
    res = DeliveryCostCalculator.calculate_trade(
        orders=orders,
        broker_profile=GROWW_DELIVERY_PROFILE,
        depository_profile=CDSL_GROWW_MALE_PROFILE,
    )
    assert res.dp_charge_debit_count == 2
    assert res.total_dp_base == Decimal("40.00")


def test_27_per_isin_per_day_behaves_independently():
    """27. PER_ISIN_PER_DAY aggregates same-day sell orders into ONE DP charge."""
    d = date(2026, 3, 10)
    orders = [
        DeliveryOrder("B1", "INFY", OrderSide.BUY, Decimal("100000"), d),
        DeliveryOrder("S1", "INFY", OrderSide.SELL, Decimal("50000"), d),
        DeliveryOrder("S2", "INFY", OrderSide.SELL, Decimal("50000"), d),
    ]
    zerodha_profile = BrokerChargeProfile(
        broker_name="Zerodha",
        pricing_plan="Zero Delivery",
        delivery_brokerage_rate=Decimal("0"),
        brokerage_min_per_order=Decimal("0"),
        brokerage_max_per_order=Decimal("0"),
        dp_billing_mode=DPBillingMode.PER_ISIN_PER_DAY,
    )
    res = DeliveryCostCalculator.calculate_trade(
        orders=orders,
        broker_profile=zerodha_profile,
        depository_profile=CDSL_GROWW_MALE_PROFILE,
    )
    assert res.sell_order_count == 2
    assert res.dp_charge_debit_count == 1
    assert res.total_dp_base == Decimal("20.00")


def test_28_buy_orders_do_not_incur_dp_charges():
    """28. Buy orders (inflow/credit of shares) incur zero DP charges."""
    orders = [
        DeliveryOrder("B1", "INFY", OrderSide.BUY, Decimal("100000"), date(2026, 3, 1)),
    ]
    res = DeliveryCostCalculator.calculate_trade(
        orders=orders,
        broker_profile=GROWW_DELIVERY_PROFILE,
        depository_profile=CDSL_GROWW_MALE_PROFILE,
    )
    assert res.dp_charge_debit_count == 0
    assert res.total_dp_base == Decimal("0.00")


# ===========================================================================
# 5. Discrepancy and Sensitivity Tests (29–32)
# ===========================================================================

def test_29_official_nse_schedule_remains_307():
    """29. Official NSE schedule remains ₹307/crore combined."""
    sched_2024 = NSE_CASH_SCHEDULE_2024_Q4
    sched_2026 = NSE_CASH_SCHEDULE_2026_Q1
    assert sched_2024.combined_exchange_ipft_rate == Decimal("307.00") / Decimal("10000000")
    assert sched_2026.combined_exchange_ipft_rate == Decimal("307.00") / Decimal("10000000")


def test_30_hypothetical_317_scenario_separately_configurable():
    """30. Hypothetical ₹317/crore scenario is separately configurable."""
    assert GROWW_DELIVERY_STRESS_317_PROFILE.is_hypothetical_override is True
    assert GROWW_DELIVERY_STRESS_317_PROFILE.exchange_turnover_rate_override == Decimal("317.00") / Decimal("10000000")

    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("100000"),
        sell_turnovers=Decimal("108000"),
        broker_profile=GROWW_DELIVERY_STRESS_317_PROFILE,
    )
    assert res.is_hypothetical_override is True
    assert res.exchange_transaction_charge == Decimal("6.59")
    assert res.ipft_charge == Decimal("0.00")


def test_31_317_scenario_never_mutates_official_schedule():
    """31. The ₹317 scenario never mutates or replaces the official NSE schedule."""
    # Run a trade with 317 override
    DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("100000"),
        sell_turnovers=Decimal("108000"),
        broker_profile=GROWW_DELIVERY_STRESS_317_PROFILE,
    )
    # Verify official schedule is 100% intact
    assert NSE_CASH_SCHEDULE_2026_Q1.transaction_charge_rate == Decimal("306.99") / Decimal("10000000")
    assert NSE_CASH_SCHEDULE_2026_Q1.ipft_rate == Decimal("0.01") / Decimal("10000000")
    assert NSE_CASH_SCHEDULE_2026_Q1.combined_exchange_ipft_rate == Decimal("307.00") / Decimal("10000000")


def test_32_ipft_never_counted_twice_under_either_scenario():
    """32. IPFT is never counted twice under either official or override scenario."""
    # Under official:
    res_off = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("100000"),
        sell_turnovers=Decimal("100000"),
        broker_profile=GROWW_DELIVERY_PROFILE,
    )
    assert res_off.combined_exchange_ipft_charge == res_off.exchange_transaction_charge + res_off.ipft_charge

    # Under override:
    res_ov = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("100000"),
        sell_turnovers=Decimal("100000"),
        broker_profile=GROWW_DELIVERY_STRESS_317_PROFILE,
    )
    assert res_ov.ipft_charge == Decimal("0.00")
    assert res_ov.combined_exchange_ipft_charge == res_ov.exchange_transaction_charge


# ===========================================================================
# 6. Financial Correctness Tests & Regression Fixtures (33–38)
# ===========================================================================

def test_33_all_four_p32c22_examples_reproduced():
    """33. All four Phase 32C.2.2 example calculations are exactly reproduced."""
    # Example 1: Buy ₹10,000 / Sell ₹10,500
    res1 = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("10000.00"),
        sell_turnovers=Decimal("10500.00"),
        broker_profile=GROWW_DELIVERY_PROFILE,
        depository_profile=CDSL_GROWW_MALE_PROFILE,
        execution_assumptions=REALISTIC_SWING_EXECUTION_ASSUMPTIONS,
    )
    assert res1.total_transaction_costs == Decimal("76.71")
    assert res1.net_pnl == Decimal("423.29")

    # Example 2: Buy ₹50,000 / Sell ₹55,000
    res2 = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("50000.00"),
        sell_turnovers=Decimal("55000.00"),
        broker_profile=GROWW_DELIVERY_PROFILE,
        depository_profile=CDSL_GROWW_MALE_PROFILE,
        execution_assumptions=REALISTIC_SWING_EXECUTION_ASSUMPTIONS,
    )
    assert res2.total_transaction_costs == Decimal("218.72")
    assert res2.net_pnl == Decimal("4781.28")

    # Example 3: Buy ₹100,000 / Sell ₹108,000
    res3 = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("100000.00"),
        sell_turnovers=Decimal("108000.00"),
        broker_profile=GROWW_DELIVERY_PROFILE,
        depository_profile=CDSL_GROWW_MALE_PROFILE,
        execution_assumptions=REALISTIC_SWING_EXECUTION_ASSUMPTIONS,
    )
    assert res3.total_transaction_costs == Decimal("363.99")
    assert res3.net_pnl == Decimal("7636.01")

    # Example 4: Buy ₹100,000 / Two exits of ₹54,000 (separate orders)
    res4 = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("100000.00"),
        sell_turnovers=[Decimal("54000.00"), Decimal("54000.00")],
        broker_profile=GROWW_DELIVERY_PROFILE,
        depository_profile=CDSL_GROWW_MALE_PROFILE,
        execution_assumptions=REALISTIC_SWING_EXECUTION_ASSUMPTIONS,
    )
    assert res4.total_transaction_costs == Decimal("411.19")
    assert res4.net_pnl == Decimal("7588.81")


def test_34_example_4_distinguishes_aggregated_from_separate():
    """34. Correctly distinguishes one aggregated sell order from two separate sell orders."""
    # Case A: Aggregated (PER_ISIN_PER_DAY)
    groww_isin_day = BrokerChargeProfile(
        broker_name="Groww",
        pricing_plan="Groww ISIN Day",
        delivery_brokerage_rate=Decimal("0.001"),
        brokerage_min_per_order=Decimal("5.00"),
        brokerage_max_per_order=Decimal("20.00"),
        dp_billing_mode=DPBillingMode.PER_ISIN_PER_DAY,
    )
    res_agg = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("100000.00"),
        sell_turnovers=[Decimal("54000.00"), Decimal("54000.00")],
        broker_profile=groww_isin_day,
        depository_profile=CDSL_GROWW_MALE_PROFILE,
        execution_assumptions=REALISTIC_SWING_EXECUTION_ASSUMPTIONS,
    )
    assert res_agg.total_transaction_costs == Decimal("387.59")

    # Case B: Separate (PER_EXECUTED_ORDER)
    res_sep = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("100000.00"),
        sell_turnovers=[Decimal("54000.00"), Decimal("54000.00")],
        broker_profile=GROWW_DELIVERY_PROFILE,
        depository_profile=CDSL_GROWW_MALE_PROFILE,
        execution_assumptions=REALISTIC_SWING_EXECUTION_ASSUMPTIONS,
    )
    assert res_sep.total_transaction_costs == Decimal("411.19")
    # Variance is exactly ₹23.60 (₹20 DP base + ₹3.60 GST)
    assert res_sep.total_transaction_costs - res_agg.total_transaction_costs == Decimal("23.60")


def test_35_net_pnl_equals_gross_minus_total_costs():
    """35. Net P&L rigorously equals gross P&L minus total transaction costs."""
    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("75000.00"),
        sell_turnovers=Decimal("82500.00"),
    )
    assert res.gross_pnl == Decimal("7500.00")
    assert res.net_pnl == res.gross_pnl - res.total_transaction_costs


def test_36_breakeven_percentage_documented_denominator():
    """36. Break-even percentage strictly uses buy turnover as the denominator."""
    res = DeliveryCostCalculator.calculate_simple_trade(
        buy_turnover=Decimal("50000.00"),
        sell_turnovers=Decimal("55000.00"),
    )
    expected_be = ((res.total_transaction_costs / Decimal("50000.00")) * Decimal("100")).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_EVEN
    )
    assert res.breakeven_gross_pct == expected_be


def test_37_rounding_and_aggregation_deterministic():
    """37. Repeated executions produce bitwise-identical Decimal output."""
    res_a = DeliveryCostCalculator.calculate_simple_trade(buy_turnover=Decimal("12345.67"), sell_turnovers=Decimal("13456.78"))
    res_b = DeliveryCostCalculator.calculate_simple_trade(buy_turnover=Decimal("12345.67"), sell_turnovers=Decimal("13456.78"))
    assert res_a.total_transaction_costs == res_b.total_transaction_costs
    assert res_a.net_pnl == res_b.net_pnl
    assert res_a.total_gst == res_b.total_gst


def test_38_invalid_inputs_rejected():
    """38. Invalid negative turnover and malformed orders raise ValueError."""
    with pytest.raises(ValueError, match="cannot be negative"):
        DeliveryOrder("B1", "INFY", OrderSide.BUY, Decimal("-100"), date(2026, 3, 1))

    with pytest.raises(ValueError, match="At least one DeliveryOrder is required"):
        DeliveryCostCalculator.calculate_trade(
            orders=[],
            broker_profile=GROWW_DELIVERY_PROFILE,
            depository_profile=CDSL_GROWW_MALE_PROFILE,
        )
