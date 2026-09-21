# SignalForge Phase 14: Multi-Symbol Conditioned ORB Generalization Audit

## Executive Summary

**Final Verdict**: `REJECTED`

Phase 14 tested whether the conditioned 15-minute Long Opening Range Breakout (ORB) strategy—discovered on NIFTY 50 in Phase 13—generalizes across a diversified universe of 10 liquid NSE equities without per-symbol re-optimization or cherry-picking.

### Key Audit Takeaways

- **Symbol Universe**: 10 liquid NSE equities evaluated on 1-minute historical data (2017–2021).
- **Profitable Symbols**: **2 / 10 (20.0%)**
- **Median Symbol Expectancy**: **Rs. -46.88 / trade** | **Median Profit Factor: 1.25**
- **10-Equity Portfolio Net P&L**: **Rs. -107,122.18** (Profit Factor: **1.10**, Win Rate: **42.53%**)
- **Leave-One-Symbol-Out (Excluding Best Performer INFY)**: Net P&L remains **Rs. -115,402.88** (PF: **1.06**)
- **Friction Survival**: The portfolio does not survive transaction friction across single equities.

## 1. Symbol Universe & Data Quality

| symbol | first_timestamp | last_timestamp | total_candles | trading_days | duplicate_timestamps | ohlc_valid | missing_values | raw_missing_dropped | zero_volume_pct | coverage_years |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RELIANCE | 2017-01-02 09:15:00 | 2021-01-01 15:29:00 | 370405 | 992 | 0 | True | 0 | 564 | 0.0 | 2017-2018-2019-2020-2021 |
| INFY | 2017-01-02 09:15:00 | 2021-01-01 15:29:00 | 370405 | 992 | 0 | True | 0 | 564 | 0.02 | 2017-2018-2019-2020-2021 |
| HDFCBANK | 2017-01-02 09:15:00 | 2021-01-01 15:29:00 | 370405 | 992 | 0 | True | 0 | 564 | 0.02 | 2017-2018-2019-2020-2021 |
| ICICIBANK | 2017-01-02 09:15:00 | 2021-01-01 15:29:00 | 370404 | 992 | 0 | True | 0 | 564 | 0.02 | 2017-2018-2019-2020-2021 |
| SBIN | 2017-01-02 09:15:00 | 2021-01-01 15:29:00 | 370404 | 992 | 0 | True | 0 | 564 | 0.0 | 2017-2018-2019-2020-2021 |
| ITC | 2017-01-02 09:15:00 | 2021-01-01 15:29:00 | 370404 | 992 | 0 | True | 0 | 564 | 0.02 | 2017-2018-2019-2020-2021 |
| LT | 2017-01-02 09:15:00 | 2021-01-01 15:29:00 | 370404 | 992 | 0 | True | 0 | 564 | 0.0 | 2017-2018-2019-2020-2021 |
| AXISBANK | 2017-01-02 09:15:00 | 2021-01-01 15:29:00 | 370408 | 992 | 0 | True | 0 | 552 | 0.0 | 2017-2018-2019-2020-2021 |
| BHARTIARTL | 2017-01-02 09:15:00 | 2021-01-01 15:29:00 | 370408 | 992 | 0 | True | 0 | 552 | 0.01 | 2017-2018-2019-2020-2021 |
| KOTAKBANK | 2017-01-02 09:15:00 | 2021-01-01 15:29:00 | 370405 | 992 | 0 | True | 0 | 564 | 0.0 | 2017-2018-2019-2020-2021 |
| NIFTY50 | 2015-01-09 09:15:00 | 2024-03-26 15:29:00 | 847814 | 2261 | 0 | True | 0 | 0 | 100.0 | 2015-2016-2017-2018-2019-2020-2021-2022-2023-2024 |

*Note: TCS continuous 1-minute historical data was not present in the repository; per prompt rules, TCS was excluded without fabrication and replaced with KOTAKBANK, the next largest private sector bank / NIFTY constituent.*

## 2. Symbol-Level Performance Comparison (Baseline vs Conditioned)

