# SignalForge — Protected Data Quarantine Incident Register

**Document ID:** SF-INCIDENT-2026-001  
**Classification:** DATA GOVERNANCE & RESEARCH INTEGRITY  
**Incident Date:** 2026-11-10  
**Phase Recorded:** Phase 27C.3.3.6  
**Status:** FORMALLY RECORDED & PERMANENTLY PRESERVED  

---

## 1. Incident Description & Scope

During the execution of Phase 27C.3.3.4 verification activities on 2026-11-10, physical binary read operations were executed against the monolithic historical dataset `data/historical/stocks/ADANIPORTS_1m.csv`.

Because this monolithic file contains continuous 1-minute historical intraday data spanning into calendar year 2020, physical binary reading of the file read the byte stream representing the quarantined 2020 partition into the process memory buffer.

This action constituted a direct breach of SignalForge's strict data governance policy, which explicitly prohibits reading, scanning, parsing, or hashing the monolithic historical dataset due to the presence of quarantined 2020 rows.

---

## 2. Confirmed Operations Executed

Two distinct `read_bytes()` operations were confirmed through execution logs and trajectory traces:

1. **Preflight Unit Test Execution:**
   - **Invocation:** Pytest regression test run.
   - **Source:** `tests/test_phase24G28_backtest_job_bridge.py:test_adaniports_canonical_hash` (line 50).
   - **Code Executed:** `h = hashlib.sha256(adani_path.read_bytes()).hexdigest()`
   - **Result:** Opened `data/historical/stocks/ADANIPORTS_1m.csv` in binary mode and read the full file byte stream.

2. **Standalone Verification Command:**
   - **Invocation:** Direct Python one-liner command during invariant verification reporting.
   - **Command:** `.\venv\Scripts\python.exe -c "... get_raw_sha256('data/historical/stocks/ADANIPORTS_1m.csv')"`
   - **Code Executed:** `Path('data/historical/stocks/ADANIPORTS_1m.csv').read_bytes()`
   - **Result:** Opened `data/historical/stocks/ADANIPORTS_1m.csv` in binary mode and computed the SHA-256 digest (`fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9`).

---

## 3. Impact Assessment & Boundary Analysis

1. **Full Dataset Read:**
   The entire binary byte stream of `data/historical/stocks/ADANIPORTS_1m.csv` was physically read into memory for hashing.

2. **Policy Violation:**
   This violated the SignalForge zero-read quarantine mandate established in Phase 24G.25 (`2020 Holdout Partition | CONTAMINATED | QUARANTINED | Zero access maintained`).

3. **No Strategy Exploitation / No Data Parsing:**
   There is zero evidence that the dataset was parsed into a Pandas DataFrame, converted into structured OHLCV bars, scanned for market features, or fed into any alpha, signal, or strategy backtest. The byte stream was consumed strictly by `hashlib.sha256()` for digest computation.

4. **Irreversibility of Historical Access:**
   The incident cannot be undone, and SignalForge does not claim that the original pristine zero-access condition has been restored across the project's historical timeline.

---

## 4. Remediation & Future Enforcement Directives

1. **Test Remediation (Phase 27C.3.3.6):**
   `tests/test_phase24G28_backtest_job_bridge.py:test_adaniports_canonical_hash` was refactored to validate against the pre-recorded canonical hash in `research/strategy_evolution_2018/phase25A_coverage_audit/phase25A_coverage_manifest.json` without opening or reading `data/historical/stocks/ADANIPORTS_1m.csv`.

2. **Offending Tests Quarantined from Execution:**
   Other legacy test suites containing full-file hashing of monolithic datasets (including `tests/test_phase27b_cost_unification.py:test_canonical_file_hashes_intact` and legacy audit tests) are prohibited from execution until similarly remediated to use manifest-based verification.

3. **Inaccessibility Enforcement:**
   Monolithic historical dataset files in `data/historical/stocks/*.csv` must remain strictly inaccessible to ordinary research, backtesting, and automated test suites. Future invariant validation must rely exclusively on signed or pre-registered metadata manifests.

