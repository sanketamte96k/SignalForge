# SignalForge — Phase 11: H5 RS Divergence Forensic Robustness Report

## 1. Executive Summary & Objective
Phase 11 conducted an isolated forensic robustness audit on **`H5_RS_DIVERGENCE`**, the sole candidate in Phase 10 with positive net P&L.

### Primary Verdict: **SYMBOL-CONCENTRATED / INSUFFICIENT SAMPLE**
**ROBUST EDGE FOUND: NO**
- **Recommendation**: DO NOT promote to production. Insufficient statistical sample and severe single-stock reliance.

---

## 2. Overall Comparison (Baseline vs H5)
| configuration | trades | win_rate | gross_expectancy | net_expectancy | gross_pf | net_pf | net_pnl | max_drawdown | trades_per_day | pct_baseline |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BASELINE (All Trades) | 11222 | 31.73 | -13.04 | -33.47 | 0.9698 | 0.9248 | -375554.43 | 374534.64 | 45.62 | 100.0 |
| H5_RS_DIVERGENCE (Candidate) | 80 | 41.25 | 272.11 | 251.54 | 1.6313 | 1.5679 | 20123.46 | 6406.4 | 0.33 | 0.71 |

---

## 3. Symbol Robustness & Concentration Audit
| symbol_group | trades | win_rate | gross_pnl | costs | net_pnl | gross_pf | net_pf | net_expectancy | max_drawdown | pnl_contribution_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL SYMBOLS | 80 | 41.25 | 21768.83 | 1645.37 | 20123.46 | 1.6313 | 1.5679 | 251.54 | 6406.4 | 100.0 |
| WITHOUT INFY | 48 | 35.42 | 1548.92 | 973.64 | 575.29 | 1.1204 | 1.0427 | 11.99 | 4536.72 | 2.86 |
| RELIANCE | 9 | 33.33 | -1876.96 | 181.86 | -2058.82 | 0.3299 | 0.2955 | -228.76 | 1755.64 | -10.23 |
| TCS | 19 | 42.11 | 5959.68 | 388.19 | 5571.49 | 2.1444 | 2.026 | 293.24 | 1553.01 | 27.69 |
| INFY | 32 | 50.0 | 20219.91 | 671.73 | 19548.18 | 1.9351 | 1.8904 | 610.88 | 4472.08 | 97.14 |
| HDFCBANK | 9 | 44.44 | 954.27 | 181.29 | 772.98 | 2.1776 | 1.8536 | 85.89 | 815.88 | 3.84 |
| ICICIBANK | 11 | 18.18 | -3488.06 | 222.3 | -3710.36 | 0.1371 | 0.1216 | -337.31 | 2776.07 | -18.44 |

- **INFY Dependency**: INFY accounts for **97.14%** of all net profits (Rs. 19,548.18 of Rs. 20,123.46).
- **Ex-INFY Performance**: With INFY removed, 2018 net P&L drops to **Rs. 575.29** across 48 trades.

---

## 4. Symbol Exclusion Matrix (Leave-One-Out)
| excluded_symbol | remaining_trades | win_rate | net_expectancy | net_pf | net_pnl | max_drawdown | pnl_change_from_total_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RELIANCE | 71 | 42.25 | 312.43 | 1.6823 | 22182.29 | 6406.4 | 10.23 |
| TCS | 61 | 40.98 | 238.56 | 1.485 | 14551.97 | 6406.4 | -27.69 |
| INFY | 48 | 35.42 | 11.99 | 1.0427 | 575.29 | 4536.72 | -97.14 |
| HDFCBANK | 71 | 40.85 | 272.54 | 1.5604 | 19350.49 | 7179.38 | -3.84 |
| ICICIBANK | 69 | 44.93 | 345.42 | 1.7636 | 23833.82 | 4472.08 | 18.44 |

---

