# SignalForge Phase 25C — Brokerage-Inclusive Shared-Capital Portfolio Report

**Model:** Chronological Event-Driven Shared Portfolio  
**Starting Capital:** ₹1,000,000 (10.00 Lakhs)  
**Allocation per Trade:** ₹100,000 (10% allocation)  
**Max Concurrent Positions:** 10 Simultaneous Open Trades  
**Evaluation Scope:** 2017-01-02 to 2019-12-31 (19,223 raw signals)  

---

## 1. Multi-Model Portfolio Performance Comparison

| Portfolio Metric | Phase 25B Baseline (1 bps Flat) | Model A (Statutory Only) | Model B (Discount Broker Realistic) | Model C (Conservative Stress) |
| :--- | :---: | :---: | :---: | :---: |
| **Initial Capital** | ₹1,000,000.00 | ₹1,000,000.00 | ₹1,000,000.00 | ₹1,000,000.00 |
| **Final Equity** | ₹996,075.60 | ₹991,548.04 | **₹983,696.86** | ₹979,866.19 |
| **Net Portfolio P&L** | -₹3,924.40 | ₹-8,451.96 | **₹-16,303.14** | **₹-20,133.81** |
| **Portfolio Return %** | -0.39% | -0.85% | **-1.63%** | **-2.01%** |
| **Max Drawdown (₹)** | ₹5,542.78 | ₹8,857.25 | **₹16,508.06** | ₹20,253.06 |
| **Max Drawdown (%)** | 0.55% | 0.89% | **1.65%** | 2.03% |
| **Total Accepted Trades** | 7,087 | 6782 | **6746** | 6744 |
| **Total Rejected Trades** | 12,136 (63.1%) | 12441 | **12477 (64.9%)** | 12479 |
| **Gross P&L (Pre-Cost)** | +₹1,327.90 | +₹-3,119.61 | **+₹-3,320.85** | +₹-3,297.30 |
| **Total Transaction Costs** | ₹5,252.30 | ₹5,332.35 | **₹12,982.29** | **₹16,836.51** |

---

## 2. Granular Cost Component Breakdown (Model B Primary Schedule)

On the **7,087 realized portfolio trades**, total friction was distributed across specific statutory and commercial fees:

| Cost Component | Total Amount (₹) | % of Total Costs | Effective Basis Points on Turnover |
| :--- | :---: | :---: | :---: |
| **Brokerage** | **₹5,698.16** | 43.9% | ~2.0 bps |
| **Securities Transaction Tax (STT)** | **₹2,373.80** | 18.3% | ~1.25 bps |
| **NSE Exchange Transaction Charges** | **₹618.44** | 4.8% | ~0.33 bps |
| **SEBI Turnover Charges** | **₹13.71** | 0.1% | ~0.01 bps |
| **State Stamp Duty** | **₹285.09** | 2.2% | ~0.15 bps |
| **Goods & Services Tax (GST 18%)** | **₹1,139.76** | 8.8% | ~0.42 bps |
| **Slippage (1.0 bps)** | **₹1,899.52** | 14.6% | ~1.00 bps |
| **Bid-Ask Spread (0.5 bps)** | **₹949.47** | 7.3% | ~0.50 bps |
| **TOTAL TRANSACTION FRICTION** | **₹12,982.29** | **100.0%** | **~5.66 bps** |

---

## 3. Trade Quality & Cost Inversion

- **Gross Winning Trades:** 3181 (47.15% Gross Win Rate)
- **Net Winning Trades:** 2853 (42.29% Net Win Rate)
- **Cost-Flipped Trades:** **328 trades** produced a positive gross gain that was completely eliminated by transaction friction, converting directly into net losses.
- **Capital Utilization:** Average capital deployed was **72.8%** with peak utilization reaching **100.0%** (10 concurrent positions).
