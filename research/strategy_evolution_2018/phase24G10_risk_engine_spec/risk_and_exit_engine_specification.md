# SignalForge Production Risk and Exit Engine Specification (V2 Architecture)

**Document Reference**: `SF-SPEC-RISK-2026-V2`  
**Status**: DRAFT SPECIFICATION (RESEARCH & TEST PLANNING ONLY)  
**Parent Phase**: Phase 24G.10  
**Baseline Strategy Reference**: SignalForge V1 (Frozen Hash: `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`)  

---

## 1. Executive Summary and Motivation

Phase 24G.9 failure diagnostics demonstrated that the SignalForge V1 strategy collapsed during out-of-sample holdout testing (2020 Net P&L: -Rs 130.35, PF: 0.7007; Combined 2017–2020 Net P&L: -Rs 284.58). The diagnostic audit confirmed four primary structural defects:
1. **Absence of an Active Intraday Exit Mechanism**: 97.74% of all trades (736 of 753) exited passively at `15:29:00` due to mandatory session-end liquidation. Mean trade duration was 258.3 minutes (~4.3 hours). Only 2.26% of trades ever exited via intraday strategy reversal.
2. **Opening Noise Clustering**: 62.95% of trades entered between 09:15 and 11:00 AM, generating 90.22% of all cumulative net losses (-Rs 256.75). Volume spikes immediately satisfied RVOL $\ge 1.5$, triggering premature false breakouts.
3. **Negative Gross Alpha**: Even with 0 bps transaction fees, gross P&L was negative (-Rs 229.40 across 2017–2020).
4. **Unconstrained Drawdown during Volatility Regimes**: Without an initial stop-loss, trailing stop, or daily loss circuit breaker, adverse moves drifted throughout the session.

This specification provides an **implementation-independent, mathematically rigorous architecture** for risk sizing, active intraday exits, and circuit breakers. 

> [!IMPORTANT]
> **Research Control Boundary**: Risk controls and exits truncate left-tail catastrophes and enforce capital preservation; **they do not create alpha out of a negative-expectancy signal**. Any future candidate strategy utilizing this engine must be versioned independently (e.g. SignalForge V2) and evaluated on fresh, uninspected out-of-sample data under realistic transaction friction.

---

## 2. Risk and Exit Engine Requirements

### 2.1 Initial Stop-Loss Placement and Sizing

1. **Stop-Loss Price Placement**:
   - For a LONG position:
     $$P_{\text{stop}} = P_{\text{entry}} - k_{\text{stop}} \cdot \text{ATR}_{14}$$
   - For a SHORT position:
     $$P_{\text{stop}} = P_{\text{entry}} + k_{\text{stop}} \cdot \text{ATR}_{14}$$
   - Where $\text{ATR}_{14}$ is the Average True Range computed causal to candle $t$ close, and $k_{\text{stop}} > 0$ is a pre-registered multiplier parameter.
   - Minimum stop distance must be clamped to at least 1 minimum tick size ($0.05$ INR on NSE) or $0.20\%$ of entry price to prevent division-by-zero or excessive sizing on compressed candles.

2. **Position Sizing Equation**:
   - Monetary risk budget per trade:
     $$R_{\text{trade}} = C \cdot r$$
     Where $C$ is current total equity and $r \in (0, 0.02]$ is the pre-registered risk fraction per trade (default baseline: $1.0\% = 0.01$).
   - Stop distance:
     $$D_{\text{stop}} = |P_{\text{entry}} - P_{\text{stop}}|$$
   - Risk-based quantity:
     $$Q_{\text{risk}} = \left\lfloor \frac{R_{\text{trade}}}{D_{\text{stop}}} \right\rfloor$$
   - Leverage-capped quantity:
     $$Q_{\text{leverage}} = \left\lfloor \frac{C \cdot L_{\max}}{P_{\text{entry}}} \right\rfloor$$
     Where $L_{\max} \le 5.0$ is the regulatory/broker intraday leverage cap.
   - Final executable order quantity:
     $$Q = \min(Q_{\text{risk}}, Q_{\text{leverage}})$$
   - If $Q < 1$, the trade MUST be rejected (insufficient capital to respect risk bounds).

---

### 2.2 Take-Profit and Trailing-Stop Behavior

