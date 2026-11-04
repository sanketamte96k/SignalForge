# SignalForge — Security Policy & Deployment Limitations

## 1. Security Architecture

SignalForge is engineered with defense-in-depth principles appropriate for quantitative financial research:

1. **Localhost Interface Binding:** The FastAPI ASGI server binds to `127.0.0.1` by default. It is not exposed to public external networks.
2. **CORS Isolation:** CORS middleware strictly enforces local browser origin whitelisting (`localhost:5173`, `127.0.0.1:5173`). Wildcard `*` origins are forbidden.
3. **Strict Path Traversal Protection:** All filesystem access points (market data loaders, universe registry, and reporting outputs) validate targets using `validate_safe_path` and `validate_symbol` in `src.core.security`. Directory traversal sequences (`../`, `..\`) are detected and rejected.
4. **Atomic File Persistence:** All persistent state modifications use `atomic_write` in `src.core.io_utils`, writing to an isolated temporary file in the destination folder, flushing to physical disk via `os.fsync`, and replacing atomically via `os.replace`. Partial or corrupted writes are physically impossible.
5. **Zero Secret Leakage:** No credentials, API tokens, or session cookies are committed to version control. The `.env` file is excluded in `.gitignore` and `.dockerignore`.
6. **Downloaded HTML Safety:** Generated HTML research tearsheets are 100% self-contained. They do not contain outbound analytics beacons, tracking pixels, or remote scripts.

---

## 2. Deployment Boundaries & Limitations

> [!WARNING]
> SignalForge is certified solely for **Local Development and Offline Research Deployment**.

- **Not Certified for Public Cloud Production:** SignalForge does not implement user authentication (OAuth2 / JWT), tenant isolation, role-based access control (RBAC), or rate-limiting DDoS protection.
- **In-Memory Coordination:** The `BacktestJobManager` is an in-memory job queue designed for workstation concurrency (`max_workers=2`). It does not use distributed queues (Celery, Redis) or database persistence.
- **Regulatory Status:** The system is an offline academic research tool under a strict ₹0 budget. It is NOT authorized for live automated order execution, proprietary capital deployment, or public investment advisory under SEBI regulations.