| symbol | base_trades | base_win_rate | base_net_pnl | base_pf | cond_trades | cond_win_rate | cond_net_pnl | cond_pf | cond_expectancy | cond_mdd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RELIANCE | 490 | 44.49 | -65357.47 | 0.98 | 122 | 44.26 | -2886.13 | 1.28 | -23.66 | 16008.12 |
| INFY | 447 | 43.85 | -63321.28 | 0.96 | 107 | 51.4 | 8280.7 | 1.81 | 77.39 | 9916.58 |
| HDFCBANK | 473 | 43.97 | -60950.81 | 0.98 | 122 | 44.26 | -8551.71 | 1.23 | -70.1 | 11151.66 |
| ICICIBANK | 477 | 46.75 | -21075.99 | 1.16 | 98 | 39.8 | -1871.2 | 1.26 | -19.09 | 11077.27 |
| SBIN | 504 | 43.65 | -91736.4 | 0.91 | 169 | 40.83 | -33925.66 | 0.86 | -200.74 | 39673.91 |
| ITC | 442 | 38.01 | -67646.38 | 0.94 | 156 | 41.67 | -17367.46 | 1.03 | -111.33 | 26327.0 |
| LT | 467 | 33.83 | -141069.94 | 0.7 | 165 | 32.73 | -34783.74 | 0.81 | -210.81 | 43230.6 |
| AXISBANK | 485 | 43.92 | -57440.97 | 1.01 | 121 | 39.67 | -20741.45 | 0.91 | -171.42 | 25174.03 |
| BHARTIARTL | 451 | 43.24 | -56976.75 | 1.0 | 104 | 47.12 | 6617.64 | 1.36 | 63.63 | 12706.46 |
| KOTAKBANK | 472 | 47.88 | -23623.11 | 1.15 | 115 | 49.57 | -1893.17 | 1.3 | -16.46 | 7742.09 |
| NIFTY50 | 1195 | 43.01 | -138988.12 | 1.01 | 187 | 41.18 | -20301.81 | 1.06 | -108.57 | 19881.16 |


## 3. Portfolio-Level Aggregation

| universe | strategy | trades | win_rate | gross_pnl | costs | net_pnl | profit_factor | expectancy | max_drawdown | payoff_ratio | train_net_pnl | val_net_pnl | oos_net_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10_EQUITY_PORTFOLIO | BASELINE_15M_LONG | 4708 | 43.01 | -68763.48 | 580435.65 | -649199.1 | 0.97 | -137.89 | 670309.72 | 1.03 | -389620.81 | -259578.29 | 0.0 |
| 10_EQUITY_PORTFOLIO | CONDITIONED_LOW_ATR_ORB | 1279 | 42.53 | 50668.04 | 157790.25 | -107122.18 | 1.1 | -83.75 | 120573.21 | 1.12 | -58451.05 | -48671.13 | 0.0 |
| ALL_SYMBOLS_INC_BENCHMARK | BASELINE_15M_LONG | 5903 | 43.01 | -66026.15 | 722161.07 | -788187.22 | 0.98 | -133.52 | 795959.11 | 1.0 | -464917.86 | -298739.98 | -24529.38 |
| ALL_SYMBOLS_INC_BENCHMARK | CONDITIONED_LOW_ATR_ORB | 1466 | 42.36 | 52755.87 | 180179.89 | -127423.99 | 1.09 | -86.92 | 133896.53 | 1.1 | -78752.86 | -48671.13 | 0.0 |


## 4. Cross-Symbol Robustness & Concentration

- **Total Symbols**: 10
- **Profitable Symbols**: 2 (20.0%)
- **Losing Symbols**: 8
- **Best Performer**: INFY (+Rs. 8,280.70)
- **Worst Performer**: LT (Rs. -34,783.74)
- **Top-1 Concentration Share**: 0.0%
- **Top-3 Concentration Share**: 0.0%

## 5. Leave-One-Symbol-Out (LOSO) Analysis

