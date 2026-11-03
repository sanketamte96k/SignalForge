# Phase 24G.22 — Angel One SmartAPI Security & Credential Architecture Audit

**Project:** SignalForge  
**Phase:** 24G.22  
**Document ID:** SF-AUDIT-PHASE24G22-SECURITY  
**Security Classification:** RESTRICTED — INTERNAL RESEARCH GOVERNANCE  
**Evaluation Mode:** STRICTLY OFFLINE (Zero Accounts, Zero Credentials, Zero Network Calls)  

---

## 1. Executive Security Assessment

Angel One SmartAPI is a full-featured retail algorithmic trading API providing both market data endpoints (historical candles, real-time quotes, WebSockets) and account/trading endpoints (order placement, modification, margin inspection, holdings, funds withdrawal).

Because Angel One does **not** provide a dedicated "read-only market-data subscription" or separate unprivileged market-data API keys, any authenticated session established for historical data retrieval technically possesses the privileges of the underlying Angel One trading account.

This audit establishes the rigorous security and architectural boundary controls required before any authorized pilot or production historical acquisition pipeline may interact with Angel One SmartAPI.

---

## 2. SmartAPI Credential Inventory & Lifecycle

To authenticate against Angel One SmartAPI (`POST /rest/auth/angelbroking/user/v1/loginByPassword`), five distinct cryptographic/identity tokens are involved:

| Credential / Artifact | Source / Generation | Lifespan / Expiry | Privilege / Scope | Storage Classification |
|:---|:---|:---|:---|:---|
| **API Key (`apiKey`)** | Generated in SmartAPI Developer Portal upon app registration | Permanent until regenerated or revoked | Identifies the registered application; rate limit bucket identifier | Sensitive Secret (`RESTRICTED`) |
| **Client Code (`clientCode`)** | Issued upon Angel One Demat account opening (e.g., `A123456`) | Permanent account identifier | Identifies user demat account; public in statements but sensitive in API context | Confidential Identifier |
| **MPIN / Password (`password`)** | User-defined 6-digit MPIN or alphanumeric password | Valid until reset | Primary authentication factor | Critical Secret (`CRITICAL`) |
| **TOTP Secret (`totp_secret`)** | 32-character base32 secret generated during 2FA authenticator setup | Valid until QR code reset | Generates dynamic 6-digit RFC 6238 time-based tokens every 30 seconds | Critical Secret (`CRITICAL`) |
| **JWT Access Token (`jwtToken`)** | Returned upon successful `loginByPassword` authentication | Session-based (valid for up to 24 hours / trading day end) | Bearer token required in `Authorization: Bearer <jwtToken>` header for all REST endpoints | Ephemeral Session Token |
| **Refresh Token (`refreshToken`)** | Returned upon successful `loginByPassword` | Valid for rolling session renew (typically 24–48 hours) | Used at `/rest/auth/angelbroking/user/v1/generateTokens` to renew expired JWT | Ephemeral Session Token |
| **Feed Token (`feedToken`)** | Returned upon successful `loginByPassword` | Synchronized with session | Authenticates WebSocket market data streaming feed | Ephemeral Streaming Token |

---

## 3. Threat Modeling & Risk Analysis

### 3.1 Threat Matrix

```
+---------------------------------------------------------------------------------------+
|                                    THREAT MODEL                                       |
+--------------------------+-----------------------+------------------------------------+
| Threat Scenario          | Impact                | Required Mitigation Control        |
+--------------------------+-----------------------+------------------------------------+
| 1. Credential Leakage in | Git history exposure  | Local .env exclusion in .gitignore |
|    Version Control       | of trading account    | Git pre-commit secret scanning     |
+--------------------------+-----------------------+------------------------------------+
| 2. Order Route Execution | Accidental live order | Total architectural decoupling;    |
|    from Collector Module | placement / loss      | Zero order-routing endpoints       |
+--------------------------+-----------------------+------------------------------------+
| 3. Plaintext Logging of  | Credential leak via   | Automatic Regex sanitization and   |
|    Tokens or TOTP Secret | disk / console logs   | string redaction in log handlers   |
+--------------------------+-----------------------+------------------------------------+
| 4. MITM / Interception   | Session hijacking     | TLS 1.3 verification; strict IP    |
|                          |                       | whitelisting in SmartAPI portal    |
+--------------------------+-----------------------+------------------------------------+
| 5. Process Memory Dump / | Memory scraping of    | Ephemeral in-memory handling; zero |
|    Core Dumps            | secrets               | persistent token serialization     |
+--------------------------+-----------------------+------------------------------------+
```

