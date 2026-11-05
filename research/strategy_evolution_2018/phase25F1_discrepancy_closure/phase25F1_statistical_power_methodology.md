# SignalForge Phase 25F.1 — Statistical Power Methodology & Forensic Audit

**Document Reference:** `SF-STAT-POWER-METHODOLOGY-2026`  
**Audited Target:** Phase 25F Section 1 Power Claim  
**Status:** **`FORMALLY_QUALIFIED_AND_DOCUMENTED`**  

---

## 1. Context of the Audit

In Phase 25F's statistical report ([`phase25F_statistical_audit.md`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase25F_independent_audit/phase25F_statistical_audit.md)), the following assertion was made:
> *"The remaining 35 stocks averaged 525 trades per stock, providing statistical power (>99%) to detect an edge >= 2% if one existed."*

This forensic audit evaluates the mathematical assumptions, effect size definitions, variance parameters, and serial correlation treatments required to substantiate, correct, and qualify that claim.

---

## 2. Mathematical Power Framework

Statistical power ($1 - \beta$) is the probability of correctly rejecting the null hypothesis $H_0$ when a specific alternative hypothesis $H_1$ is true. Power depends on four interdependent variables:
1. **Sample Size ($N$):** Number of observed trades.
2. **Significance Level ($\alpha$):** Type I error rate (standard one-sided $\alpha = 0.05, z_\alpha = 1.645$).
3. **Variance ($\sigma^2$):** Dispersion of the underlying test statistic.
4. **Effect Size ($\Delta$):** The magnitude of true alpha above the null.

In quantitative strategy evaluation, statistical edge is tested via two formal frameworks:
- **Framework A:** Binomial Sign Test on Win Rate ($H_0: p \le 0.50$ vs $H_1: p > 0.50$).
- **Framework B:** One-Sample Parametric Test on Mean Per-Trade Return ($H_0: \mu \le 0$ vs $H_1: \mu > 0$).

---

## 3. Framework A: Win-Rate Proportion Power Analysis

### 3.1 Mathematical Formulation
Under $H_0$, trade outcomes follow a Bernoulli distribution with $p_0 = 0.50$. For sample size $N$, the standard error is:
$$\sigma_0 = \sqrt{\frac{p_0(1 - p_0)}{N}} = \sqrt{\frac{0.25}{N}}$$

For a one-sided test at $\alpha = 0.05$, the critical win-rate threshold $p_{crit}$ is:
$$p_{crit} = p_0 + z_\alpha \sqrt{\frac{0.25}{N}} = 0.50 + 1.645 \sqrt{\frac{0.25}{525}} = 0.50 + 0.0359 = \mathbf{53.59\%}$$

If the true win rate under $H_1$ is $p_1 = p_0 + \Delta p$, the statistical power is:
$$1 - \beta = \Phi\left( \frac{\Delta p \sqrt{N} - z_\alpha \sqrt{p_0(1 - p_0)}}{\sqrt{p_1(1 - p_1)}} \right)$$

### 3.2 Power Calculations for Average Stock Sample ($N = 525$)
Suppose an "edge of 2%" refers to a **+2.0% win-rate edge** ($p_1 = 0.520$):
$$\Delta p \sqrt{N} = 0.02 \times \sqrt{525} = 0.02 \times 22.913 = 0.4583$$
$$z_\alpha \sqrt{p_0(1 - p_0)} = 1.645 \times 0.50 = 0.8225$$
$$\sqrt{p_1(1 - p_1)} = \sqrt{0.52 \times 0.48} = 0.4996$$
$$z_{power} = \frac{0.4583 - 0.8225}{0.4996} = \frac{-0.3642}{0.4996} = -0.729$$
$$1 - \beta = \Phi(-0.729) \approx \mathbf{23.3\%}$$

**Finding:** For a +2% win-rate edge, $N = 525$ provides only **23.3% power** (a 76.7% Type II error rate). To achieve 99% power ($z_\beta = 2.326$) for a +2% win rate, the required sample size is:
$$N_{req} = \frac{(z_\alpha + z_\beta)^2 \cdot p_0(1 - p_0)}{(\Delta p)^2} = \frac{(1.645 + 2.326)^2 \times 0.25}{(0.02)^2} = \frac{15.769 \times 0.25}{0.0004} \approx \mathbf{9,856 \text{ trades}}$$

---

## 4. Framework B: Mean Trade Return Power Analysis

### 4.1 Empirical Return Distribution of SignalForge V1
From the committed 38-stock raw cache ([`phase25E_38stock_raw_trades_cache.json`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/research/strategy_evolution_2018/phase25E_historical_backtest/phase25E_38stock_raw_trades_cache.json)):
- **Average Trade Sample Size:** $N = 525$ trades per stock.
- **Empirical Mean Return per Trade:** $\bar{\mu} = -0.017\%$ (-1.7 bps gross), $\bar{\mu}_{net} = -0.112\%$ (-11.2 bps net).
- **Empirical Return Standard Deviation:** $\sigma = 1.322\%$ (132.2 bps).
- **Standard Error of Mean:** $\text{SE} = \frac{\sigma}{\sqrt{N}} = \frac{132.2 \text{ bps}}{\sqrt{525}} \approx \mathbf{5.77 \text{ bps}}$.

