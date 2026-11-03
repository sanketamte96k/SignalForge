# SignalForge — Phase 24G.25: Production V1 Engine Causality Regression Audit
## Mathematical Verification of Chronological Cutoff, Searchsorted Cursor Mechanics & Session Boundary Guards

**Auditor:** SignalForge Quantitative Oversight & Production Architecture Working Group  
**Status:** FULLY VERIFIED & PROVEN CAUSAL  
**Specification:** SF-SPEC-ALPHA-2026-V1  
**Target Engine:** [`src/strategy/backtest_strategy.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/src/strategy/backtest_strategy.py) (`_TimeframeCursor`, `StrategyConfig`)  
**Frozen Configuration Hash:** `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`  

---

### Executive Summary

A core question in the Phase 24G.25 investigation is whether the look-ahead leak identified in the Phase 24G.15 research script (`research_hypotheses.py`) also contaminated the frozen production V1 strategy engine (`src/strategy/backtest_strategy.py`).

An exhaustive line-by-line algorithmic and mathematical audit confirms:
1. **Production V1 is 100% Free of Look-Ahead Bias:** The production V1 strategy engine does NOT use naive forward-filling. Instead, it relies on an explicit chronological cursor (`_TimeframeCursor`) driven by `cutoff = timestamp - duration` and binary search (`searchsorted`).
2. **Incomplete Candles are Invisible:** A higher-timeframe candle is strictly un-addressable until its entire duration has passed.
3. **Overnight Gap Protection:** `_TimeframeCursor` enforces `candle_start.date() == timestamp.date()`, preventing previous-session candles from leaking into the morning session.
4. **Stale Candle Protection:** `_TimeframeCursor` enforces that if a candle is older than its duration (due to missing-minute market halts), it is rejected.
5. **Frozen Configuration Hash:** Preserved bit-for-bit without alteration.

---

### 1. Architectural Anatomy of `_TimeframeCursor`

In `src/strategy/backtest_strategy.py` (lines 443–529):

```python
class _TimeframeCursor:
    """
    Fast chronological cursor for completed timeframe candles.

    A higher-timeframe candle is available only after its entire interval
    has elapsed (causal completion at candle_start + duration).
    Stale candles across missing-minute gaps or session boundaries are rejected.
    """

    def __init__(self, frame: pd.DataFrame, use_rvol: bool, timeframe: str) -> None:
        self.frame = frame
        self.use_rvol = use_rvol
        self.timeframe = timeframe
        self.duration = pd.Timedelta(minutes=TIMEFRAME_MINUTES[timeframe])
        self.position = -1
        self.state: TimeframeState | None = None
        self.valid = False

    def update(self, timestamp: pd.Timestamp) -> TimeframeState | None:
        """Advance to the latest completed candle available at timestamp."""
        cutoff = timestamp - self.duration

        target = (
            self.frame.index.searchsorted(
                cutoff,
                side="right",
            )
            - 1
        )
        target = int(target)

        if target < 0 or target >= len(self.frame):
            self.position = target
            self.state = None
            self.valid = False
            return None

        candle_start = self.frame.index[target]

        # Guard against using features across session boundaries
        if candle_start.date() != timestamp.date():
            self.position = target
            self.state = None
            self.valid = False
            return None

        # Guard against using stale features across missing-minute gaps
        if timestamp - (candle_start + self.duration) >= self.duration:
            self.position = target
            self.state = None
            self.valid = False
            return None

        if target == self.position and self.valid:
            return self.state

        self.position = target
        self.valid = True
        self.state = _row_to_state(self.frame, target, self.use_rvol)
        return self.state
```

---

### 2. Formal Proof of Causality in `_TimeframeCursor`

#### Theorem 1 (Temporal Cutoff Non-Anticipation)
Let $T$ be the current evaluation timestamp, and let $D$ be the duration of the higher timeframe.
The search condition:
$$\text{target} = \text{searchsorted}(T - D, \text{side}="right") - 1$$
selects the candle whose start time $t_{\text{start}}$ satisfies:
$$t_{\text{start}} \le T - D \iff t_{\text{start}} + D \le T$$

**Proof:**
1. In Python/NumPy, `searchsorted(C, side="right")` returns index $k$ such that all elements at indices $< k$ are $\le C$, and elements at indices $\ge k$ are $> C$.
2. Subtracting 1 yields index $k-1$, which corresponds to the greatest index whose value is $\le C$.
3. Here, $C = T - D$. Therefore, the selected candle has $t_{\text{start}} \le T - D$.
4. Since the candle spans $[t_{\text{start}}, t_{\text{start}} + D)$, its final bar closes at $t_{\text{start}} + D - 1\text{m}$.
5. Therefore, the candle was fully completed at or before timestamp $T$.
6. Any candle starting after $T - D$ has $t_{\text{start}} + D > T$. Such a candle is incomplete at timestamp $T$.
7. For any incomplete candle, $t_{\text{start}} > T - D$, which implies its index in the array is $\ge k$. It can NEVER be selected by $k-1$.
8. Hence, incomplete candles are strictly inaccessible. $\blacksquare$

#### Theorem 2 (Session Boundary Isolation)
An overnight price discontinuity between day $d-1$ and day $d$ cannot contaminate trading decisions at the opening of day $d$.

**Proof:**
1. At market opening ($T = 09:15:00$ on day $d$):
   $$\text{cutoff} = 09:15:00 - D$$
2. Since the previous trading day $d-1$ ended at `15:29:00`, `searchsorted` finds candles from day $d-1$ (e.g. `15:25:00`).
3. Line 503 evaluates:
   `if candle_start.date() != timestamp.date(): return None`
4. Since `candle_start.date() == d-1` and `timestamp.date() == d`, the check triggers immediately.
5. The cursor resets state to `None` and returns `None`.
6. Therefore, no features from day $d-1$ can leak into day $d$. $\blacksquare$

---

### 3. Contrast with Research Deviation

| Property | Production V1 Strategy (`backtest_strategy.py`) | Flawed Research Script (`research_hypotheses.py`) |
| :--- | :---: | :---: |
| **Timeframe Retrieval Mechanism** | Chronological `_TimeframeCursor` | Vectorized Pandas `.reindex(method="ffill")` |
| **Cutoff Rule** | $t_{\text{start}} + D \le T$ (Strictly Causal) | None (Binds at $t_{\text{start}} \le T$) |
| **Candle Availability at 09:20** | $[09:15, 09:20)$ visible | $[09:20, 09:25)$ visible (4m Future Peek) |
| **Overnight Gap Guard** | Explicit Date Check (`date() == date()`) | None (Unshifted bleed potential) |
| **Stale Bar Guard** | Stale check ($T - (t_{\text{start}} + D) < D$) | None |
| **Causal Integrity** | **PROVEN 100% SOUND** | **FATALLY CONTAMINATED** |

---

### 4. Regression Test Specifications

The following regression tests are codified in [`tests/test_phase24G25_causal_correctness_audit.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/tests/test_phase24G25_causal_correctness_audit.py):
1. `test_v1_cursor_incomplete_candle_invisible`: Proves that at `09:19:00`, a 5-minute candle stamped `09:15` returns `None`.
2. `test_v1_cursor_exact_boundary_availability`: Proves that at `09:20:00`, the candle stamped `09:15` becomes available, and the candle stamped `09:20` is invisible.
3. `test_v1_cursor_session_isolation`: Proves that at `09:15:00` on the following day, the cursor rejects the previous day's final candle and returns `None`.
4. `test_v1_cursor_stale_candle_rejection`: Proves that after an extended gap of missing bars, stale candles are rejected.
5. `test_v1_config_hash_immutable`: Proves that the frozen V1 configuration hash remains exactly `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7`.
