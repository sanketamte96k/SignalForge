# SignalForge — Phase 9: Selective Signal Engine Research Report

## 1. Executive Summary & Core Hypothesis
Phase 9 evaluated whether a causal, multi-pillar selective signal engine with quality scoring (0–100) can selectively identify high-quality trading opportunities and reject low-quality noise from the 11,222 validated 2018 baseline trades on 1-minute Indian equity data.

The engine scores every candidate setup at entry timestamp $T$ using 8 causal pillars:
- **Trend Quality (0–20)**
- **Momentum Strength (0–15)**
- **Pullback Depth (0–15)**
- **Market Location (0–15)**
- **Volatility Contraction/Expansion (0–10)**
- **Price Action Confirmation (0–10)**
- **Time-of-Day Context (0–5)**
- **Risk/Reward Geometry (0–10)**

### Primary Verdict
**ROBUST EDGE FOUND: NO**
Criteria Met: 6/14.

---

## 2. Baseline vs Selective Configuration
| Metric | Baseline | Phase 9 Selective (Score >= 40) |
| :--- | :--- | :--- |
| **Total Trades / Signals** | 11,222 | 11,222.0 (100.0%) |
| **Gross Win Rate** | 41.69% | 31.73% |
| **Gross Expectancy** | Rs. 43.14 | Rs. -13.04 |
| **Net Expectancy** | Rs. -33.47 | Rs. -33.47 |
| **Gross Profit Factor** | 1.1097 | 0.9698 |
| **Net Profit Factor** | 0.9248 | 0.9248 |
| **Net P&L** | -Rs. 375,554.43 | Rs. -375,554.43 |
| **Max Drawdown** | Rs. 411,467.55 | Rs. 374,534.64 |
| **Trades / Day** | 45.62 | 45.62 |

---

## 3. Score Bucket Monotonicity Analysis
The 8-pillar quality score was partitioned into 7 intervals to test whether higher scores monotonically improve net expectancy:

| bucket | trades | pct_of_total | win_rate | gross_expectancy | net_expectancy | gross_pf | net_pf | net_pnl | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0–39 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 40–49 | 1 | 0.01 | 100.0 | 1553.76 | 1532.98 | 999.0 | 999.0 | 1532.98 | 0.0 |
| 50–59 | 164 | 1.46 | 41.46 | 110.85 | 90.38 | 1.2686 | 1.2128 | 14821.84 | 10604.03 |
| 60–69 | 2013 | 17.94 | 33.38 | 7.68 | -12.73 | 1.0187 | 0.97 | -25628.39 | 68504.56 |
| 70–79 | 4533 | 40.39 | 33.18 | 23.9 | 3.47 | 1.057 | 1.008 | 15732.57 | 96048.99 |
| 80–89 | 4111 | 36.63 | 29.48 | -53.81 | -74.24 | 0.8809 | 0.8407 | -305187.82 | 311107.77 |
| 90–100 | 400 | 3.56 | 26.0 | -171.68 | -192.06 | 0.6326 | 0.6018 | -76825.61 | 77121.69 |

---