### 4.2 Minimum Detectable Effect (MDE)
The Minimum Detectable Effect size for a given power ($1 - \beta$) and significance level ($\alpha = 0.05, z_\alpha = 1.645$) is:
$$\text{MDE} = (z_\alpha + z_\beta) \times \frac{\sigma}{\sqrt{N}}$$

| Target Statistical Power ($1 - \beta$) | Required $z_\beta$ | Total Multiplier $(z_\alpha + z_\beta)$ | MDE (bps per trade) | MDE (% return per trade) |
| :---: | :---: | :---: | :---: | :---: |
| **50% Power** | 0.000 | 1.645 | **9.49 bps** | +0.095% |
| **80% Power** (Standard) | 0.842 | 2.487 | **14.35 bps** | +0.143% |
| **90% Power** | 1.282 | 2.927 | **16.89 bps** | +0.169% |
| **95% Power** | 1.645 | 3.290 | **18.98 bps** | +0.190% |
| **99% Power** | 2.326 | 3.971 | **22.91 bps** | +0.229% |

### 4.3 Origin of the "Edge $\ge 2\%$" Statement
If the author of Phase 25F interpreted "an edge $\ge 2\%$" literally as **$+2.0\%$ per trade** ($+200$ bps):
$$z = \frac{200 \text{ bps} - 1.645(5.77 \text{ bps})}{5.77 \text{ bps}} = \frac{200 - 9.49}{5.77} = 33.02 \implies \text{Power} > 99.9999\%$$
While mathematically true that $N = 525$ has $>99\%$ power to detect a $+200$ bps edge, **a 200 bps per-trade edge is completely unrealistic for 1-minute intraday equity trading**. Institutional intraday edges typically range from 5 to 15 bps per trade. Stating ">99% power" without specifying that the assumed effect was 200 bps was misleading.

---

## 5. Serial Correlation & Effective Sample Size Adjustment

### 5.1 Intra-Day Trade Dependence
Trades generated by the V1 strategy on the same stock or across stocks exhibit temporal and cross-sectional clustering:
- Morning breakout signals cluster at 09:45–10:30 AM following market open volatility.
- Trade returns share exposure to daily market-wide index trend and sector momentum.
- Empirical first-order lag autocorrelation of trade returns across the 38 stocks is $\rho_1 \approx 0.063$.

### 5.2 Effective Sample Size ($N_{eff}$)
Accounting for first-order autocorrelation via the Bartlett adjustment:
$$N_{eff} = \frac{N}{1 + 2 \sum_{k=1}^\infty \rho_k} \approx \frac{N}{1 + 2\rho_1} = \frac{525}{1 + 2(0.063)} = \frac{525}{1.126} \approx \mathbf{466 \text{ trades}}$$

### 5.3 Dependence-Adjusted Power & MDE
Using $N_{eff} = 466$:
$$\text{SE}_{eff} = \frac{132.2 \text{ bps}}{\sqrt{466}} \approx \mathbf{6.12 \text{ bps}}$$
- **Dependence-Adjusted 80% MDE:** $2.487 \times 6.12 = \mathbf{15.22 \text{ bps}}$ (+0.152% per trade).
- **Dependence-Adjusted 99% MDE:** $3.971 \times 6.12 = \mathbf{24.30 \text{ bps}}$ (+0.243% per trade).

---

## 6. Formal Qualification and Conclusion

### 6.1 Corrected Statement
The unadorned statement in Phase 25F is formally replaced with the following qualified assertion:
> *"The 35 stocks with complete membership tenure averaged 525 trades ($N_{eff} \approx 466$ after autocorrelation adjustment). This sample size provides $\ge 80\%$ power to detect a per-trade return edge $\ge 15.2$ bps, and $\ge 99\%$ power to detect a per-trade return edge $\ge 24.3$ bps. For smaller subtle edges (2–5 bps) or win-rate edges ($p \le 0.52$), the sample size is underpowered ($< 25\%$ power)."*

### 6.2 Why the Strategy Failure Is Definitive Regardless of Power
Low statistical power only hinders research when the observed sample mean is positive but fails to reach the critical threshold (Type II error). Here, the empirical evidence across 31 continuous stocks is **unambiguously negative**:
- **Gross P&L:** Negative or flat across the majority of stocks.
- **Model B Net P&L:** Deeply negative across 31 of 34 continuous stocks.
- **Net Expectancy:** An average loss of **-₹175.46 per trade** in portfolio deployment.

Because the empirical point estimates lie deeply in the negative loss territory rather than near zero, the strategy is rejected not because of a lack of statistical power, but because of **demonstrated negative alpha after friction**.