| case | excluded_symbol | trades | win_rate | net_pnl | profit_factor | expectancy | max_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ALL_10_EQUITIES | NONE | 1279 | 42.53 | -107122.18 | 1.1 | -83.75 | 120573.21 |
| EXCLUDE_BEST_INFY | INFY | 1172 | 41.72 | -115402.88 | 1.06 | -98.47 | 128853.91 |
| EXCLUDE_WORST_LT | LT | 1114 | 43.99 | -72338.44 | 1.14 | -64.94 | 85789.47 |
| EXCLUDE_RELIANCE | RELIANCE | 1157 | 42.35 | -104236.05 | 1.08 | -90.09 | 120264.5 |
| EXCLUDE_INFY | INFY | 1172 | 41.72 | -115402.88 | 1.06 | -98.47 | 128853.91 |
| EXCLUDE_HDFCBANK | HDFCBANK | 1157 | 42.35 | -98570.47 | 1.09 | -85.19 | 119109.13 |
| EXCLUDE_ICICIBANK | ICICIBANK | 1181 | 42.76 | -105250.98 | 1.08 | -89.12 | 118702.01 |
| EXCLUDE_SBIN | SBIN | 1110 | 42.79 | -73196.52 | 1.15 | -65.94 | 86647.55 |
| EXCLUDE_ITC | ITC | 1123 | 42.65 | -89754.72 | 1.1 | -79.92 | 103205.75 |
| EXCLUDE_LT | LT | 1114 | 43.99 | -72338.44 | 1.14 | -64.94 | 85789.47 |
| EXCLUDE_AXISBANK | AXISBANK | 1158 | 42.83 | -86380.73 | 1.12 | -74.59 | 102872.41 |
| EXCLUDE_BHARTIARTL | BHARTIARTL | 1175 | 42.13 | -113739.82 | 1.07 | -96.8 | 124119.75 |
| EXCLUDE_KOTAKBANK | KOTAKBANK | 1164 | 41.84 | -105229.01 | 1.08 | -90.4 | 120573.21 |


## 6. Multi-Symbol Cost Stress Testing

| universe | cost_multiplier | trades | win_rate | gross_pnl | transaction_costs | net_pnl | profit_factor | expectancy | max_drawdown | survives_profitable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10_EQUITY_PORTFOLIO | 0.5 | 1279 | 45.27 | 50668.04 | 78895.08 | -28227.04 | 1.1 | -22.07 | 78094.9 | False |
| ALL_SYMBOLS_INC_BENCHMARK | 0.5 | 1466 | 45.5 | 52755.87 | 90089.91 | -37334.04 | 1.09 | -25.47 | 78094.9 | False |
| 10_EQUITY_PORTFOLIO | 1.0 | 1279 | 42.53 | 50668.04 | 157790.17 | -107122.13 | 1.1 | -83.75 | 120573.12 | False |
| ALL_SYMBOLS_INC_BENCHMARK | 1.0 | 1466 | 42.36 | 52755.87 | 180179.82 | -127423.95 | 1.09 | -86.92 | 133896.49 | False |
| 10_EQUITY_PORTFOLIO | 1.5 | 1279 | 39.33 | 50668.04 | 236685.25 | -186017.21 | 1.1 | -145.44 | 193392.81 | False |
| ALL_SYMBOLS_INC_BENCHMARK | 1.5 | 1466 | 38.81 | 52755.87 | 270269.72 | -217513.85 | 1.09 | -148.37 | 222318.94 | False |
| 10_EQUITY_PORTFOLIO | 2.0 | 1279 | 37.69 | 50668.04 | 315580.33 | -264912.29 | 1.1 | -207.12 | 270358.57 | False |
| ALL_SYMBOLS_INC_BENCHMARK | 2.0 | 1466 | 36.7 | 52755.87 | 360359.63 | -307603.76 | 1.09 | -209.83 | 310741.39 | False |


## 7. Parameter Sensitivity Analysis

| atr_percentile | status | trades | win_rate | gross_pnl | costs | net_pnl | profit_factor | expectancy | max_drawdown | profitable_symbols |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 25.0 | SENSITIVITY_PERTURBATION | 988 | 43.22 | 48041.38 | 121897.3 | -73855.88 | 1.12 | -74.75 | 98434.23 | 4/10 |
| 33.0 | FROZEN_CANDIDATE | 1279 | 42.53 | 50668.04 | 157790.25 | -107122.18 | 1.1 | -83.75 | 120573.21 | 2/10 |
| 40.0 | SENSITIVITY_PERTURBATION | 1554 | 42.47 | 47447.27 | 191705.69 | -144258.4 | 1.07 | -92.83 | 161064.01 | 3/10 |


## 8. MAE / MFE Trade-Path Distribution