1. **Take-Profit (Target) Placement**:
   - For LONG:
     $$P_{\text{target}} = P_{\text{entry}} + k_{\text{target}} \cdot \text{ATR}_{14}$$
   - For SHORT:
     $$P_{\text{target}} = P_{\text{entry}} - k_{\text{target}} \cdot \text{ATR}_{14}$$
   - Where $k_{\text{target}} \ge k_{\text{stop}}$ (ensuring a minimum reward-to-risk ratio $\ge 1.0$).
2. **Trailing Stop Ratchet Property**:
   - A trailing stop moves strictly in the favorable direction (non-decreasing for LONG, non-increasing for SHORT). It can NEVER loosen.
   - For LONG at bar $\tau > t_{\text{entry}}$:
     $$P_{\text{trail},\tau} = \max\left(P_{\text{trail},\tau-1},\, \max_{s \in [t_{\text{entry}}, \tau]} \text{High}_s - k_{\text{trail}} \cdot \text{ATR}_{14}\right)$$
   - For SHORT at bar $\tau > t_{\text{entry}}$:
     $$P_{\text{trail},\tau} = \min\left(P_{\text{trail},\tau-1},\, \min_{s \in [t_{\text{entry}}, \tau]} \text{Low}_s + k_{\text{trail}} \cdot \text{ATR}_{14}\right)$$
   - Activation condition: Trailing stop activates only after unrealized gain exceeds a threshold (e.g. $+1.0 R = 1.0 \cdot D_{\text{stop}}$). Until activated, $P_{\text{stop}}$ remains active.

---

### 2.3 Maximum Holding Time and Session End Liquidation

1. **Time-Based Exit ($T_{\max}$)**:
   - To eliminate the 4.3-hour drift defect, an active position that has neither hit its stop nor target within $M_{\max}$ bars (e.g. 60 bars = 60 minutes) MUST trigger a time-stop market exit at the open of bar $t_{\text{entry}} + M_{\max} + 1$.
   - $M_{\max}$ is designated an open pre-registered parameter.
2. **Mandatory 15:29 EOD Liquidation**:
   - All positions remaining open at `15:29:00` IST MUST be forcibly squared off at `15:29:00` close.
   - Zero overnight exposure is guaranteed under all circumstances.

---

### 2.4 Daily Loss and Consecutive-Loss Circuit Breakers

1. **Daily Loss Threshold ($L_{\text{day}}$)**:
   - At the beginning of each calendar trading day $d$, record opening capital $C_{d,\text{start}}$.
   - Running daily net P&L:
     $$\Delta C_d(\tau) = \text{Realized P\&L}_d(\tau) + \text{Unrealized P\&L}_d(\tau)$$
   - If $\Delta C_d(\tau) \le -C_{d,\text{start}} \cdot \theta_{\text{day}}$ (e.g. $\theta_{\text{day}} = 2.0\%$ of capital):
     - Immediately close any open position at market.
     - Cancel all pending orders.
     - Suspend all new signal generation for instrument/portfolio for the remainder of day $d$.
2. **Consecutive Losing Streak Breaker ($N_{\text{streak}}$)**:
   - If $N_{\text{streak}} \ge 3$ consecutive realized losses occur within a single session:
     - Impose a mandatory cooling-off period of $T_{\text{cooldown}} = 60$ minutes or halt trading for the remainder of the session.

---

### 2.5 Gap-Through-Stop and Conservative Fill Assumptions

1. **Intraday Bar Execution**:
   - During bar $\tau$, if $\text{Low}_\tau \le P_{\text{stop}}$ (for Long) and $\text{Open}_\tau \ge P_{\text{stop}}$, the stop is triggered intrabar. In simulation, the fill price is modeled at $\min(\text{Open}_\tau, P_{\text{stop}}) - \text{Slippage}$.
2. **Gap-Through-Stop Event**:
   - If the market gaps past the stop on the opening tick of bar $\tau$:
     - For LONG: $\text{Open}_\tau < P_{\text{stop}}$
     - The exit fill MUST be at $\text{Open}_\tau - \text{Slippage}$, **NOT at $P_{\text{stop}}$**.
     - *Simulator Rule*: Assuming fill at $P_{\text{stop}}$ during a gap-through event is strictly prohibited as an optimistic simulation artifact.

---

### 2.6 Same-Candle Collision Resolution (Stop vs. Target)

