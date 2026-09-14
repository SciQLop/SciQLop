"""Snippet rendering primitives for graph-context "Copy Python code" actions."""

from __future__ import annotations

from typing import Iterable, Optional

from ._renderer import render_snippet

__all__ = ["format_product_path", "split_product_path", "render_snippet"]


def split_product_path(path: str | Iterable[str]) -> list[str]:
    """Split a user-supplied product path into segments.

    Leading/trailing ``/`` separators are stripped, so all of these
    are equivalent: ``"a//b"``, ``"//a//b"``, ``"/a//b"``, ``"a/b"``,
    ``"/a/b"``. Splits on ``//`` when present (segment names may
    themselves contain ``/``, e.g. AMDA's ``"final / prelim"``),
    otherwise on ``/``. Inner empty segments are preserved so callers
    can reject them (e.g. ``"a////b"``); fully blank paths return ``[]``.
    A list input passes through (also dropping a leading ``"root"``).
    """
    if path is None:
        return []
    if isinstance(path, str):
        s = path.strip().strip("/").strip()
        if not s:
            return []
        if "//" in s:
            return s.split("//")
        return s.split("/")
    segments = [str(s) for s in path]
    if segments and segments[0] == "root":
        segments = segments[1:]
    return segments


def format_product_path(path: Optional[Iterable[str]]) -> str:
    """Render a product-tree path as ``"a//b//c"``, dropping the implicit
    ``"root"`` prefix.

    Uses ``//`` rather than ``/`` because segment names can themselves
    contain ``/`` (e.g. AMDA's ``"final / prelim"``). ``to_product_path``
    (user_api) prefers ``//`` when present so the round-trip stays lossless;
    ``ProductsModel::node`` (SciQLopPlots) strips a leading ``"root"`` when
    looking up by name.
    """
    if not path:
        return ""
    segments = [str(s) for s in path]
    if segments and segments[0] == "root":
        segments = segments[1:]
    return "//".join(segments)