## 4. Threshold Sensitivity Analysis
| threshold | total_signals | long_signals | short_signals | pct_retained | trades_per_day | win_rate | gross_expectancy | net_expectancy | gross_pf | net_pf | gross_pnl | transaction_costs | net_pnl | avg_winner | avg_loser | max_drawdown | max_loss_streak |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 40.0 | 11222.0 | 5615.0 | 5607.0 | 100.0 | 45.62 | 31.73 | -13.04 | -33.47 | 0.9698 | 0.9248 | -146346.59 | 229207.84 | -375554.43 | 1297.62 | -652.18 | 374534.64 | 55.0 |
| 50.0 | 11221.0 | 5615.0 | 5606.0 | 99.99 | 45.61 | 31.73 | -13.18 | -33.61 | 0.9694 | 0.9245 | -147900.35 | 229187.07 | -377087.41 | 1297.55 | -652.18 | 376067.62 | 55.0 |
| 60.0 | 11057.0 | 5529.0 | 5528.0 | 98.53 | 44.95 | 31.58 | -15.02 | -35.44 | 0.9652 | 0.9205 | -166078.97 | 225830.29 | -391909.26 | 1298.63 | -651.25 | 390889.47 | 54.0 |
| 70.0 | 9044.0 | 4519.0 | 4525.0 | 80.59 | 36.76 | 31.18 | -20.07 | -40.5 | 0.954 | 0.91 | -181546.37 | 184734.5 | -366280.87 | 1313.9 | -654.16 | 368927.03 | 49.0 |
| 75.0 | 6894.0 | 3468.0 | 3426.0 | 61.43 | 28.02 | 30.29 | -34.78 | -55.21 | 0.9207 | 0.8781 | -239799.85 | 140783.61 | -380583.46 | 1312.44 | -649.39 | 387781.59 | 41.0 |
| 80.0 | 4511.0 | 2292.0 | 2219.0 | 40.2 | 18.34 | 29.17 | -64.26 | -84.68 | 0.8581 | 0.8188 | -289894.72 | 92118.71 | -382013.43 | 1311.9 | -659.93 | 386303.47 | 30.0 |
| 85.0 | 2068.0 | 1048.0 | 1020.0 | 18.43 | 8.41 | 28.43 | -87.66 | -108.07 | 0.8066 | 0.769 | -181282.19 | 42206.64 | -223488.83 | 1265.0 | -653.59 | 231553.42 | 23.0 |
| 90.0 | 400.0 | 215.0 | 185.0 | 3.56 | 1.63 | 26.0 | -171.68 | -192.06 | 0.6326 | 0.6018 | -68673.01 | 8152.6 | -76825.61 | 1116.61 | -651.87 | 77121.69 | 11.0 |

---

## 5. Regime-Conditional Breakdown
| regime | total_baseline_trades | filtered_trades | win_rate | net_expectancy | net_pf | net_pnl | long_trades | long_net_exp | short_trades | short_net_exp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TREND_UP | 1 | 1 | 100.0 | 1556.7 | 999.0 | 1556.7 | 1 | 1556.7 | 0 | 0.0 |
| TREND_DOWN | 0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0.0 | 0 | 0.0 |
| RANGE | 6347 | 6347 | 31.98 | -30.24 | 0.9288 | -191954.51 | 3112 | -69.74 | 3235 | 7.76 |
| HIGH_VOLATILITY | 1339 | 1339 | 32.56 | 0.27 | 1.0006 | 356.09 | 693 | 6.53 | 646 | -6.46 |
| LOW_VOLATILITY | 664 | 664 | 35.54 | 69.94 | 1.1552 | 46442.24 | 327 | 100.21 | 337 | 40.57 |
| TRANSITION | 2871 | 2871 | 29.89 | -80.79 | 0.8289 | -231954.94 | 1482 | -79.86 | 1389 | -81.79 |

---

## 6. Cross-Symbol Robustness
| symbol | baseline_trades | filtered_trades | win_rate | gross_expectancy | net_expectancy | net_pf | net_pnl | pnl_contribution_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RELIANCE | 2571 | 2571 | 32.48 | -15.44 | -35.77 | 0.8986 | -91972.31 | 24.49 |
| TCS | 1799 | 1799 | 28.35 | -35.27 | -55.57 | 0.8351 | -99976.91 | 26.62 |
| INFY | 2460 | 2460 | 34.35 | 25.6 | 4.7 | 1.0052 | 11554.46 | -3.08 |
| HDFCBANK | 1825 | 1825 | 29.53 | -34.58 | -54.8 | 0.7755 | -100002.5 | 26.63 |
| ICICIBANK | 2567 | 2567 | 32.41 | -16.77 | -37.07 | 0.8848 | -95157.16 | 25.34 |

---

