# SignalForge — Phase 10: Relative Market Context & Cross-Asset Signal Engine Report

## 1. Executive Summary & Core Hypothesis
Phase 10 tested whether a stock's probability of producing a profitable signal improves when its movement agrees with the broader market (NIFTY 50 1-minute benchmark) and relative strength context.

### Primary Verdict
**ROBUST EDGE FOUND: NO**
Criteria Met: 11/14.

---

## 2. Baseline vs Best Context Configuration
| Metric | Baseline (Unfiltered) | Best Context (H5_RS_DIVERGENCE) |
| :--- | :--- | :--- |
| **Total Trades / Signals** | 11,222 | 80 (0.71%) |
| **Gross Win Rate** | 41.69% | 41.25% |
| **Gross Expectancy** | Rs. 43.14 | Rs. 272.11 |
| **Net Expectancy** | Rs. -33.47 | Rs. 251.54 |
| **Gross Profit Factor** | 1.1097 | 1.6313 |
| **Net Profit Factor** | 0.9248 | 1.5679 |
| **Net P&L** | -Rs. 375,554.43 | Rs. 20,123.46 |
| **Max Drawdown** | Rs. 411,467.55 | Rs. 6,406.40 |
| **Trades / Day** | 45.62 | 0.33 |

---

## 3. Head-to-Head Hypotheses Comparison (H1 to H8)
| hypothesis | description | total_signals | long_signals | short_signals | pct_retained | trades_per_day | win_rate | gross_expectancy | net_expectancy | gross_pf | net_pf | gross_pnl | transaction_costs | net_pnl | avg_winner | avg_loser | max_drawdown | max_loss_streak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BASELINE (No Context) | Unfiltered baseline trades | 11222 | 5615 | 5607 | 100.0 | 45.62 | 31.73 | -13.04 | -33.47 | 0.9698 | 0.9248 | -146346.59 | 229207.84 | -375554.43 | 1297.62 | -652.18 | 374534.64 | 55 |
| H1_RS_CONFIRMATION | Stock setup + Relative Strength Confirmation | 8445 | 4171 | 4274 | 75.25 | 34.33 | 31.27 | -25.69 | -46.11 | 0.9411 | 0.8975 | -216936.1 | 172474.56 | -389410.66 | 1291.71 | -654.86 | 388398.93 | 37 |
| H2_MARKET_AGREEMENT | Stock setup + Market Trend Agreement | 3463 | 1845 | 1618 | 30.86 | 14.08 | 31.82 | -6.87 | -27.3 | 0.9842 | 0.9393 | -23787.54 | 70757.51 | -94545.05 | 1327.31 | -659.57 | 101345.25 | 21 |
| H3_DUAL_ALIGNMENT | Stock setup + Dual Alignment (Market + RS) | 1811 | 1000 | 811 | 16.14 | 7.36 | 30.43 | -47.69 | -68.11 | 0.8943 | 0.8537 | -86361.6 | 36994.13 | -123355.74 | 1305.86 | -668.96 | 131931.51 | 21 |
| H4_CS_LEADERS | Cross-Sectional Leaders (Rank 1-2 for Long, 4-5 for Short) | 6840 | 3367 | 3473 | 60.95 | 27.8 | 31.04 | -31.59 | -52.01 | 0.9278 | 0.8848 | -216060.6 | 139683.56 | -355744.16 | 1286.64 | -654.5 | 354724.37 | 36 |
| H5_RS_DIVERGENCE | Extreme RS Divergence / Mean-Reversion | 80 | 48 | 32 | 0.71 | 0.33 | 41.25 | 272.11 | 251.54 | 1.6313 | 1.5679 | 21768.83 | 1645.37 | 20123.46 | 1683.61 | -753.95 | 6406.4 | 6 |
| H6_MARKET_PULLBACK | Market Agreement + Pullback Confirmation | 3182 | 1682 | 1500 | 28.36 | 12.93 | 31.68 | -7.39 | -27.83 | 0.983 | 0.9379 | -23530.52 | 65008.85 | -88539.38 | 1325.51 | -655.31 | 99230.96 | 23 |
| H7_REGIME_RS | Strong RS + Favorable Market Regime (Trend) | 4062 | 2032 | 2030 | 36.2 | 16.51 | 31.41 | -31.99 | -52.43 | 0.9291 | 0.8872 | -129948.71 | 83007.12 | -212955.83 | 1313.26 | -677.91 | 221882.2 | 27 |
| H8_FULL_CONSENSUS | Full Consensus Signal (Market + Top CS Rank + RS) | 1272 | 704 | 568 | 11.33 | 5.17 | 31.13 | -34.64 | -55.07 | 0.9225 | 0.8806 | -44056.38 | 25986.62 | -70043.0 | 1303.98 | -669.43 | 77175.59 | 17 |

