# SignalForge — Phase 24G.30: Equity and Drawdown Metric Definitions

## 1. Scope & Mathematical Conventions

This document formalizes the quantitative definitions, formulas, recovery dynamics, and rounding conventions governing equity progression and drawdown analytics in SignalForge.

---

## 2. Equity Progression Formulation

Let $C_0$ denote the initial account capital (e.g. ₹100,000.00).  
Let $T = [t_1, t_2, \dots, t_N]$ represent the sequence of completed trades in strict chronological order by exit timestamp.

For each trade $k \in [1, N]$:
- $\text{Gross P\&L}_k$: Gross trade return in ₹.
- $\text{Costs}_k$: Aggregate transaction costs, slippage, and fees in ₹.
- $\text{Net P\&L}_k = \text{Gross P\&L}_k - \text{Costs}_k$.

The chronological account equity sequence $E = [E_0, E_1, \dots, E_N]$ is defined recursively:

$$E_0 = C_0$$
$$E_k = E_{k-1} + \text{Net P\&L}_k \quad \forall k \in [1, N]$$

### Invariant Properties
1. **Zero Fabrication:** The sequence contains exactly $N + 1$ discrete points ($E_0$ at starting capital, plus one point per completed trade). No synthetic intermediate valuations are generated between trade completions.
2. **Terminal Invariant:** The final equity satisfies $E_N = C_0 + \sum_{k=1}^N \text{Net P\&L}_k$.

---

## 3. Drawdown and Peak Equity Analytics

### Running Peak Equity ($P_k$)
The peak equity represents the highest account equity achieved up to step $k$:

$$P_0 = C_0$$
$$P_k = \max(P_{k-1}, E_k) = \max_{j \in [0, k]} E_j$$

### Absolute Drawdown ($D_k$) in ₹
The absolute currency drawdown at step $k$ measures the account deficit below the previous running peak:

$$D_k = E_k - P_k \quad (\text{where } D_k \le 0)$$

- When $E_k \ge P_{k-1}$, a new peak is reached or matched, and $D_k = 0.00$.
- When $E_k < P_k$, the account is in an active drawdown trough, and $D_k < 0.00$.

### Percentage Drawdown ($DP_k$) in %
The relative percentage drawdown scales the currency drawdown against the peak equity:

$$DP_k = \begin{cases} 
\frac{E_k - P_k}{P_k} \times 100 & \text{if } P_k > 0 \\ 
0.00 & \text{otherwise} 
\end{cases} \quad (\text{where } DP_k \le 0.0\%)$$

### Peak Recovery Dynamics
When an account experiences a drawdown followed by subsequent winning trades that bring equity back to or above $P_{k-1}$:
1. $E_k \ge P_{k-1} \implies P_k = E_k$.
2. $D_k = E_k - P_k = 0.00$.
3. $DP_k = 0.00\%$.
4. The drawdown curve fully resets to zero. Peak recovery is verified in unit tests against multi-trade recovery fixtures.

---

## 4. Maximum Drawdown vs. Total Loss

> [!IMPORTANT]
> Maximum Drawdown is NOT synonymous with Total Loss. Total loss measures cumulative terminal P&L, whereas Maximum Drawdown measures the worst peak-to-trough drop at any intermediate point during the simulation.

- **Maximum Currency Drawdown ($\text{MDD}_₹$):**
  $$\text{MDD}_₹ = \min_{k \in [0, N]} D_k \quad (\text{or magnitude } |\min D_k|)$$
- **Maximum Percentage Drawdown ($\text{MDD}_{\%}$):**
  $$\text{MDD}_{\%} = \min_{k \in [0, N]} DP_k \quad (\text{or magnitude } |\min DP_k|)$$

**Example Distinction:**  
Consider an account starting at ₹100,000.  
Trade 1 loses ₹1,000 (Equity ₹99,000, Drawdown -₹1,000 / -1.0%).  
Trade 2 gains ₹2,500 (Equity ₹101,500, Drawdown ₹0 / 0.0%).  
- Net P&L = +₹1,500 (+1.5% profit).
- Maximum Drawdown = -₹1,000 (-1.0%).  
The strategy is profitable overall, yet experienced a 1.0% maximum intermediate drawdown.

---

## 5. Extended Performance Metric Definitions

| Metric | Mathematical Formula | Definition |
| :--- | :--- | :--- |
| **Win Rate (%)** | $\frac{N_{\text{win}}}{N} \times 100$ | Proportion of trades where $\text{Net P\&L} > 0$. |
| **Average Win (₹)** | $\frac{1}{N_{\text{win}}} \sum_{k \in \text{wins}} \text{Net P\&L}_k$ | Mean net profit of winning trades. |
| **Average Loss (₹)** | $\frac{1}{N_{\text{loss}}} \sum_{k \in \text{losses}} \text{Net P\&L}_k$ | Mean net loss of losing trades ($< 0$). |
| **Win / Loss Ratio** | $\frac{\text{Average Win}}{\|\text{Average Loss}\|}$ | Ratio of average winning trade magnitude to average losing trade magnitude. |
| **Profit Factor** | $\frac{\sum \text{Gross Gains}}{\|\sum \text{Gross Losses}\|}$ | Aggregate gross profit divided by aggregate gross loss. Formatted as `"inf"` if gross loss is zero. |
| **Expectancy (₹)** | $(W \times \text{Avg Win}) + ((1 - W) \times \text{Avg Loss})$ | Expected net return per trade, where $W = \frac{N_{\text{win}}}{N}$. |
| **Recovery Factor** | $\frac{\text{Net P\&L}}{\|\text{MDD}_₹\|}$ | Strategy profit relative to worst currency drawdown. Defined as $0.00$ if $\text{MDD}_₹ = 0$ or $\text{Net P\&L} \le 0$. |
| **Max Consecutive Wins** | $\max(\text{streak}_{\text{win}})$ | Longest unbroken sequence of trades with $\text{Net P\&L} > 0$. |
| **Max Consecutive Losses** | $\max(\text{streak}_{\text{loss}})$ | Longest unbroken sequence of trades with $\text{Net P\&L} < 0$. |

---

## 6. Rounding Conventions

All reported figures adhere to strict financial display rounding rules:
1. **Currency Values (₹):** Rounded to 2 decimal places using standard half-to-even arithmetic (`round(val, 2)`).
2. **Percentages (%):** Rounded to 2 decimal places (`round(pct, 2)`).
3. **Profit Factor & Ratios:** Rounded to 2 decimal places. In cases with zero loss and positive profit, serialized as `"inf"`. In cases with zero trades, serialized as `0.0`.
4. **Intermediate Math:** Floating-point operations maintain full 64-bit IEEE 754 precision; rounding is applied strictly at point construction and serialization boundaries.
