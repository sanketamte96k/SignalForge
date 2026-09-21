# SignalForge Phase 12 — Structural ORB Robustness Audit Report

## 1. Executive Summary

Phase 12 transitions the SignalForge research agenda from the previously falsified `H3_OPENING_RUSH` indicator-based hypothesis to a rigorous, multi-year structural evaluation of **Opening Range Breakout (ORB)** mechanics.

Using the verified 9.25-year 1-minute dataset (`data/historical/nifty50_1m_signalforge.csv`, 847,814 candles, 2015–2024), we evaluated the complete **3 Opening Ranges x 5 Confirmation Modes = 15 Parameter Combinations** matrix utilizing the existing SignalForge Phase 4 engine.

### Key Strategy Benchmark (Best Validated Configuration: `15m` `close_confirm`)
- **Total Trades**: 2,144
- **Win Rate**: 43.75%
- **Gross P&L**: INR 28,690.65
- **Transaction Costs**: INR 44,024.22
- **Net P&L**: INR -15,333.58
- **Profit Factor**: 0.99
- **Expectancy / Avg Trade**: INR -7.15
- **Max Drawdown**: INR 41,804.32

---

## 2. 15-Combination Parameter Matrix Results

| Opening Range | Confirmation Mode | Trades | Win Rate | Gross P&L (INR) | Costs (INR) | Net P&L (INR) | Profit Factor | Status |
|---|---|---|---|---|---|---|---|---|
| 15m | immediate | 2184 | 42.63% | -11,961.00 | 44,673.23 | -56,634.23 | 0.94 | VALIDATED |
| 15m | close_confirm | 2144 | 43.75% | 28,690.65 | 44,024.22 | -15,333.58 | 0.99 | VALIDATED |
| 15m | volume_confirm | 0 | 0.00% | 0.00 | 0.00 | 0.00 | 0.00 | DATA_LIMITED / INVALID_FOR_VOLUME_VALIDATION |
| 15m | vwap_confirm | 0 | 0.00% | 0.00 | 0.00 | 0.00 | 0.00 | DATA_LIMITED / INVALID_FOR_VOLUME_VALIDATION |
| 15m | retest | 1908 | 43.66% | 22,263.57 | 39,204.94 | -16,941.37 | 0.98 | VALIDATED |
| 30m | immediate | 2013 | 42.77% | -7,028.03 | 41,286.72 | -48,314.75 | 0.95 | VALIDATED |
| 30m | close_confirm | 1954 | 42.32% | -27,992.81 | 39,757.40 | -67,750.22 | 0.91 | VALIDATED |
| 30m | volume_confirm | 0 | 0.00% | 0.00 | 0.00 | 0.00 | 0.00 | DATA_LIMITED / INVALID_FOR_VOLUME_VALIDATION |
| 30m | vwap_confirm | 0 | 0.00% | 0.00 | 0.00 | 0.00 | 0.00 | DATA_LIMITED / INVALID_FOR_VOLUME_VALIDATION |
| 30m | retest | 1684 | 41.57% | -37,606.71 | 34,276.16 | -71,882.87 | 0.89 | VALIDATED |
| 45m | immediate | 1835 | 41.58% | -38,118.26 | 37,319.07 | -75,437.33 | 0.89 | VALIDATED |
| 45m | close_confirm | 1753 | 41.24% | -42,099.23 | 35,635.97 | -77,735.20 | 0.87 | VALIDATED |
| 45m | volume_confirm | 0 | 0.00% | 0.00 | 0.00 | 0.00 | 0.00 | DATA_LIMITED / INVALID_FOR_VOLUME_VALIDATION |
| 45m | vwap_confirm | 0 | 0.00% | 0.00 | 0.00 | 0.00 | 0.00 | DATA_LIMITED / INVALID_FOR_VOLUME_VALIDATION |
| 45m | retest | 1466 | 41.27% | -38,805.02 | 29,849.99 | -68,655.01 | 0.88 | VALIDATED |