If a single 1-minute OHLC candle satisfies both stop-loss and take-profit conditions ($\text{Low}_\tau \le P_{\text{stop}}$ and $\text{High}_\tau \ge P_{\text{target}}$):
- **Conservative Resolution Rule**: **THE STOP-LOSS IS ASSUMED TO HAVE TRIGGERED FIRST**.
- **Execution**: The position is liquidated at $P_{\text{stop}}$ (or $\text{Open}_\tau$ if gapped), and the target is ignored.
- *Justification*: Prevents positive survivorship bias and eliminates optimistic fill assumptions when intrabar tick sequencing is unobserved.

---

### 2.7 Reversals and Pending Order Handling

1. **Reversal Signals**:
   - If an opposite signal is emitted while position $P$ is active:
     - Step 1: Liquidate position $P$ at next bar open $P_{\text{open},\tau+1}$.
     - Step 2: Check risk gates (daily loss limit, leverage cap, cooldown).
     - Step 3: If gates pass, open reversed position at $P_{\text{open},\tau+1}$. If gates fail, remain flat.
2. **Pending Orders at Session and Partition Boundaries**:
   - A signal emitted at `15:29:00` generates a pending order.
   - At session rollover (`date(t) != date(t-1)`), **ALL pending orders MUST be cancelled**.
   - No pending order may execute at `09:15:00` open of the next session.
   - Across partition boundaries (e.g. Dec 31 to Jan 1), all pending orders and active positions MUST be completely purged.

---

### 2.8 Missing Candles, Stale Marks, and Invalid Data

1. **Missing Candle Gap**:
   - If consecutive candle timestamp gap exceeds standard frequency ($\Delta t > 1$ minute inside regular market hours `09:15–15:30`):
     - Cancel any pending entry order.
     - If in an open position, mark data discontinuity warning; evaluate stops against the next valid bar open.
2. **Invalid Price Data**:
   - If any bar violates $\text{High} < \text{Low}$, $\text{Low} \le 0$, $\text{Open} \le 0$, $\text{Close} \le 0$, or $\text{Volume} < 0$:
     - Abort trade execution immediately; log data corruption event.

---

### 2.9 Transaction Friction Model

The engine must support two clearly delineated cost models:

1. **Historical Research Baseline**:
   - Flat turnover fee: $C_{\text{flat}} = \text{Turnover} \times 0.0001$ (1 basis point).
2. **Production Indian Equity Intraday Friction Model**:
   - Brokerage: $\min(\text{Rs } 20, \text{Turnover} \times 0.0005)$ per executed order.
   - STT (Securities Transaction Tax): $0.025\%$ on Sell side turnover only.
   - Exchange Turnover Charge (NSE): $0.00297\%$ on both Buy and Sell turnover.
   - SEBI Turnover Charges: $0.0001\%$ on both Buy and Sell turnover.
   - Stamp Duty: $0.003\%$ on Buy side turnover only.
   - GST: $18\%$ on $(\text{Brokerage} + \text{Exchange Charges} + \text{SEBI Charges})$.
   - Slippage: Minimum 1 tick ($0.05$ INR) or $\text{Turnover} \times 0.0002$ ($2$ bps) during normal market, expanding to $5$ bps during first 15 minutes (`09:15–09:30`).

---

## 3. Mathematical Risk Calculations & Worked Examples

### Example 1: Standard Intraday Sizing & Fill
- **Inputs**:
  - Available Equity: $C = \text{Rs } 100,000$
  - Risk fraction: $r = 1.0\% \implies R_{\text{trade}} = 100,000 \times 0.01 = \text{Rs } 1,000$
  - Instrument: ADANIPORTS @ Entry Price $P_{\text{entry}} = \text{Rs } 300.00$
  - $\text{ATR}_{14} = \text{Rs } 4.00$
  - Stop multiplier $k_{\text{stop}} = 1.5 \implies D_{\text{stop}} = 1.5 \times 4.00 = \text{Rs } 6.00$
  - Stop Price: $P_{\text{stop}} = 300.00 - 6.00 = \text{Rs } 294.00$
  - Target multiplier $k_{\text{target}} = 3.0 \implies P_{\text{target}} = 300.00 + (3.0 \times 4.00) = \text{Rs } 312.00$
  - Leverage cap: $L_{\max} = 5.0$
- **Calculations**:
  - $Q_{\text{risk}} = \lfloor 1,000 / 6.00 \rfloor = \lfloor 166.67 \rfloor = 166$ units
  - $Q_{\text{leverage}} = \lfloor (100,000 \times 5.0) / 300.00 \rfloor = \lfloor 500,000 / 300 \rfloor = 1,666$ units
  - Executable Quantity: $Q = \min(166, 1666) = \mathbf{166 \text{ units}}$
  - Capital Allocated: $166 \times 300.00 = \text{Rs } 49,800$ (Notional exposure: $0.498\times$ capital)
  - True Maximum Risk at Stop: $166 \times \text{Rs } 6.00 = \text{Rs } 996.00 \le \text{Rs } 1,000$.