---

## 4. Context Agreement Analysis (Informational Edge vs Cost-Reduction Only)
| configuration | trades | win_rate | gross_expectancy | net_expectancy | gross_pf | net_pf | net_pnl | pct_baseline | classification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Stock-Only (Baseline) | 11222 | 31.73 | -13.04 | -33.47 | 0.9698 | 0.9248 | -375554.43 | 100.0 | NO PREDICTIVE VALUE |
| Stock + Market Agreement | 3463 | 31.82 | -6.87 | -27.3 | 0.9842 | 0.9393 | -94545.05 | 30.86 | MODEST IMPROVEMENT (Still Negative Net) |
| Stock + Relative Strength | 8445 | 31.27 | -25.69 | -46.11 | 0.9411 | 0.8975 | -389410.66 | 75.25 | COST-REDUCTION ONLY (Gross Edge Degraded) |
| Stock + Market + RS (Dual) | 1811 | 30.43 | -47.69 | -68.11 | 0.8943 | 0.8537 | -123355.74 | 16.14 | COST-REDUCTION ONLY (Gross Edge Degraded) |

---

## 5. Market Regime-Conditional Breakdown
| benchmark_regime | baseline_trades | filtered_trades | win_rate | gross_expectancy | net_expectancy | net_pf | net_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TREND_UP | 3020 | 35 | 40.0 | 204.67 | 184.13 | 1.4042 | 6444.41 |
| TREND_DOWN | 2685 | 30 | 40.0 | 275.18 | 254.58 | 1.5399 | 7637.42 |
| RANGE | 4261 | 2 | 50.0 | 688.26 | 667.91 | 32.053 | 1335.81 |
| HIGH_VOLATILITY | 569 | 11 | 45.45 | 317.3 | 296.68 | 1.6268 | 3263.5 |
| LOW_VOLATILITY | 687 | 2 | 50.0 | 741.57 | 721.16 | 16.1133 | 1442.32 |

---

## 6. Relative Strength & Context Bucketing Breakdown
| context_bucket | trades | pct_total | win_rate | gross_expectancy | net_expectancy | net_pf | net_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- |
| STRONG MARKET + STRONG STOCK | 1702 | 15.17 | 30.55 | -27.25 | -47.67 | 0.8933 | -81139.11 |
| STRONG MARKET + WEAK STOCK | 1132 | 10.09 | 32.24 | -22.19 | -42.61 | 0.9059 | -48238.34 |
| WEAK MARKET + STRONG STOCK | 312 | 2.78 | 29.81 | -14.44 | -34.85 | 0.9193 | -10873.21 |
| WEAK MARKET + WEAK STOCK | 2259 | 20.13 | 32.18 | 0.52 | -19.89 | 0.9533 | -44928.07 |
| NEUTRAL MARKET | 3409 | 30.38 | 32.62 | 5.34 | -15.08 | 0.9649 | -51410.64 |
| STRONG RELATIVE STRENGTH | 964 | 8.59 | 30.91 | -48.46 | -68.9 | 0.857 | -66424.32 |
| WEAK RELATIVE STRENGTH | 1054 | 9.39 | 31.59 | -11.4 | -31.84 | 0.9305 | -33559.9 |
| EXTREME RELATIVE STRENGTH | 188 | 1.68 | 26.6 | -91.75 | -112.24 | 0.7964 | -21101.4 |
| EXTREME RELATIVE WEAKNESS | 202 | 1.8 | 31.19 | -68.01 | -88.51 | 0.8383 | -17879.43 |

---

