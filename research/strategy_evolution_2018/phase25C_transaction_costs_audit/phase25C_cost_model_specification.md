# SignalForge Phase 25C — Indian Equity Intraday Transaction Cost Specification

**Document Reference:** SF-SPEC-COST-2026-V1  
**Target Market:** National Stock Exchange of India (NSE) — Cash Equity Segment  
**Trading Style:** Pure Intraday (No Overnight Carry, 09:15 to 15:30 IST)  

---

## 1. Statutory & Regulatory Charges Schedule

Under Indian taxation and securities regulation, equity cash intraday trading is governed by specific tax treatments that differ substantially from delivery trades:

| Charge Component | Governing Body / Rule | Applicable Intraday Rate | Leg Applicability | Taxable for GST? |
| :--- | :--- | :--- | :--- | :---: |
| **Securities Transaction Tax (STT)** | Ministry of Finance / CBDT | **0.025%** ($0.00025$) | **SELL Leg Only** | **No** (Direct Tax) |
| **Exchange Transaction Charges (ETC)** | National Stock Exchange (NSE) | **0.00325%** ($0.0000325$) | **Total Turnover** (Both Legs) | **Yes** (18% GST) |
| **SEBI Turnover Charges (STC)** | SEBI Regulatory Fee | **0.0001%** ($0.000001$ = ₹10/crore) | **Total Turnover** (Both Legs) | **Yes** (18% GST) |
| **State Stamp Duty (SD)** | Indian Stamp Act (Uniform Schedule) | **0.003%** ($0.00003$ = ₹300/crore) | **BUY Leg Only** | **No** (Statutory Duty) |
| **Goods & Services Tax (GST)** | Central & State GST (CGST + SGST) | **18.0%** ($0.18$) | On $(Brokerage + ETC + STC)$ | N/A |

---

## 2. Configurable Cost Model Profiles

### Model A: Broker-Agnostic Statutory Charges Model
Isolates pure regulatory and tax drag from broker fee structures.
- **Brokerage:** ₹0.00
- **STT:** 0.025% on Sell leg
- **NSE Charges:** 0.00325% on total turnover
- **SEBI Charges:** 0.0001% on total turnover
- **Stamp Duty:** 0.003% on Buy leg
- **GST:** 18% on $(ETC + STC)$
- **Slippage:** 1.0 bps on total turnover
- **Spread:** 0.0 bps

### Model B: Configurable Discount-Broker Model (Baseline Realistic Schedule)
Reflects industry-standard retail discount broker pricing (e.g., Zerodha, AngelOne, Groww).
- **Brokerage:** `min(₹20.00, 0.03% * turnover)` per executed leg (Entry & Exit)
- **STT:** 0.025% on Sell leg
- **NSE Charges:** 0.00325% on total turnover
- **SEBI Charges:** 0.0001% on total turnover
- **Stamp Duty:** 0.003% on Buy leg
- **GST:** 18% on $(Brokerage + ETC + STC)$
- **Slippage:** 1.0 bps on total turnover
- **Spread:** 0.5 bps on total turnover

### Model C: Conservative Slippage & Spread Stress Model
Stresses liquidity friction, wider spreads, and regulatory revisions.
- **Brokerage:** `min(₹20.00, 0.03% * turnover)` per executed leg
- **STT:** 0.025% on Sell leg
- **NSE Charges:** 0.00345% on total turnover
- **SEBI Charges:** 0.00015% on total turnover
- **Stamp Duty:** 0.003% on Buy leg
- **GST:** 18% on $(Brokerage + ETC + STC)$
- **Slippage:** 2.5 bps on total turnover
- **Spread:** 1.0 bps on total turnover