## 7. Monthly Performance Stability
| month | trades | win_rate | gross_expectancy | net_expectancy | net_pf | net_pnl |
| --- | --- | --- | --- | --- | --- | --- |
| 2018-01 | 1082 | 31.05 | -68.63 | -89.18 | 0.85 | -96488.08 |
| 2018-02 | 901 | 35.41 | 57.25 | 36.69 | 1.0675 | 33060.4 |
| 2018-03 | 954 | 33.65 | -0.6 | -21.15 | 0.9623 | -20173.81 |
| 2018-04 | 1074 | 32.77 | -11.11 | -31.65 | 0.9436 | -33994.69 |
| 2018-05 | 1185 | 30.38 | -48.67 | -69.13 | 0.8592 | -81913.24 |
| 2018-06 | 1064 | 31.86 | -10.32 | -30.69 | 0.9211 | -32658.54 |
| 2018-07 | 1162 | 31.93 | 44.71 | 24.36 | 1.072 | 28311.33 |
| 2018-08 | 1089 | 29.38 | -27.01 | -47.37 | 0.8756 | -51580.93 |
| 2018-09 | 773 | 30.4 | -39.0 | -59.3 | 0.8227 | -45838.33 |
| 2018-10 | 688 | 31.1 | -22.03 | -42.41 | 0.8941 | -29178.59 |
| 2018-11 | 624 | 30.93 | -38.04 | -58.34 | 0.8251 | -36405.54 |
| 2018-12 | 626 | 32.11 | 6.39 | -13.89 | 0.9516 | -8694.4 |

---

## 8. Time-of-Day Distribution
| window | trades | win_rate | gross_expectancy | net_expectancy | net_pf | net_pnl |
| --- | --- | --- | --- | --- | --- | --- |
| 09:15–10:00 | 1416 | 34.39 | 32.25 | 11.82 | 1.0274 | 16735.92 |
| 10:00–11:00 | 1635 | 31.01 | -18.16 | -38.59 | 0.914 | -63086.53 |
| 11:00–12:00 | 1707 | 32.57 | -21.78 | -42.2 | 0.9052 | -72042.71 |
| 12:00–13:00 | 1769 | 30.58 | -50.01 | -70.42 | 0.8457 | -124580.01 |
| 13:00–14:00 | 1876 | 31.34 | -11.19 | -31.61 | 0.9287 | -59305.35 |
| 14:00–15:00 | 1874 | 30.42 | -26.44 | -46.87 | 0.8961 | -87828.02 |
| 15:00–15:30 | 945 | 33.02 | 35.84 | 15.4 | 1.0357 | 14552.27 |

---