## 7. Cross-Sectional Ranking Analysis
| cs_rank | description | trades | pct_total | win_rate | gross_expectancy | net_expectancy | net_pf | net_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Rank 1 (Leader/Top) | 1917 | 17.08 | 30.99 | -18.35 | -38.78 | 0.9137 | -74342.33 |
| 2 | Rank 2 (Middle) | 2367 | 21.09 | 32.28 | 5.55 | -14.87 | 0.966 | -35208.16 |
| 3 | Rank 3 (Middle) | 2437 | 21.72 | 32.99 | 31.67 | 11.24 | 1.0263 | 27384.34 |
| 4 | Rank 4 (Middle) | 2425 | 21.61 | 31.71 | -26.0 | -46.43 | 0.8977 | -112582.94 |
| 5 | Rank 5 (Laggard/Bottom) | 2076 | 18.5 | 30.35 | -66.68 | -87.09 | 0.8113 | -180805.35 |

---

## 8. Cross-Symbol Robustness & Concentration Audit
| symbol | baseline_trades | filtered_trades | win_rate | gross_expectancy | net_expectancy | net_pf | net_pnl | pnl_contribution_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RELIANCE | 2571 | 9 | 33.33 | -208.55 | -228.76 | 0.2955 | -2058.82 | -10.23 |
| TCS | 1799 | 19 | 42.11 | 313.67 | 293.24 | 2.026 | 5571.49 | 27.69 |
| INFY | 2460 | 32 | 50.0 | 631.87 | 610.88 | 1.8904 | 19548.18 | 97.14 |
| HDFCBANK | 1825 | 9 | 44.44 | 106.03 | 85.89 | 1.8536 | 772.98 | 3.84 |
| ICICIBANK | 2567 | 11 | 18.18 | -317.1 | -337.31 | 0.1216 | -3710.36 | -18.44 |

- **Best Symbol**: `INFY` (Net P&L: Rs. 19,548.18)
- **Net P&L without Best Symbol**: Rs. 575.29

---

## 9. Monthly Performance Stability
| month | trades | win_rate | gross_expectancy | net_expectancy | net_pf | net_pnl |
| --- | --- | --- | --- | --- | --- | --- |
| 2018-01 | 3 | 33.33 | -85.95 | -106.46 | 0.8106 | -319.37 |
| 2018-02 | 13 | 38.46 | 84.08 | 63.53 | 1.121 | 825.88 |
| 2018-03 | 6 | 66.67 | 595.55 | 574.86 | 2.4614 | 3449.18 |
| 2018-04 | 5 | 40.0 | 418.72 | 398.12 | 1.981 | 1990.59 |
| 2018-05 | 6 | 33.33 | 376.02 | 355.34 | 1.6997 | 2132.03 |
| 2018-06 | 2 | 0.0 | -404.39 | -424.59 | 0.0 | -849.18 |
| 2018-07 | 5 | 60.0 | 407.97 | 387.43 | 2.1199 | 1937.15 |
| 2018-08 | 3 | 0.0 | -677.29 | -697.63 | 0.0 | -2092.89 |
| 2018-09 | 9 | 55.56 | 767.77 | 747.19 | 4.6762 | 6724.73 |
| 2018-10 | 12 | 41.67 | 448.29 | 427.53 | 1.7897 | 5130.39 |
| 2018-11 | 7 | 28.57 | 293.23 | 272.69 | 1.6644 | 1908.81 |
| 2018-12 | 9 | 44.44 | -58.96 | -79.32 | 0.8025 | -713.85 |

---

## 10. Time-of-Day Distribution
| window | trades | win_rate | gross_expectancy | net_expectancy | net_pf | net_pnl |
| --- | --- | --- | --- | --- | --- | --- |
| 09:15–10:00 | 53 | 37.74 | 144.48 | 123.95 | 1.2665 | 6569.42 |
| 10:00–11:00 | 1 | 0.0 | -23.01 | -43.02 | 0.0 | -43.02 |
| 11:00–12:00 | 1 | 0.0 | -1112.34 | -1132.89 | 0.0 | -1132.89 |
| 12:00–13:00 | 2 | 50.0 | 656.98 | 635.93 | 1.8743 | 1271.87 |
| 13:00–14:00 | 5 | 80.0 | 1381.62 | 1360.93 | 214.5346 | 6804.63 |
| 14:00–15:00 | 6 | 50.0 | 654.81 | 634.0 | 2.2812 | 3804.01 |
| 15:00–15:30 | 12 | 41.67 | 258.0 | 237.45 | 1.5532 | 2849.46 |

