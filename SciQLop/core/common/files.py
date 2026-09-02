"""Filesystem primitives on the thin launcher import path (stdlib only)."""

from __future__ import annotations

import os
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
