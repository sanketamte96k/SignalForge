# SignalForge — Phase 5: Multi-Year Historical Data Specification

## Status
**PHASE 5 CANNOT COMPLETE MULTI-YEAR VALIDATION — ADDITIONAL HISTORICAL DATA REQUIRED.**

## Required Datasets for Production Validation
To complete true multi-year out-of-sample validation without look-ahead bias or synthetic fabrication, the following clean 1-minute historical datasets are required:

1. **2018 (Reference/Development)**: RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK (Available & Validated: 11,222 trades)
2. **2019 (Cross-Year Validation)**: RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK (1-minute OHLCV, 09:15-15:30)
3. **2020+ (Multi-Year Out-Of-Sample)**: RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK (1-minute OHLCV, 09:15-15:30)

## Scientific Principle
SignalForge strictly prohibits simulating synthetic market years or random shuffling of time-series data. Until 2019 and 2020+ data are acquired and cleansed through the institutional data pipeline, temporal validation remains limited to 2018 chronological splits (Train: Jan-Jun, Val: Jul-Sep, OOS: Oct-Dec).
