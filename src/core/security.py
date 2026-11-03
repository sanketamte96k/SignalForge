"""
SignalForge — Path Validation & Security Hardening
==================================================
Provides centralized path validation and input sanitization to prevent:
1. Directory traversal attacks (../, ..\\, absolute paths).
2. Symlink escape beyond designated data boundaries.
3. Unsafe symbol injection in filesystem paths and database queries.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Union


class SecurityError(ValueError):
    """Base exception for security validation failures, inheriting from ValueError."""
    pass


class PathTraversalError(SecurityError):
    """Raised when a resolved file path escapes its designated root boundary."""
    pass


class InvalidSymbolError(SecurityError):
    """Raised when a stock symbol contains invalid or dangerous characters."""
    pass


# Whitelist regex for NSE stock symbols and Yahoo-style tickers:
# Allows uppercase letters, digits, underscores, hyphens (e.g. BAJAJ-AUTO),
# ampersands (e.g. M&M), and single dot for exchange suffixes (e.g. RELIANCE.NS).
# Explicitly forbids path separators (/ and \), null bytes, and parent-directory tokens (..).
_VALID_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9_\-&]+(\.[A-Z0-9]+)?$")


def validate_symbol(symbol: str) -> str:
    """
    Validate and normalize a stock symbol.

    Parameters
    ----------
    symbol : str
        Stock symbol to validate.

    Returns
    -------
    str
        Uppercased, stripped, validated symbol.

    Raises
    ------
    InvalidSymbolError
        If symbol is empty, contains path traversal sequences, or violates whitelist.
    """
    if not isinstance(symbol, str):
        raise TypeError("Stock symbol must be a string.")

    cleaned = symbol.strip().upper()

    if not cleaned:
        raise InvalidSymbolError("Stock symbol must not be empty.")

    if len(cleaned) > 30:
        raise InvalidSymbolError(f"Stock symbol exceeds maximum length (30): '{cleaned}'")

    # Reject explicit directory traversal tokens
    if ".." in cleaned or "/" in cleaned or "\\" in cleaned or "\0" in cleaned:
        raise InvalidSymbolError(f"Directory traversal tokens forbidden in symbol: '{symbol}'")

    if not _VALID_SYMBOL_PATTERN.match(cleaned):
        raise InvalidSymbolError(
            f"Invalid stock symbol format: '{cleaned}'. "
            "Must contain only alphanumeric characters, hyphens, underscores, ampersands, and exchange suffix."
        )

    return cleaned


def validate_safe_path(
    target_path: Union[Path, str],
    base_dir: Union[Path, str],
    *,
    allow_nonexistent: bool = True,
) -> Path:
    """
    Verify that target_path strictly resolves within base_dir.

    Handles relative paths, absolute paths, parent traversal ('..'),
    and symlink resolution via Path.resolve().

    Parameters
    ----------
    target_path : Path | str
        The path to validate.
    base_dir : Path | str
        The permitted root boundary directory.
    allow_nonexistent : bool, default True
        Whether to permit target paths that do not yet exist on disk
        (e.g. targets for prospective file creation).

    Returns
    -------
    Path
        Canonical resolved path strictly guaranteed to be within base_dir.

    Raises
    ------
    PathTraversalError
        If target_path escapes base_dir.
    FileNotFoundError
        If allow_nonexistent is False and target_path does not exist.
    """
    base = Path(base_dir).resolve()
    target = Path(target_path)

    # If target is relative, resolve it relative to base
    if not target.is_absolute():
        resolved_target = (base / target).resolve()
    else:
        resolved_target = target.resolve()

    # Use is_relative_to (Python 3.9+) to avoid unsafe string-prefix vulnerabilities
    try:
        is_safe = resolved_target.is_relative_to(base)
    except AttributeError:
        # Fallback for older python or mock environments
        try:
            resolved_target.relative_to(base)
            is_safe = True
        except ValueError:
            is_safe = False

    if not is_safe:
        raise PathTraversalError(
            f"Path traversal detected: Target '{target_path}' resolves to '{resolved_target}', "
            f"which escapes permitted boundary '{base}'."
        )

    if not allow_nonexistent and not resolved_target.exists():
        raise FileNotFoundError(f"Safe path does not exist: '{resolved_target}'")

    return resolved_target


def safe_resolve_symbol_path(
    symbol: str,
    base_dir: Union[Path, str],
    *,
    suffix: str = "_1m.csv",
) -> Path:
    """
    Validate a stock symbol and safely resolve its data file path inside base_dir.

    Parameters
    ----------
    symbol : str
        Stock symbol.
    base_dir : Path | str
        Directory containing symbol data files.
    suffix : str, default "_1m.csv"
        File suffix to append.

    Returns
    -------
    Path
        Fully resolved, validated path within base_dir.
    """
    clean_symbol = validate_symbol(symbol)
    filename = f"{clean_symbol}{suffix}"
    return validate_safe_path(filename, base_dir)
