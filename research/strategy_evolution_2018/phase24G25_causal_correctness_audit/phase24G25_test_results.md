# SignalForge — Phase 24G.25: Comprehensive Audit Test Results
## Verification Metrics Across Deterministic Fixtures, Empirical P&L, Micro-Benchmarks & Code Scans

**Auditor:** SignalForge Quantitative Oversight & Integrity Working Group  
**Status:** COMPLETED & VERIFIED  
**Specification:** SF-SPEC-ALPHA-2026-V1  
**Target Candidate:** Hypothesis B — Multi-Timeframe Volatility Compression & Breakout  

---

### 1. Test Suite Summary Matrix

The independent audit conducted six comprehensive verification experiments:

| Experiment / Verification Track | Target System | Scope | Result | Verdict |
| :--- | :--- | :--- | :---: | :---: |
| **1. Deterministic Timeline Fixture** | Resampling & Forward-Fill | 15-minute isolated fixture | 4-minute future peek reproduced | **CONFIRMED_LEAK** |
| **2. Multi-Asset P&L Reconciliation** | 15 Asset-Years (2017–2019) | 1,379,777 1m bars across 5 stocks | Exactly 0 discrepancies vs 24G.24 | **EXACT_MATCH (15/15)** |
| **3. Causal P&L Destruction** | Hypothesis B (Shifted) | 15 Asset-Years (5 stocks $\times$ 3 yrs) | Net P&L collapsed: $+₹94.6\text{k} \rightarrow -₹141.9\text{k}$ | **0 / 15 Profitable** |
| **4. NumPy Optimization Benchmark** | Signal Engine Loop | 91,935 bars (ADANIPORTS 2018) | 100% bit-for-bit signal & trade match; 132x speedup | **PARITY_PROVEN** |
| **5. Cross-Project Lookahead Scan** | Whole Repo (`src/`, `research/`) | 182 pattern matches across 62 files | 0 negative shifts; all `merge_asof` causal | **SCAN_CLEAN (ISOLATED)** |
| **6. Production V1 Engine Audit** | `_TimeframeCursor` | Frozen V1 Strategy Engine | Cutoff $T - D$ proven causal; overnight gap protected | **100% CAUSAL** |

---

### 2. Empirical P&L Reconciliation Summary

From [`phase24G25_pnl_reconciliation.csv`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G25_causal_correctness_audit/phase24G25_pnl_reconciliation.csv):

| Aggregate Metric | Phase 24G.24 Reported | Phase 24G.25 Independent Reproduction | Absolute Discrepancy | Relative Discrepancy |
| :--- | :---: | :---: | :---: | :---: |
| **Total Asset-Years Evaluated** | 15 | 15 | 0 | 0.00% |
| **Total 1-Minute Bars** | 1,379,777 | 1,379,777 | 0 | 0.00% |
| **Original Trade Count** | 360 | 360 | 0 | 0.00% |
| **Original Average Win Rate** | 80.89% | 80.89% | 0.00% | 0.00% |
| **Original Gross P&L** | +₹258,703.85 | +₹258,703.85 | ₹0.00 | 0.00% |
| **Original Total Costs** | ₹164,049.48 | ₹164,049.48 | ₹0.00 | 0.00% |
| **Original Net P&L** | **+₹94,654.37** | **+₹94,654.37** | **₹0.00** | **0.00%** |
| **Causal Trade Count** | 356 | 356 | 0 | 0.00% |
| **Causal Average Win Rate** | 43.38% | 43.38% | 0.00% | 0.00% |
| **Causal Gross P&L** | +₹7,529.67 | +₹7,529.67 | ₹0.00 | 0.00% |
| **Causal Total Costs** | ₹149,447.38 | ₹149,447.38 | ₹0.00 | 0.00% |
| **Causal Net P&L** | **-₹141,917.72** | **-₹141,917.72** | **₹0.00** | **0.00%** |
| **Net Leak Impact ($\Delta$)** | **-₹236,572.09** | **-₹236,572.09** | **₹0.00** | **0.00%** |
| **Causal Profitable Asset-Years** | **0 / 15** | **0 / 15** | **0** | **0.00%** |

---

### 3. Benchmarking Distribution Statistics

From [`numpy_benchmark_phase24G25.json`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G25_causal_correctness_audit/numpy_benchmark_phase24G25.json):
- **Parity:** 91,935 bars, 19 trades, ₹5,753.4409 Net P&L (100% exact match).
- **Original Execution Time (3 Runs):**
  - Median: **37.7463s**
  - Mean: **36.7057s**
  - Range: [33.2211s, 39.1499s]
- **Optimized NumPy Execution Time (10 Runs):**
  - Median: **0.286199s**
  - Mean: **0.278510s**
  - Std Dev: **0.023987s**
  - Minimum: **0.242478s**
  - Maximum: **0.311900s**
- **Speedup Factor:**
  - End-to-end function: **131.9x** (Median)
  - Raw loop iteration: **~1,750x** (Median)

---

### 4. Safety Invariants Status

- **Frozen V1 Configuration Hash:** `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` (Intact).
- **Canonical ADANIPORTS SHA-256:** `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` (Intact).
- **Active Paper Ledger (`data/paper_trading/interactive_trades.json`):** Intact (8 records).
- **Universe Registry (`data/universe_registry.json`):** Intact (100 instruments).
- **2020 Holdout Partition:** Quarantined (`EXPLORATORY / CONTAMINATED`, Zero Access).
- **Unrelated Working Tree Files:** Preserved uncommitted (`tests/test_watchlist.py`).