### 3.2 High-Risk Finding: Unified Account Privileges (No Dedicated Data-Only Keys)
- **Finding:** Unlike dedicated institutional data vendors (e.g., TrueData, Global Datafeeds) where API keys only grant read-only market data access, Angel One SmartAPI uses the broker's unified trading API.
- **Risk:** If credentials are breached or if software bugs invoke order endpoints, real capital could be exposed.
- **Architectural Requirement:** The historical data acquisition adapter must be strictly decoupled into a single-purpose, read-only client. The module `AngelOneHistoricalClient` must strictly implement `getCandleData` and `searchScrip` only. It must contain zero imports, zero wrappers, and zero bindings to order-placement APIs (`placeOrder`, `modifyOrder`, `cancelOrder`, `gtt`, `convertPosition`).

---

## 4. SignalForge Defense-in-Depth Security Controls

Before any future authorized pilot is executed, the following mandatory technical controls must be implemented:

### 4.1 Environment Variable Isolation
1. All secrets (`ANGEL_API_KEY`, `ANGEL_CLIENT_CODE`, `ANGEL_MPIN`, `ANGEL_TOTP_SECRET`) must be provided strictly via environment variables or a local non-committed `.env` file.
2. The root `.gitignore` file must explicitly exclude `.env`, `*.secret`, `*.key`, and any credentials cache.
3. SignalForge preflight test suite will assert that no files containing API secrets or tokens exist in version control.

### 4.2 Automated Secret Redaction Filter
Any future logging infrastructure used for acquisition must register a `SecretRedactionFilter` with Python's standard `logging` module:

```python
import re
import logging

class SensitiveDataRedactor(logging.Filter):
    PATTERNS = [
        re.compile(r'(?i)(api[_-]?key\s*[:=]\s*)([\'"][^\'"]+[\'"]|[^\s,]+)'),
        re.compile(r'(?i)(client[_-]?code\s*[:=]\s*)([\'"][^\'"]+[\'"]|[^\s,]+)'),
        re.compile(r'(?i)(mpin|password\s*[:=]\s*)([\'"][^\'"]+[\'"]|[^\s,]+)'),
        re.compile(r'(?i)(totp[_-]?secret\s*[:=]\s*)([\'"][^\'"]+[\'"]|[^\s,]+)'),
        re.compile(r'(Bearer\s+)([A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*)'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern in self.PATTERNS:
                record.msg = pattern.sub(r'\1[REDACTED]', record.msg)
        return True
```

### 4.3 Static IP Whitelisting (SmartAPI Developer Portal)
- SmartAPI enforces developer-defined static IP binding for production API apps.
- All requests originating from an IP address outside the configured whitelist are rejected with HTTP 401/403.
- This creates an effective network boundary protecting against credential reuse even if keys were inadvertently intercepted.

### 4.4 Automated TOTP Generation (RFC 6238)
- Instead of requiring manual interactive entry during execution, standard RFC 6238 time-based tokens are computed deterministically using `pyotp.TOTP(secret).now()`.
- The secret seed remains strictly in memory and is wiped when the process terminates.

---

## 5. Offline Verification Status (Phase 24G.22 Invariant Audit)

The repository was audited to verify that zero Angel One credentials, accounts, or connections currently exist:

1. **Repository Grep for Angel One Secrets:**
   - Checked for `ANGEL_API_KEY`, `SMARTAPI_KEY`, `jwtToken`, and Angel One endpoints in all codebase and data files.
   - Result: Zero active secrets or credentials detected.
2. **Network Activity Audit:**
   - Zero outbound requests to `apiconnect.angelbroking.com` or `smartapi.angelbroking.com`.
3. **Execution Path Quarantine:**
   - Active strategy V1 configuration hash: `920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7` (CONFIRMED UNCHANGED).
   - Paper trading ledger: `data/paper_trading/interactive_trades.json` (CONFIRMED UNTOUCHED).
   - Universe registry: `data/universe_registry.json` (CONFIRMED UNTOUCHED).

---

## 6. Security Conclusion & Approval Conditions

Angel One SmartAPI is **architecturally acceptable from a security perspective**, subject to the following non-negotiable operational conditions for any future pilot:

1. **Zero Order-Routing Codebase Inclusion:** The historical data collector must be an isolated library without trading capabilities.
2. **Zero Storage of Static Credentials in Source Code:** Verified via automated static analysis and Git hooks.
3. **Dedicated Research Account Recommendation:** If feasible, user should utilize a demat account dedicated solely to data acquisition with zero trading capital or margin balances, eliminating financial exposure from potential credential theft.
