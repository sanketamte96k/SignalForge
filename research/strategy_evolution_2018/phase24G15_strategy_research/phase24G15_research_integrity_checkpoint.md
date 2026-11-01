# SignalForge Phase 24G.15 — Research Integrity Checkpoint Report

**Document Reference:** `SF-CHK-RESEARCH-INTEGRITY-2020-HOLDOUT`  
**Checkpoint Date:** November 1, 2026  
**Auditor / Investigator:** SignalForge Independent Quantitative Governance Team  
**Subject:** 2020 Holdout Exposure Audit, Contamination Status Classification, and Research Boundary Protocol  
**Repository State:** `main` @ `a16262f`  
**Frozen V1 Hash:** `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`  
**Dataset SHA-256:** `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9`  

---

## Executive Summary

Pursuant to SignalForge quantitative governance standards, an immediate research-integrity checkpoint was conducted to audit the chronological boundary isolation of the **2020 Holdout Partition** (`2020-01-01 09:15:00` to `2020-12-31 15:29:00`) following the initial execution of `run_experiments.py` in Phase 24G.15.

### Key Audit Findings

1. **Holdout Access Identified:**  
   The experiment runner script (`research/strategy_evolution_2018/phase24G15_strategy_research/run_experiments.py`) programmatically evaluated the 2020 Holdout partition across all four research hypotheses (Hypotheses A, B, C, and D) under both flat 1 bps baseline and realistic Indian statutory cost models during its initial automated execution sweep.
2. **Methodology Pre-Commitment Gap:**  
   Although the strategy parameters and indicator thresholds were designed using prior economic theory and Phase 24G.14 failure analysis, **no independent, pre-registered candidate freeze document was formally signed and committed to git prior to the 2020 backtest execution**.
3. **Formal Contamination Status Classification:**  
   In accordance with strict quantitative hygiene rules, all 2020 Holdout results produced by this initial run are formally classified as:
   $$\mathbf{EXPLORATORY\ /\ CONTAMINATED}$$
   **Mandatory Research Boundary:** These 2020 metrics must **NOT** be used for parameter selection, iterative hypothesis adjustment, model tuning, or as confirmatory out-of-sample evidence.
4. **Immediate Protocol Enforcement:**  
   All additional 2020 holdout backtests are immediately stopped. Ongoing research is restricted strictly to the **Training (2017–2018)** and **Validation (2019)** partitions.

---

## 1. Inventory of 2020 Holdout Exposure

The following eight experiment configurations were executed on the 2020 Holdout partition (`94,063` 1-minute candles) during the initial sweep:

| Experiment Configuration | Partition | Cost Model | Trades | Gross P&L (Rs) | Net P&L (Rs) | Profit Factor | Output Trade Log Artifact |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Hypothesis A: Trend Pullback** | Holdout (2020) | 1 bps baseline | 973 | +28,91,721.04 | +21,80,651.70 | 1.5244 | `trades_HYPOTHESIS_A_TREND_PULLBACK_holdout_2020_baseline.csv` |
| **Hypothesis A: Trend Pullback** | Holdout (2020) | Realistic statutory | 922 | +5,27,753.09 | +51,329.67 | 1.0621 | `trades_HYPOTHESIS_A_TREND_PULLBACK_holdout_2020_realistic.csv` |
| **Hypothesis B: Squeeze Breakout**| Holdout (2020) | 1 bps baseline | 17 | +16,311.68 | +14,573.53 | 5.2154 | `trades_HYPOTHESIS_B_VOLATILITY_BREAKOUT_holdout_2020_baseline.csv` |
| **Hypothesis B: Squeeze Breakout**| Holdout (2020) | Realistic statutory | 17 | +15,836.06 | +8,657.06 | 2.9730 | `trades_HYPOTHESIS_B_VOLATILITY_BREAKOUT_holdout_2020_realistic.csv` |
| **Hypothesis C: Mean Reversion** | Holdout (2020) | 1 bps baseline | 23 | +19,281.09 | +17,664.48 | 2.6346 | `trades_HYPOTHESIS_C_MEAN_REVERSION_holdout_2020_baseline.csv` |
| **Hypothesis C: Mean Reversion** | Holdout (2020) | Realistic statutory | 23 | +18,853.58 | +10,975.36 | 1.8580 | `trades_HYPOTHESIS_C_MEAN_REVERSION_holdout_2020_realistic.csv` |
| **Hypothesis D: Regime Adaptive**| Holdout (2020) | 1 bps baseline | 607 | +5,88,158.11 | +4,38,214.71 | 1.5050 | `trades_HYPOTHESIS_D_REGIME_ADAPTIVE_holdout_2020_baseline.csv` |
| **Hypothesis D: Regime Adaptive**| Holdout (2020) | Realistic statutory | 575 | +1,83,522.57 | -21,775.59 | 0.9389 | `trades_HYPOTHESIS_D_REGIME_ADAPTIVE_holdout_2020_realistic.csv` |

