"""
SignalForge — Phase 24G.27: Core Reliability & Security Tests
==============================================================
Validates:
1. Pre-flight safety invariants (V1 config hash, canonical ADANIPORTS SHA-256, registry/ledger).
2. Atomic file write operations (atomic_write, atomic_write_json, atomic_write_stream).
3. Write failure recovery and absence of temporary file leakage.
4. JSON pre-serialization protection against file destruction.
5. Path traversal protection (validate_safe_path, validate_symbol, safe_resolve_symbol_path).
6. Symlink escape detection.
7. Centralized Pydantic application configuration (SignalForgeSettings, env overrides, secrets masking).
8. Existing API compatibility and error contract preservation.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import pytest

from src.core.config import SignalForgeSettings, get_settings
from src.core.io_utils import atomic_write, atomic_write_json, atomic_write_stream
from src.core.security import (
    InvalidSymbolError,
    PathTraversalError,
    safe_resolve_symbol_path,
    validate_safe_path,
    validate_symbol,
)


# ----------------------------------------------------------------------------
# 1. Preflight Invariants
# ----------------------------------------------------------------------------

def test_v1_config_hash_immutable():
    """Verify frozen V1 baseline configuration hash matches canonical value."""
    v1_path = Path("research/strategy_evolution_2018/phase22_final_validation/strategy_snapshot.json")
    assert v1_path.exists(), "V1 strategy snapshot file missing"
    with open(v1_path, "r", encoding="utf-8") as f:
        snap = json.load(f)
    v1_h = hashlib.sha256(json.dumps(snap, sort_keys=True).encode("utf-8")).hexdigest()
    assert v1_h == "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"


def test_adaniports_canonical_hash():
    """Verify canonical on-disk ADANIPORTS dataset hash is untouched."""
    adani_path = Path("data/historical/stocks/ADANIPORTS_1m.csv")
    assert adani_path.exists(), "ADANIPORTS dataset missing"
    h = hashlib.sha256(adani_path.read_bytes()).hexdigest()
    assert h == "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"


def test_safety_invariants_registry_and_paper_ledger():
    """Verify universe registry and paper trading ledger are intact."""
    reg_path = Path("data/universe_registry.json")
    led_path = Path("data/paper_trading/interactive_trades.json")
    assert reg_path.exists(), "Universe registry missing"
    assert led_path.exists(), "Paper trading ledger missing"


# ----------------------------------------------------------------------------
# 2. Atomic File Write Tests
# ----------------------------------------------------------------------------

def test_atomic_write_text_success(tmp_path: Path):
    """Verify atomic write creates text file with exact content and parent dirs."""
    target = tmp_path / "subdir" / "nested" / "test.txt"
    content = "Hello SignalForge Atomic Write\nLine 2"

    result = atomic_write(target, content)
    assert result == target
    assert target.exists()
    assert target.read_text(encoding="utf-8") == content

    # Verify no temporary files remain in target directory
    temp_files = list(target.parent.glob("*.tmp"))
    assert len(temp_files) == 0


def test_atomic_write_binary_success(tmp_path: Path):
    """Verify atomic write persists binary bytes cleanly."""
    target = tmp_path / "binary_data.bin"
    payload = b"\x00\x01\x02\x03\xFF\xFE\xFD"

    result = atomic_write(target, payload)
    assert result == target
    assert target.read_bytes() == payload
    assert len(list(tmp_path.glob("*.tmp"))) == 0


def test_atomic_write_preserves_original_on_failure(tmp_path: Path):
    """Verify that an interrupted write leaves the existing file completely intact."""
    target = tmp_path / "critical_data.txt"
    original_content = "ORIGINAL CRITICAL DATA"
    target.write_text(original_content, encoding="utf-8")

    # Simulate failure by attempting to atomic write to an unwriteable read-only directory or invalid path
    # We can also mock os.replace or NamedTemporaryFile to raise an exception
    class SimulatedDiskError(Exception):
        pass

    with pytest.raises(SimulatedDiskError):
        # We simulate failure during atomic_write_stream
        with atomic_write_stream(target) as stream:
            stream.write("CORRUPTED HALF DATA")
            raise SimulatedDiskError("Disk full simulation")

    # Target must remain 100% original
    assert target.exists()
    assert target.read_text(encoding="utf-8") == original_content

    # No leftover .tmp files
    assert len(list(tmp_path.glob("*.tmp"))) == 0


def test_atomic_write_json_success(tmp_path: Path):
    """Verify atomic JSON write outputs valid formatted JSON."""
    target = tmp_path / "trades" / "session.json"
    data = {
        "status": "ACTIVE",
        "capital": 100000.0,
        "positions": [{"symbol": "TCS", "qty": 10}],
    }

    result = atomic_write_json(target, data, indent=2)
    assert result == target
    assert target.exists()

    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded == data
    assert len(list(target.parent.glob("*.tmp"))) == 0


def test_atomic_write_json_serialization_failure_protection(tmp_path: Path):
    """Verify that non-serializable object raises TypeError before touching disk."""
    target = tmp_path / "corrupt_test.json"
    original_content = '{"safe": true}\n'
    target.write_text(original_content, encoding="utf-8")

    # Data containing non-serializable type (e.g. set)
    bad_data = {"symbol": "INFY", "unserializable": {1, 2, 3}}

    with pytest.raises(TypeError):
        atomic_write_json(target, bad_data)

    # File on disk must NOT be modified or wiped
    assert target.read_text(encoding="utf-8") == original_content
    # Zero orphan temp files
    assert len(list(tmp_path.glob("*.tmp"))) == 0


def test_atomic_write_stream_normal(tmp_path: Path):
    """Verify streaming atomic write functions cleanly on normal exit."""
    target = tmp_path / "stream_output.csv"
    with atomic_write_stream(target) as f:
        f.write("date,open,high,low,close,volume\n")
        f.write("2026-01-01,100,105,99,102,5000\n")

    assert target.exists()
    assert "2026-01-01" in target.read_text(encoding="utf-8")
    assert len(list(tmp_path.glob("*.tmp"))) == 0


# ----------------------------------------------------------------------------
# 3. Path Traversal & Security Tests
# ----------------------------------------------------------------------------

def test_validate_symbol_valid():
    """Verify legitimate symbols with hyphens, ampersands, and suffixes are accepted."""
    assert validate_symbol("RELIANCE") == "RELIANCE"
    assert validate_symbol(" reliance ") == "RELIANCE"
    assert validate_symbol("M&M") == "M&M"
    assert validate_symbol("BAJAJ-AUTO") == "BAJAJ-AUTO"
    assert validate_symbol("TCS.NS") == "TCS.NS"
    assert validate_symbol("NIFTY_50") == "NIFTY_50"


def test_validate_symbol_invalid_and_traversal_attempts():
    """Verify traversal patterns and dangerous characters are strictly rejected."""
    bad_symbols = [
        "../../etc/passwd",
        r"..\..\boot.ini",
        "foo/bar",
        r"foo\bar",
        "foo\0bar",
        "",
        "   ",
        "A" * 35,  # Exceeds max length
        "STOCK;DROP TABLE",
        "STOCK|COMMAND",
    ]
    for bad in bad_symbols:
        with pytest.raises((InvalidSymbolError, ValueError)):
            validate_symbol(bad)


def test_validate_safe_path_valid(tmp_path: Path):
    """Verify paths within base directory resolve safely."""
    base = tmp_path / "data"
    base.mkdir()
    subfile = base / "stocks" / "RELIANCE_1m.csv"

    resolved = validate_safe_path(subfile, base)
    assert resolved.is_relative_to(base.resolve())
    assert resolved.name == "RELIANCE_1m.csv"


def test_validate_safe_path_traversal_rejection(tmp_path: Path):
    """Verify relative traversal escapes ('..') are caught and rejected."""
    base = tmp_path / "data" / "historical"
    base.mkdir(parents=True)

    escapes = [
        "../secret.json",
        "../../outside.txt",
        r"..\..\..\Windows\System32",
    ]
    for esc in escapes:
        with pytest.raises(PathTraversalError):
            validate_safe_path(esc, base)


def test_validate_safe_path_absolute_escape_rejection(tmp_path: Path):
    """Verify absolute paths outside base directory are rejected."""
    base = tmp_path / "data"
    base.mkdir()
    outside = tmp_path / "other_folder" / "secret.txt"

    with pytest.raises(PathTraversalError):
        validate_safe_path(outside, base)


def test_safe_resolve_symbol_path(tmp_path: Path):
    """Verify safe symbol resolver binds correctly within base directory."""
    base = tmp_path / "stocks"
    base.mkdir()

    # Valid symbol
    resolved = safe_resolve_symbol_path("INFY", base)
    assert resolved.name == "INFY_1m.csv"
    assert resolved.is_relative_to(base.resolve())

    # Traversal attempt in symbol
    with pytest.raises((InvalidSymbolError, PathTraversalError, ValueError)):
        safe_resolve_symbol_path("../../passwd", base)


def test_symlink_escape_rejection(tmp_path: Path):
    """Verify symlinks pointing outside root are caught by resolve() boundary check."""
    root_dir = tmp_path / "safe_root"
    outside_dir = tmp_path / "outside_jail"
    root_dir.mkdir()
    outside_dir.mkdir()

    secret_file = outside_dir / "confidential.txt"
    secret_file.write_text("CONFIDENTIAL", encoding="utf-8")

    link_target = root_dir / "symlink_escape.txt"
    try:
        link_target.symlink_to(secret_file)
    except (OSError, NotImplementedError):
        # On Windows workstations without SeCreateSymbolicLinkPrivilege, symlink creation may be restricted
        pytest.skip("Symlink creation not permitted in current OS execution environment")

    # The link is inside root_dir, but its resolved target is in outside_dir!
    with pytest.raises(PathTraversalError):
        validate_safe_path(link_target, root_dir)


# ----------------------------------------------------------------------------
# 4. Centralized Configuration Tests
# ----------------------------------------------------------------------------

def test_settings_development_defaults():
    """Verify standard development defaults are active without environment overrides."""
    # Ensure standard defaults
    settings = SignalForgeSettings()
    assert settings.app_env == "development"
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8000
    assert "http://localhost:5173" in settings.cors_origins
    assert settings.data_root_dir == Path("data")
    assert settings.groww_api_key is None or isinstance(settings.groww_api_key, str)


def test_settings_environment_overrides(monkeypatch):
    """Verify environment variables cleanly override defaults."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_PORT", "9090")
    monkeypatch.setenv("CORS_ORIGINS", "https://signalforge.io, https://app.signalforge.io")
    monkeypatch.setenv("DATA_ROOT_DIR", "custom_data")

    loaded = SignalForgeSettings.from_env()
    assert loaded.app_env == "production"
    assert loaded.api_host == "0.0.0.0"
    assert loaded.api_port == 9090
    assert loaded.cors_origins == ["https://signalforge.io", "https://app.signalforge.io"]
    assert loaded.data_root_dir == Path("custom_data")


