# SignalForge Phase 24G.17A — Test Results Certification

**Audit Reference:** SF-PHASE24G17A-TEST-EXEC  
**Date:** 2026-11-02  
**Platform:** Windows 11 (win32), Python 3.14.3, Pytest 9.1.1  
**Target Commit:** `a176a91` (HEAD)  
**Status:** ALL TESTS PASSING (77/77 passed in 28.60s)

---

## 1. Executive Summary

As part of Phase 24G.17A (Independent Reproducibility & Statistical Audit of Cross-Asset Evaluation), a dedicated test suite was constructed (`tests/test_phase24G17A_independent_audit.py`) and executed in combination with all historical phase regression suites:
- `tests/test_phase24G17A_independent_audit.py` (6 tests)
- `tests/test_phase24G17_cross_asset.py` (5 tests)
- `tests/test_phase24G16_hypothesis_b_audit.py` (5 tests)
- `tests/test_phase24G15_research_integrity.py` (8 tests)
- `tests/test_phase24G15_strategy_research.py` (4 tests)
- `tests/test_phase24G14_cost_and_alpha_investigation.py` (5 tests)
- `tests/test_risk_engine_v2_audit.py` (14 tests)
- `tests/test_risk_and_exit_engine_spec.py` (30 tests)

**Total Test Count:** 77  
**Passed:** 77 (100.0%)  
**Failed:** 0 (0.0%)  
**Skipped:** 0 (0.0%)  
**Total Wall Clock Runtime:** 28.60 seconds

---

## 2. Dedicated Phase 24G.17A Test Suite Execution Log

```
tests/test_phase24G17A_independent_audit.py::test_hash_reconciliation_and_transcription_resolution PASSED [ 16%]
tests/test_phase24G17A_independent_audit.py::test_numerical_reproduction_zero_discrepancies PASSED [ 33%]
tests/test_phase24G17A_independent_audit.py::test_cluster_bootstrap_dependence_awareness PASSED [ 50%]
tests/test_phase24G17A_independent_audit.py::test_winner_concentration_fragility_classifications PASSED [ 66%]
tests/test_phase24G17A_independent_audit.py::test_directional_verdict_reconciliation PASSED [ 83%]
tests/test_phase24G17A_independent_audit.py::test_discrepancy_register_and_reconciliation PASSED [100%]
```

### Detailed Breakdown of Phase 24G.17A Test Coverage:

1. `test_hash_reconciliation_and_transcription_resolution`:
   - Validates that the on-disk SHA-256 for `ADANIPORTS_1m.csv` is the canonical 64-character hash `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9`.
   - Confirms that the prompt string `fb3275527303879c5edd26bc08ba6a9a41c5de85f5acc6ead21b01fce26cf9` is exactly 62 hex characters due to a 2-character omission (`ff` dropped at index 24).
   - Validates that on-disk datasets for RELIANCE, INFY, and ICICIBANK match their Phase 24G.17 manifests with zero byte corruption.

2. `test_numerical_reproduction_zero_discrepancies`:
   - Inspects `phase24G17A_reproduction_discrepancy.csv`.
   - Verifies that all 128 metric checks (16 metrics across 4 assets and 2 partitions) have `discrepancy == 0.0` and status `EXACT_MATCH`.

3. `test_cluster_bootstrap_dependence_awareness`:
   - Inspects `phase24G17A_cluster_bootstrap_analysis.csv`.
   - Verifies that block and trading-day cluster bootstrap confidence intervals are wider than naive IID bootstrap, demonstrating dependence awareness.
   - Asserts that pooled validation p-value under naive binomial assumption ($3.24 \times 10^{-8}$) is statistically invalid for cross-asset inference due to unmodeled asset clustering.

4. `test_winner_concentration_fragility_classifications`:
   - Inspects `phase24G17A_winner_concentration_audit.csv`.
   - Confirms that ADANIPORTS and INFY validation partitions are classified as `FRAGILE` because excluding top-3 winning trades causes net P&L to flip negative (-₹979.05 and -₹210.91 respectively).
   - Confirms that RELIANCE and ICICIBANK are classified as `RESILIENT` because net P&L remains positive even after top-3 winner removal (+₹9,056.88 and +₹2,842.18 respectively).

