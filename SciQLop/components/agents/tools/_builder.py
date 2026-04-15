"""Build the canonical SciQLop tool surface for LLM agent backends.

All tools are always registered so the agent session stays stable across
write-toggle changes. Tools that mutate state carry `gated=True`; backends
deny them entirely when writes are disabled, and otherwise prompt the user
per call via the backend's confirm callback.
"""
from __future__ import annotations

import asyncio
import base64
import os
import tempfile
from typing import Any, Callable, Dict, List, Optional

from SciQLop.user_api.threading import on_main_thread

from . import context


def build_sciqlop_tools(main_window) -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = [
        _read_tool(
            "sciqlop_active_panel",
            "Return the currently active SciQLop plot panel: its name, time range, and the products currently plotted on it.",
            on_main_thread(lambda: context.active_panel_snapshot(main_window)),
        ),
        _read_tool(
            "sciqlop_list_panels",
            "List all open SciQLop plot panels with their time ranges.",
            on_main_thread(lambda: context.list_panels(main_window)),
        ),
        _read_tool(
            "sciqlop_window_state",
            "High-level snapshot of the SciQLop main window: panel count, active panel summary.",
            on_main_thread(lambda: context.main_window_snapshot(main_window)),
        ),
        _screenshot_panel_tool(main_window),
        _screenshot_plot_tool(main_window),
        _api_reference_tool(),
        _speasy_inventory_tool(),
        _products_tree_tool(),
        _wait_for_plot_data_tool(main_window),
        _list_notebooks_tool(),
        _read_notebook_tool(),
    ]
    tools.extend(_write_tools(main_window))
    return tools


def _read_tool(name: str, description: str, handler: Callable[[], Any]) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "input_schema": {"type": "object", "properties": {}, "required": []},
        "handler": lambda _input: handler(),
    }


def _text_tool(
    name: str,
    description: str,
    schema: Dict[str, Any],
    call: Callable[[Dict[str, Any]], Any],
    gated: bool = False,
) -> Dict[str, Any]:
    async def _run(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = call(payload)
            if asyncio.iscoroutine(result):
                result = await result
        except Exception as e:
            return _error_content(f"{type(e).__name__}: {e}")
        if isinstance(result, dict) and "content" in result:
            return result
        return {"content": [{"type": "text", "text": str(result)}]}

    return {
        "name": name,
        "description": description,
        "input_schema": schema,
        "handler": _run,
        "gated": gated,
    }


def _error_content(msg: str) -> Dict[str, Any]:
    return {"content": [{"type": "text", "text": msg}]}


def _png_to_image_content(path: str) -> Dict[str, Any]:
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return {"content": [{"type": "image", "data": data, "mimeType": "image/png"}]}


def _screenshot_to_content(save_fn: Callable[[str], None]) -> Dict[str, Any]:
    fd, path = tempfile.mkstemp(suffix=".png", prefix="sciqlop_agent_")
    os.close(fd)
    save_fn(path)
    try:
        return _png_to_image_content(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _screenshot_panel_tool(main_window) -> Dict[str, Any]:
    @on_main_thread
    def _shoot(name: Optional[str]):
        panel = context._panel(name) if name else context._active_panel(main_window)
        if panel is None:
            return _error_content(f"panel not found: {name!r}" if name else "no active panel")
        return _screenshot_to_content(panel._get_impl_or_raise().save_png)

    return {
        "name": "sciqlop_screenshot_panel",
        "description": "Render a PNG screenshot of a SciQLop plot panel. Pass the panel name, or omit to screenshot the active panel.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": [],
        },
        "handler": lambda payload: _shoot(payload.get("name")),
    }


def _screenshot_plot_tool(main_window) -> Dict[str, Any]:
    @on_main_thread
    def _shoot(name: Optional[str], plot_index: int):
        panel = context._panel(name) if name else context._active_panel(main_window)
        if panel is None:
            return _error_content(f"panel not found: {name!r}" if name else "no active panel")
        plots = panel.plots
        if not plots:
            return _error_content("panel has no plots")
        if plot_index < 0 or plot_index >= len(plots):
            return _error_content(f"plot_index {plot_index} out of range (0..{len(plots) - 1})")
        return _screenshot_to_content(plots[plot_index]._impl.save_png)

    return {
        "name": "sciqlop_screenshot_plot",
        "description": "Render a PNG screenshot of a single subplot inside a SciQLop panel. plot_index is 0-based. Omit name to target the active panel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "plot_index": {"type": "integer"},
            },
            "required": ["plot_index"],
        },
        "handler": lambda payload: _shoot(payload.get("name"), int(payload["plot_index"])),
    }


def _api_reference_tool() -> Dict[str, Any]:
    from . import api_reference
    return _text_tool(
        "sciqlop_api_reference",
        (
            "Introspect SciQLop's public Python API (SciQLop.user_api). "
            "Pass an empty string to list submodules, or a submodule name like "
            "'plot', 'gui', 'catalogs', 'virtual_products', 'threading'. Returns "
            "markdown with class/function signatures and docstrings — call this "
            "before writing code against user_api so you don't hallucinate method names."
        ),
        {
            "type": "object",
            "properties": {"module": {"type": "string"}},
            "required": [],
        },
        lambda p: api_reference.render(str(p.get("module", ""))),
    )