## 5. Monthly Robustness & Concentration
| month | trades | win_rate | gross_expectancy | net_expectancy | net_pf | net_pnl | contribution_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2018-01 | 3 | 33.33 | -85.95 | -106.46 | 0.8106 | -319.37 | -1.59 |
| 2018-02 | 13 | 38.46 | 84.08 | 63.53 | 1.121 | 825.88 | 4.1 |
| 2018-03 | 6 | 66.67 | 595.55 | 574.86 | 2.4614 | 3449.18 | 17.14 |
| 2018-04 | 5 | 40.0 | 418.72 | 398.12 | 1.981 | 1990.59 | 9.89 |
| 2018-05 | 6 | 33.33 | 376.02 | 355.34 | 1.6997 | 2132.03 | 10.59 |
| 2018-06 | 2 | 0.0 | -404.39 | -424.59 | 0.0 | -849.18 | -4.22 |
| 2018-07 | 5 | 60.0 | 407.97 | 387.43 | 2.1199 | 1937.15 | 9.63 |
| 2018-08 | 3 | 0.0 | -677.29 | -697.63 | 0.0 | -2092.89 | -10.4 |
| 2018-09 | 9 | 55.56 | 767.77 | 747.19 | 4.6762 | 6724.73 | 33.42 |
| 2018-10 | 12 | 41.67 | 448.29 | 427.53 | 1.7897 | 5130.39 | 25.49 |
| 2018-11 | 7 | 28.57 | 293.23 | 272.69 | 1.6644 | 1908.81 | 9.49 |
| 2018-12 | 9 | 44.44 | -58.96 | -79.32 | 0.8025 | -713.85 | -3.55 |

- **Best Month**: `2018-09` contributed **33.42%** of total profits.
- **P&L without Best Month**: Rs. 13,398.74.

---

## 6. Directional Robustness (Long vs Short)
| direction | trades | pct_total_trades | win_rate | gross_expectancy | net_expectancy | gross_pf | net_pf | net_pnl | avg_winner | avg_loser | max_drawdown | max_loss_streak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LONG | 48 | 60.0 | 43.75 | 330.46 | 309.91 | 1.8644 | 1.7871 | 14875.63 | 1608.37 | -700.0 | 3558.11 | 6 |
| SHORT | 32 | 40.0 | 37.5 | 184.59 | 163.99 | 1.3661 | 1.3174 | 5247.84 | 1815.28 | -826.78 | 5376.4 | 6 |

---

## 7. Cost Stress & Breakeven Analysis
| cost_tier | trades | gross_expectancy | net_expectancy | net_pf | net_pnl | total_costs |
| --- | --- | --- | --- | --- | --- | --- |
| 0.0x | 80 | 272.11 | 272.11 | 1.6313 | 21768.83 | 0.0 |
| 1.0x | 80 | 272.11 | 251.54 | 1.5679 | 20123.46 | 1645.37 |
| 1.5x | 80 | 272.11 | 241.26 | 1.5373 | 19300.78 | 2468.05 |
| 2.0x | 80 | 272.11 | 230.98 | 1.5075 | 18478.1 | 3290.74 |
| 2.5x | 80 | 272.11 | 220.69 | 1.4785 | 17655.41 | 4113.42 |
| 3.0x | 80 | 272.11 | 210.41 | 1.4502 | 16832.73 | 4936.1 |

- **Breakeven Cost Multiplier**: **13.23x** transaction costs.

---

