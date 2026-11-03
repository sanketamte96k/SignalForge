"""
SignalForge — Atomic File-Writing & I/O Safety Utilities
=========================================================
Provides atomic, crash-resilient file persistence using temporary files
and atomic replacement (os.replace). Guarantees:
1. Writes are performed into a hidden temporary file in the target directory (same filesystem).
2. Files are fully flushed to disk (flush + os.fsync) and closed before replacement.
3. Original destination files remain untouched if any write, serialization, or sync error occurs.
4. Temporary files are always cleaned up upon failure.
5. File permissions (st_mode) are preserved from existing targets where applicable.
6. JSON serialization is validated prior to opening file descriptors.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Generator, Union


def atomic_write(
    destination: Union[Path, str],
    content: Union[str, bytes],
    *,
    encoding: str = "utf-8",
    make_parents: bool = True,
    preserve_mode: bool = True,
    sync: bool = True,
) -> Path:
    """
    Safely write text or binary content to destination path atomically.

    Parameters
    ----------
    destination : Path | str
        Target file path.
    content : str | bytes
        Data payload to persist.
    encoding : str, default "utf-8"
        Text encoding (used only when content is str).
    make_parents : bool, default True
        Automatically create parent directories if missing.
    preserve_mode : bool, default True
        Preserve existing file permissions if destination already exists.
    sync : bool, default True
        Force physical flush to disk via os.fsync.

    Returns
    -------
    Path
        Canonical resolved path of the successfully written file.
    """
    dest_path = Path(destination)

    if make_parents:
        dest_path.parent.mkdir(parents=True, exist_ok=True)

    is_binary = isinstance(content, (bytes, bytearray, memoryview))
    mode_flag = "wb" if is_binary else "w"

    existing_mode = None
    if preserve_mode and dest_path.exists():
        try:
            existing_mode = dest_path.stat().st_mode
        except OSError:
            existing_mode = None

    temp_path: Path | None = None
    try:
        # Create temporary file in the exact same directory to ensure atomic same-filesystem os.replace
        with tempfile.NamedTemporaryFile(
            mode=mode_flag,
            dir=dest_path.parent,
            prefix=f".{dest_path.name}.",
            suffix=".tmp",
            delete=False,
            encoding=None if is_binary else encoding,
        ) as tmp:
            temp_path = Path(tmp.name)
            tmp.write(content)
            tmp.flush()
            if sync and hasattr(os, "fsync"):
                os.fsync(tmp.fileno())

        # Close is complete. Apply permissions if preserving existing mode
        if existing_mode is not None and temp_path is not None:
            try:
                temp_path.chmod(existing_mode)
            except (OSError, NotImplementedError):
                pass

        # Atomic replacement: replaces destination cleanly or raises OSError
        os.replace(temp_path, dest_path)
        temp_path = None  # Replaced successfully, no longer orphan
        return dest_path

    except Exception:
        # Guarantee cleanup of temporary file on any error
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise


def atomic_write_json(
    destination: Union[Path, str],
    data: Any,
    *,
    indent: int = 2,
    sort_keys: bool = False,
    make_parents: bool = True,
    encoding: str = "utf-8",
    preserve_mode: bool = True,
    sync: bool = True,
) -> Path:
    """
    Safely serialize and write JSON data to destination atomically.

    Validates and serializes the JSON string BEFORE creating or modifying any
    files on disk. A serialization failure (e.g. TypeError on non-serializable object)
    will fail immediately without leaving temporary files or modifying the destination.

    Parameters
    ----------
    destination : Path | str
        Target JSON file path.
    data : Any
        JSON-serializable data structure.
    indent : int, default 2
        Indentation spaces for formatting.
    sort_keys : bool, default False
        Whether to sort dictionary keys.
    make_parents : bool, default True
        Automatically create parent directories.
    encoding : str, default "utf-8"
        Text encoding.
    preserve_mode : bool, default True
        Preserve existing file permissions.
    sync : bool, default True
        Force physical flush to disk via os.fsync.

    Returns
    -------
    Path
        Path of the persisted JSON file.
    """
    # 1. Pre-serialize to validate JSON before touching filesystem
    serialized = json.dumps(data, indent=indent, sort_keys=sort_keys, ensure_ascii=False)
    # Append trailing newline for POSIX/JSON clean formatting
    serialized_with_newline = f"{serialized}\n"

    # 2. Persist atomically
    return atomic_write(
        destination=destination,
        content=serialized_with_newline,
        encoding=encoding,
        make_parents=make_parents,
        preserve_mode=preserve_mode,
        sync=sync,
    )


@contextlib.contextmanager
def atomic_write_stream(
    destination: Union[Path, str],
    *,
    mode: str = "w",
    encoding: str = "utf-8",
    make_parents: bool = True,
    preserve_mode: bool = True,
    sync: bool = True,
) -> Generator[io.IOBase, None, None]:
    """
    Context manager for streaming atomic writes.

    Yields an open file handle to a temporary file in the destination's parent directory.
    Upon exiting the context block cleanly, flushes, syncs, closes the file, and replaces
    the destination atomically.
    If an exception occurs within the context block, the file handle is closed, the temporary
    file is unlinked, and the original destination is preserved.
    """
    dest_path = Path(destination)
    if make_parents:
        dest_path.parent.mkdir(parents=True, exist_ok=True)

    is_binary = "b" in mode
    existing_mode = None
    if preserve_mode and dest_path.exists():
        try:
            existing_mode = dest_path.stat().st_mode
        except OSError:
            existing_mode = None

    temp_path: Path | None = None
    tmp_file = tempfile.NamedTemporaryFile(
        mode=mode,
        dir=dest_path.parent,
        prefix=f".{dest_path.name}.",
        suffix=".tmp",
        delete=False,
        encoding=None if is_binary else encoding,
    )
    temp_path = Path(tmp_file.name)

    try:
        yield tmp_file
        tmp_file.flush()
        if sync and hasattr(os, "fsync"):
            os.fsync(tmp_file.fileno())
        tmp_file.close()

        if existing_mode is not None:
            try:
                temp_path.chmod(existing_mode)
            except (OSError, NotImplementedError):
                pass

        os.replace(temp_path, dest_path)
        temp_path = None

    except Exception:
        try:
            if not tmp_file.closed:
                tmp_file.close()
        except Exception:
            pass
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