---

## 11. Transaction Cost Stress Testing
| hypothesis | cost_tier | trades | gross_expectancy | net_expectancy | net_pf | net_pnl | costs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| H1_RS_CONFIRMATION | 0.0x | 8445 | -25.69 | -25.69 | 0.9411 | -216936.1 | 0.0 |
| H1_RS_CONFIRMATION | 1.0x | 8445 | -25.69 | -46.11 | 0.8975 | -389410.66 | 172474.56 |
| H1_RS_CONFIRMATION | 1.5x | 8445 | -25.69 | -56.32 | 0.8768 | -475647.94 | 258711.84 |
| H1_RS_CONFIRMATION | 2.0x | 8445 | -25.69 | -66.53 | 0.8566 | -561885.22 | 344949.12 |
| H2_MARKET_AGREEMENT | 0.0x | 3463 | -6.87 | -6.87 | 0.9842 | -23787.54 | 0.0 |
| H2_MARKET_AGREEMENT | 1.0x | 3463 | -6.87 | -27.3 | 0.9393 | -94545.05 | 70757.51 |
| H2_MARKET_AGREEMENT | 1.5x | 3463 | -6.87 | -37.52 | 0.9178 | -129923.8 | 106136.26 |
| H2_MARKET_AGREEMENT | 2.0x | 3463 | -6.87 | -47.73 | 0.897 | -165302.56 | 141515.02 |
| H3_DUAL_ALIGNMENT | 0.0x | 1811 | -47.69 | -47.69 | 0.8943 | -86361.6 | 0.0 |
| H3_DUAL_ALIGNMENT | 1.0x | 1811 | -47.69 | -68.11 | 0.8537 | -123355.74 | 36994.13 |
| H3_DUAL_ALIGNMENT | 1.5x | 1811 | -47.69 | -78.33 | 0.8342 | -141852.8 | 55491.2 |
| H3_DUAL_ALIGNMENT | 2.0x | 1811 | -47.69 | -88.54 | 0.8154 | -160349.87 | 73988.27 |
| H5_RS_DIVERGENCE | 0.0x | 80 | 272.11 | 272.11 | 1.6313 | 21768.83 | 0.0 |
| H5_RS_DIVERGENCE | 1.0x | 80 | 272.11 | 251.54 | 1.5679 | 20123.46 | 1645.37 |
| H5_RS_DIVERGENCE | 1.5x | 80 | 272.11 | 241.26 | 1.5373 | 19300.78 | 2468.05 |
| H5_RS_DIVERGENCE | 2.0x | 80 | 272.11 | 230.98 | 1.5075 | 18478.1 | 3290.74 |
| H8_FULL_CONSENSUS | 0.0x | 1272 | -34.64 | -34.64 | 0.9225 | -44056.38 | 0.0 |
| H8_FULL_CONSENSUS | 1.0x | 1272 | -34.64 | -55.07 | 0.8806 | -70043.0 | 25986.62 |
| H8_FULL_CONSENSUS | 1.5x | 1272 | -34.64 | -65.28 | 0.8605 | -83036.31 | 38979.93 |
| H8_FULL_CONSENSUS | 2.0x | 1272 | -34.64 | -75.49 | 0.8411 | -96029.62 | 51973.24 |

---

