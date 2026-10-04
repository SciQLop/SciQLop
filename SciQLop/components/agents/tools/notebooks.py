"""Workspace notebook inspection / editing helpers.

Paths are resolved relative to the active SciQLop workspace directory
and confined to it — no traversal outside.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

_PRUNED_DIRS = {
    ".venv", ".venv-b", "venv", ".ipynb_checkpoints", "__pycache__", ".git",
    "node_modules", "site-packages", "archive", ".tox", ".mypy_cache",
}


def workspace_dir() -> Path:
    env = os.environ.get("SCIQLOP_WORKSPACE_DIR")
    if env:
        return Path(env).resolve()
    try:
        from SciQLop.components.workspaces import workspaces_manager_instance
        ws = workspaces_manager_instance().workspace
        return Path(ws.workspace_dir).resolve()
    except Exception as e:
        raise RuntimeError(f"cannot determine workspace dir: {e}")


def _resolve_notebook(rel_path: str) -> Path:
    base = workspace_dir()
    candidate = (base / rel_path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise ValueError(f"path escapes workspace: {rel_path!r}")
    if candidate.suffix != ".ipynb":
        raise ValueError(f"not a notebook path: {rel_path!r}")
    return candidate


def _walk_notebooks(base: Path) -> List[Path]:
    out: List[Path] = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in _PRUNED_DIRS and not d.startswith(".")]
        for name in files:
            if name.endswith(".ipynb"):
                out.append(Path(root) / name)
    out.sort()
    return out


def list_notebooks() -> str:
    base = workspace_dir()
    notebooks = _walk_notebooks(base)
    if not notebooks:
        return f"# Notebooks in `{base}`\n\n*(none found)*"
    lines = [f"# Notebooks in `{base}`", ""]
    for nb in notebooks:
        rel = nb.relative_to(base)
        size_kb = nb.stat().st_size / 1024
        lines.append(f"- `{rel}` — {_count_cells(nb)} cells, {size_kb:.1f} KiB")
    return "\n".join(lines)


def _count_cells(path: Path) -> int:
    try:
        with path.open("rb") as f:
            return len(json.load(f).get("cells", []))
    except Exception:
        return -1


def read_notebook(rel_path: str) -> str:
    import nbformat
    nb_path = _resolve_notebook(rel_path)
    nb = nbformat.read(str(nb_path), as_version=4)
    lines = [f"# `{rel_path}` — {len(nb.cells)} cells", ""]
    for i, cell in enumerate(nb.cells):
        lines += _render_cell(i, cell)
    return "\n".join(lines)


def _render_cell(index: int, cell) -> List[str]:
    kind = cell.get("cell_type", "?")
    src = cell.get("source", "")
    if isinstance(src, list):
        src = "".join(src)
    header = f"## Cell {index} — `{kind}`"
    if kind == "code":
        body = f"```python\n{src}\n```"
    elif kind == "markdown":
        body = f"````markdown\n{src}\n````"
    else:
        body = f"```\n{src}\n```"
    parts = [header, "", body]
    if kind == "code":
        parts += _render_outputs(cell.get("outputs", []))
    parts.append("")
    return parts


_MAX_OUTPUT_CHARS = 2000


def _render_outputs(outputs) -> List[str]:
    if not outputs:
        return []
    lines = ["", "**outputs:**"]
    for o in outputs:
        ot = o.get("output_type")
        if ot == "stream":
            lines.append(f"```\n{str(o.get('text', ''))[:_MAX_OUTPUT_CHARS]}\n```")
        elif ot in ("execute_result", "display_data"):
            data = o.get("data", {})
            if "text/plain" in data:
                lines.append(f"```\n{str(data['text/plain'])[:_MAX_OUTPUT_CHARS]}\n```")
            for mime in data:
                if mime.startswith("image/"):
                    lines.append(f"[image: {mime}]")
        elif ot == "error":
            tb = "\n".join(o.get("traceback", []))[:_MAX_OUTPUT_CHARS]
            lines.append(f"```\n{o.get('ename', '')}: {o.get('evalue', '')}\n{tb}\n```")
    return lines


def write_cell(rel_path: str, index: int, source: str, cell_type: Optional[str]) -> Dict[str, Any]:
    import nbformat
    nb_path = _resolve_notebook(rel_path)
    nb = nbformat.read(str(nb_path), as_version=4)
    if index < 0 or index >= len(nb.cells):
        return {"ok": False, "error": f"index {index} out of range (0..{len(nb.cells) - 1})"}
    cell = nb.cells[index]
    if cell_type and cell_type != cell.get("cell_type"):
        nb.cells[index] = _new_cell(cell_type, source)
    else:
        cell["source"] = source
        if cell.get("cell_type") == "code":
            cell["outputs"] = []
            cell["execution_count"] = None
    nbformat.write(nb, str(nb_path))
    return {"ok": True, "path": str(nb_path)}


def insert_cell(rel_path: str, index: int, source: str, cell_type: str) -> Dict[str, Any]:
    import nbformat
    nb_path = _resolve_notebook(rel_path)
    nb = nbformat.read(str(nb_path), as_version=4)
    index = max(0, min(index, len(nb.cells)))
    nb.cells.insert(index, _new_cell(cell_type, source))
    nbformat.write(nb, str(nb_path))
    return {"ok": True, "path": str(nb_path), "index": index}


def delete_cell(rel_path: str, index: int) -> Dict[str, Any]:
    import nbformat
    nb_path = _resolve_notebook(rel_path)
    nb = nbformat.read(str(nb_path), as_version=4)
    if index < 0 or index >= len(nb.cells):
        return {"ok": False, "error": f"index {index} out of range (0..{len(nb.cells) - 1})"}
    del nb.cells[index]
    nbformat.write(nb, str(nb_path))
    return {"ok": True, "path": str(nb_path)}


def create_notebook(rel_path: str) -> Dict[str, Any]:
    import nbformat
    base = workspace_dir()
    target = (base / rel_path).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        return {"ok": False, "error": f"path escapes workspace: {rel_path!r}"}
    if target.suffix != ".ipynb":
        return {"ok": False, "error": "path must end in .ipynb"}
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return {"ok": False, "error": f"already exists: {rel_path}"}
    with os.fdopen(fd, "w") as f:
        nbformat.write(nbformat.v4.new_notebook(), f)
    return {"ok": True, "path": str(target)}


def _new_cell(cell_type: str, source: str):
    import nbformat
    if cell_type == "code":
        return nbformat.v4.new_code_cell(source)
    if cell_type == "markdown":
        return nbformat.v4.new_markdown_cell(source)
    if cell_type == "raw":
        return nbformat.v4.new_raw_cell(source)
    raise ValueError(f"unknown cell_type: {cell_type!r}")


def run_cell(km, rel_path: str, index: int, sink=None):
    """Run a code cell on the embedded kernel, write its outputs back via the
    sink, and return a concurrent.futures.Future[str] summary. ``km`` is the
    KernelManager; ``sink`` defaults to DiskNotebookSink."""
    import nbformat
    from concurrent.futures import Future
    from ._notebook_sink import DiskNotebookSink
    from ._outputs import to_nbformat

    nb_path = _resolve_notebook(rel_path)
    nb = nbformat.read(str(nb_path), as_version=4)
    if index < 0 or index >= len(nb.cells):
        f: Future = Future()
        f.set_result(f"error: index {index} out of range (0..{len(nb.cells) - 1})")
        return f
    cell = nb.cells[index]
    if cell.get("cell_type") != "code":
        f = Future()
        f.set_result(f"error: cell {index} is {cell.get('cell_type')}, not code")
        return f
    source = cell.get("source", "")
    if isinstance(source, list):
        source = "".join(source)
    the_sink = sink or DiskNotebookSink()

    cap_future = km.run_cell_capture(source)
    out: Future = Future()

    def _done(cf):
        try:
            captured = cf.result()
            outputs = to_nbformat(captured)
            the_sink.write_outputs(rel_path, index, outputs, captured["execution_count"])
            out.set_result(_summarize(captured))
        except Exception as e:  # noqa: BLE001
            out.set_result(f"error: {type(e).__name__}: {e}")

    cap_future.add_done_callback(_done)
    return out


def _summarize(captured) -> str:
    n = captured.get("execution_count")
    head = f"[{n}] " + ("ok" if captured.get("success") else "error")
    parts = [head]
    if captured.get("stdout"):
        parts.append("stdout: " + captured["stdout"].strip()[:500])
    if captured.get("result") is not None:
        parts.append("result: " + str(captured["result"])[:500])
    if not captured.get("success"):
        parts.append(captured.get("error") or "cell failed")
    return "\n".join(parts)
