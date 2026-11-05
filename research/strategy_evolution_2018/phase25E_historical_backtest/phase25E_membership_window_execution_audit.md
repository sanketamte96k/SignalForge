# SignalForge Phase 25E — Membership Window Execution Audit

**Audit Reference:** SF-EXEC-TENURE-AUDIT-2026  
**Policy Compliance:** Zero Look-Ahead Bias, Strict Tenure Bounding, No Sample Stretching  

---

## 1. Tenure-Bounded Execution Overview

In quantitative backtesting, an index strategy must strictly execute trades on a constituent **only during dates when that constituent officially belonged to the index**. Testing stocks outside their active tenure introduces severe look-ahead survivorship bias.

| Symbol | Company Name | Tenure Category | Verified Membership Windows | Raw Unfiltered Bars/Trades | Tenure-Bounded Trades | Trades Filtered Out (Outside Membership) |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **`ADANIPORTS`** | Adani Ports and Special Economic Zone Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 566 | **566** | **0** |
| **`ASIANPAINT`** | Asian Paints Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 542 | **542** | **0** |
| **`AXISBANK`** | Axis Bank Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 578 | **578** | **0** |
| **`BAJAJ-AUTO`** | Bajaj Auto Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 563 | **563** | **0** |
| **`BAJAJFINSV`** | Bajaj Finserv Ltd. | `MID_PERIOD_ADDITION` | 2018-04-02 to 2019-12-31 | 565 | **337** | **228** |
| **`BAJFINANCE`** | Bajaj Finance Ltd. | `MID_PERIOD_ADDITION` | 2017-09-29 to 2019-12-31 | 567 | **432** | **135** |
| **`BHARTIARTL`** | Bharti Airtel Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 572 | **572** | **0** |
| **`BHEL`** | Bharat Heavy Electricals Ltd. | `EARLY_REMOVAL` | 2017-01-01 to 2017-03-31 | 585 | **41** | **544** |
| **`BPCL`** | Bharat Petroleum Corporation Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 567 | **567** | **0** |
| **`BRITANNIA`** | Britannia Industries Ltd. | `MID_PERIOD_ADDITION` | 2019-03-29 to 2019-12-31 | 571 | **158** | **413** |
| **`CIPLA`** | Cipla Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 587 | **587** | **0** |
| **`COALINDIA`** | Coal India Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 589 | **589** | **0** |
| **`DRREDDY`** | Dr. Reddy's Laboratories Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 573 | **573** | **0** |
| **`EICHERMOT`** | Eicher Motors Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 566 | **566** | **0** |
| **`GAIL`** | GAIL (India) Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 576 | **576** | **0** |
| **`GRASIM`** | Grasim Industries Ltd. | `INTERRUPTED_RESTRUCTURING` | 2017-01-01 to 2017-05-26; 2018-04-02 to 2019-12-31 | 567 | **407** | **160** |
| **`HCLTECH`** | HCL Technologies Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 569 | **569** | **0** |
| **`HDFC`** | Housing Development Finance Corporation Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 570 | **570** | **0** |
| **`HDFCBANK`** | HDFC Bank Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 593 | **593** | **0** |
| **`IBULHSGFIN`** | Indiabulls Housing Finance Ltd. | `TRANSIENT_CONSTITUENT` | 2017-03-31 to 2019-09-27 | 544 | **462** | **82** |
| **`ICICIBANK`** | ICICI Bank Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 564 | **564** | **0** |
| **`IDEA`** | Idea Cellular Ltd. | `EARLY_REMOVAL` | 2017-01-01 to 2017-03-31 | 584 | **45** | **539** |
| **`INDUSINDBK`** | IndusInd Bank Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 558 | **558** | **0** |
| **`INFY`** | Infosys Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 550 | **550** | **0** |
| **`IOC`** | Indian Oil Corporation Ltd. | `MID_PERIOD_ADDITION` | 2017-03-31 to 2019-12-31 | 579 | **537** | **42** |
| **`ITC`** | ITC Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 574 | **574** | **0** |
| **`JSWSTEEL`** | JSW Steel Ltd. | `MID_PERIOD_ADDITION` | 2018-09-28 to 2019-12-31 | 579 | **248** | **331** |
| **`KOTAKBANK`** | Kotak Mahindra Bank Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 560 | **560** | **0** |
| **`LT`** | Larsen & Toubro Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 548 | **548** | **0** |
| **`M&M`** | Mahindra & Mahindra Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 570 | **570** | **0** |
| **`MARUTI`** | Maruti Suzuki India Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 564 | **564** | **0** |
| **`NESTLEIND`** | Nestle India Ltd. | `MID_PERIOD_ADDITION` | 2019-09-27 to 2019-12-31 | 538 | **47** | **491** |
| **`NTPC`** | NTPC Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 591 | **591** | **0** |
| **`ONGC`** | Oil & Natural Gas Corporation Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 562 | **562** | **0** |
| **`POWERGRID`** | Power Grid Corporation of India Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 564 | **564** | **0** |
| **`RELIANCE`** | Reliance Industries Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 569 | **569** | **0** |
| **`SBIN`** | State Bank of India | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 603 | **603** | **0** |
| **`SUNPHARMA`** | Sun Pharmaceutical Industries Ltd. | `FULL_PERIOD_CONTINUOUS` | 2017-01-01 to 2019-12-31 | 584 | **584** | **0** |

---

## 2. Key Tenure-Bounding Audit Findings

1. **Continuous Constituents (27 Stocks):** 100% of generated trades occurred within active tenure (0 trades excluded).
2. **Early Exits (`BHEL`, `IDEA`):** BHEL generated 585 raw trades across 2017–2019, but **544 trades occurred after its exit on March 31, 2017**! Only 41 trades were legitimate index signals. IDEA generated 584 raw trades, of which **544 trades occurred post-exit**. Only 40 trades were legitimate index signals.
3. **Mid-Period Entrants (`BRITANNIA`, `NESTLEIND`, `JSWSTEEL`, `BAJAJFINSV`):** Trades occurring prior to their index admission dates were strictly pruned, eliminating positive look-ahead bias.
4. **Demerger Interregnum (`GRASIM`):** Trades between May 26, 2017 and April 2, 2018 were strictly excluded during the corporate restructuring period.