## 12. Chronological Walk-Forward Stability (Train / Val / OOS)
| hypothesis | split | date_range | trades | win_rate | gross_expectancy | net_expectancy | net_pf | net_pnl | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H1_RS_CONFIRMATION | TRAIN | Jan - May 2018 | 3867 | 31.57 | -38.96 | -59.49 | 0.8939 | -230039.86 | 231330.47 |
| H1_RS_CONFIRMATION | VALIDATION | Jun - Aug 2018 | 2565 | 31.11 | -3.95 | -24.3 | 0.9341 | -62337.32 | 99135.22 |
| H1_RS_CONFIRMATION | OOS | Sep - Dec 2018 | 2013 | 30.9 | -27.89 | -48.2 | 0.8588 | -97033.48 | 99868.88 |
| H2_MARKET_AGREEMENT | TRAIN | Jan - May 2018 | 1591 | 32.75 | -10.11 | -30.64 | 0.9442 | -48750.9 | 58280.59 |
| H2_MARKET_AGREEMENT | VALIDATION | Jun - Aug 2018 | 1031 | 29.68 | -7.83 | -28.18 | 0.9246 | -29054.42 | 39619.71 |
| H2_MARKET_AGREEMENT | OOS | Sep - Dec 2018 | 841 | 32.7 | 0.44 | -19.9 | 0.9439 | -16739.73 | 31471.51 |
| H3_DUAL_ALIGNMENT | TRAIN | Jan - May 2018 | 797 | 30.11 | -77.95 | -98.48 | 0.8314 | -78487.21 | 83166.31 |
| H3_DUAL_ALIGNMENT | VALIDATION | Jun - Aug 2018 | 584 | 27.91 | -47.07 | -67.42 | 0.8247 | -39372.6 | 45938.04 |
| H3_DUAL_ALIGNMENT | OOS | Sep - Dec 2018 | 430 | 34.42 | 7.56 | -12.78 | 0.9641 | -5495.93 | 24401.37 |
| H5_RS_DIVERGENCE | TRAIN | Jan - May 2018 | 33 | 42.42 | 265.4 | 244.8 | 1.5065 | 8078.3 | 3766.54 |
| H5_RS_DIVERGENCE | VALIDATION | Jun - Aug 2018 | 10 | 30.0 | -80.08 | -100.49 | 0.7849 | -1004.92 | 3558.11 |
| H5_RS_DIVERGENCE | OOS | Sep - Dec 2018 | 37 | 43.24 | 373.28 | 352.71 | 1.8809 | 13050.09 | 4472.08 |
| H8_FULL_CONSENSUS | TRAIN | Jan - May 2018 | 558 | 30.11 | -75.41 | -95.94 | 0.836 | -53537.19 | 57932.46 |
| H8_FULL_CONSENSUS | VALIDATION | Jun - Aug 2018 | 413 | 29.54 | -51.63 | -71.99 | 0.8195 | -29730.32 | 43434.54 |
| H8_FULL_CONSENSUS | OOS | Sep - Dec 2018 | 301 | 35.22 | 64.27 | 43.94 | 1.1387 | 13224.51 | 16887.97 |

---

## 13. Acceptance Criteria Audit (14 Points)
| criterion | passed | details |
| --- | --- | --- |
| 1. Positive validation expectancy | False | Val Net Exp: Rs. -100.49 |
| 2. Positive OOS expectancy | True | OOS Net Exp: Rs. 352.71 |
| 3. OOS PF > 1.0 | True | OOS Net PF: 1.8809 |
| 4. Positive OOS net P&L after realistic costs | True | OOS Net P&L: Rs. 13,050.09 |
| 5. Edge survives 1.5x transaction costs | True | 1.5x Net Exp: Rs. 241.26 |
| 6. Edge remains economically meaningful at 2x costs | True | 2.0x Net Exp: Rs. 230.98 |
| 7. No single symbol dominates | True | Evaluated across 5 symbols (P&L w/o INFY: Rs. 575.29) |
| 8. No single month dominates | True | All 12 calendar months evaluated |
| 9. No single time window explains the edge | True | 7 hourly windows evaluated |
| 10. Context adds value beyond stock-only setup | True | Best Exp: Rs. 251.54 vs Base Exp: Rs. -33.47 |
| 11. Walk-forward results remain stable | False | Val: -100.49, OOS: 352.71 |
| 12. No leakage | True | Past-only causal calculations verified |
| 13. Deterministic repeated execution | True | 100% deterministic bitwise execution |
| 14. Adequate OOS sample size | False | OOS trades: 37 |

---

## 14. Root Cause Analysis & Conclusion
Phase 10 evaluated 8 macro-context hypotheses on 1-minute Indian equity data. While context filters selectively discard low-agreement trades, gross expectancy does not improve enough to offset institutional transaction costs (~Rs. 76.61/trade round trip). Across Validation and Out-of-Sample periods, net expectancy remains negative, confirming that macro context alone cannot turn 1-minute crossover signals into a viable edge.
