# SignalForge — Phase 24G.27: Atomic File-Write Implementation Report

## 1. Executive Summary

As identified during the Phase 24G.26 architecture audit, file-based persistence in SignalForge historically relied on non-atomic direct stream writing (`with open(path, "w") as f: json.dump(payload, f)`). Under concurrent execution, sudden application termination, power interruptions, or unhandled exceptions, this pattern risks truncating existing files, leading to permanent state corruption and complete loss of session history.

In Phase 24G.27, a production-grade, crash-resilient atomic I/O subsystem was implemented in [`src/core/io_utils.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/src/core/io_utils.py). The utility guarantees all-or-nothing file replacement across POSIX and Windows NTFS environments, enforces strict pre-serialization validation, cleans up all temporary files on failure, and preserves file permissions.

---

## 2. Failure Mode Analysis of Legacy File Writing

The legacy persistence mechanism exhibited four primary vulnerabilities:

1. **Truncation Window on Open:**
   Opening a file with mode `"w"` immediately truncates the file length to 0 bytes before any data is written. If the process is halted before serialization finishes, the existing file is permanently wiped.
2. **Orphan Corrupted Data on Partial Writes:**
   If serialization fails halfway (e.g. encountering a non-serializable object or out-of-disk space), the file on disk contains malformed, incomplete JSON syntax.
3. **Cross-Filesystem Replacement Failures:**
   Creating temporary files in the system default temp folder (e.g., `C:\Users\...\AppData\Local\Temp`) and attempting to move them across distinct volumes or drives fails on `os.replace` with `EXDEV` (Invalid cross-device link).
4. **Windows File-Lock Collisions (`WinError 32`):**
   On Windows NTFS, attempting to replace or overwrite a file while any handle remains open causes immediate `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process`.

---

## 3. Architecture & Technical Design of `src/core/io_utils.py`

### 3.1 Core Components

The new I/O subsystem exposes three primary functions:

```
src/core/io_utils.py
├── atomic_write(destination, content, encoding="utf-8", make_parents=True, preserve_mode=True, sync=True)
├── atomic_write_json(destination, data, indent=2, sort_keys=False, make_parents=True, encoding="utf-8", sync=True)
└── atomic_write_stream(destination, mode="w", encoding="utf-8", make_parents=True, preserve_mode=True, sync=True)
```

### 3.2 Technical Safeguards

1. **Colocated Temporary File Creation:**
   Temporary files are instantiated directly inside `destination.parent` using `tempfile.NamedTemporaryFile(dir=dest_path.parent, prefix=f".{dest_path.name}.", suffix=".tmp", delete=False)`. This guarantees that the temporary file and destination file share the identical filesystem inode table and volume, ensuring atomic `os.replace`.
2. **Deterministic Flush and Disk Synchronization:**
   The file buffer is explicitly flushed (`tmp.flush()`) and synced to physical storage (`os.fsync(tmp.fileno())`) prior to file closure, ensuring dirty pages are committed to non-volatile storage.
3. **Strict Close-Before-Replace Protocol:**
   The temporary file handle is explicitly closed before invoking `os.replace(temp_path, dest_path)`. This completely eliminates Windows NTFS handle contention.
4. **JSON In-Memory Pre-Serialization:**
   `atomic_write_json` validates and serializes the complete Python data structure into an in-memory string (`json.dumps(...)`) *before* creating or opening any temporary file. If a serialization error occurs (e.g. `TypeError` on non-serializable sets or custom objects), the function aborts instantly without touching the disk or generating orphan `.tmp` files.
5. **Robust Exception Cleanup & Rollback:**
   All operations are enclosed in `try ... except ...` blocks. If any exception occurs during writing, syncing, or replacing, the temporary file is unlinked immediately (`temp_path.unlink(missing_ok=True)`), and the exception is re-raised. The existing target file remains 100% unaltered.
6. **File Permission Preservation:**
   If the destination file already exists, its permission bits (`stat().st_mode`) are captured and applied to the temporary file (`chmod`) prior to atomic replacement.

---

## 4. Call Site Migration & Phased Rollout

In accordance with Phase 24G.27 safety mandates, write operations were audited and migrated selectively starting with high-risk, critical state consumers:

| Call Site / Module | Operation Type | Migration Status | Rationale |
| :--- | :--- | :---: | :--- |
| [`src/paper_trading/persistence.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/src/paper_trading/persistence.py) | `save_paper_trading_report` | **MIGRATED** | Persists session performance reports; protects against truncated reports. |
| [`src/paper_trading/interactive_engine.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/src/paper_trading/interactive_engine.py) | `_save_to_disk` | **MIGRATED** | Persists active interactive paper trades and equity curve; highest risk of history loss on crash. |
| [`src/universe/registry.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/src/universe/registry.py) | `_save` | Deferred | Protected file (`data/universe_registry.json`). Preserved untouched during current audit. |
| [`src/data/downloader.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/src/data/downloader.py) | `save_market_data` | Deferred | Downloader is currently inactive under ₹0 budget mode. |

---

## 5. Verification & Test Evidence

The atomic write implementation was validated via dedicated unit tests in [`tests/test_phase24G27_reliability_security.py`](file:///c:/Study%20Roadmap/PROJECTS/SignalForge/tests/test_phase24G27_reliability_security.py):

1. `test_atomic_write_text_success`: Verified correct text persistence and zero leftover `.tmp` files.
2. `test_atomic_write_binary_success`: Verified binary data persistence without corruption.
3. `test_atomic_write_preserves_original_on_failure`: Simulated write interruption and confirmed the pre-existing target file was 100% untouched with zero orphan temporary files.
4. `test_atomic_write_json_success`: Confirmed valid formatted JSON output.
5. `test_atomic_write_json_serialization_failure_protection`: Confirmed that a `TypeError` during serialization aborts immediately and leaves the target file untouched.
6. `test_atomic_write_stream_normal`: Confirmed clean streaming context manager operation.

All atomic write tests passed with 100% success.
