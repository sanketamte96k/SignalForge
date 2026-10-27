# SignalForge Risk and Exit Engine — Acceptance Test Matrix

**Document Reference**: `SF-TEST-RISK-2026-V2`  
**Parent Specification**: `SF-SPEC-RISK-2026-V2` ([`risk_and_exit_engine_specification.md`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G10_risk_engine_spec/risk_and_exit_engine_specification.md))  

---

## Acceptance Test Suite Overview

This matrix specifies the functional and mathematical test cases required to validate any implementation of the SignalForge Risk and Exit Engine. Every test defines exact inputs, deterministic assertions, and unambiguous pass/fail criteria.

---

## Acceptance Test Matrix

| Test ID | Test Category | Input Preconditions | Market Event / Candle Sequence | Expected Engine Behavior | Pass/Fail Verification Metric |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-RISK-01** | **Causal Next-Open Fill** | Flat position. Strategy emits `BUY` at candle $t$ close ($10:15:00$). | Candle $t+1$ opens at $10:16:00$ with $\text{Open} = 300.00$. | Order queues at $t$ close; executes at $t+1$ open. | `trade.entry_time == "10:16:00"`, `trade.entry_price == 300.00`. Fills strictly after signal bar. |
| **TC-RISK-02** | **Normal Intrabar Stop Loss** | Active LONG position: Entry 300.00, $P_{\text{stop}} = 294.00$, $Q = 100$. | Candle $\tau$: $\text{Open} = 297.00$, $\text{High} = 298.00$, $\text{Low} = 293.50$, $\text{Close} = 295.00$. | Stop triggered intrabar since $\text{Low} \le P_{\text{stop}}$. Exit filled at $P_{\text{stop}}$. | `trade.exit_price == 294.00`, `trade.exit_reason == "STOP_LOSS"`, `trade.net_pnl == -600.0 - fees`. |
| **TC-RISK-03** | **Gap-Through Stop Loss** | Active LONG position: Entry 300.00, $P_{\text{stop}} = 294.00$, $Q = 100$. | Candle $\tau$: Gaps down on open: $\text{Open} = 289.00$, $\text{High} = 291.00$, $\text{Low} = 287.00$, $\text{Close} = 290.00$. | Stop breached by opening gap. Fill price MUST be $\text{Open} - \text{Slippage}$, NOT $P_{\text{stop}}$. | `trade.exit_price == 289.00` (or $288.95$ with 1-tick slippage). `trade.exit_price < 294.00`. |
| **TC-RISK-04** | **Same-Candle Stop/Target Conflict** | Active LONG position: Entry 300.00, $P_{\text{stop}} = 294.00$, $P_{\text{target}} = 312.00$. | Candle $\tau$: Wild spike candle: $\text{Open} = 302.00$, $\text{High} = 315.00$, $\text{Low} = 292.00$, $\text{Close} = 305.00$. | Both stop and target touched. Conservative rule: Stop triggers first. Target ignored. | `trade.exit_price == 294.00`, `trade.exit_reason == "STOP_LOSS"`, Net P&L is negative. |
| **TC-RISK-05** | **Trailing Stop Ratchet Monotonicity** | Active LONG position: Entry 300.00, initial stop 294.00, $k_{\text{trail}} = 1.5 \text{ ATR}$, $\text{ATR} = 4.00$. | Candle 1: High 310.00. Candle 2: High 305.00 (pullback). Candle 3: Low 298.00. | Trailing stop ratchets up to $310 - 6 = 304.00$ on Candle 1. On Candle 2 pullback, stop remains $304.00$. On Candle 3, exits at $304.00$. | Trailing stop price is monotonically non-decreasing over time: $P_{\text{stop},t+1} \ge P_{\text{stop},t}$. Position locks profit. |
| **TC-RISK-06** | **Max Holding Time Expiration** | Position opened at $10:00:00$ with $M_{\max} = 60$ minutes. | Neither stop nor target hit by $11:00:00$ (60 elapsed bars). | Time-based exit triggered. Market exit order executed at $11:01:00$ open. | `trade.exit_time == "11:01:00"`, `trade.exit_reason == "MAX_TIME"`. Eliminates passive drift. |
| **TC-RISK-07** | **Mandatory 15:29 EOD Liquidation** | Active position remains open at $15:28:00$. | Clock reaches $15:29:00$ IST. | Forced session liquidation executed at $15:29:00$ close. Zero overnight carry. | `trade.exit_time == "15:29:00"`, `trade.exit_reason == "EOD"`. Position is flat before next day. |
| **TC-RISK-08** | **Pending Order Cancellation at Day Rollover** | Signal generated at $15:29:00$ close. Pending order created. | Next candle is day $d+1$ at $09:15:00$. Day boundary crossed. | Pending order is CANCELLED at session rollover. Zero fill at $09:15:00$. | Total trades remains unchanged. No trade entered at morning open. |
| **TC-RISK-09** | **Partition Boundary Purge** | Historical backtest partitioned into 2017–2018 and 2019. | Final candle of 2018 partition reached ($2018-12-31\ 15:29$). | Open position forced closed at $15:29$. Pending orders purged. 2019 starts completely flat. | Zero position carryover across partition boundaries. Independent partition accounting. |
| **TC-RISK-10** | **Daily Loss Circuit Breaker** | Daily loss limit $\theta_{\text{day}} = 2.0\%$ (Rs 2,000 on Rs 100k equity). | Trade 1 loses Rs 1,100; Trade 2 loses Rs 1,000 (total day loss: Rs 2,100). | Daily loss exceeded. Engine state switches to `HALTED_FOR_DAY`. Subsequent signals rejected. | `signals_rejected_daily_limit > 0`. Zero trades executed for remainder of day. Auto-resets next day. |
| **TC-RISK-11** | **Consecutive Loss Cooldown** | Consecutive loss limit $N_{\text{streak}} = 3$, $T_{\text{cooldown}} = 60\text{ min}$. | 3 consecutive losing trades occur by $11:30:00$. | Cooldown activated until $12:30:00$. Any signal emitted during window rejected. | Signals between $11:30$ and $12:30$ rejected with reason `CONSECUTIVE_LOSS_COOLDOWN`. |
| **TC-RISK-12** | **Risk-Budget Leverage Clamping** | Capital = Rs 10,000, $L_{\max} = 5.0$, Stock price = Rs 1,000. Stop distance = Rs 1.00 ($r = 1\% \implies \text{Risk } = 100$). | Sizing calculation: $Q_{\text{risk}} = 100 / 1.00 = 100$ units (Notional: Rs 100,000 = $10\times$). | Leverage cap clamps quantity: $Q_{\text{lev}} = \lfloor (10,000 \times 5) / 1,000 \rfloor = 50$ units. | Executed $Q == 50$. Notional exposure respects $5.0\times$ cap. |
| **TC-RISK-13** | **Missing Minute Gap Rejection** | Pending entry order queued at $10:00:00$. | Next bar is $10:05:00$ (4-minute missing data gap). | Engine detects missing data discontinuity ($\Delta t > 1\text{m}$). Pending order cancelled. | Order cancelled with reason `MISSING_DATA_GAP`. Prevents unobserved gap executions. |
| **TC-RISK-14** | **Zero-Capital Bankruptcy Protection** | Capital drops to $\le 0$ following catastrophic gap loss. | Ongoing market data stream continues. | Trading halted permanently with explicit bankruptcy reason logged. | Simulation terminates; `bankruptcy_reason` populated; portfolio does not trade negative capital. |
| **TC-RISK-15** | **Deterministic Replay Agreement** | Entire test dataset and configuration executed twice independently. | Fresh engine and signal generator instances on identical data. | Trade logs and performance metrics must match byte-for-byte. | `sha256(trade_log_run1) == sha256(trade_log_run2)`. Delta across all metrics is $0.000000$. |

---

## Acceptance Verification Protocol

1. **Pre-Requisite**: Every test case must be validated via an automated, deterministic unit/integration test.
2. **Tolerance**: Absolute numerical tolerance for monetary calculations is $10^{-6}$ INR.
3. **Audit Log**: Every rejection, cancellation, and exit must be recorded with an immutable timestamp and explicit exit reason code (`STOP_LOSS`, `TAKE_PROFIT`, `TRAILING_STOP`, `MAX_TIME`, `EOD`, `DAILY_LOSS_HALT`, `COOLDOWN_HALT`, `GAP_REJECTION`).
