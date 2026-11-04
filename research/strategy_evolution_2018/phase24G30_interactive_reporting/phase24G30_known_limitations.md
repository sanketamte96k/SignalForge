# SignalForge — Phase 24G.30: Known Scope & Methodological Limitations

## 1. Methodological & Simulation Boundaries

While Phase 24G.30 provides deterministic, zero-fabrication research reporting, the following physical and analytical boundaries apply:

### 1. Bar-Level Trade Resolution (Non-Tick-Level)
- Backtest simulation operates on discrete 1-minute OHLCV candles.
- In `next_open` execution, entry orders are assumed to fill at the open price of the bar following the signal.
- In-bar price paths between Open, High, Low, and Close are approximated using candle extremes rather than a full Level-2/Level-3 market depth order book.
- Stop losses and take profits that could theoretically execute within the same 1-minute bar rely on candle-priority rules rather than nanosecond order matching.

### 2. Transaction Cost Approximations
- Fixed proportional slippage and statutory costs (1.0 bps) are applied per trade.
- Real-world institutional market impact, order queuing delays, bid-ask spread widening during volatility spikes, and liquidity depletion are not modelled dynamically.

### 3. Ephemeral In-Memory Job Management
- The `BacktestJobManager` remains an in-memory coordinator with a 50-job FIFO retention cap.
- Server restart clears active in-memory jobs and results. Long-term research archiving requires saving the exported HTML tearsheets or raw JSON payloads to disk.
- Distributed task runners (Celery/Redis/Kafka) are intentionally omitted under the ₹0 local engineering mandate.

---

## 2. Research Protocol & Regulatory Disclaimers

> [!WARNING]
> SignalForge is an offline research and quantitative validation platform. All simulation results, equity curves, drawdown numbers, and performance metrics reflect historical analysis under a ₹0 research protocol.

- **No Future Profit Guarantee:** Past simulated performance on historical datasets does not guarantee future live trading results.
- **SEBI & Regulatory Notice:** This platform does not provide investment advice, algorithmic trading execution, or broker routing.
- **Disqualified Hypotheses:** Hypothesis B remains disqualified due to the look-ahead bias identified in Phase 24G.24/25. Only causal execution models (`next_open`) represent valid research baselines.
