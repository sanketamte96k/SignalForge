"""
SignalForge Core Engine Package
===============================
Provides cross-cutting infrastructure:
- io_utils: Atomic file write and serialization safety.
- security: Path traversal prevention and input sanitization.
- config: Centralized Pydantic application settings.
"""

from src.core.config import SignalForgeSettings, get_settings
from src.core.io_utils import atomic_write, atomic_write_json
from src.core.security import (
    InvalidSymbolError,
    PathTraversalError,
    SecurityError,
    safe_resolve_symbol_path,
    validate_safe_path,
    validate_symbol,
)

__all__ = [
    "atomic_write",
    "atomic_write_json",
    "validate_safe_path",
    "validate_symbol",
    "safe_resolve_symbol_path",
    "SecurityError",
    "PathTraversalError",
    "InvalidSymbolError",
    "SignalForgeSettings",
    "get_settings",
]
