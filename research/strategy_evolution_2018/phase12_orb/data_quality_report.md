# SignalForge Phase 12 — Data Quality & Integrity Audit

## Dataset Overview

- **Source Path**: `C:\Study Roadmap\PROJECTS\SignalForge\data\historical\nifty50_1m_signalforge.csv`
- **Total Minute Records**: 847,814
- **Total Unique Trading Sessions**: 2,261
- **Historical Range**: 2015-01-09 09:15:00 to 2024-03-26 15:29:00 (~9.25 years)
- **Asset Type**: NIFTY 50 Spot Benchmark Index

## Data Integrity Checklist

| Integrity Verification Check | Measured Outcome | Status |
|---|---|---|
| Timestamp Parsing & Sorting | Monotonic increasing, zero unparseable rows | PASS |
| Duplicate Timestamp Check | 0 duplicates detected | PASS |
| Missing/NaN Values (OHLC) | 0 NaNs | PASS |
| Non-Positive Prices | 0 non-positive prices | PASS |
| OHLC Consistency ($H \ge \max(O,C), L \le \min(O,C)$) | 100% compliant across all candles | PASS |
| Session Boundaries (09:15 to 15:29) | 0 out-of-session bars | PASS |
| Volume Data Usability | 847,814 zero-volume records (100.0%) | **DATA_LIMITED** |

## Volume Usability Finding

> [!WARNING]
> **Volume Availability Limitation**:
> In the official NIFTY 50 spot cash index, volume is recorded as `0.0` for all 847,814 candles because the NSE cash index itself does not trade shares directly.
>
> Consequently:
> 1. `volume_confirm` mode cannot be meaningfully evaluated on this index dataset.
> 2. `vwap_confirm` mode (which requires cumulative volume) cannot be computed on spot index data without volume.
> 3. Both modes are explicitly classified as `DATA_LIMITED / INVALID_FOR_VOLUME_VALIDATION`.
> 4. Non-volume structural modes (`immediate`, `close_confirm`, and `retest`) remain fully causal and statistically valid.