## 9. Transaction Cost Stress Testing
| threshold | cost_tier | trades | gross_expectancy | net_expectancy | net_pf | net_pnl | costs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 40 | 0.0x | 11222 | -13.04 | -13.04 | 0.9698 | -146346.59 | 0.0 |
| 40 | 1.0x | 11222 | -13.04 | -33.47 | 0.9248 | -375554.43 | 229207.84 |
| 40 | 1.5x | 11222 | -13.04 | -43.68 | 0.9034 | -490158.35 | 343811.76 |
| 40 | 2.0x | 11222 | -13.04 | -53.89 | 0.8826 | -604762.27 | 458415.69 |
| 50 | 0.0x | 11221 | -13.18 | -13.18 | 0.9694 | -147900.35 | 0.0 |
| 50 | 1.0x | 11221 | -13.18 | -33.61 | 0.9245 | -377087.41 | 229187.07 |
| 50 | 1.5x | 11221 | -13.18 | -43.82 | 0.9031 | -491680.95 | 343780.6 |
| 50 | 2.0x | 11221 | -13.18 | -54.03 | 0.8823 | -606274.48 | 458374.13 |
| 60 | 0.0x | 11057 | -15.02 | -15.02 | 0.9652 | -166078.97 | 0.0 |
| 60 | 1.0x | 11057 | -15.02 | -35.44 | 0.9205 | -391909.26 | 225830.29 |
| 60 | 1.5x | 11057 | -15.02 | -45.66 | 0.8991 | -504824.4 | 338745.43 |
| 60 | 2.0x | 11057 | -15.02 | -55.87 | 0.8784 | -617739.54 | 451660.58 |
| 70 | 0.0x | 9044 | -20.07 | -20.07 | 0.954 | -181546.37 | 0.0 |
| 70 | 1.0x | 9044 | -20.07 | -40.5 | 0.91 | -366280.87 | 184734.5 |
| 70 | 1.5x | 9044 | -20.07 | -50.71 | 0.8891 | -458648.12 | 277101.75 |
| 70 | 2.0x | 9044 | -20.07 | -60.93 | 0.8687 | -551015.37 | 369468.99 |
| 75 | 0.0x | 6894 | -34.78 | -34.78 | 0.9207 | -239799.85 | 0.0 |
| 75 | 1.0x | 6894 | -34.78 | -55.21 | 0.8781 | -380583.46 | 140783.61 |
| 75 | 1.5x | 6894 | -34.78 | -65.42 | 0.8577 | -450975.26 | 211175.41 |
| 75 | 2.0x | 6894 | -34.78 | -75.63 | 0.838 | -521367.06 | 281567.21 |
| 80 | 0.0x | 4511 | -64.26 | -64.26 | 0.8581 | -289894.72 | 0.0 |
| 80 | 1.0x | 4511 | -64.26 | -84.68 | 0.8188 | -382013.43 | 92118.71 |
| 80 | 1.5x | 4511 | -64.26 | -94.9 | 0.8001 | -428072.79 | 138178.07 |
| 80 | 2.0x | 4511 | -64.26 | -105.11 | 0.7819 | -474132.15 | 184237.42 |
| 85 | 0.0x | 2068 | -87.66 | -87.66 | 0.8066 | -181282.19 | 0.0 |
| 85 | 1.0x | 2068 | -87.66 | -108.07 | 0.769 | -223488.83 | 42206.64 |
| 85 | 1.5x | 2068 | -87.66 | -118.27 | 0.751 | -244592.15 | 63309.96 |
| 85 | 2.0x | 2068 | -87.66 | -128.48 | 0.7336 | -265695.47 | 84413.28 |
| 90 | 0.0x | 400 | -171.68 | -171.68 | 0.6326 | -68673.01 | 0.0 |
| 90 | 1.0x | 400 | -171.68 | -192.06 | 0.6018 | -76825.61 | 8152.6 |
| 90 | 1.5x | 400 | -171.68 | -202.25 | 0.5872 | -80901.91 | 12228.9 |
| 90 | 2.0x | 400 | -171.68 | -212.45 | 0.5729 | -84978.22 | 16305.21 |

---

