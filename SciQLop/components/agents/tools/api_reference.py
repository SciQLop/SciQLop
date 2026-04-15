"""Markdown introspection of `SciQLop.user_api` for LLM agents."""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any, List

from ._text import first_line, trim_lines

_ROOT = "SciQLop.user_api"
_MAX_DOC_LINES = 8


def render(module: str) -> str:
    module = (module or "").strip().strip(".")
    if not module:
        return _render_index()
    full = f"{_ROOT}.{module}"
    mod = importlib.import_module(full)
    return _render_module(mod, module)


def _render_index() -> str:
    root = importlib.import_module(_ROOT)
    lines: List[str] = [
        f"# `{_ROOT}` — public API index",
        "",
        "Call `sciqlop_api_reference('<submodule>')` to expand any of these.",
        "",
    ]
    for name, is_pkg in _iter_submodules(root):
        summary = _one_line_doc(importlib.import_module(f"{_ROOT}.{name}"))
        marker = "📦" if is_pkg else "📄"
        lines.append(f"- {marker} **`{name}`** — {summary}")
    root_doc = _one_line_doc(root)
    if root_doc:
        lines.insert(2, f"> {root_doc}")
        lines.insert(3, "")
    return "\n".join(lines)


def _iter_submodules(package) -> List[tuple[str, bool]]:
    if not hasattr(package, "__path__"):
        return []
    out: List[tuple[str, bool]] = []
    for info in pkgutil.iter_modules(package.__path__):
        if info.name.startswith("_"):
            continue
        out.append((info.name, info.ispkg))
    out.sort()
    return out


def _render_module(mod, short_name: str) -> str:
    lines: List[str] = [f"# `{_ROOT}.{short_name}`"]
    doc = inspect.getdoc(mod)
    if doc:
        lines += ["", doc.strip()]

    public = _public_members(mod)
    modules = [(n, o) for n, o in public if inspect.ismodule(o)]
    classes = [(n, o) for n, o in public if inspect.isclass(o)]
    functions = [
        (n, o) for n, o in public
        if inspect.isroutine(o) and not inspect.isclass(o)
    ]
    others = [
        (n, o) for n, o in public
        if not (inspect.ismodule(o) or inspect.isclass(o) or inspect.isroutine(o))
    ]

    if functions:
        lines += ["", "## Functions", ""]
        for name, fn in functions:
            lines += _render_callable(name, fn, heading_level=3)

    if classes:
        lines += ["", "## Classes", ""]
        for name, cls in classes:
            lines += _render_class(name, cls)

    if modules:
        lines += ["", "## Re-exported modules", ""]
        for name, submod in modules:
            origin = getattr(submod, "__name__", "?")
            summary = _one_line_doc(submod)
            suffix = f" — {summary}" if summary else ""
            lines.append(f"- **`{name}`** (`{origin}`){suffix}")

    if others:
        lines += ["", "## Constants / values", ""]
        for name, obj in others:
            lines.append(f"- `{name}` — `{type(obj).__name__}`")

    submods = _iter_submodules(mod)
    if submods:
        lines += ["", "## Submodules", ""]
        for name, is_pkg in submods:
            marker = "📦" if is_pkg else "📄"
            lines.append(
                f"- {marker} **`{short_name}.{name}`** — "
                f"call `sciqlop_api_reference('{short_name}.{name}')`"
            )

    return "\n".join(lines)


def _public_members(mod) -> List[tuple[str, Any]]:
    exported = getattr(mod, "__all__", None)
    out: List[tuple[str, Any]] = []
    if exported is not None:
        for name in exported:
            if name.startswith("_"):
                continue
            obj = getattr(mod, name, None)
            if obj is None:
                continue
            out.append((name, obj))
    else:
        for name, obj in inspect.getmembers(mod):
            if name.startswith("_"):
                continue
            if not _belongs_to(obj, mod):
                continue
            out.append((name, obj))
    out.sort(key=lambda it: it[0])
    return out


def _belongs_to(obj, mod) -> bool:
    origin = getattr(obj, "__module__", None)
    if origin is None:
        return False
    return origin == mod.__name__ or origin.startswith(mod.__name__ + ".")


def _render_callable(name: str, fn, heading_level: int) -> List[str]:
    sig = _safe_signature(fn)
    header = "#" * heading_level
    lines = [f"{header} `{name}{sig}`"]
    doc = inspect.getdoc(fn)
    if doc:
        lines.append("")
        lines.append(_trim_doc(doc))
    lines.append("")
    return lines


def _render_class(name: str, cls) -> List[str]:
    sig = _safe_signature(cls)
    lines = [f"### `class {name}{sig}`"]
    doc = inspect.getdoc(cls)
    if doc:
        lines += ["", _trim_doc(doc)]
    methods = _public_class_members(cls)
    if methods:
        lines += ["", "**Members:**", ""]
        for m_name, m_obj, kind in methods:
            lines.append(_render_class_member(m_name, m_obj, kind))
    lines.append("")
    return lines


def _render_class_member(name: str, obj, kind: str) -> str:
    if kind == "property":
        fget = getattr(obj, "fget", None)
        doc = inspect.getdoc(fget) if fget else inspect.getdoc(obj)
        one_line = first_line(doc) if doc else ""
        suffix = f" — {one_line}" if one_line else ""
        return f"- `{name}` *(property)*{suffix}"
    if kind == "attribute":
        return f"- `{name}` — `{type(obj).__name__}`"
    sig = _safe_signature(obj)
    doc = inspect.getdoc(obj)
    one_line = first_line(doc) if doc else ""
    suffix = f" — {one_line}" if one_line else ""
    tag = ""
    if kind == "staticmethod":
        tag = " *(static)*"
    elif kind == "classmethod":
        tag = " *(classmethod)*"
    return f"- `{name}{sig}`{tag}{suffix}"


def _public_class_members(cls) -> List[tuple[str, Any, str]]:
    out: List[tuple[str, Any, str]] = []
    for name in dir(cls):
        if name.startswith("_"):
            continue
        raw = inspect.getattr_static(cls, name, None)
        if raw is None:
            continue
        if isinstance(raw, property):
            out.append((name, raw, "property"))
        elif isinstance(raw, staticmethod):
            out.append((name, raw.__func__, "staticmethod"))
        elif isinstance(raw, classmethod):
            out.append((name, raw.__func__, "classmethod"))
        elif inspect.isfunction(raw) or inspect.ismethoddescriptor(raw) or inspect.isbuiltin(raw):
            out.append((name, raw, "method"))
        elif callable(raw):
            out.append((name, raw, "method"))
        else:
            out.append((name, raw, "attribute"))
    out.sort(key=lambda it: it[0])
    return out


def _safe_signature(obj) -> str:
    try:
        return str(inspect.signature(obj))
    except (TypeError, ValueError):
        return ""


def _one_line_doc(obj) -> str:
    return first_line(inspect.getdoc(obj) or "")


def _trim_doc(doc: str) -> str:
    return trim_lines(doc, _MAX_DOC_LINES)
