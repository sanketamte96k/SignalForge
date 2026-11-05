# SignalForge Phase 25C — Historical NIFTY 50 Survivorship Bias Audit

**Scope:** Analysis of Index Composition Mismatch (2017–2019 vs Modern Universe)  
**Historical Period:** 2017-01-02 to 2019-12-31  

---

## 1. Executive Survivorship Bias Finding

The constituent list utilized in Phase 25A and Phase 25B was derived from the recent (October 2026 / current) NIFTY 50 index composition (`ind_nifty50list.csv`).
A forensic historical investigation into official NSE Index reconstitutions reveals significant **look-ahead selection bias / survivorship bias**:

> [!WARNING]
> **Critical Audit Finding:**  
> **5 of the 34 evaluated stocks (14.7%) were NEVER constituents of the NIFTY 50 during the 2017–2019 testing window!**  
> Furthermore, **7 stocks (20.6%) were only added mid-way through the testing period.**  
> Conversely, severely decaying companies that suffered catastrophic declines during 2017–2019 (such as `YESBANK`, `IBULHSGFIN`, and `ZEEL`) were excluded from the backtest universe because they were expelled from the modern index.

---

## 2. Forensic Breakdown of Tested Stocks vs Historical Index Membership

| Symbol | Company Name | Historical Membership Status (2017–2019) | Actual Reconstitution Event | Survivorship / Look-Ahead Bias Severity |
| :--- | :--- | :--- | :--- | :--- |
| **ADANIENT** | Adani Enterprises Ltd. | **NON-CONSTITUENT** | Added to NIFTY 50 in **September 2022** (replaced SHREECEM) | **HIGH** (~4 years before inclusion) |
| **APOLLOHOSP** | Apollo Hospitals Enterprise Ltd. | **NON-CONSTITUENT** | Added to NIFTY 50 in **March 2022** (replaced IOC) | **HIGH** (~3 years before inclusion) |
| **BEL** | Bharat Electronics Ltd. | **NON-CONSTITUENT** | Added to NIFTY 50 in **September 2024** | **HIGH** (~5 years before inclusion) |
| **SBILIFE** | SBI Life Insurance Co. Ltd. | **NON-CONSTITUENT** | Listed Oct 2017; Added in **September 2020** (replaced ZEEL) | **HIGH** (~1.5 years before inclusion) |
| **SHRIRAMFIN** | Shriram Finance Ltd. | **NON-CONSTITUENT** | Added to NIFTY 50 in **March 2024** (replaced UPL) | **HIGH** (~5 years before inclusion) |
| **BAJAJFINSV** | Bajaj Finserv Ltd. | **PARTIAL (58% of period)** | Added to NIFTY 50 in **April 2018** | **MODERATE** (Non-member for first 15 months) |
| **GRASIM** | Grasim Industries Ltd. | **PARTIAL (58% of period)** | Added to NIFTY 50 in **April 2018** | **MODERATE** (Non-member for first 15 months) |
| **JSWSTEEL** | JSW Steel Ltd. | **PARTIAL (42% of period)** | Added to NIFTY 50 in **September 2018** | **MODERATE** (Non-member for first 21 months) |
| **NESTLEIND** | Nestle India Ltd. | **PARTIAL (8% of period)** | Added to NIFTY 50 in **September 2019** | **HIGH** (Non-member for 33 of 36 months) |
| **BAJFINANCE** | Bajaj Finance Ltd. | **PARTIAL (75% of period)** | Added to NIFTY 50 in **September 2017** | **LOW** (Non-member for first 9 months) |
| **HCLTECH** | HCL Technologies Ltd. | **PARTIAL (75% of period)** | Added to NIFTY 50 in **September 2017** | **LOW** (Non-member for first 9 months) |
| **EICHERMOT** | Eicher Motors Ltd. | **PARTIAL (92% of period)** | Added to NIFTY 50 in **March 2017** | **NEGLIGIBLE** (Non-member for first 3 months) |

---

## 3. Omitted Historical Constituents (Expelled / Distressed Stocks)

The following companies were authentic, highly active constituents of the NIFTY 50 during 2017–2019 but were **completely omitted** from the research sample because they were dropped from modern lists:

1. **YESBANK:** Continuous constituent throughout 2017–2019. Suffered acute liquidity crises, governance investigations, and massive price declines in 2018–2019 before expulsion in March 2020.
2. **IBULHSGFIN (Indiabulls Housing Finance):** Included in March 2017, expelled in September 2019 following the NBFC liquidity crunch. Plunged >80%.
3. **ZEEL (Zee Entertainment):** Continuous constituent throughout 2017–2019; expelled in September 2020 following promoter pledge crises.
4. **INFRATEL (Bharti Infratel):** Continuous constituent throughout 2017–2019; expelled in 2020.
5. **VEDL (Vedanta Ltd.):** Continuous constituent throughout 2017–2019; expelled in July 2020.

---

## 4. Impact on Phase 25B "Positive" Stocks

In Phase 25B, exactly 3 stocks were classified as `POSITIVE_RESEARCH_RESULT`:
1. `MARUTI` (Constituent throughout 2017–2019) — **Genuine Historical Member**
2. `BAJAJFINSV` (Added April 2018) — **Subject to Partial Selection Bias**
3. `EICHERMOT` (Added March 2017) — **Genuine Historical Member for 92% of period**

This confirms that while `MARUTI` and `EICHERMOT` were genuine constituents, modern universe filtering inadvertently biased universe liquidity and momentum upward.
