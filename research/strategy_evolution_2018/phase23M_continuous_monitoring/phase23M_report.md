# Phase 23M: Safe Continuous Forward Paper Monitoring

## Objective
Maintain the existing SignalForge forward paper-trading pipeline and collect genuine, auditable forward results until the required sample size is reached.

## Status
- **Strategy**: VARIANT_C_ONE_TRADE_PER_SYMBOL_PER_DAY
- **Frozen config hash**: 920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7
- **Current Verified Trade Count**: 0 (INSUFFICIENT_FORWARD_SAMPLE)
- **Monitoring Location**: `research/strategy_evolution_2018/phase23M_continuous_monitoring/`
- **Ledger Storage**: `interactive_trades.json` (inside monitoring location)

## Exact Commands

**To Start Monitoring:**
```bash
python -m scripts.phase23M_continuous_monitoring
```
(Recommended to run inside a detached `tmux` or `screen` session to survive SSH disconnects.)

**To Stop Monitoring (Graceful Shutdown):**
Press `Ctrl+C` in the terminal where it is running. The process captures `KeyboardInterrupt` to shut down gracefully without corrupting ledger files.

## Persistence and Restart Tests
- **Restart Recovery**: If the process crashes or is restarted, the `InteractivePaperTradingService` strictly loads from `interactive_trades.json`. The scheduler inspects these past trades and reliably applies the `1-trade-per-day-per-symbol` rule, ensuring no duplicate entries are fabricated on restart.
- **Verification**: You can verify that the collector is actually running by tailing the process output. The script emits a log via Python's standard `logging` module every minute during market hours ("Polling data for [SYMBOL] for candle [TIME]"). Outside market hours, it logs a sleep message every 5 minutes.
- **Safety**: Rate limits (via YFinance) invoke an exponential backoff sequence (starting at 5 seconds) rather than a crash. No data is fetched outside of NSE market hours (09:15 - 15:30 IST).
- **Execution Rules**: Real broker execution strictly remains disabled.

## Final Note
The collection pipeline is active, robust to restarts, and will slowly build the 30-trade forward sample. **Profitability cannot and should not be claimed until the 30-trade minimum is met.**
