"""Shared base64-image → tempfile helper."""
from __future__ import annotations

import base64
import uuid
from pathlib import Path
from typing import Optional


def write_b64_image(data: Optional[str], mime: str, tempdir: Path, prefix: str = "img") -> Optional[str]:
    if not data:
        return None
    if "png" in mime:
        ext = ".png"
    elif "jpeg" in mime or "jpg" in mime:
        ext = ".jpg"
    else:
        ext = ".bin"
    path = Path(tempdir) / f"{prefix}_{uuid.uuid4().hex}{ext}"
    try:
        path.write_bytes(base64.b64decode(data))
    except (ValueError, OSError):
        return None
    return str(path)
