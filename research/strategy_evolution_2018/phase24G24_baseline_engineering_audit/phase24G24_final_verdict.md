# SignalForge — Phase 24G.24: Final Engineering & Research Verdict
## Baseline Research & Engineering Infrastructure Validation

**Author:** SignalForge Quantitative Oversight & Engineering Committee  
**Date:** 2026-11-03  
**Target Candidate:** Hypothesis B — Multi-Timeframe Volatility Compression & Breakout  
**Specification:** SF-SPEC-ALPHA-2026-V1  
**Repository State:** main (`3e47219`)  
**Budget:** Strict ₹0.00  

---

### Final Formal Verdict

```
================================================================================
VERDICT: ENGINEERING_CORRECTIONS_VALIDATED_HYPOTHESIS_B_INVALIDATED_BY_LOOKAHEAD
================================================================================
```

---

### 1. Architectural & Scientific Summary

Under Phase 24G.24, an exhaustive audit and engineering overhaul of SignalForge's baseline research infrastructure was completed under strict ₹0 budget conditions. 

The audit established four decisive outcomes:

#### 1.1 Backtesting Engine Correctness & Bugfix
- Discovered and corrected a type-handling vulnerability in `src/backtest/risk_engine_v2.py`: when signals were passed as a `pd.Series` with a `DatetimeIndex`, integer indexing caused `KeyError: 0`. The engine was patched to handle `pd.Series`, `np.ndarray`, and Python lists seamlessly.
- Validated that the production engine's position sizing ($Q = \min(Q_{\text{risk}}, Q_{\text{leverage}})$), clamped stop distances (0.3%–3.0%), monotonic trailing stop ratchets, EOD liquidation (`15:20:00` IST), and `stop_first` collision rules are operating with institutional precision.

#### 1.2 Data Pipeline Reliability & Invariants
- Verified that all five continuous 1-minute historical equity datasets (`ADANIENT`, `ADANIPORTS`, `ICICIBANK`, `INFY`, `RELIANCE`) match their canonical SHA-256 hashes bit-for-bit.
- Verified that the frozen production V1 configuration hash (`920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`) and canonical ADANIPORTS dataset hash (`fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9`) remain strictly untouched.
- Confirmed that the active paper trading ledger (`data/paper_trading/interactive_trades.json`) and universe registry (`data/universe_registry.json`) are completely untouched.
- Enforced strict quarantine of the 2020 Holdout partition (`EXPLORATORY / CONTAMINATED`, Zero Access).

#### 1.3 Forensic Proof of Multi-Timeframe Lookahead Leak
- Proven mathematically and empirically that the research script `research_hypotheses.py` created in Phase 24G.15 introduced an unintentional 4-minute future peek due to naive `.reindex(..., method="ffill")` on left-labeled resampled bars.
- When signals were evaluated at `09:20:00`, the 5-minute candle inspected was $[09:20:00, 09:25:00)$, which already contained the close of `09:24:00`. At `09:21:00`, trades were entered with 4 minutes of future knowledge.
- In frozen production V1 (`src/strategy/backtest_strategy.py`), `_TimeframeCursor` correctly enforced `cutoff = timestamp - duration`, proving that the frozen V1 baseline was causally sound and unaffected by this flaw.

#### 1.4 Empirical Invalidation of Hypothesis B
- When causally shifted across 15 asset-years (1,379,777 1-minute bars across 5 equities over 2017, 2018, and 2019):
  - Original reported net P&L: **+₹94,654.37** (Average WR: **80.89%**, 15/15 profitable asset-years).
  - Causal net P&L: **-₹141,917.72** (Average WR: **43.38%**, **0/15 profitable asset-years**).
  - Net P&L destruction: **-₹236,572.09**.
- Not a single asset-year was profitable under causal execution. The apparent alpha of Hypothesis B was entirely an illusion created by lookahead bias.

---

### 2. Strategy Candidate Classification Status

| Component | Status Prior to Phase 24G.24 | Status After Phase 24G.24 |
| :--- | :--- | :--- |
| **Hypothesis B (Breakout)** | `PROMISING_RESEARCH_CANDIDATE` | `INVALIDATED_AND_DISQUALIFIED` |
| **RiskEngineV2** | `ALPHA_PRE_RELEASE` | `PRODUCTION_VERIFIED` |
| **Causal HTF Synchronizer** | `IMPLICIT_CURSOR` | `STANDARDIZED_CAUSAL_SHIFT` |
| **Production V1 Strategy** | `FROZEN_BASE_STRATEGY` | `FROZEN_BASE_STRATEGY (UNTOUCHED)` |

---

### 3. Directives for Subsequent Research

1. **Formal Disqualification:** Hypothesis B is formally disqualified from promotion to paper trading, live trading, or candidate alpha specification.
2. **Causal Shift Mandate:** Any future multi-timeframe research script must shift left-labeled resampled features by 1 period before forward-filling.
3. **Preservation of Core Assets:** All active ledgers, universe registries, and frozen configuration hashes remain strictly protected.
4. **Zero-Cost Budget Compliance:** Continue all quantitative engineering under the strict ₹0 budget restriction without paid data acquisition.
