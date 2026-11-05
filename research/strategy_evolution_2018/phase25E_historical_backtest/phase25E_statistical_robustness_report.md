# SignalForge Phase 25E — Statistical & Robustness Audit Report

**Audit Reference:** SF-STAT-ROBUST-25E-2026  

## 1. Classification Summary Across 38 Historical Constituents

| Classification Category | Stock Count | Percentage | Description |
| :--- | :---: | :---: | :--- |
| **`POSITIVE_RESEARCH_RESULT`** | **0** | **0.0%** | Sustained positive net P&L across both Training and Validation with N >= 100 |
| **`NEGATIVE_RESEARCH_RESULT`** | **31** | **81.6%** | Systematically negative net P&L across regimes |
| **`STATISTICALLY_INCONCLUSIVE`** | **4** | **10.5%** | Regime-inconsistent results (positive in one period, negative in other) |
| **`INSUFFICIENT_SAMPLE`** | **3** | **7.9%** | Truncated index tenure resulting in total trades N < 100 |
| **`BLOCKED_DATA_QUALITY`** | **0** | **0.0%** | Zero datasets blocked for quality |

---

## 2. Regime Stability & Training vs Validation Decay

A critical test of quantitative validity is whether performance replicates across non-overlapping market regimes:
- **Training Period (2017–2018):** Low volatility, bull trending market.
- **Validation Period (2019):** High volatility, IL&FS NBFC liquidity crisis, polar market breadth.

Zero stocks produced positive net returns in both regimes. For instance, `MARUTI` produced -₹986.23 in Training and +₹1,109.10 in Validation, showing regime inconsistency rather than systematic structural edge.