### Example 2: Gap-Through-Stop Event
- Position: LONG 166 units @ Rs 300.00, $P_{\text{stop}} = \text{Rs } 294.00$.
- Intraday shock: Next candle open gaps down violently to $\text{Open}_{\tau} = \text{Rs } 288.00$.
- **Simulator Behavior**:
  - The stop was breached by a gap: $\text{Open}_\tau < P_{\text{stop}}$ ($288.00 < 294.00$).
  - Fill price is $\text{Rs } 288.00 - 1 \text{ tick } (0.05) = \text{Rs } 287.95$.
  - Realized loss: $166 \times (287.95 - 300.00) = -\text{Rs } 2,000.30$.
  - The loss exceeds the nominal $1R$ budget due to the unfillable gap. The engine correctly records the gap slippage.

### Example 3: Same-Candle Collision
- LONG position active with $P_{\text{stop}} = \text{Rs } 294.00$ and $P_{\text{target}} = \text{Rs } 312.00$.
- Extreme 1-minute candle: $\text{Open} = 305.00, \text{High} = 314.00, \text{Low} = 292.00, \text{Close} = 308.00$.
- **Resolution**:
  - Both target ($314 \ge 312$) and stop ($292 \le 294$) were touched.
  - Applying Conservative Collision Rule: Stop triggered first.
  - Position exits at $P_{\text{stop}} = \text{Rs } 294.00$.
  - Result: Loss of $166 \times (294.00 - 300.00) = -\text{Rs } 996.00$. Target profit is NOT credited.

### Example 4: Daily Loss Circuit Breaker
- Opening Capital: $C_{d,\text{start}} = \text{Rs } 100,000$. Daily loss limit $\theta_{\text{day}} = 2.0\% \implies \text{Max Loss} = \text{Rs } 2,000$.
- Trade 1: Loss of -Rs 996.00.
- Trade 2: Gap loss of -Rs 1,050.00.
- Cumulative Day Loss: $-996.00 - 1050.00 = -\text{Rs } 2,046.00 \le -\text{Rs } 2,000$.
- **Engine Action**:
  - Circuit breaker trips at timestamp of Trade 2 exit.
  - State transitions to `HALTED_FOR_DAY`.
  - All subsequent signals on day $d$ are rejected.
  - Reset occurs at `09:15:00` of day $d+1$.

---

## 4. Simulator Guarantees vs. Broker Guarantees

| Engine Feature | Simulation Environment Guarantee | Real-World Broker / Market Reality |
| :--- | :--- | :--- |
| **Stop Fill Price** | Guaranteed fill at $\min(\text{Open}, P_{\text{stop}})$ | **No guarantee**. Stop-loss market orders become market orders upon trigger and fill at prevailing bid/ask depth. Extreme illiquidity may cause severe slippage. |
| **Simultaneous Stop & Target** | Deterministic stop-first precedence | Order-matching depends on whether price ticked down or up first in the exchange matching engine (L3 order book). OCO (One-Cancels-Other) bracket orders cancel the opposite leg once exchange confirms fill. |
| **EOD Square-Off** | Exact exit at 15:29:00 close | Broker RMS (Risk Management System) auto-square-off runs between 15:15 and 15:25, subjecting market orders to spread widening and broker square-off charges (e.g. Rs 50/order). |
| **Leverage Cap** | Fixed $L_{\max} = 5.0\times$ cap | SEBI peak margin rules mandate 100% upfront margin based on VAR + ELM. Broker margin multiplier varies by stock and intraday volatility category. |
| **Data Gaps** | Next available candle used | During exchange connectivity dropouts or circuit halts, trading is suspended; orders cannot be modified or cancelled. |

---

## 5. Specification Approval & Research Sign-Off

- **Specification Status**: APPROVED SPECIFICATION FOR IMPLEMENTATION & TEST DESIGN
- **Applicability**: SignalForge Risk Engine Architecture V2
- **Strategy Modifications**: **NONE**. SignalForge V1 frozen baseline remains unchanged.
- **Authorizing Role**: Quantitative Risk & Strategy Governance
