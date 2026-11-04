# SignalForge — Environment Configuration Guide

## 1. Overview

SignalForge operates with secure, safe defaults. In offline research mode, **no external API keys, broker accounts, or credentials are required**. All features (causal backtesting, equity analytics, strategy signal evaluation, and interactive tearsheets) run out of the box.

---

## 2. Environment Variables & `.env`

If custom local configurations are desired, copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

### Supported Configuration Keys

| Key | Default | Type | Description |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | `development` | String | Environment mode: `development`, `testing`, or `production`. |
| `API_HOST` | `127.0.0.1` | String | Local network interface binding. Keep `127.0.0.1` for local safety. |
| `API_PORT` | `8000` | Integer | HTTP port for the FastAPI ASGI backend. |
| `CORS_ORIGINS` | `["http://localhost:5173", "http://127.0.0.1:5173"]` | List[str] | Allowed browser origins for cross-origin requests. |
| `DATA_DIR` | `./data` | Path | Root directory for market data and universe files. |
| `LOG_LEVEL` | `INFO` | String | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

---

## 3. Security Invariant: Never Commit Secrets

> [!CAUTION]
> The `.env` file is excluded from version control in `.gitignore`. Never commit API keys, personal credentials, or live passwords to git.
