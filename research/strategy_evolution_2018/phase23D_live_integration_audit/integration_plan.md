# Safe Live Integration Plan

## 1. Unblocking Data Access
The current `GrowwProvider` is implemented but restricted by invalid credentials (`HTTP 403`). A valid `GROWW_API_KEY` and `GROWW_API_SECRET` must be provided in `.env`.

## 2. Minimal Viable Integration
Once data access is unblocked:
1. Initialize the `GrowwProvider` within a lightweight background polling daemon (or `FastAPI` startup event).
2. Schedule a fetch of 15m candles every minute for `HDFCBANK, ICICIBANK, INFY, RELIANCE` using `GrowwProvider`.
3. Feed closed 15m candles into the existing `InteractivePaperTradingService.update_trade` pipeline.
4. Keep the original frozen configurations (`VARIANT_C_ONE_TRADE_PER_SYMBOL_PER_DAY`, `15m` timeframe) unchanged.

## 3. Real Broker Safety
Real broker execution remains strictly **DISABLED**. The forward integration will only use the paper-trading models and logic without routing orders to an exchange.