def test_settings_secrets_masking(monkeypatch):
    """Verify credentials are masked in repr and str to avoid leaking tokens in logs."""
    monkeypatch.setenv("GROWW_API_KEY", "real_secret_key_12345")
    monkeypatch.setenv("GROWW_API_SECRET", "super_secret_token_abcdef")

    loaded = SignalForgeSettings.from_env()
    rep = repr(loaded)
    s = str(loaded)

    assert "real_secret_key_12345" not in rep
    assert "super_secret_token_abcdef" not in rep
    assert "***" in rep
    assert "***" in s


def test_settings_get_settings_caching():
    """Verify get_settings returns singleton and cache_clear works."""
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
    get_settings.cache_clear()


# ----------------------------------------------------------------------------
# 5. Phase 24G.27 Deliverables & Manifest Integrity
# ----------------------------------------------------------------------------

PHASE27_DIR = Path("research/strategy_evolution_2018/phase24G27_reliability_security")
PHASE27_MANIFEST = PHASE27_DIR / "phase24G27_manifest.json"

EXPECTED_DELIVERABLES = [
    "phase24G27_atomic_write_report.md",
    "phase24G27_path_validation_report.md",
    "phase24G27_configuration_report.md",
    "phase24G27_security_test_results.md",
    "phase24G27_regression_test_results.md",
    "phase24G27_final_report.md",
    "phase24G27_manifest.json",
]


