# SignalForge Risk and Exit Engine — Unresolved Decisions and Pre-Registration Register

**Document Reference**: `SF-REG-DECISIONS-2026-V2`  
**Parent Specification**: `SF-SPEC-RISK-2026-V2` ([`risk_and_exit_engine_specification.md`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase24G10_risk_engine_spec/risk_and_exit_engine_specification.md))  

---

## 1. Governance Principles for Pre-Registration

To prevent retrospective curve-fitting and p-hacking, **no parameter value in this register may be declared "optimal" without formal pre-registered empirical validation**. Every threshold identified in Phase 24G.9 failure diagnostics is documented here as an **unresolved research decision**.

Any future strategy version (e.g. SignalForge V2) seeking qualification must explicitly pre-register its choices from this register and evaluate them on fresh, chronologically distinct data under realistic transaction friction.

---

## 2. Unresolved Decisions Register

| Decision ID | Parameter Name | Current Status | Engineering Role | Candidate Range / Hypotheses | Pre-Registration & Evaluation Protocol | Overfitting Guardrail |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DEC-01** | **$k_{\text{stop}}$ (ATR Stop Multiplier)** | **OPEN** | Determines distance of initial stop loss from fill price. | Candidate values: $[1.0, 1.5, 2.0, 2.5] \times \text{ATR}_{14}$. | Evaluate on 2017–2018 training data with fixed friction. Select single value before evaluating 2019 validation. | Must not be optimized separately for Long vs Short. Parameter must remain stationary across regimes. |
| **DEC-02** | **$k_{\text{target}}$ (ATR Target Multiplier)** | **OPEN** | Determines take-profit price target. | Candidate values: $[\text{None}, 2.0, 3.0, 4.0] \times \text{ATR}_{14}$. | Compare fixed take-profit vs trailing-stop-only exit models. | Reward-to-risk ratio $k_{\text{target}} / k_{\text{stop}}$ must be $\ge 1.0$. |
| **DEC-03** | **$k_{\text{trail}}$ (Trailing Stop Distance)** | **OPEN** | Ratchet distance behind peak favorable excursion. | Candidate values: $[1.0, 1.5, 2.0] \times \text{ATR}_{14}$. | Test activation threshold (e.g. activate only after $+1.0 R$ unrealized profit). | Stop price must obey strict ratchet monotonicity ($\Delta P_{\text{stop}} \ge 0$ for Long). |
| **DEC-04** | **$M_{\max}$ (Max Holding Duration)** | **OPEN** | Caps the time a position may drift without reaching target/stop. | Candidate values: $[30, 45, 60, 90, 120]$ minutes. | Phase 24G.9 showed 97.74% of trades drifted 258 mins into 15:29 EOD exits. Test whether truncating holding time reduces tail drift. | Must be enforced uniformly across all trade entries. |
| **DEC-05** | **$T_{\text{open\_filter}}$ (Morning Entry Blackout)** | **OPEN** | Suppresses signal entry during volatile market opening rush. | Candidate windows: Blackout until `09:30`, `09:45`, or `10:00` IST. | Phase 24G.9 proved that entries before 11:00 AM caused 90.22% of all cumulative losses. Pre-register single blackout window. | Cannot be tuned per stock; must be a universal market structure rule. |
| **DEC-06** | **$\theta_{\text{day}}$ (Daily Loss Circuit Breaker)** | **OPEN** | Portfolio-level daily stop out percentage. | Candidate limits: $[1.5\%, 2.0\%, 3.0\%]$ of day opening equity. | Test drawdown reduction during March 2020 crash days. | Halts all trading for remainder of day; no intraday re-arming permitted. |
| **DEC-07** | **$N_{\text{streak}}$ (Consecutive Loss Cooldown)** | **OPEN** | Number of consecutive losses before cooling-off pause. | Candidate limits: $[3, 4, 5]$ consecutive losses; cooldown duration $T_{\text{cooldown}} \in [45, 60, 90]$ mins. | Measure whether cooling off prevents psychological revenge trading and volatility cluster compounding. | Pure safety rule; must execute deterministically without exception. |
| **DEC-08** | **Intrabar Tick-Sequence Assumption** | **FROZEN BY SPEC** | Resolves candle where both Stop and Target are touched. | **CONSERVATIVE RULE (FROZEN)**: Stop-loss is assumed to trigger first. | Verified in Phase 24G.10 specification. Eliminates optimistic fill artifacts. | Non-negotiable safety invariant. Cannot be relaxed to improve backtest metrics. |
| **DEC-09** | **Real-World Transaction Cost Model** | **OPEN FOR PRODUCTION** | Evaluates realistic statutory fees and market spread slippage. | Candidate models: Flat 1 bps (research) vs Full SEBI/NSE statutory fee breakdown + 1–2 tick slippage. | Evaluate strategy viability under realistic Indian equity turnover friction. | If a strategy cannot survive full friction, it must be rejected before paper trading. |

---

## 3. Explicit Constraints on Future Research

1. **Alpha Independence**:
   - Risk management parameters (DEC-01 through DEC-07) control variance, truncate tail risk, and protect capital. **They do not generate positive gross alpha**.
   - If an underlying indicator logic has a negative gross expectancy at 0 bps transaction fees, tuning exit parameters cannot make it a viable commercial trading strategy.
2. **Pre-Registration Enforcement**:
   - Before any backtest run on 2019 or 2020 data is conducted, the research candidate must commit its chosen parameters into an immutable snapshot JSON file with a verifiable SHA-256 hash.
3. **Qualification Gate**:
   - ADANIPORTS remains `NOT_TESTED`.
   - ADANIENT remains `VERIFICATION_REQUIRED`.
   - No automated qualification transitions are permitted without formal sign-off.
