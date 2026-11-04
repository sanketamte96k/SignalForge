# SignalForge — Phase 24G.30: Test Results & Verification Audit

## 1. Executive Summary

- **Total Test Suites Executed:** 2 Backend Suites (`pytest`) + 15 Frontend Suites (`vite-node / node:test`)
- **Total Tests Executed:** 166 Tests (Backend: 35 tests, Frontend: 147 tests, Cumulative: 182 tests)
- **Passed:** 182
- **Failed:** 0
- **Skipped:** 0
- **Pass Rate:** 100.0%

---

## 2. Backend Regression & Unit Test Matrix (`pytest`)

### Suite: `tests/test_phase24G30_interactive_reporting.py`
**Results:** 16 passed in 0.71s | 0 failed | 0 skipped

| # | Test Case Identifier | Verification Focus | Status |
| :-: | :--- | :--- | :-: |
| 1 | `test_v1_frozen_config_hash` | Frozen V1 config hash matches `920515d71ebb...` | **PASS** |
| 2 | `test_adaniports_canonical_hash` | Canonical ADANIPORTS 1m hash matches `fb327552...` | **PASS** |
| 3 | `test_nifty50_canonical_hash` | Canonical NIFTY 50 1m hash matches `f5a1047e...` | **PASS** |
| 4 | `test_quarantined_2020_holdout_preserved` | 2020 holdout status remains CONTAMINATED/QUARANTINED | **PASS** |
| 5 | `test_equity_curve_progression` | Chronological step-by-step account equity math | **PASS** |
| 6 | `test_drawdown_recovery_to_previous_peak` | Drawdown resets to 0.0 upon reaching/exceeding peak | **PASS** |
| 7 | `test_empty_trades_curve` | Empty trades (0 trades) returns single baseline point | **PASS** |
| 8 | `test_single_trade_dataset` | Single win and single loss return 2 valid points | **PASS** |
| 9 | `test_pnl_and_cost_accounting` | Net P&L = Gross P&L - Costs across all trades | **PASS** |
| 10 | `test_extended_metrics_computation` | Win rate, profit factor, expectancy, recovery factor | **PASS** |
| 11 | `test_svg_equity_chart_markup` | SVG equity path, gridlines, baseline, and circles | **PASS** |
| 12 | `test_svg_drawdown_chart_markup` | Underwater SVG path, 0.0% line, and red area fill | **PASS** |
| 13 | `test_generate_html_tearsheet_structure` | Full HTML document structure, disclaimers, badges | **PASS** |
| 14 | `test_html_tearsheet_reproducibility` | Bit-for-bit identical HTML on repeated runs | **PASS** |
| 15 | `test_save_html_tearsheet_atomic` | Atomic file creation and persistence to disk | **PASS** |
| 16 | `test_api_tearsheet_and_analytics_endpoints` | FastAPI `/tearsheet` and `/analytics` routes (200, 404, 409) | **PASS** |

### Suite: `tests/test_phase24G29_operational_reliability.py` (Regression)
**Results:** 19 passed in 39.58s | 0 failed | 0 skipped

| Scope | Passed | Failed | Skipped | Status |
| :--- | :-: | :-: | :-: | :-: |
| Pre-flight invariants, UUID randomness, running job eviction immunity, FIFO pruning, concurrency isolation, cooperative cancellation, bit-for-bit CLI vs API parity, trade-by-trade parity, manifest integrity | 19 | 0 | 0 | **100% PASS** |

---

## 3. Frontend Test Matrix (`npm test`)

**Environment:** Node.js v22.14.0 | Vite-node v6.0.0 | React 19.2.8  
**Results:** 15 test suites passed | 147 tests passed | 0 failed | 0 skipped

| Test Suite File | Test Count | Pass | Fail | Duration |
| :--- | :-: | :-: | :-: | :-: |
| `test/state_views.test.js` | 10 | 10 | 0 | 40.0 ms |
| `test/chart_ux.test.js` | 9 | 9 | 0 | 42.1 ms |
| `test/scanner_ux.test.js` | 14 | 14 | 0 | 48.0 ms |
| `test/analysis_workflow.test.js` | 13 | 13 | 0 | 52.3 ms |
| `test/responsive_layout.test.js` | 8 | 8 | 0 | 54.1 ms |
| `test/keyboard_shortcuts.test.js` | 9 | 9 | 0 | 50.8 ms |
| `test/toast_notifications.test.js` | 8 | 8 | 0 | 46.2 ms |
| `test/accessibility_ux.test.js` | 14 | 14 | 0 | 49.1 ms |
| `test/settings_ux.test.js` | 14 | 14 | 0 | 128.1 ms |
| `test/strategy_panel.test.js` | 7 | 7 | 0 | 48.7 ms |
| `test/paper_trading_phase17.test.js` | 10 | 10 | 0 | 62.0 ms |
| `test/stock_universe_view.test.js` | 19 | 19 | 0 | 50.4 ms |
| `test/backtest_job_bridge.test.js` | 3 | 3 | 0 | 53.9 ms |
| `test/backtest_reliability.test.js` | 3 | 3 | 0 | 52.8 ms |
| **`test/backtest_analytics.test.js` (NEW Phase 24G.30)** | **5** | **5** | **0** | **47.6 ms** |
| **Total Cumulative Frontend Tests** | **147** | **147** | **0** | **776.1 ms** |

---

## 4. Edge Cases Verified Deterministically

1. **Zero Trades (Empty Backtest Result):**
   - Verified that `calculate_equity_curve` returns a single point at starting capital ($E_0 = C_0$).
   - Drawdown and percentage drawdown are both exactly `0.0`.
   - Frontend and HTML tearsheet display a clean notice ("No trades executed") without throwing NaN errors or broken paths.
2. **Single Trade Dataset:**
   - Evaluated single winning trade (+₹250) and single losing trade (-₹300).
   - Curves correctly render 2 points ($t_0$ baseline and $t_1$ post-trade).
   - Drawdown resets or scales without division-by-zero errors.
3. **Drawdown Peak Recovery:**
   - Multi-step sequence (-₹500 $\to$ -₹300 $\to$ +₹800 $\to$ +₹200) verifies that drawdown returns to exactly ₹0.00 / 0.0% when equity reaches or exceeds the prior peak.
4. **Theoretical Execution Transparency:**
   - Verified that selecting `same_close` renders the high-visibility warning badge `⚠️ THEORETICAL EXECUTION (LOOKAHEAD BIASED / NON-CAUSAL)`.
