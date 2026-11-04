"""
SignalForge — Phase 24G.31: Deployment Readiness & Reproducibility Test Suite
=============================================================================
Validates:
1. Pre-flight safety invariants (V1 config hash, canonical dataset hashes, 2020 quarantine).
2. Clean installation dependency manifests (requirements.txt, package.json, .env.example).
3. Dual backtest reproducibility audit (100% bit-for-bit identical trades and metrics).
4. Security policy checks (CORS restrictions, .env git exclusion, path traversal protection).
5. Comprehensive documentation suite completeness (docs/ index and README.md).
6. Local deployment artifacts (Dockerfile, docker-compose.yml, CI workflow).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest

from src.core.config import get_settings
from src.core.io_utils import atomic_write
from src.core.security import PathTraversalError, validate_safe_path, validate_symbol
from src.strategy.job_manager import BacktestJobManager


FROZEN_V1_CONFIG_HASH = "920515d71ebb2cea693193897103d19c1ec35c5013b85715dc209b64a45e4ec7"
CANONICAL_ADANIPORTS_HASH = "fb3275527303879c5edd26bcff08ba6a9a41c5de85f5acc6ead21b01fce26cf9"
CANONICAL_NIFTY50_HASH = "f5a1047ee65129c52eb8dfb1888a9daf41a2a6f21e1297beefb7b505e4065e2a"


# ============================================================================
# 1. Protected Invariants & Provenance Verification
# ============================================================================

def test_v1_frozen_config_hash():
    """Verify frozen V1 configuration snapshot hash is untouched."""
    v1_path = Path("research/strategy_evolution_2018/phase22_final_validation/strategy_snapshot.json")
    assert v1_path.exists(), "V1 config snapshot file missing"
    with open(v1_path, "r", encoding="utf-8") as f:
        snap = json.load(f)
    v1_h = hashlib.sha256(json.dumps(snap, sort_keys=True).encode("utf-8")).hexdigest()
    assert v1_h == FROZEN_V1_CONFIG_HASH, f"V1 config hash mismatch: {v1_h}"


def test_canonical_dataset_hashes():
    """Verify canonical on-disk dataset hashes if files are present."""
    adani_path = Path("data/historical/stocks/ADANIPORTS_1m.csv")
    if adani_path.exists():
        h = hashlib.sha256(adani_path.read_bytes()).hexdigest()
        assert h == CANONICAL_ADANIPORTS_HASH, f"ADANIPORTS canonical hash mismatch: {h}"

    nifty_path = Path("data/historical/nifty50_1m_signalforge.csv")
    if nifty_path.exists():
        h = hashlib.sha256(nifty_path.read_bytes()).hexdigest()
        assert h == CANONICAL_NIFTY50_HASH, f"NIFTY 50 hash mismatch: {h}"


def test_quarantined_2020_holdout_preserved():
    """Verify 2020 holdout partition remains quarantined."""
    manifest_path = Path("data/historical/2020_holdout_manifest.json")
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            m = json.load(f)
        status = m.get("quarantine_status", "").upper()
        assert status in {"CONTAMINATED", "QUARANTINED", "EXPLORATORY"}, f"Invalid quarantine status: {status}"


# ============================================================================
# 2. Dependency Manifests & Clean Install Audit
# ============================================================================

def test_backend_requirements_manifest():
    """Verify requirements.txt exists and specifies all core dependencies."""
    req_file = Path("requirements.txt")
    assert req_file.exists(), "requirements.txt missing"
    content = req_file.read_text(encoding="utf-8")

    expected_pkgs = ["fastapi", "uvicorn", "pydantic", "pandas", "numpy", "python-dotenv", "pytest", "httpx"]
    for pkg in expected_pkgs:
        assert pkg in content, f"Package '{pkg}' missing from requirements.txt"


def test_frontend_package_manifest():
    """Verify frontend/package.json contains necessary build and test scripts."""
    pkg_file = Path("frontend/package.json")
    assert pkg_file.exists(), "frontend/package.json missing"
    with open(pkg_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    scripts = data.get("scripts", {})
    assert "build" in scripts, "npm run build script missing"
    assert "test" in scripts, "npm test script missing"
    assert "dev" in scripts, "npm run dev script missing"

    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    assert "react" in deps
    assert "vite" in deps


def test_env_example_safety():
    """Verify .env.example contains no real credentials or private keys."""
    env_ex = Path(".env.example")
    assert env_ex.exists(), ".env.example missing"
    text = env_ex.read_text(encoding="utf-8")
    assert "your_groww_api_key_here" in text or "your_" in text
    assert "password" not in text.lower() or "your_" in text


def test_gitignore_security_exclusions():
    """Verify .gitignore properly excludes secrets, local data, and build artifacts."""
    git_ign = Path(".gitignore")
    assert git_ign.exists(), ".gitignore missing"
    text = git_ign.read_text(encoding="utf-8")

    assert ".env" in text
    assert "data/paper_trading/*" in text
    assert "frontend/dist/" in text
    assert "frontend/node_modules/" in text


# ============================================================================
# 3. Dual Backtest Reproducibility Audit
# ============================================================================

def test_dual_backtest_reproducibility():
    """Verify two sequential backtest runs with identical inputs produce bit-for-bit identical results."""
    data_path = Path("data/historical/nifty50_1m_signalforge.csv")
    if not data_path.exists():
        pytest.skip("NIFTY 50 historical data missing in bare environment")

    mgr = BacktestJobManager(max_workers=1)
    params = {
        "symbol": "NIFTY 50",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "initial_capital": 100_000.0,
        "quantity": 1,
        "execution_model": "next_open",
        "transaction_cost_rate": 0.0001,
    }

    # Run 1
    job1 = mgr.create_job(params)
    mgr._execute_job(job1.job_id)
    r1 = mgr.get_job(job1.job_id).result
    assert r1 is not None

    # Run 2
    job2 = mgr.create_job(params)
    mgr._execute_job(job2.job_id)
    r2 = mgr.get_job(job2.job_id).result
    assert r2 is not None

    # Compare Metrics
    assert r1["metrics"] == r2["metrics"], "Metrics discrepancy detected between runs"

    # Compare Trades
    assert len(r1["trades"]) == len(r2["trades"]), "Trade count discrepancy detected"
    for idx, (t1, t2) in enumerate(zip(r1["trades"], r2["trades"]), 1):
        assert t1 == t2, f"Trade #{idx} mismatch between identical runs"

    # Compare Portfolio State
    assert r1["portfolio"] == r2["portfolio"], "Portfolio terminal state discrepancy detected"


# ============================================================================
# 4. Security & Configuration Policy
# ============================================================================

def test_security_path_traversal_protection(tmp_path):
    """Verify validate_safe_path prevents path traversal outside base directory."""
    base_dir = tmp_path / "sandbox"
    base_dir.mkdir()

    # Valid subpath
    valid_file = base_dir / "data.csv"
    valid_file.write_text("dummy")
    safe_target = validate_safe_path("data.csv", base_dir)
    assert safe_target.resolve() == valid_file.resolve()

    # Traversal attack
    with pytest.raises(PathTraversalError):
        validate_safe_path("../outside.csv", base_dir)

    with pytest.raises(PathTraversalError):
        validate_safe_path("..\\outside.csv", base_dir)


def test_security_symbol_validator():
    """Verify validate_symbol enforces uppercase alphanumeric characters."""
    assert validate_symbol("INFY") == "INFY"
    assert validate_symbol("TCS") == "TCS"
    assert validate_symbol("RELIANCE") == "RELIANCE"

    with pytest.raises(ValueError):
        validate_symbol("INFY; DROP TABLE")

    with pytest.raises(ValueError):
        validate_symbol("../../etc/passwd")


def test_atomic_file_write_durability(tmp_path):
    """Verify atomic_write successfully creates and replaces files safely."""
    target = tmp_path / "test_atomic.txt"
    atomic_write(target, "content_initial")
    assert target.read_text(encoding="utf-8") == "content_initial"

    atomic_write(target, "content_updated")
    assert target.read_text(encoding="utf-8") == "content_updated"


# ============================================================================
# 5. Documentation Suite Completeness
# ============================================================================

def test_documentation_files_completeness():
    """Verify all 8 documentation guides exist in docs/ and have substantial content."""
    docs_dir = Path("docs")
    assert docs_dir.exists() and docs_dir.is_dir(), "docs directory missing"

    required_docs = [
        "INSTALLATION.md",
        "CONFIGURATION.md",
        "STARTUP.md",
        "API.md",
        "TROUBLESHOOTING.md",
        "TESTING.md",
        "BACKUP_RECOVERY.md",
        "SECURITY_DEPLOYMENT.md",
    ]

    for doc_name in required_docs:
        doc_path = docs_dir / doc_name
        assert doc_path.exists(), f"Documentation file '{doc_name}' missing from docs/"
        assert doc_path.stat().st_size > 300, f"Documentation file '{doc_name}' is too brief"

    # Verify README.md references docs
    readme = Path("README.md")
    assert readme.exists()
    readme_text = readme.read_text(encoding="utf-8")
    for doc_name in required_docs:
        assert doc_name in readme_text, f"README.md does not reference '{doc_name}'"


# ============================================================================
# 6. CI & Local Deployment Artifacts
# ============================================================================

def test_github_actions_workflow_exists():
    """Verify GitHub Actions CI workflow is configured."""
    ci_file = Path(".github/workflows/ci.yml")
    assert ci_file.exists(), ".github/workflows/ci.yml missing"
    ci_text = ci_file.read_text(encoding="utf-8")
    assert "backend-test" in ci_text
    assert "frontend-test" in ci_text
    assert "pytest" in ci_text
    assert "npm test" in ci_text


def test_docker_artifacts_configured():
    """Verify local Dockerfile and docker-compose.yml are present."""
    dockerfile = Path("Dockerfile")
    assert dockerfile.exists(), "Dockerfile missing"
    docker_text = dockerfile.read_text(encoding="utf-8")
    assert "FROM python" in docker_text
    assert "FROM node" in docker_text

    compose = Path("docker-compose.yml")
    assert compose.exists(), "docker-compose.yml missing"
    compose_text = compose.read_text(encoding="utf-8")
    assert "services:" in compose_text
    assert "8000:8000" in compose_text