def test_phase27_all_deliverables_exist():
    """Verify all 7 deliverables exist and have substantial size."""
    assert PHASE27_DIR.exists()
    for fname in EXPECTED_DELIVERABLES:
        fpath = PHASE27_DIR / fname
        assert fpath.exists(), f"Missing deliverable: {fname}"
        assert fpath.stat().st_size > 500, f"Deliverable too small: {fname}"


def test_phase27_manifest_sha256_integrity():
    """Verify cryptographic manifest checksums match on-disk deliverables."""
    assert PHASE27_MANIFEST.exists()
    with open(PHASE27_MANIFEST, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["phase"] == "Phase 24G.27"
    assert manifest["verdict"] == "RELIABILITY_HARDENING_COMPLETED"
    assert manifest["budget_consumed_inr"] == 0.0

    deliverables = manifest["deliverables"]
    assert len(deliverables) == 6

    for item in deliverables:
        fname = item["filename"]
        expected_hash = item["sha256"]
        fpath = PHASE27_DIR / fname
        assert fpath.exists()
        raw = fpath.read_bytes().replace(b"\r\n", b"\n")
        actual_hash = hashlib.sha256(raw).hexdigest()
        assert actual_hash == expected_hash, (
            f"Hash mismatch for {fname}: expected {expected_hash}, got {actual_hash}"
        )


def test_phase27_final_verdict():
    """Verify final report contains formal verdict."""
    final_report = PHASE27_DIR / "phase24G27_final_report.md"
    assert final_report.exists()
    text = final_report.read_text(encoding="utf-8")
    assert "RELIABILITY_HARDENING_COMPLETED" in text
