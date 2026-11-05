# SignalForge Phase 25F — Shared-Capital Portfolio Forensic Audit

**Audit Reference:** SF-AUDIT-25F-PORT-2026  
**Audited Engine:** Phase 25E Chronological Portfolio Simulator (`simulate_shared_portfolio`)  
**Audit Status:** **`REPRODUCED_AND_VERIFIED`**  

---

## 1. Portfolio Architectural Constraints & Invariants

The Phase 25E shared-capital portfolio simulation was audited against strict portfolio engineering specifications:
- **Starting Capital:** ₹10,00,000.00 (₹10 Lakh).
- **Slot Allocation:** Fixed ₹1,00,000.00 (₹1 Lakh) per position.
- **Maximum Concurrent Slots:** 10 positions (100% maximum deployment).
- **Position Sizing:** `shares = max(1, int(100,000 / entry_price))`.
- **Chronological Ordering:** Sorted strictly by `entry_time`.
- **Cash Lifecycle:** Complete reservation of ₹100,000 upon entry; release of capital + Net P&L upon exit.
- **Rejection Policy:** Instant rejection when all 10 slots are occupied or available cash is < ₹100,000.

---

## 2. Independent Reproduction Audit Results

| Portfolio Metric | Phase 25E Reported | Phase 25F Reproduced | Discrepancy (Absolute) | Discrepancy (%) | Audit Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Initial Capital** | ₹1,000,000.00 | ₹1,000,000.00 | ₹0.00 | 0.00% | **EXACT_MATCH** |
| **Final Equity (Model B)** | **₹285,174.66** | **₹285,174.66** | **₹0.00** | **0.00%** | **EXACT_MATCH** |
| **Net Portfolio P&L** | **₹-714,825.34** | **₹-714,825.34** | **₹0.00** | **0.00%** | **EXACT_MATCH** |
| **Portfolio Return %** | **-71.48%** | **-71.48%** | 0.00% | 0.00% | **EXACT_MATCH** |
| **Maximum Drawdown (₹)** | **₹902,997.58** | **₹902,997.58** | **₹0.00** | **0.00%** | **EXACT_MATCH** |
| **Maximum Drawdown %** | **90.30%** | **90.30%** | 0.00% | 0.00% | **EXACT_MATCH** |
| **Candidate Trade Signals** | 18,686 | 18,686 | 0 | 0.00% | **EXACT_MATCH** |
| **Accepted Trades (Executed)** | **4,074** | **4,074** | 0 | 0.00% | **EXACT_MATCH** |
| **Rejected Signals (Capacity)** | **14,612** | **14,612** | 0 | 0.00% | **EXACT_MATCH** |
| **Signal Rejection Rate** | **78.20%** | **78.20%** | 0.00% | 0.00% | **EXACT_MATCH** |
| **Total Costs Paid** | **₹459,066.11** | **₹459,066.11** | **₹0.00** | **0.00%** | **EXACT_MATCH** |
| **Gross Win Rate %** | 46.78% | 46.78% | 0.00% | 0.00% | **EXACT_MATCH** |
| **Net Win Rate %** | 42.54% | 42.54% | 0.00% | 0.00% | **EXACT_MATCH** |
| **Cost-Flipped Trades** | 173 | 173 | 0 | 0.00% | **EXACT_MATCH** |
| **Average Capital Utilization** | 45.0% | 45.0% | 0.0% | 0.00% | **EXACT_MATCH** |

---

## 3. Mathematical Accounting Verification

All fundamental accounting identities hold true down to ₹0.000000:
1. **Equity Balance Identity:**
   $$\text{Final Equity} = \text{Initial Capital} + \text{Net Portfolio P&L}$$
   $$₹285,174.66 = ₹1,000,000.00 + (-₹714,825.34)$$
2. **P&L Cost Decomposition Identity:**
   $$\text{Net Portfolio P&L} = \text{Gross P&L} - \text{Total Transaction Costs}$$
   $$-₹714,825.34 = -₹255,759.23 - ₹459,066.11$$
3. **Signal Conservation Identity:**
   $$\text{Total Candidate Signals} = \text{Accepted Trades} + \text{Rejected Signals}$$
   $$18,686 = 4,074 + 14,612$$

---

## 4. Key Forensic Observations

1. **Capacity Congestion & High Rejection (78.2%):**
   Due to market-wide intraday momentum clusters (e.g. morning breakout signals at 09:45–10:30 AM), tens of stocks triggered signals simultaneously. The 10-slot limit caused 78.2% of signals to be rejected.
2. **Structural Drag of Negative Expectancy:**
   Each executed trade lost an average of **₹175.46 net** (-₹62.78 gross loss + ₹112.68 friction). Executing 4,074 trades with negative net expectancy led inevitably to capital decay, driving portfolio drawdown to **90.30%**.
