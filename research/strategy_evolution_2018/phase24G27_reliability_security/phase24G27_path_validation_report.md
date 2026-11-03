# SignalForge — Phase 24G.27: Path Validation & Security Hardening Report

## 1. Executive Summary

During the Phase 24G.26 architecture audit, potential path traversal vulnerabilities were identified in endpoints and modules accepting stock symbols. Prior implementations relied on simple string stripping (`symbol.strip().upper()`) and unvalidated path concatenation (`data_directory / f"{symbol}_1m.csv"`). A crafted input containing directory traversal sequences (such as `../../etc/passwd` or `..\boot.ini`) could escape the historical market data directory and query or overwrite arbitrary system files.

In Phase 24G.27, centralized path validation and symbol sanitization were implemented in [`src/core/security.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/src/core/security.py). The implementation uses canonical path resolution (`Path.resolve()`) and standard library containment checks (`Path.is_relative_to()`) to eliminate string-prefix flaws, handle symlink escapes, and enforce strict symbol whitelisting.

---

## 2. Vulnerability Analysis & Threat Model

### 2.1 Threat Vectors
1. **Parent Directory Traversal (`../` and `..\`):**
   Attackers could pass path traversal sequences in symbol parameters (`GET /api/stocks/..%2F..%2Fetc%2Fpasswd/readiness`), causing file existence checks or read operations on unauthorized system files.
2. **Absolute Path Injection:**
   Passing an absolute path (e.g., `C:\Windows\System32\...` or `/etc/shadow`) bypasses relative path joins on many path libraries.
3. **Symlink Escape:**
   A symbolic link located inside the permitted directory pointing to a file outside the boundary could allow unauthorized access if the path is not canonicalized.
4. **Fragile String-Prefix Checking:**
   Checking whether `str(target).startswith(str(base))` is vulnerable to prefix collision (e.g. `/data/historical_backup` starts with `/data/historical` but is outside the boundary).

---

## 3. Architecture & Implementation of `src/core/security.py`

### 3.1 Exception Hierarchy
```python
class SecurityError(ValueError):
    """Base exception for security validation failures, inheriting from ValueError."""
    pass

class PathTraversalError(SecurityError):
    """Raised when a resolved file path escapes its designated root boundary."""
    pass

class InvalidSymbolError(SecurityError):
    """Raised when a stock symbol contains invalid or dangerous characters."""
    pass
```
> [!IMPORTANT]
> Because `SecurityError` inherits from `ValueError`, existing FastAPI route handlers catching `(TypeError, ValueError)` automatically catch path traversal attempts and return **HTTP 400 Bad Request** without crashing or leaking stack traces.

### 3.2 Symbol Sanitization (`validate_symbol`)
- **Length Bounds:** Enforces $1 \le \text{length} \le 30$ characters.
- **Explicit Token Rejection:** Forbids directory traversal tokens (`..`), path separators (`/`, `\`), and null bytes (`\0`).
- **Whitelist Regex:**
  ```python
  _VALID_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9_\-&]+(\.[A-Z0-9]+)?$")
  ```
  - Allows alphanumeric uppercase characters, underscores, and hyphens (e.g. `BAJAJ-AUTO`).
  - Supports ampersands (e.g. `M&M`, confirmed present in `data/universe_registry.json`).
  - Supports standard exchange suffixes (e.g. `.NS` for Yahoo Finance tickers).
  - Strictly forbids any characters capable of filesystem navigation.

### 3.3 Centralized Path Boundary Verification (`validate_safe_path`)
```python
def validate_safe_path(target_path: Path | str, base_dir: Path | str, *, allow_nonexistent: bool = True) -> Path:
    base = Path(base_dir).resolve()
    target = Path(target_path)
    resolved_target = (base / target).resolve() if not target.is_absolute() else target.resolve()

    if not resolved_target.is_relative_to(base):
        raise PathTraversalError(
            f"Path traversal detected: Target '{target_path}' resolves to '{resolved_target}', "
            f"which escapes permitted boundary '{base}'."
        )
    return resolved_target
```
- **Canonicalization:** Resolves symlinks and relative tokens using `.resolve()`.
- **Containment Check:** Leverages `is_relative_to(base)` to mathematically verify path hierarchy.
- **Symlink Defense:** If a symlink within `base_dir` resolves to a target outside `base_dir`, `is_relative_to(base)` evaluates to `False` and immediately raises `PathTraversalError`.

---

## 4. Call Site Integration & Compatibility

The security utilities were integrated directly into the core market data provider:

### [`src/data/stock_provider.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/src/data/stock_provider.py)
```python
    def local_path(self, symbol: str) -> Path:
        """Return the standard local historical-data path with path validation."""
        normalized_symbol = self._normalize_symbol(symbol)
        target = self.data_directory / f"{normalized_symbol}_1m.csv"

        from src.core.security import validate_safe_path
        validate_safe_path(target, self.data_directory)

        return target

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Normalize and validate a stock symbol."""
        if not isinstance(symbol, str):
            raise TypeError("symbol must be a string.")

        from src.core.security import validate_symbol
        return validate_symbol(symbol)
```

### Compatibility Impact
- Valid NSE tickers (`RELIANCE`, `TCS`, `INFY`, `M&M`, `BAJAJ-AUTO`) continue to function with zero disruption.
- Malicious inputs (`../../etc/passwd`, `..\boot.ini`, `foo/bar`) raise `InvalidSymbolError` (which inherits from `ValueError`), causing API routes to cleanly return HTTP 400.
- All 13 existing unit tests in `tests/test_stock_provider.py` and 4 integration tests in `tests/test_stock_validation_readiness_integration.py` pass without regression.

---

## 5. Verification & Test Evidence

The path validation system was rigorously evaluated in [`tests/test_phase24G27_reliability_security.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/tests/test_phase24G27_reliability_security.py):

| Test Case | Scenario Evaluated | Expected Outcome | Result |
| :--- | :--- | :--- | :---: |
| `test_validate_symbol_valid` | `RELIANCE`, `M&M`, `BAJAJ-AUTO`, `TCS.NS` | Clean normalization | **PASS** |
| `test_validate_symbol_invalid` | `../../etc/passwd`, `..\boot.ini`, `foo/bar`, `\0` | `InvalidSymbolError` raised | **PASS** |
| `test_validate_safe_path_valid` | Nested CSV subpaths within `data/` | Resolves within boundary | **PASS** |
| `test_validate_safe_path_traversal` | `../secret.json`, `../../outside.txt` | `PathTraversalError` raised | **PASS** |
| `test_validate_safe_path_absolute` | Absolute paths outside base directory | `PathTraversalError` raised | **PASS** |
| `test_safe_resolve_symbol_path` | Valid symbol resolution vs injected traversal | Resolves or rejects | **PASS** |
| `test_symlink_escape_rejection` | Symlink pointing outside jail directory | `PathTraversalError` raised | **PASS** |

All security assertions executed cleanly with zero defects.