def _speasy_inventory_tool() -> Dict[str, Any]:
    from . import speasy_inventory
    return _text_tool(
        "sciqlop_speasy_inventory",
        (
            "Browse speasy's product inventory (speasy.inventories.data_tree). "
            "Pass an empty string to list providers (amda, cda, ssc, archive, ...), "
            "or a dotted path like 'amda.Parameters.MMS.MMS1' to drill into a node. "
            "Leaves return the parameter's spz_uid, units, description and time "
            "coverage so you can plot or fetch it. Call this before guessing "
            "product paths."
        ),
        {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": [],
        },
        lambda p: speasy_inventory.render(str(p.get("path", ""))),
    )


def _products_tree_tool() -> Dict[str, Any]:
    from . import products_tree
    return _text_tool(
        "sciqlop_products_tree",
        (
            "Browse SciQLop's live ProductsModel — the tree that `plot_product` "
            "actually resolves against. Pass an empty string to list top-level "
            "providers (e.g. 'speasy'), or a `//`-joined path like "
            "'speasy//amda//Parameters//MMS//MMS1' to drill down. Leaves return "
            "the ready-to-use full path string to pass to `plot_product`. "
            "PREFER this over `sciqlop_speasy_inventory` when plotting — the "
            "speasy inventory returns spz_uid paths that `plot_product` does "
            "NOT accept."
        ),
        {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": [],
        },
        lambda p: products_tree.render(str(p.get("path", ""))),
    )


def _wait_for_plot_data_tool(main_window) -> Dict[str, Any]:
    import time

    @on_main_thread
    def _poll_once(name: Optional[str]) -> Optional[bool]:
        panel = context._panel(name) if name else context._active_panel(main_window)
        if panel is None:
            return None
        any_plot = False
        for plot in panel.plots or []:
            impl = getattr(plot, "_impl", None)
            if impl is None:
                continue
            for graph in impl.plottables() or []:
                any_plot = True
                if bool(graph.property("busy")):
                    return False
        return any_plot

    async def _wait(name: Optional[str], timeout: float) -> Dict[str, Any]:
        deadline = time.monotonic() + max(0.1, float(timeout))
        while time.monotonic() < deadline:
            state = _poll_once(name)
            if state is None:
                return _error_content(f"panel not found: {name!r}" if name else "no active panel")
            if state:
                return {"content": [{"type": "text", "text": "ok: all plottables settled"}]}
            await asyncio.sleep(0.2)
        return {"content": [{"type": "text", "text": f"timeout after {timeout:.1f}s — plottables still busy"}]}

    return _text_tool(
        "sciqlop_wait_for_plot_data",
        (
            "Block until all plottables on a panel have finished fetching data "
            "(polls the `busy` flag of every graph). Call this right after "
            "`plot_product` and before `sciqlop_screenshot_panel`, otherwise "
            "the screenshot captures an empty plot. Default timeout 10 seconds."
        ),
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "timeout": {"type": "number"},
            },
            "required": [],
        },
        lambda p: _wait(p.get("name"), p.get("timeout", 10.0)),
    )


def _list_notebooks_tool() -> Dict[str, Any]:
    from . import notebooks
    return _text_tool(
        "sciqlop_list_notebooks",
        (
            "List all Jupyter notebooks (*.ipynb) inside the active SciQLop "
            "workspace directory, with cell counts and sizes."
        ),
        {"type": "object", "properties": {}, "required": []},
        lambda _: notebooks.list_notebooks(),
    )


def _read_notebook_tool() -> Dict[str, Any]:
    from . import notebooks
    return _text_tool(
        "sciqlop_read_notebook",
        (
            "Read a workspace notebook and return its cells as markdown "
            "(code cells in ```python fences, markdown cells verbatim). "
            "Path is relative to the workspace dir."
        ),
        {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        lambda p: notebooks.read_notebook(str(p["path"])),
    )


def _write_tools(main_window) -> List[Dict[str, Any]]:
    @on_main_thread
    def _set_time_range(name: Optional[str], start: float, stop: float):
        panel = context._panel(name) if name else context._active_panel(main_window)
        if panel is None:
            return _error_content(f"panel not found: {name!r}" if name else "no active panel")
        from SciQLop.core import TimeRange
        panel.time_range = TimeRange(float(start), float(stop))
        label = name or "active panel"
        return {"content": [{"type": "text", "text": f"ok: set {label} time range"}]}

    set_time_range = _text_tool(
        "sciqlop_set_time_range",
        (
            "Set a plot panel's time range. Arguments are POSIX timestamps in "
            "seconds. Pass `name` to target a specific panel, or omit to target "
            "the active panel."
        ),
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "start": {"type": "number"},
                "stop": {"type": "number"},
            },
            "required": ["start", "stop"],
        },
        lambda p: _set_time_range(p.get("name"), p["start"], p["stop"]),
        gated=True,
    )

    return [set_time_range, _create_panel_tool(main_window), _exec_python_tool()] + _notebook_write_tools()


