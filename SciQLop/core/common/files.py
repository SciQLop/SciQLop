"""Filesystem primitives on the thin launcher import path (stdlib only)."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path


def write_text_atomic(path: Path, text: str) -> None:
    """Write *text* to *path* atomically.

    Writes to a sibling temp file then ``os.replace``s it into place, so a
    crash or power loss mid-write can never leave *path* truncated or
    half-written — readers always see either the old content or the new one.
    """
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text)
    os.replace(tmp_path, path)


def remove_tree(path: Path, attempts: int = 6, first_delay: float = 0.25) -> None:
    """``shutil.rmtree`` that rides out Windows' asynchronous deletes.

    https://github.com/python/cpython/issues/84324 — a scanner (Defender,
    Search indexer) holding a just-unlinked file open leaves its directory
    entry pending, so the parent ``rmdir`` fails with ERROR_DIR_NOT_EMPTY
    until the scanner lets go. Retrying with a short backoff is what pip does.
    """
    delay = first_delay
    for remaining in reversed(range(attempts)):
        try:
            shutil.rmtree(path)
            return
        except OSError:
            if not path.exists():
                return
            if remaining == 0:
                raise
        time.sleep(delay)
        delay *= 2
