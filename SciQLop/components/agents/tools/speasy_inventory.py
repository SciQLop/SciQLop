"""Markdown browser for `speasy.inventories.data_tree` (provider → parameter)."""
from __future__ import annotations

from typing import List, Tuple

from ._text import first_line, trim_lines


def render(path: str) -> str:
    import speasy as spz
    from speasy.core.inventory.indexes import ParameterIndex, SpeasyIndex

    path = (path or "").strip().strip(".")
    root = spz.inventories.data_tree

    if not path:
        return _render_providers(root)

    node = _resolve(root, path)
    if node is None:
        return f"no inventory node at path `{path}`"

    if isinstance(node, ParameterIndex):
        return _render_parameter(path, node)

    if isinstance(node, SpeasyIndex):
        return _render_dir(path, node, ParameterIndex)

    return f"unexpected node type at `{path}`: {type(node).__name__}"


def _resolve(root, path: str):
    node = root
    for part in path.split("."):
        node = getattr(node, part, None)
        if node is None:
            return None
    return node


def _render_providers(root) -> str:
    providers = sorted(k for k in dir(root) if not k.startswith("_"))
    lines = [
        "# `speasy.inventories.data_tree` — providers",
        "",
        "Call `sciqlop_speasy_inventory('<provider>')` to drill in.",
        "",
    ]
    for p in providers:
        lines.append(f"- **`{p}`**")
    return "\n".join(lines)


def _render_dir(path: str, node, ParameterIndex) -> str:
    dirs: List[Tuple[str, object]] = []
    params: List[Tuple[str, object]] = []
    for name in sorted(dir(node)):
        if name.startswith("_"):
            continue
        child = getattr(node, name, None)
        if child is None or getattr(child, "spz_name", None) is None:
            continue
        if isinstance(child, ParameterIndex):
            params.append((name, child))
        else:
            dirs.append((name, child))

    lines = [f"# `{path}`", ""]
    doc = first_line(getattr(node, "description", "") or "")
    if doc:
        lines += [f"> {doc}", ""]

    if dirs:
        lines += [f"## Subdirectories ({len(dirs)})", ""]
        for name, child in dirs:
            label = type(child).__name__
            display = _display_name(child, name)
            lines.append(
                f"- **`{name}`** — {label}"
                + (f" — {display}" if display and display != name else "")
            )
        lines.append("")

    if params:
        lines += [f"## Parameters ({len(params)})", ""]
        for name, p in params:
            lines.append(f"- `{name}` — {_param_summary(p)}")
        lines.append("")

    if not dirs and not params:
        lines.append("*(empty node)*")

    lines.append(
        f"\nDrill deeper with `sciqlop_speasy_inventory('{path}.<child>')`."
    )
    return "\n".join(lines)


def _render_parameter(path: str, p) -> str:
    lines = [f"# `{path}` — parameter", ""]
    lines.append(f"- **name**: {_display_name(p, path.rsplit('.', 1)[-1])}")
    uid = _call(p, "spz_uid")
    provider = _call(p, "spz_provider")
    if uid:
        lines.append(f"- **spz_uid**: `{uid}`")
    if provider:
        lines.append(f"- **provider**: `{provider}`")
    for attr in ("units", "start_date", "stop_date", "dataset"):
        val = getattr(p, attr, None)
        if val:
            lines.append(f"- **{attr}**: {val}")
    desc = getattr(p, "description", None)
    if desc:
        lines += ["", "**Description:**", "", trim_lines(str(desc), 12)]
    if uid and provider:
        lines += [
            "",
            "**Fetch example:**",
            "",
            "```python",
            "import speasy as spz",
            f"v = spz.get_data('{provider}/{uid}', start, stop)",
            "```",
        ]
    return "\n".join(lines)


def _param_summary(p) -> str:
    bits = []
    display = _display_name(p, "")
    if display:
        bits.append(display)
    units = getattr(p, "units", None)
    if units:
        bits.append(f"[{units}]")
    uid = _call(p, "spz_uid")
    if uid:
        bits.append(f"uid=`{uid}`")
    return " ".join(bits) if bits else "parameter"


def _display_name(node, fallback: str) -> str:
    name = _call(node, "spz_name") or getattr(node, "name", None) or fallback
    return str(name) if name else fallback


def _call(node, attr: str):
    fn = getattr(node, attr, None)
    if fn is None:
        return None
    try:
        return fn() if callable(fn) else fn
    except Exception:
        return None