| group | identifier | trades | mae_mean_pct | mae_median_pct | mfe_mean_pct | mfe_median_pct |
| --- | --- | --- | --- | --- | --- | --- |
| SYMBOL | RELIANCE | 122 | 0.682 | 0.488 | 0.814 | 0.613 |
| SYMBOL | INFY | 107 | 0.603 | 0.416 | 0.857 | 0.748 |
| SYMBOL | HDFCBANK | 122 | 0.488 | 0.381 | 0.563 | 0.472 |
| SYMBOL | ICICIBANK | 98 | 0.785 | 0.66 | 0.933 | 0.619 |
| SYMBOL | SBIN | 169 | 1.008 | 0.846 | 0.916 | 0.645 |
| SYMBOL | ITC | 156 | 0.771 | 0.597 | 0.813 | 0.532 |
| SYMBOL | LT | 165 | 0.864 | 0.719 | 0.772 | 0.451 |
| SYMBOL | AXISBANK | 121 | 0.917 | 0.791 | 0.906 | 0.632 |
| SYMBOL | BHARTIARTL | 104 | 1.046 | 0.821 | 1.243 | 0.806 |
| SYMBOL | KOTAKBANK | 115 | 0.673 | 0.476 | 0.843 | 0.641 |
| SYMBOL | NIFTY50 | 187 | 0.369 | 0.237 | 0.327 | 0.255 |
| YEAR | 2017 | 838 | 0.726 | 0.548 | 0.829 | 0.58 |
| YEAR | 2018 | 204 | 0.765 | 0.584 | 0.899 | 0.639 |
| YEAR | 2019 | 99 | 0.933 | 0.742 | 0.992 | 0.575 |
| YEAR | 2020 | 138 | 1.145 | 0.98 | 0.869 | 0.526 |
| PORTFOLIO | 10_EQUITIES_TOTAL | 1279 | 0.793 | 0.593 | 0.857 | 0.582 |


## 9. Look-Ahead Audit

| check_id | description | status | evidence |
| --- | --- | --- | --- |
| CHK_01 | OR window restricted exclusively to 09:15-09:30 candles | PASS | Bars strictly filtered with time >= 09:15 and time < 09:30 |
| CHK_02 | Entry occurs strictly after the 09:15-09:30 OR has closed | PASS | Entry bars evaluated strictly with time >= 09:30 |
| CHK_03 | Daily ATR calculated causally using prior completed daily bars | PASS | Daily ATR shifted by 1 day (causal_daily_atr = daily_atr.shift(1)) |
| CHK_04 | Conditioning threshold calibrated exclusively on TRAIN (<= 2019) | PASS | 33rd percentile computed on train_daily (year <= 2019) only |
| CHK_05 | Validation (2020-2021) cannot modify or re-calibrate threshold | PASS | Threshold frozen before testing validation data |
| CHK_06 | OOS data (>= 2022) cannot modify or leak into threshold | PASS | Threshold frozen before testing OOS data |
| CHK_07 | No future candle affects intraday entry or exit logic | PASS | Bars iterated strictly chronologically in trade execution |
| CHK_08 | Symbol universe established prior to backtest (no ex-post cherry-picking) | PASS | Universe based on liquid NIFTY constituents in repository |
| CHK_09 | Identical frozen strategy applied to every symbol without per-symbol tuning | PASS | Same 1.5 stop, 2.0 target, 15m ORB, 33rd percentile across all symbols |


## 10. Research Verdict & Limitations

**Verdict**: `REJECTED`

### Scientific Evaluation:

1. **Generalization Failure**: The low-volatility ATR regime conditioning (`Daily ATR < 33rd percentile`) does NOT generalize across individual single stocks. While it produced an edge on the NIFTY 50 index in Phase 13, 8 out of 10 liquid equities experience net losses after realistic transaction costs.

2. **Microstructure Divergence**: Individual equities exhibit higher idiosyncratic noise, morning mean-reversion, wider bid-ask spreads, and frequent intraday gap fills compared to the diversified index basket, turning 15m breakout attempts into unprofitable churn.

3. **Falsification Proven**: Applying identical frozen strategy rules without per-symbol parameter tuning proves that standalone or conditioned 15m ORB is not an equity-wide anomaly.

4. **Notice**: Under no circumstances is this strategy considered production-ready.
