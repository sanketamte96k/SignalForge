# SignalForge Phase 25D — Distressed & Expelled Constituent Coverage Audit

**Audit Reference:** SF-AUDIT-DISTRESSED-2017-2019  
**Objective:** Audit historical constituents that suffered catastrophic distress, massive drawdowns, or expulsion from the NIFTY 50 during 2017–2019.

---

## 1. Distressed Constituent Inventory & Data Availability

| Symbol | Company Name | Period in NIFTY 50 | Primary Distress Mechanism | 2017–2019 Drawdown Profile | 1-Minute Data Status in Repo |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **IBULHSGFIN** | Indiabulls Housing Finance Ltd. | 2017-03-31 to 2019-09-27 | IL&FS crisis, liquidity shock, promoter allegations | **>80% collapse** (Peak ~₹1,400 to ~₹200) | **AVAILABLE (`RAW_ARCHIVE`)** |
| **YESBANK** | Yes Bank Ltd. | 2017-01-01 to 2019-12-31+ | Escalating bad debt, hidden NPAs, governance collapse | **>90% collapse** (Peak ~₹400 to ~₹40) | **BLOCKED_MISSING_DATA** |
| **ZEEL** | Zee Entertainment Enterprises Ltd. | 2017-01-01 to 2019-12-31+ | Essel Group debt pledge crisis, collateral calls | **>65% collapse** (Peak ~₹600 to ~₹200) | **BLOCKED_MISSING_DATA** |
| **IDEA** | Idea Cellular Ltd. | 2017-01-01 to 2017-03-31 | Telecom price war, cash burn, AGR liabilities | **>70% collapse** | **AVAILABLE (`RAW_ARCHIVE`)** |
| **BHEL** | Bharat Heavy Electricals Ltd. | 2017-01-01 to 2017-03-31 | Structural industrial capex contraction, NPA buildup | **>50% erosion** | **AVAILABLE (`RAW_ARCHIVE`)** |
| **VEDL** | Vedanta Ltd. | 2017-05-26 to 2019-12-31+ | Debt burden, Tuticorin plant closure, delisting offer | **>55% cyclical drawdown** | **BLOCKED_MISSING_DATA** |
| **INFRATEL** | Bharti Infratel Ltd. | 2017-01-01 to 2019-12-31+ | Tenancy losses, telecom consolidation | **>50% drawdown** | **BLOCKED_MISSING_DATA** |

---

## 2. Survivorship Bias Quantification & Impact

1. **Survivors-Only Bias:** Testing only modern survivors creates an artificial upward drift in aggregate performance metrics because distressed stocks that deteriorated and were expelled are systematically erased from modern constituent lists.
2. **Available Distressed Data:** We possess complete 1-minute historical data for `IBULHSGFIN`, `IDEA`, and `BHEL`. Testing these constituents reflects realistic market turbulence during the 2018 NBFC liquidity freeze and telecom disruption.
3. **Missing Distress Risk:** The absence of `YESBANK` and `ZEEL` data means our testable sample still underestimates extreme downside tail events that a real 2017–2019 index investor experienced.