## 8. Parameter Perturbation & Stability Grid
| rs_threshold | bm_threshold | is_baseline | trades | win_rate | net_expectancy | net_pf | net_pnl | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.002 | 0.0003 | False | 218 | 37.16 | 145.26 | 1.3326 | 31666.62 | 7944.03 |
| 0.002 | 0.0004 | False | 213 | 37.56 | 157.24 | 1.3603 | 33492.68 | 7944.03 |
| 0.002 | 0.0005 | False | 211 | 37.44 | 146.49 | 1.3331 | 30908.89 | 7944.03 |
| 0.002 | 0.0006 | False | 210 | 37.62 | 147.2 | 1.3331 | 30911.81 | 7944.03 |
| 0.002 | 0.0007 | False | 208 | 37.98 | 154.86 | 1.352 | 32210.36 | 7842.51 |
| 0.0025 | 0.0003 | False | 122 | 34.43 | 109.84 | 1.2463 | 13400.3 | 10127.4 |
| 0.0025 | 0.0004 | False | 118 | 34.75 | 125.5 | 1.2817 | 14808.5 | 10182.4 |
| 0.0025 | 0.0005 | False | 117 | 34.19 | 103.19 | 1.2297 | 12072.86 | 10182.4 |
| 0.0025 | 0.0006 | False | 116 | 34.48 | 104.1 | 1.2297 | 12075.78 | 10179.48 |
| 0.0025 | 0.0007 | False | 115 | 34.78 | 106.7 | 1.2343 | 12270.91 | 10179.48 |
| 0.003 | 0.0003 | False | 82 | 42.68 | 283.96 | 1.6571 | 23284.76 | 6041.6 |
| 0.003 | 0.0004 | False | 81 | 41.98 | 282.21 | 1.6451 | 22859.1 | 6406.4 |
| 0.003 | 0.0005 | True | 80 | 41.25 | 251.54 | 1.5679 | 20123.46 | 6406.4 |
| 0.003 | 0.0006 | False | 80 | 41.25 | 251.54 | 1.5679 | 20123.46 | 6406.4 |
| 0.003 | 0.0007 | False | 80 | 41.25 | 251.54 | 1.5679 | 20123.46 | 6406.4 |
| 0.0035 | 0.0003 | False | 54 | 44.44 | 336.71 | 1.7677 | 18182.32 | 4123.93 |
| 0.0035 | 0.0004 | False | 53 | 43.4 | 335.03 | 1.7498 | 17756.66 | 4123.93 |
| 0.0035 | 0.0005 | False | 53 | 43.4 | 335.03 | 1.7498 | 17756.66 | 4123.93 |
| 0.0035 | 0.0006 | False | 53 | 43.4 | 335.03 | 1.7498 | 17756.66 | 4123.93 |
| 0.0035 | 0.0007 | False | 53 | 43.4 | 335.03 | 1.7498 | 17756.66 | 4123.93 |
| 0.004 | 0.0003 | False | 39 | 33.33 | 98.14 | 1.1896 | 3827.43 | 6791.27 |
| 0.004 | 0.0004 | False | 38 | 31.58 | 89.52 | 1.1686 | 3401.77 | 6791.27 |
| 0.004 | 0.0005 | False | 38 | 31.58 | 89.52 | 1.1686 | 3401.77 | 6791.27 |
| 0.004 | 0.0006 | False | 38 | 31.58 | 89.52 | 1.1686 | 3401.77 | 6791.27 |
| 0.004 | 0.0007 | False | 38 | 31.58 | 89.52 | 1.1686 | 3401.77 | 6791.27 |

- **Grid Survival Rate**: 100.0% of neighboring grids produce positive net P&L.

---

## 9. Trade Distribution & Winner Dependency
| metric | value |
| --- | --- |
| total_trades | 80.0 |
| mean_net_expectancy | 251.54 |
| median_net_pnl | -147.55 |
| std_dev_pnl | 1417.07 |
| p25_pnl | -825.67 |
| p75_pnl | 1382.91 |
| iqr_pnl | 2208.58 |
| largest_winner | 2945.72 |
| largest_loser | -1988.2 |
| top_1pct_winners_pnl | 2945.72 |
| top_1pct_pnl_share_pct | 14.64 |
| top_5pct_winners_pnl | 11622.19 |
| top_5pct_pnl_share_pct | 57.75 |
| top_10pct_winners_pnl | 22409.91 |
| top_10pct_pnl_share_pct | 111.36 |

---

## 10. MAE / MFE Adverse Excursion Analysis
| excursion_metric | value |
| --- | --- |
| mean_mfe_pts | 3.92 |
| median_mfe_pts | 2.81 |
| mean_mfe_pct | 0.425 |
| mean_mae_pts | 2.86 |
| median_mae_pts | 1.67 |
| mean_mae_pct | 0.297 |
| mfe_to_mae_ratio | 1.37 |