All eight trade log files and their summary entries in `phase24G15_experiments_summary.csv` and `phase24G15_metrics.json` are preserved intact to maintain an audit trail.

---

## 2. Methodology & Freezing Analysis

### Was Methodology Frozen Prior to Holdout Access?
- **Finding:** **No formal freeze registry was established.**
- **Details:** The runner script evaluated Training (2017–2018) and Validation (2019), outputted an interim summary table, and then proceeded directly into the 2020 Holdout evaluation within the same unattended execution run.
- **Consequence:** Even though the strategy parameters were derived a priori without 2020 optimization, the lack of an external, immutable pre-commitment checkpoint introduces potential confirmation and observation bias.
- **Remedial Action:** The 2020 Holdout results are permanently quarantined as **Exploratory Diagnostics**. They cannot serve as the validation authority for approving any candidate for deployment.

---

## 3. Data Integrity & Invariant Preservation

The audit re-verified all core data and platform invariants:

1. **Frozen V1 Strategy Config Hash:**  
   `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` $\implies$ **`VERIFIED_UNTOUCHED`**.
2. **ADANIPORTS 1m Historical Dataset Hash:**  
   `fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9` $\implies$ **`VERIFIED_UNTOUCHED`**.
3. **Active Paper Trading Ledger:**  
   `data/paper_trading/interactive_trades.json` $\implies$ **`VERIFIED_UNTOUCHED`**.
4. **Universe Registry:**  
   `data/universe_registry.json` $\implies$ **`VERIFIED_UNTOUCHED`**.
5. **Continuous Collector State:**  
   No process starts, stops, or restarts.
6. **Execution Paths:**  
   Zero broker API calls, zero orders submitted.

---

## 4. Immediate Research Guardrails & Next Safe Steps

To restore full methodological integrity, the following rules are active immediately:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        ACTIVE RESEARCH INTEGRITY PROTOCOLS                             │
├──────────────────────────┬─────────────────────────────────────────────────────────────┤
│ 1. 2020 Holdout Lockdown │ Zero new backtest executions on 2020 data. All 2020 metrics │
│                          │ classified as EXPLORATORY / CONTAMINATED.                   │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 2. Research Focus        │ Hypothesis refinement, sensitivity analysis, and stress     │
│                          │ testing restricted strictly to Training (2017–2018) and     │
│                          │ Validation (2019).                                          │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 3. Preservation Policy   │ All existing trade logs and summary metrics preserved to    │
│                          │ maintain complete transparency and reproducibility.         │
├──────────────────────────┼─────────────────────────────────────────────────────────────┤
│ 4. Candidate Freezing    │ If a candidate emerges from Training and Validation, its    │
│    Requirement           │ configuration, indicators, and exact code must be formally  │
│                          │ registered and committed before any future out-of-sample    │
│                          │ testing is authorized.                                      │
└──────────────────────────┴─────────────────────────────────────────────────────────────┘
```

---

**Checkpoint Certification:**  
*SignalForge Independent Quantitative Governance Team*  
*Timestamp: 2026-11-01T20:55:00+05:30*