def _create_panel_tool(main_window) -> Dict[str, Any]:
    @on_main_thread
    def _create() -> Dict[str, Any]:
        from SciQLop.user_api.plot import create_plot_panel
        before = set(context._panel_names())
        panel = create_plot_panel()
        after = context._panel_names()
        new_name = next((n for n in after if n not in before), after[-1] if after else "")
        tr = context._time_range_dict(panel) if panel is not None else None
        body = f"created panel `{new_name}`"
        if tr:
            body += f"\ntime_range: [{tr['start']}, {tr['stop']}]"
        return {"content": [{"type": "text", "text": body}]}

    return _text_tool(
        "sciqlop_create_panel",
        (
            "Create a new empty plot panel and return its name. Use the returned "
            "name with `sciqlop_exec_python` (e.g. "
            "`plot_panel('Panel3').plot_product(...)`), `sciqlop_set_time_range`, "
            "`sciqlop_screenshot_panel` and `sciqlop_wait_for_plot_data` to target "
            "that specific panel instead of relying on which one is active."
        ),
        {"type": "object", "properties": {}, "required": []},
        lambda _: _create(),
        gated=True,
    )


def _exec_python_tool() -> Dict[str, Any]:
    @on_main_thread
    def _run(code: str) -> Dict[str, Any]:
        shell = _get_shell()
        if shell is None:
            return _error_content("embedded IPython shell is not available")
        from IPython.utils.capture import capture_output
        with capture_output() as cap:
            result = shell.run_cell(code, store_history=False)
        lines: List[str] = []
        if cap.stdout:
            lines.append(f"stdout:\n{cap.stdout.rstrip()}")
        if cap.stderr:
            lines.append(f"stderr:\n{cap.stderr.rstrip()}")
        if result.result is not None:
            lines.append(f"result: {result.result!r}")
        if not result.success:
            err = result.error_in_exec or result.error_before_exec
            if err is not None:
                lines.append(f"error: {type(err).__name__}: {err}")
            else:
                lines.append("error: cell failed without exception detail")
        if not lines:
            lines.append("ok (no output)")
        return {"content": [{"type": "text", "text": "\n\n".join(lines)}]}

    return _text_tool(
        "sciqlop_exec_python",
        (
            "Run arbitrary Python in the SciQLop embedded IPython kernel. "
            "The SciQLop `user_api` (sciqlop.user_api.plot, user_api.gui, user_api.catalogs, "
            "user_api.virtual_products), speasy, numpy and the main window are all "
            "importable. Prefer this over bespoke tools for anything SciQLop-related. "
            "Returns captured stdout/stderr, repr of the last expression, and any exception."
        ),
        {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
        lambda p: _run(str(p["code"])),
        gated=True,
    )


_CELL_TYPES = ["code", "markdown", "raw"]


def _notebook_write_tools() -> List[Dict[str, Any]]:
    from . import notebooks

    def _write(p):
        return notebooks.write_cell(
            str(p["path"]), int(p["index"]), str(p["source"]), p.get("cell_type")
        )

    def _insert(p):
        return notebooks.insert_cell(
            str(p["path"]), int(p["index"]), str(p["source"]),
            str(p.get("cell_type", "code")),
        )

    def _delete(p):
        return notebooks.delete_cell(str(p["path"]), int(p["index"]))

    def _create(p):
        return notebooks.create_notebook(str(p["path"]))

    cell_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "index": {"type": "integer"},
            "source": {"type": "string"},
            "cell_type": {"type": "string", "enum": _CELL_TYPES},
        },
        "required": ["path", "index", "source"],
    }

    return [
        _text_tool(
            "sciqlop_write_notebook_cell",
            (
                "Replace the source of a single cell in a workspace notebook. "
                "Clears execution outputs for code cells. Optionally change "
                "the cell_type ('code', 'markdown', 'raw')."
            ),
            cell_schema, _write, gated=True,
        ),
        _text_tool(
            "sciqlop_insert_notebook_cell",
            "Insert a new cell at the given index in a workspace notebook. cell_type defaults to 'code'.",
            cell_schema, _insert, gated=True,
        ),
        _text_tool(
            "sciqlop_delete_notebook_cell",
            "Delete the cell at the given index in a workspace notebook.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "index": {"type": "integer"},
                },
                "required": ["path", "index"],
            },
            _delete, gated=True,
        ),
        _text_tool(
            "sciqlop_create_notebook",
            (
                "Create a new empty Jupyter notebook at the given workspace-relative "
                "path. Fails if the file already exists."
            ),
            {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            _create, gated=True,
        ),
    ]


def _get_shell():
    try:
        from SciQLop.components.workspaces import workspaces_manager_instance
        mgr = workspaces_manager_instance()
        km = getattr(mgr, "_kernel_manager", None)
        return getattr(km, "shell", None) if km is not None else None
    except Exception:
        return None
