# SignalForge — Testing Guide & Verification Workflows

## 1. Testing Philosophy

SignalForge enforces a rigorous multi-tier testing discipline:
1. **Mathematical Invariant Tests:** Cryptographic hash integrity of frozen configurations (`920515d7...`) and canonical datasets (`fb327552...`).
2. **Causal Correctness Tests:** Enforces strictly causal lookback periods; verifies zero future-bar lookahead leakage.
3. **Operational Concurrency & Eviction Tests:** Validates thread safety, cooperative cancellation checkpoints, and FIFO eviction.
4. **Interactive Reporting Tests:** Deterministic equity calculation, drawdown peak recovery, edge case handling (0 trades, single trade), and bit-for-bit HTML tearsheet reproducibility.
5. **Frontend Regression Tests:** Fast component testing using `vite-node` and Node.js native test runner (`node:test`).

---

## 2. Running Backend Tests (`pytest`)

Activate your virtual environment and execute pytest:

```bash
# Run complete test suite
pytest

# Run focused Phase 24G.30 interactive reporting tests
pytest tests/test_phase24G30_interactive_reporting.py -v

# Run Phase 24G.29 operational reliability & concurrency tests
pytest tests/test_phase24G29_operational_reliability.py -v

# Run with concise summary
pytest --tb=short
```

---

## 3. Running Frontend Tests (`npm test`)

Navigate to the `frontend` directory and run the test suites:

```bash
cd frontend
npm test
```

This runs all 15 test suites:
- `test/state_views.test.js`
- `test/chart_ux.test.js`
- `test/scanner_ux.test.js`
- `test/analysis_workflow.test.js`
- `test/responsive_layout.test.js`
- `test/keyboard_shortcuts.test.js`
- `test/toast_notifications.test.js`
- `test/accessibility_ux.test.js`
- `test/settings_ux.test.js`
- `test/strategy_panel.test.js`
- `test/paper_trading_phase17.test.js`
- `test/stock_universe_view.test.js`
- `test/backtest_job_bridge.test.js`
- `test/backtest_reliability.test.js`
- `test/backtest_analytics.test.js`

Expected output: `15 suites passed, 147 tests passed, 0 failed`.