## 10. Walk-Forward Stability (Train / Val / OOS)
| threshold | split | date_range | trades | win_rate | gross_expectancy | net_expectancy | net_pf | net_pnl | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 40 | TRAIN | Jan - May 2018 | 5196 | 32.49 | -17.87 | -38.4 | 0.9301 | -199509.41 | 204200.48 |
| 40 | VALIDATION | Jun - Aug 2018 | 3315 | 31.07 | 3.49 | -16.87 | 0.9542 | -55928.15 | 107663.59 |
| 40 | OOS | Sep - Dec 2018 | 2711 | 31.1 | -23.99 | -44.31 | 0.8697 | -120116.87 | 124098.2 |
| 50 | TRAIN | Jan - May 2018 | 5195 | 32.47 | -18.17 | -38.7 | 0.9295 | -201042.4 | 205733.46 |
| 50 | VALIDATION | Jun - Aug 2018 | 3315 | 31.07 | 3.49 | -16.87 | 0.9542 | -55928.15 | 107663.59 |
| 50 | OOS | Sep - Dec 2018 | 2711 | 31.1 | -23.99 | -44.31 | 0.8697 | -120116.87 | 124098.2 |
| 60 | TRAIN | Jan - May 2018 | 5109 | 32.35 | -21.72 | -42.24 | 0.9232 | -215819.09 | 221007.48 |
| 60 | VALIDATION | Jun - Aug 2018 | 3262 | 30.93 | 3.2 | -17.15 | 0.9534 | -55959.39 | 116259.7 |
| 60 | OOS | Sep - Dec 2018 | 2686 | 30.9 | -24.41 | -44.72 | 0.8686 | -120130.77 | 124484.23 |
| 70 | TRAIN | Jan - May 2018 | 4145 | 31.89 | -29.59 | -50.12 | 0.9099 | -207737.13 | 219537.38 |
| 70 | VALIDATION | Jun - Aug 2018 | 2625 | 30.55 | -2.97 | -23.33 | 0.9381 | -61240.32 | 116768.17 |
| 70 | OOS | Sep - Dec 2018 | 2274 | 30.61 | -22.47 | -42.79 | 0.8745 | -97303.42 | 102137.49 |
| 75 | TRAIN | Jan - May 2018 | 3138 | 30.72 | -55.95 | -76.48 | 0.8648 | -239984.82 | 255881.99 |
| 75 | VALIDATION | Jun - Aug 2018 | 1989 | 30.32 | -1.6 | -21.96 | 0.9418 | -43675.48 | 88868.43 |
| 75 | OOS | Sep - Dec 2018 | 1767 | 29.49 | -34.55 | -54.85 | 0.8372 | -96923.16 | 100541.31 |
| 80 | TRAIN | Jan - May 2018 | 2074 | 29.07 | -100.89 | -121.41 | 0.7922 | -251809.47 | 260412.44 |
| 80 | VALIDATION | Jun - Aug 2018 | 1267 | 29.36 | -28.82 | -49.18 | 0.8751 | -62317.09 | 68462.44 |
| 80 | OOS | Sep - Dec 2018 | 1170 | 29.15 | -37.72 | -58.02 | 0.8292 | -67886.87 | 68794.17 |
| 85 | TRAIN | Jan - May 2018 | 923 | 28.39 | -122.89 | -143.42 | 0.7618 | -132374.37 | 142534.85 |
| 85 | VALIDATION | Jun - Aug 2018 | 562 | 29.89 | -43.87 | -64.2 | 0.8264 | -36083.2 | 41268.69 |
| 85 | OOS | Sep - Dec 2018 | 583 | 27.1 | -74.1 | -94.39 | 0.73 | -55031.26 | 58034.8 |
| 90 | TRAIN | Jan - May 2018 | 184 | 22.83 | -263.52 | -284.01 | 0.5609 | -52258.75 | 51425.58 |
| 90 | VALIDATION | Jun - Aug 2018 | 110 | 28.18 | -77.27 | -97.53 | 0.6795 | -10727.82 | 13732.6 |
| 90 | OOS | Sep - Dec 2018 | 106 | 29.25 | -110.24 | -130.56 | 0.6579 | -13839.04 | 18178.22 |

---

## 11. Acceptance Criteria Audit (14 Points)
| criterion | passed | details |
| --- | --- | --- |
| 1. Positive validation expectancy | False | Val Net Exp: Rs. -16.87 |
| 2. Positive OOS expectancy | False | OOS Net Exp: Rs. -44.31 |
| 3. OOS PF > 1.0 | False | OOS Net PF: 0.8697 |
| 4. Positive OOS net P&L after realistic costs | False | OOS Net P&L: Rs. -120,116.87 |
| 5. Edge survives 1.5x transaction costs | False | 1.5x Net Exp: Rs. -43.68 |
| 6. Edge survives 2x costs or acceptably small degradation | False | 2.0x Net Exp: Rs. -53.89 |
| 7. No single symbol contributes majority of profits | True | Evaluated across 5 symbols |
| 8. No single month dominates performance | True | 12 months evaluated |
| 9. No single time window explains entire edge | True | 7 hourly windows evaluated |
| 10. Score buckets demonstrate monotonic improvement | False | Bucket exp: [0.0, 1532.98, 90.38, -12.73, 3.47, -74.24, -192.06] |
| 11. Walk-forward performance remains positive | False | Val: -16.87, OOS: -44.31 |
| 12. No look-ahead detected | True | Past-only feature calculation verified |
| 13. Deterministic repeated execution | True | 100% deterministic |
| 14. Adequate OOS sample size | True | OOS trades: 2711 |

---

## 12. Root Cause Analysis & Research Conclusion
The Phase 9 Selective Signal Engine confirms that while selective scoring produces granular multi-pillar metrics across 8 dimensions, filtering on 1-minute intraday signals alone cannot overcome institutional friction (~Rs. 76.61/trade round-trip costs) across all market regimes. Even at high quality thresholds, negative net expectancy persists out-of-sample. Therefore, no robust edge exists for deployment without higher time-frame structural edge discovery.