---

## 3. Chronological Train / Validation / OOS Partitioning

Rather than applying randomized k-fold splits which leak regime structures, the dataset is evaluated across strictly chronological boundaries:
- **TRAIN**: 2015-01-01 to 2019-12-31 (Pre-COVID baseline, 5 years)
- **VALIDATION**: 2020-01-01 to 2021-12-31 (COVID volatility & recovery, 2 years)
- **OUT-OF-SAMPLE (OOS)**: 2022-01-01 to 2024-03-26 (Recent market regime, ~2.25 years)

| Split | Period | Trades | Win Rate | Net P&L (INR) | Profit Factor | Avg Trade (INR) | Max Drawdown (INR) |
|---|---|---|---|---|---|---|---|
| TRAIN | 2015-01-01 to 2019-12-31 | 1139 | 44.51% | 11,943.49 | 1.02 | 10.49 | 23,704.75 |
| VALIDATION | 2020-01-01 to 2021-12-31 | 476 | 41.60% | -26,471.66 | 0.90 | -55.61 | 40,998.19 |
| OOS | 2022-01-01 to 2024-12-31 | 529 | 44.05% | -805.41 | 1.00 | -1.52 | 17,650.69 |

---

## 4. Yearly Performance Breakdown (2015–2024)

| Year | Trades | Win Rate | Gross P&L (INR) | Costs (INR) | Net P&L (INR) | Profit Factor | Max DD (INR) |
|---|---|---|---|---|---|---|---|
| 2015.0 | 216.0 | 42.13% | -5,142.58 | 4,431.13 | -9,573.71 | 0.92 | 20,721.82 |
| 2016.0 | 224.0 | 45.09% | 9,380.56 | 4,600.16 | 4,780.40 | 1.04 | 16,938.03 |
| 2017.0 | 237.0 | 42.19% | -4,962.60 | 4,856.37 | -9,818.97 | 0.92 | 15,663.95 |
| 2018.0 | 233.0 | 46.35% | 16,059.02 | 4,788.51 | 11,270.51 | 1.09 | 13,242.85 |
| 2019.0 | 229.0 | 46.72% | 20,006.57 | 4,721.30 | 15,285.26 | 1.11 | 14,312.16 |
| 2020.0 | 238.0 | 42.44% | -4,005.06 | 4,904.24 | -8,909.29 | 0.94 | 24,964.94 |
| 2021.0 | 238.0 | 40.76% | -12,682.15 | 4,880.21 | -17,562.36 | 0.86 | 24,571.03 |
| 2022.0 | 240.0 | 43.75% | 3,101.39 | 4,914.43 | -1,813.04 | 0.98 | 15,740.70 |
| 2023.0 | 232.0 | 46.55% | 16,423.08 | 4,757.73 | 11,665.35 | 1.10 | 11,225.78 |
| 2024.0 | 57.0 | 35.09% | -9,487.58 | 1,170.14 | -10,657.72 | 0.70 | 17,650.69 |

---

## 5. Directional Asymmetry Analysis (LONG vs SHORT)

| Direction | Trades | Win Rate | Gross P&L (INR) | Costs (INR) | Net P&L (INR) | Profit Factor | Avg Trade (INR) |
|---|---|---|---|---|---|---|---|
| LONG | 992 | 44.76% | 31,976.36 | 20,371.54 | 11,604.82 | 1.02 | 11.70 |
| SHORT | 1152 | 42.88% | -3,285.71 | 23,652.68 | -26,938.40 | 0.96 | -23.38 |

---

## 6. Transaction Cost Stress Testing

To verify execution viability under real-world market friction, brokerage and slippage are stressed from 0.5x to 5.0x baseline rates:

