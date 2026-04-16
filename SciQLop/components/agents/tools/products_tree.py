"""Markdown browser for SciQLop's live ProductsModel.

Unlike `speasy_inventory` (which returns spz_uid-flavored paths for
`speasy.get_data`), this walks the tree that `PlotPanel.plot_product`
actually resolves against — display names with spaces, rooted at
"speasy". Leaves return a ready-to-use `//`-joined path.
"""
from __future__ import annotations

from typing import List, Tuple

from ._text import first_line  # noqa: F401 — reserved for future summaries


def render(path: str) -> str:
    from SciQLopPlots import ProductsModel, ProductsModelNodeType

    parts = _split_path(path)
    pm = ProductsModel.instance()
    node = pm.node(parts)
    if node is None:
        return f"no products node at path `{path}`" if path else _render_root(pm, ProductsModelNodeType)

    if _is_parameter(node, ProductsModelNodeType):
        return _render_parameter(parts, node)
    return _render_folder(parts, node, ProductsModelNodeType)


def _split_path(path: str) -> List[str]:
    path = (path or "").strip().strip("/")
    if not path:
        return []
    if "//" in path:
        return [p for p in path.split("//") if p]
    return [p for p in path.split("/") if p]


def _render_root(pm, node_types) -> str:
    root = pm.node([])
    if root is not None:
        return _render_folder([], root, node_types)
    # ProductsModel has no explicit root node — enumerate top-level children
    # via the QAbstractItemModel API (rowCount at invalid parent index).
    from PySide6.QtCore import QModelIndex
    count = pm.rowCount(QModelIndex())
    if count == 0:
        return "# Products tree is empty — no providers loaded."
    names = []
    for i in range(count):
        idx = pm.index(i, 0, QModelIndex())
        names.append(idx.data() or f"<row {i}>")
    lines = ["# `<root>`", "", f"## Providers ({count})", ""]
    for name in names:
        lines.append(f"- 📁 **`{name}`**")
    lines.append("")
    lines.append(f"Drill deeper with `sciqlop_products_tree('{names[0]}')`.")
    return "\n".join(lines)


def _render_folder(parts: List[str], node, node_types) -> str:
    folders: List[Tuple[str, object]] = []
    parameters: List[Tuple[str, object]] = []
    for child in _children(node):
        name = child.name()
        if _is_parameter(child, node_types):
            parameters.append((name, child))
        else:
            folders.append((name, child))

    title = "//".join(parts) if parts else "<root>"
    lines = [f"# `{title}`", ""]
    if parts:
        lines.append(
            "Path format for `plot_product`: the items listed below joined "
            "with `//`, e.g. `" + "//".join(parts + ["<child>"]) + "`."
        )
        lines.append("")

    if folders:
        lines += [f"## Folders ({len(folders)})", ""]
        for name, _ in folders:
            lines.append(f"- 📁 **`{name}`**")
        lines.append("")

    if parameters:
        lines += [f"## Parameters ({len(parameters)})", ""]
        for name, p in parameters:
            full = "//".join(parts + [name])
            meta = _parameter_meta(p)
            suffix = f" — {meta}" if meta else ""
            lines.append(f"- 📊 `{full}`{suffix}")
        lines.append("")

    if not folders and not parameters:
        lines.append("*(empty node)*")
    else:
        sample = (folders + parameters)[0][0]
        next_path = "//".join(parts + [sample]) if parts else sample
        lines.append(
            f"Drill deeper with `sciqlop_products_tree('{next_path}')`."
        )

    return "\n".join(lines)


def _render_parameter(parts: List[str], node) -> str:
    full = "//".join(parts)
    lines = [
        f"# `{full}` — parameter",
        "",
        f"**Full path (ready for `plot_product`):** `{full}`",
        "",
    ]
    ptype = _safe(lambda: str(node.parameter_type()).rsplit(".", 1)[-1])
    if ptype:
        lines.append(f"- **parameter_type**: `{ptype}`")
    provider = _safe(lambda: node.provider())
    if provider:
        lines.append(f"- **provider**: `{provider}`")
    tooltip = _safe(lambda: node.tooltip())
    if tooltip:
        lines += ["", "**Tooltip:**", "", str(tooltip)]
    lines += [
        "",
        "**Usage:**",
        "",
        "```python",
        "from SciQLop.user_api.plot import create_plot_panel",
        "panel = create_plot_panel()",
        f'panel.plot_product("{full}")',
        "```",
    ]
    return "\n".join(lines)


def _children(node) -> List[object]:
    try:
        n = node.children_count()
    except Exception:
        return []
    out = []
    for i in range(n):
        c = _safe(lambda i=i: node.child(i))
        if c is not None:
            out.append(c)
    return out


def _is_parameter(node, node_types) -> bool:
    try:
        return node.node_type() == node_types.PARAMETER
    except Exception:
        return False


def _parameter_meta(node) -> str:
    bits = []
    ptype = _safe(lambda: str(node.parameter_type()).rsplit(".", 1)[-1])
    if ptype:
        bits.append(ptype)
    provider = _safe(lambda: node.provider())
    if provider:
        bits.append(f"via `{provider}`")
    return " ".join(bits)


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None
