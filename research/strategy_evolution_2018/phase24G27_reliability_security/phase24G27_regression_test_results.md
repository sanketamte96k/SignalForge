# SignalForge — Phase 24G.27: Regression Test Results

## 1. Executive Summary

This report documents comprehensive regression test execution across SignalForge following the integration of Phase 24G.27 Core Reliability and Security Hardening improvements.

All core subsystems—including causal backtesting, paper trading execution, historical stock validation, technical indicators, and API configuration—were tested against existing suites. Zero functional regressions were introduced.

---

## 2. Test Execution Breakdown by Subsystem

### 2.1 Phase 24 Research & Audit Lineage Tests
All historical audit test modules from Phase 24G.14 through Phase 24G.27 were executed concurrently:
```
tests/test_phase24G14_cost_and_alpha_investigation.py .....              [  4%]
tests/test_phase24G15_research_integrity.py ........                     [ 10%]
tests/test_phase24G15_strategy_research.py ....                          [ 14%]
tests/test_phase24G16_hypothesis_b_audit.py .....                        [ 18%]
tests/test_phase24G17A_independent_audit.py .......                      [ 24%]
tests/test_phase24G17_cross_asset.py .....                               [ 28%]
tests/test_phase24G18_fresh_oos.py ........                              [ 35%]
tests/test_phase24G19_data_acquisition_audit.py .......                  [ 41%]
tests/test_phase24G20_provider_verification.py ........                  [ 47%]
tests/test_phase24G22_angelone_feasibility.py ..........                 [ 56%]
tests/test_phase24G23_zero_cost_data.py ..........                       [ 64%]
tests/test_phase24G24_baseline_engineering_audit.py ......               [ 69%]
tests/test_phase24G25_causal_correctness_audit.py .........              [ 77%]
tests/test_phase24G26_architecture_product_audit.py .......              [ 83%]
tests/test_phase24G27_reliability_security.py ...............s....       [100%]
```
- **Total Tests Collected:** 119
- **Passed:** 118
- **Skipped:** 1 (`test_symlink_escape_rejection` skipped gracefully on Windows workstations without unprivileged symlink perms)
- **Failed:** 0
- **Execution Time:** ~45 seconds

---

### 2.2 Paper Trading Subsystem Tests
All 10 paper trading test modules, including the modified `persistence.py` and `interactive_engine.py` modules, were verified:
```
tests/test_paper_backtest_parity.py .
tests/test_paper_trading_alignment.py ....
tests/test_paper_trading_engine.py .........
tests/test_paper_trading_models.py ......
tests/test_paper_trading_persistence.py .....
tests/test_paper_trading_replay_runner.py ..........
tests/test_paper_trading_reporting.py ...
tests/test_paper_trading_runner.py ........
tests/test_paper_trading_runner_reporting.py ...
tests/test_paper_trading_session.py ....
```
- **Total Tests Collected:** 53
- **Passed:** 53
- **Failed:** 0
- **Status:** **100% PASS**

---

### 2.3 Market Data & Stock Validation Tests
Modules utilizing `StockDataProvider` (now protected by `validate_safe_path` and `validate_symbol`):
```
tests/test_stock_data_readiness.py .......
tests/test_stock_importer.py .......
tests/test_stock_provider.py .............
tests/test_stock_scanner_engine.py ........
tests/test_stock_validation_readiness_integration.py ....
tests/test_stock_validation_service.py .......
tests/test_stock_validator.py ......
tests/test_groww_provider.py ...................................
tests/test_nifty50.py .....
```
- **Total Tests Collected:** 92
- **Passed:** 92
- **Failed:** 0
- **Status:** **100% PASS**

---

### 2.4 Frontend UX & Component Test Suites
All 12 frontend suites executed via `vite-node` / `node:test`:
- `accessibility_ux.test.js`
- `analysis_workflow.test.js`
- `chart_ux.test.js`
- `keyboard_shortcuts.test.js`
- `paper_trading_phase17.test.js`
- `responsive_layout.test.js`
- `scanner_ux.test.js`
- `settings_ux.test.js`
- `state_views.test.js`
- `stock_universe_view.test.js`
- `strategy_panel.test.js`
- `toast_notifications.test.js`
- **Total Assertions:** 119
- **Status:** **100% PASS**

---

## 3. Invariants Verification Audit Table

| Invariant / Checkpoint | Expected Value | Observed Result | Status |
| :--- | :--- | :--- | :---: |
| **V1 Baseline Frozen Hash** | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` | **CONFIRMED** |
| **Canonical ADANIPORTS SHA-256** | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` | **CONFIRMED** |
| **Active Paper Trading Ledger** | `data/paper_trading/interactive_trades.json` | Untouched, strictly preserved | **CONFIRMED** |
| **Stock Universe Registry** | `data/universe_registry.json` | Untouched, strictly preserved | **CONFIRMED** |
| **2020 Holdout Status** | Quarantined (`EXPLORATORY / CONTAMINATED`) | Zero access during testing | **CONFIRMED** |
| **Preserved Uncommitted File** | `tests/test_watchlist.py` | Untouched, unstaged | **CONFIRMED** |
| **Strict ₹0 Budget** | Total expenses ₹0.00 | Zero expenditure incurred | **CONFIRMED** |

---

## 4. Conclusion

The Phase 24G.27 reliability and security enhancements integrated seamlessly into SignalForge without breaking any existing API contracts, backtesting workflows, or validation pipelines. The application demonstrated 100% functional stability across all executed tests.
