"""Snippet rendering primitives for graph-context "Copy Python code" actions."""
from __future__ import annotations

from typing import Iterable, Optional

from ._renderer import render_snippet

__all__ = ["format_product_path", "render_snippet"]


def format_product_path(path: Optional[Iterable[str]]) -> str:
    """Render a product-tree path as ``"a/b/c"``, dropping the implicit
    ``"root"`` prefix.

    ``ProductsModel::node`` (SciQLopPlots) strips a leading ``"root"`` when
    looking up by name, and ``to_product_path`` (user_api) splits on ``/``
    or ``//`` — so the receiver accepts this form unchanged. The list-literal
    form was harder to read in clipboard output.
    """
    if not path:
        return ""
    segments = [str(s) for s in path]
    if segments and segments[0] == "root":
        segments = segments[1:]
    return "/".join(segments)