| Cost Multiplier | Brokerage (INR) | Slippage | Gross P&L (INR) | Costs (INR) | Net P&L (INR) | Profit Factor | Survives? |
|---|---|---|---|---|---|---|---|
| 0.5x | INR 10.0 | 0.00025 | 28,690.65 | 22,012.11 | 6,678.53 | 1.01 | YES |
| 1.0x | INR 20.0 | 0.0005 | 28,690.65 | 44,024.22 | -15,333.58 | 0.99 | NO (Fails) |
| 1.5x | INR 30.0 | 0.00075 | 28,690.65 | 66,036.33 | -37,345.69 | 0.97 | NO (Fails) |
| 2.0x | INR 40.0 | 0.001 | 28,690.65 | 88,048.45 | -59,357.80 | 0.95 | NO (Fails) |
| 3.0x | INR 60.0 | 0.0015 | 28,690.65 | 132,072.67 | -103,382.02 | 0.91 | NO (Fails) |
| 5.0x | INR 100.0 | 0.0025 | 28,690.65 | 220,121.12 | -191,430.47 | 0.85 | NO (Fails) |

---

## 7. Winner Concentration & Tail Risk

| Concentration Metric | Value |
|---|---|
| total_trades | 2144.00 |
| total_net_pnl | -15333.58 |
| max_single_win | 1540.52 |
| max_single_loss | -1202.29 |
| top_1pct_trade_count | 22.00 |
| top_1pct_pnl_share_pct | 2.92 |
| top_5pct_trade_count | 108.00 |
| top_5pct_pnl_share_pct | 13.87 |
| top_10pct_trade_count | 215.00 |
| top_10pct_pnl_share_pct | 26.37 |

---

## 8. MAE / MFE Excursion Analysis (ATR Normalized)

| Excursion Metric | Value |
|---|---|
| avg_mae_atr_all | 1.2778 |
| avg_mfe_atr_all | 1.4865 |
| avg_mae_atr_wins | 0.5312 |
| avg_mfe_atr_wins | 2.474 |
| avg_mae_atr_losses | 1.8585 |
| avg_mfe_atr_losses | 0.7184 |
| max_mae_atr | 5.3242 |
| max_mfe_atr | 8.0938 |
| avg_holding_bars | 9.29 |

---

## 9. Critical Interpretation Rule: Index-Level vs Stock-Level

> [!IMPORTANT]
> **INDEX-LEVEL EVIDENCE DOES NOT EQUAL STOCK-LEVEL ROBUSTNESS**
>
> 1. This audit was executed on **NIFTY 50 spot cash index data**.
> 2. Index volatility, mean reversion, gap frequency, and market impact profile differ substantially from single equities (which suffer from higher idiosyncratic earnings shocks, stock-specific liquidity dry-ups, and corporate actions).
> 3. Therefore, an index-level ORB edge cannot and must not be used to claim that ORB is validated or production-ready for individual NSE stocks.
> 4. Stock-level deployment requires symbol-level walk-forward optimization, individual volume data, and sector-level leave-one-out cross-validation.

---

## 10. Research Verdict

**FINAL CLASSIFICATION**: `REJECTED`

### Reasoning
- **Empirical Expectancy**: The best performing configuration (`15m` `close_confirm`) achieved Net P&L of INR -15,333.58 across 2144 trades (Profit Factor: 0.99).
- **Friction Drag**: Transaction costs (INR 44,024.22) exceed gross gains, leaving net expectancy negative across the 9.25-year index test period.
- **OOS Performance**: In the 2022–2024 out-of-sample period, Net P&L was INR -805.41 (Profit Factor: 1.00).
- **Cost Resilience**: Under standard retail brokerage and slippage, the raw mechanical ORB without secondary regime/trend filtering does not overcome execution costs.
- **Data Boundary**: Volume confirmation is marked `DATA_LIMITED` because spot index data lacks volume.
- **Production Gate**: Under SignalForge strict protocols, this candidate is `REJECTED` and NEVER marked `PRODUCTION_READY`.