---

## 11. Chronological Walk-Forward Stability
| split | date_range | trades | win_rate | gross_expectancy | net_expectancy | net_pf | net_pnl | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TRAIN | Jan - May 2018 | 33 | 42.42 | 265.4 | 244.8 | 1.5065 | 8078.3 | 3766.54 |
| VALIDATION | Jun - Aug 2018 | 10 | 30.0 | -80.08 | -100.49 | 0.7849 | -1004.92 | 3558.11 |
| OOS | Sep - Dec 2018 | 37 | 43.24 | 373.28 | 352.71 | 1.8809 | 13050.09 | 4472.08 |

- **Validation Drawdown**: Jun–Aug 2018 experienced **-Rs. 100.49 net expectancy** (Net PF: 0.7849).

---

## 12. Quarterly Rolling Walk-Forward
| quarter | trades | win_rate | gross_expectancy | net_expectancy | net_pf | net_pnl | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Q1_2018 | 22 | 45.45 | 200.39 | 179.8 | 1.3638 | 3955.68 | 2950.66 |
| Q2_2018 | 13 | 30.77 | 272.38 | 251.8 | 1.5524 | 3273.44 | 2485.44 |
| Q3_2018 | 17 | 47.06 | 406.94 | 386.41 | 2.1623 | 6568.99 | 3558.11 |
| Q4_2018 | 28 | 39.29 | 246.48 | 225.91 | 1.4871 | 6325.35 | 4472.08 |

---

## 13. Concentration & Dependency Metrics
| dimension | value | threshold_limit | risk_flag |
| --- | --- | --- | --- |
| symbol_infy_share_pct | 97.14 | 50.0 | True |
| symbol_pnl_without_infy | 575.29 | 0.0 | False |
| month_best_month_share_pct | 33.42 | 50.0 | False |
| month_pnl_without_best_month | 13398.74 | 0.0 | False |
| top_1pct_winner_share_pct | 14.64 | 25.0 | False |
| top_5pct_winner_share_pct | 57.75 | 50.0 | True |
| top_10pct_winner_share_pct | 111.36 | 70.0 | True |
| sample_size_trades | 80.0 | 200.0 | True |

---

## 14. Forensic Falsification Audit (8 Flags)
| falsification_flag | flagged | details |
| --- | --- | --- |
| 1. INSUFFICIENT_SAMPLE_SIZE | True | Total trades 80 (< 200 threshold). OOS trades: 37 (< 200). |
| 2. SYMBOL_CONCENTRATION_RISK | True | INFY accounts for 97.14% of total net profits. P&L w/o INFY: Rs. 575.29. |
| 3. MONTH_CONCENTRATION_RISK | False | Best month (2018-09) accounts for 33.42% of profits. |
| 4. DIRECTIONAL_ASYMMETRY | False | Long win rate 43.75% vs Short win rate 37.5%. Both directions traded. |
| 5. PARAMETER_FRAGILITY | False | 100.0% of neighboring parameter combinations profitable. |
| 6. COST_FRAGILITY | False | Breakeven multiplier is 13.23x costs. |
| 7. VALIDATION_FAILURE | True | Validation net expectancy is negative: -Rs. 100.49. |
| 8. WINNER_DEPENDENCY | False | Top 5% of winners contribute 57.75% of total net profits. |

---

## 15. Forensic Conclusion & Governance Decision
While `H5_RS_DIVERGENCE` demonstrates genuine counter-trend characteristics with high cost survival (13.23x breakeven) and positive OOS return, it is **disqualified from production promotion** due to:
1. **Severe single-stock concentration** (INFY = 97.14% of profits).
2. **Extreme sample scarcity** (80 trades across the entire year 2018; only 0.33 trades/day).
3. **Validation drawdown** (-Rs. 100.49 net expectancy in Jun–Aug 2018).