5. `test_directional_verdict_reconciliation`:
   - Inspects `phase24G17A_directional_audit.csv`.
   - Confirms all 8 directional slices have Gross Profit Factor > 1.0 (positive gross alpha).
   - Reconciles that short trading contributes +₹32,854.56 net profit across all validation assets, verifying that short trading is robust and should not be disabled.

6. `test_discrepancy_register_and_reconciliation`:
   - Inspects `phase24G17A_reproduction_comparison.csv` (128 rows, all 0.0 absolute differences).
   - Reconciles the exact ₹0.41 difference between Table 6.1 directional row sum (₹19,178.15) and Table 5.1 pooled net P&L (₹19,177.74).
   - Verifies Component A: Long friction understatement in Table 6.1 (₹20,144.67 vs true ₹20,145.07 $\implies$ ₹0.40 error).
   - Verifies Component B: INFY directional rounding difference ($₹3,339.83 - ₹374.33 = ₹2,965.50$ vs reported ₹2,965.49 $\implies$ ₹0.01 error).
   - Asserts that `phase24G17A_final_audit_verdict.md` contains formal verdict `REPRODUCIBLE_BUT_STATISTICALLY_INCONCLUSIVE`.

---

## 3. Full 77-Item Regression Test Suite Execution Log

```
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\Sanket Amte\AppData\Local\Programs\Python\Python314\python.exe
cachedir: .pytest_cache
rootdir: C:\Study Roadmap\PROJECTS\SignalForge
plugins: anyio-4.13.0
collecting ... collected 77 items

tests/test_phase24G17A_independent_audit.py::test_hash_reconciliation_and_transcription_resolution PASSED [  1%]
tests/test_phase24G17A_independent_audit.py::test_numerical_reproduction_zero_discrepancies PASSED [  2%]
tests/test_phase24G17A_independent_audit.py::test_cluster_bootstrap_dependence_awareness PASSED [  3%]
tests/test_phase24G17A_independent_audit.py::test_winner_concentration_fragility_classifications PASSED [  5%]
tests/test_phase24G17A_independent_audit.py::test_directional_verdict_reconciliation PASSED [  6%]
tests/test_phase24G17A_independent_audit.py::test_discrepancy_register_and_reconciliation PASSED [  7%]
tests/test_phase24G17_cross_asset.py::test_core_invariants_and_ledger_protection PASSED [  9%]
tests/test_phase24G17_cross_asset.py::test_cross_asset_data_quality_and_provenance PASSED [ 10%]
tests/test_phase24G17_cross_asset.py::test_cross_asset_reproducibility_validation_2019 PASSED [ 11%]
tests/test_phase24G17_cross_asset.py::test_directional_breakdown_consistency PASSED [ 12%]
tests/test_phase24G17_cross_asset.py::test_quarantine_enforcement_cross_asset PASSED [ 14%]
tests/test_phase24G16_hypothesis_b_audit.py::test_hypothesis_b_exact_reproduction PASSED [ 15%]
tests/test_phase24G16_hypothesis_b_audit.py::test_transaction_cost_reconciliation PASSED [ 16%]
tests/test_phase24G16_hypothesis_b_audit.py::test_winner_exclusion_stress_test PASSED [ 18%]
tests/test_phase24G16_hypothesis_b_audit.py::test_statistical_binomial_tests PASSED [ 19%]
tests/test_phase24G16_hypothesis_b_audit.py::test_protected_assets_and_quarantine_integrity PASSED [ 20%]
tests/test_phase24G15_research_integrity.py::test_quarantine_2020_holdout_lockout PASSED [ 22%]
tests/test_phase24G15_research_integrity.py::test_strict_temporal_causality PASSED [ 23%]
tests/test_phase24G15_research_integrity.py::test_execution_causality_next_bar_open PASSED [ 24%]
tests/test_phase24G15_research_integrity.py::test_single_application_of_transaction_friction PASSED [ 25%]
tests/test_phase24G15_research_integrity.py::test_max_concurrent_positions_enforcement PASSED [ 27%]
tests/test_phase24G15_research_integrity.py::test_partition_state_isolation PASSED [ 28%]
tests/test_phase24G15_research_integrity.py::test_deterministic_reproducibility PASSED [ 29%]
tests/test_phase24G15_research_integrity.py::test_protected_assets_integrity PASSED [ 31%]
tests/test_phase24G15_strategy_research.py::test_indicator_calculations PASSED [ 32%]
tests/test_phase24G15_strategy_research.py::test_squeeze_condition_logic PASSED [ 33%]
tests/test_phase24G15_strategy_research.py::test_multi_timeframe_feature_builder PASSED [ 35%]
tests/test_phase24G15_strategy_research.py::test_hypothesis_signal_invariants PASSED [ 36%]
tests/test_phase24G14_cost_and_alpha_investigation.py::test_statutory_charges_large_turnover_long PASSED [ 37%]
tests/test_phase24G14_cost_and_alpha_investigation.py::test_statutory_charges_short_side_asymmetry PASSED [ 38%]
tests/test_phase24G14_cost_and_alpha_investigation.py::test_statutory_charges_small_turnover_minimum_tick_slippage PASSED [ 40%]
tests/test_phase24G14_cost_and_alpha_investigation.py::test_morning_window_slippage_rate PASSED [ 41%]
tests/test_phase24G14_cost_and_alpha_investigation.py::test_rejection_mechanics_trade_count_discrepancy PASSED [ 42%]
tests/test_risk_engine_v2_audit.py::test_position_sizing_boundary_zero_and_negative PASSED [ 44%]
tests/test_risk_engine_v2_audit.py::test_position_sizing_non_finite_inputs PASSED [ 45%]
tests/test_risk_engine_v2_audit.py::test_clamped_stop_distance_clamping_and_boundaries PASSED [ 46%]
tests/test_risk_engine_v2_audit.py::test_stated_risk_budget_covers_gross_price_risk_not_friction PASSED [ 48%]
tests/test_risk_engine_v2_audit.py::test_adversarial_intrabar_stop_breach_before_trailing_ratchet_long PASSED [ 49%]
tests/test_risk_engine_v2_audit.py::test_adversarial_intrabar_stop_breach_before_trailing_ratchet_short PASSED [ 50%]
tests/test_risk_engine_v2_audit.py::test_adversarial_slippage_accounting_no_double_deduction PASSED [ 51%]
tests/test_risk_engine_v2_audit.py::test_circuit_breaker_exact_threshold_boundary PASSED [ 53%]
tests/test_risk_engine_v2_audit.py::test_circuit_breaker_remains_active_for_entire_session PASSED [ 54%]
tests/test_risk_engine_v2_audit.py::test_adversarial_consecutive_loss_cooldown_same_close_reversal PASSED [ 55%]
tests/test_risk_engine_v2_audit.py::test_data_validation_rejects_nan_and_inf PASSED [ 57%]
tests/test_risk_engine_v2_audit.py::test_no_position_or_order_carry_across_session_boundary PASSED [ 58%]
tests/test_risk_engine_v2_audit.py::test_signal_on_final_bar_does_not_execute_or_corrupt PASSED [ 59%]
tests/test_risk_engine_v2_audit.py::test_deterministic_replay_and_hash_stability PASSED [ 61%]
tests/test_risk_and_exit_engine_spec.py::test_position_sizing_respects_risk_budget PASSED [ 62%]
tests/test_risk_and_exit_engine_spec.py::test_position_sizing_respects_leverage_cap PASSED [ 63%]
tests/test_risk_and_exit_engine_spec.py::test_position_sizing_rejects_insufficient_capital PASSED [ 64%]
tests/test_risk_and_exit_engine_spec.py::test_stop_distance_clamping PASSED [ 66%]
tests/test_risk_and_exit_engine_spec.py::test_tc_risk_01_causal_next_open_fill PASSED [ 67%]
tests/test_risk_and_exit_engine_spec.py::test_tc_risk_02_normal_intrabar_stop_loss PASSED [ 68%]
tests/test_risk_and_exit_engine_spec.py::test_tc_risk_03_gap_through_stop_loss PASSED [ 70%]
tests/test_risk_and_exit_engine_spec.py::test_tc_risk_04_same_candle_stop_target_conflict PASSED [ 71%]
tests/test_risk_and_exit_engine_spec.py::test_tc_risk_05_trailing_stop_ratchet_monotonicity PASSED [ 72%]
tests/test_risk_and_exit_engine_spec.py::test_tc_risk_06_max_holding_time_expiration PASSED [ 74%]
tests/test_risk_and_exit_engine_spec.py::test_tc_risk_07_mandatory_1529_eod_liquidation PASSED [ 75%]
tests/test_risk_and_exit_engine_spec.py::test_tc_risk_08_pending_order_cancellation_at_day_rollover PASSED [ 76%]
tests/test_risk_and_exit_engine_spec.py::test_tc_risk_09_partition_boundary_purge PASSED [ 77%]
tests/test_risk_and_exit_engine_spec.py::test_tc_risk_10_daily_loss_circuit_breaker PASSED [ 79%]
tests/test_risk_and_exit_engine_spec.py::test_tc_risk_11_consecutive_loss_cooldown PASSED [ 80%]
tests/test_risk_and_exit_engine_spec.py::test_tc_risk_12_risk_budget_leverage_clamping PASSED [ 81%]
tests/test_risk_and_exit_engine_spec.py::test_tc_risk_13_missing_minute_gap_rejection PASSED [ 83%]
tests/test_risk_and_exit_engine_spec.py::test_tc_risk_14_zero_capital_bankruptcy_protection PASSED [ 84%]
tests/test_risk_and_exit_engine_spec.py::test_tc_risk_15_deterministic_replay_agreement PASSED [ 85%]
tests/test_risk_and_exit_engine_spec.py::test_short_side_causal_next_open_fill PASSED [ 87%]
tests/test_risk_and_exit_engine_spec.py::test_short_side_normal_intrabar_stop_loss PASSED [ 88%]
tests/test_risk_and_exit_engine_spec.py::test_short_side_gap_through_stop_loss PASSED [ 89%]
tests/test_risk_and_exit_engine_spec.py::test_short_side_trailing_ratchet_monotonicity PASSED [ 90%]
tests/test_risk_and_exit_engine_spec.py::test_short_side_same_candle_collision PASSED [ 92%]
tests/test_risk_and_exit_engine_spec.py::test_complex_wave_long_monotonicity PASSED [ 93%]
tests/test_risk_and_exit_engine_spec.py::test_complex_wave_short_monotonicity PASSED [ 94%]
tests/test_risk_and_exit_engine_spec.py::test_gap_through_loss_exceeds_one_r PASSED [ 96%]
tests/test_risk_and_exit_engine_spec.py::test_reversal_handling_flow PASSED [ 97%]
tests/test_risk_and_exit_engine_spec.py::test_data_corruption_and_invalid_prices PASSED [ 98%]
tests/test_risk_and_exit_engine_spec.py::test_transaction_cost_models_comparison PASSED [100%]

============================= 77 passed in 28.60s =============================
```

---

## 4. Certification Conclusion

All unit, property, and adversarial tests pass without regressions. The Phase 24G.17A audit verification suite certifies that:
1. The numerical reproduction of Phase 24G.17 is 100% bit-for-bit exact across 128 metric checks ($0.0$ difference).
2. The dataset hash mismatch was definitively proven to be a 62-character prompt truncation rather than data corruption.
3. The ₹0.41 directional P&L discrepancy is fully reconciled down to ₹0.40 friction transcription in Table 6.1 and ₹0.01 INFY float rounding.
4. The statistical inference methodology properly accounts for cross-asset correlation, cluster structure, and winner concentration.
5. The formal audit verdict is `REPRODUCIBLE_BUT_STATISTICALLY_INCONCLUSIVE`.
