# Phase 10B: Groww Market Data Adapter Documentation

## 1. Objective

Phase 10B integrates Groww's official Trading API into SignalForge's provider-agnostic market data abstraction layer (`MarketDataService`). This adapter allows live querying of historical market data directly from Groww while enforcing strict contracts:
- Canonical OHLCV format (`Open, High, Low, Close, Volume` with `Asia/Kolkata` local timestamps).
- Zero silent fallback to other providers.
- Strict secrets safety: credentials are never leaked in logs, exception strings, or result metadata.
- Complete compliance with official Groww API parameters, date duration limitations, and response structures.

---

## 2. Official Groww API Documentation & Endpoints

Based on Groww's official developer documentation (`https://groww.in/trade-api/`):

### Primary Endpoint
- **Method**: `GET`
- **URL**: `https://api.groww.in/v1/historical/candles`
- **Note on Deprecation**: Older endpoints such as `/v1/historical/candle/range` and SDK method `get_historical_candle_data` are deprecated by Groww in favor of `/v1/historical/candles` (`get_historical_candles`).

### Query Parameters
| Parameter | Type | Example | Description |
| :--- | :--- | :--- | :--- |
| `exchange` | string | `NSE` | Exchange identifier (`NSE`, `BSE`). |
| `segment` | string | `CASH` | Market segment (`CASH` for equities, `FNO` for derivatives). |
| `groww_symbol` | string | `NSE-RELIANCE` | Instrument symbol formatted as `{EXCHANGE}-{SYMBOL}`. |
| `start_time` | string | `2024-01-01 09:15:00` | Range start in `YYYY-MM-DD HH:mm:ss`. |
| `end_time` | string | `2024-01-15 15:30:00` | Range end in `YYYY-MM-DD HH:mm:ss`. |
| `candle_interval` | string | `1minute` | Bar resolution (e.g. `1minute`, `5minute`, `15minute`, `1hour`, `1day`). |

### Request Headers
```http
Authorization: Bearer {GROWW_API_KEY}
X-API-VERSION: 1.0
Accept: application/json
```

---

## 3. Authentication Mechanism

Authentication requires an active Groww Trading API subscription.
- **Token Format**: Bearer access token generated from the user's Groww Trading API dashboard.
- **Token Expiration**: Groww API tokens expire daily at 06:00 AM IST.
- **Headers**: Supplied via the standard `Authorization: Bearer <TOKEN>` header.
- **Environment Variable**: `GROWW_API_KEY` (with optional `GROWW_API_SECRET`).

---

## 4. Supported Intervals & Official Request Limitations

Groww enforces strict duration limits per request based on the bar resolution:

| Interval Code | Groww Parameter | Maximum Duration per Request |
| :--- | :--- | :--- |
| `1m`, `2m`, `3m`, `5m` | `1minute`, `2minute`, `3minute`, `5minute` | **30 days** |
| `10m`, `15m`, `30m` | `10minute`, `15minute`, `30minute` | **90 days** |
| `1h`, `60m`, `1d` | `1hour`, `1day` | **180 days** |

Unsupported intervals (e.g. `45m`, `1wk`, `1mo`) are rejected early with an informative `ValueError`.

### Bounded Chunking Strategy
When a query's date range exceeds the duration limit for its interval:
1. `GrowwProvider._generate_chunks()` divides the range into deterministic, contiguous sub-intervals where `duration <= max_duration`.
2. Each chunk is retrieved independently.
3. Chunks are concatenated, sorted chronologically, and duplicate timestamps across chunk boundaries are removed (`~combined.index.duplicated(keep="last")`).
4. Invariants are validated across the entire combined dataset.

---

## 5. Timestamp & Timezone Conventions

- **Groww Raw Response**: Each candle returned contains an integer timestamp representing **epoch seconds** in UTC.
- **SignalForge Canonical Convention**:
  1. Parse epoch seconds to UTC: `pd.to_datetime(timestamps, unit="s", utc=True)`.
  2. Convert to Indian Standard Time: `.tz_convert("Asia/Kolkata")`.
  3. De-localize to timezone-naive representation: `.tz_localize(None)`.
- This ensures timestamps accurately represent Indian market wall-clock time (`09:15:00` to `15:30:00`) as a `pd.DatetimeIndex` without ambiguous UTC offsets.

---

## 6. Symbol & Instrument Mapping

Groww requires instruments to be addressed by their full exchange-prefixed identifier:
- Default rule: `{EXCHANGE}-{SYMBOL}` (e.g. `NSE-RELIANCE`, `NSE-TCS`, `NSE-INFY`, `NSE-HDFCBANK`, `NSE-SBIN`).
- Explicit symbol map: `DEFAULT_SYMBOL_MAP` maps standard symbols, and custom dictionary mappings can be passed to `GrowwProvider(symbol_map=...)`.

---

## 7. Error Handling & Rate Limiting

The adapter maps HTTP status codes and response bodies into a structured exception hierarchy:
- **`GrowwAuthenticationError`** (HTTP 401, 403, or unconfigured credentials).
- **`GrowwRateLimitError`** (HTTP 429 Too Many Requests).
- **`GrowwAPIError`** (HTTP 4xx, 5xx server errors, or `"status": "FAILURE"` responses).
- **`GrowwDataFormatError`** (Non-JSON payload, missing `"candles"` key, or malformed inner array).
- **`GrowwSymbolMappingError`** (Empty or invalid instrument identifier).

### Zero Silent Fallback
Under no circumstances does `GrowwProvider` or `MarketDataService` catch a Groww failure to silently retry using a different provider (such as `local`). All exceptions are raised immediately to maintain backtest and execution integrity.

---

## 8. Configuration & Secrets Safety

- **Configuration File**: `.env.example` provides sample environment variables (`GROWW_API_KEY`, `GROWW_API_SECRET`, `GROWW_API_BASE_URL`, `GROWW_REQUEST_TIMEOUT`).
- **Secrets Isolation**:
  - `GrowwConfig.__repr__` explicitly masks keys as `***`.
  - Exception classes do not print token values in error messages.
  - `MarketDataResult.metadata` records only operational audit fields (`source`, `groww_symbol`, `candle_interval`, `row_count`, `chunks_count`), never the API token.
  - Real credentials must NEVER be committed to version control.

---

## 9. Testing Strategy

All unit and integration tests in `tests/test_groww_provider.py` execute with **100% mocked HTTP responses**:
- Zero network requests are made to Groww during test execution.
- Tests verify configuration loading, credential masking, symbol mapping, successful 200 OK normalization, invariant violations (NaN, High < Low, non-positive Low, negative volume), HTTP error handling (401, 429, 500, invalid JSON), chunking across boundaries, and `MarketDataService` routing without silent fallback.

---

## 10. What Groww Can and Cannot Provide for SignalForge

### What Groww CAN Provide:
- High-fidelity 1-minute and intraday OHLCV candle data for NSE/BSE equities.
- Real-time and near-term historical data from **2020 to present**.
- Direct API integration for paper trading and live algorithmic order execution.

### What Groww CANNOT Provide:
> [!IMPORTANT]
> **Coverage Boundary**:
> Groww's historical candle database only stores data from **2020 onwards**.
> Therefore, **Phase 10B does NOT solve SignalForge's 10-year historical dataset requirement (2015–2019)**.
> Institutional historical datasets (such as TickData or NSE official historical archives) remain mandatory to fulfill the 2015–2019 backtesting requirements.

### Zero Download Confirmation
During Phase 10B, **NO real market data was downloaded**, **NO real trades were placed**, and **NO external network connections were established**.
