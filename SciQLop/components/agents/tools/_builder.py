"""Build the canonical SciQLop tool surface for LLM agent backends.

All tools are always registered so the agent session stays stable across
write-toggle changes. Tools that mutate state carry `gated=True`; backends
deny them entirely when writes are disabled, and otherwise prompt the user
per call via the backend's confirm callback.
"""
from __future__ import annotations

import asyncio
import json
import base64
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

from SciQLop.user_api.threading import on_main_thread
from SciQLop.user_api import jobs as user_api_jobs
from SciQLop.user_api import screenshot as screenshot_api

from . import context

# Off-loop pool for tools that do blocking I/O with no Qt affinity (speasy
# inventory, api-reference introspection, notebook file I/O). Keeps the qasync
# event loop — which is the Qt GUI thread — responsive while they run.
_IO_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sciqlop-agent-tool")


async def _in_io_pool(fn: Callable[..., Any], *args: Any) -> Any:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_IO_POOL, fn, *args)


def build_sciqlop_tools(main_window) -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = [
        _snapshot_tool(
            "sciqlop_active_panel",
            "Return the currently active SciQLop plot panel: its name, time range, and the products currently plotted on it.",
            lambda: context.active_panel_snapshot(main_window),
        ),
        _snapshot_tool(
            "sciqlop_list_panels",
            "List all open SciQLop plot panels with their time ranges.",
            lambda: context.list_panels(main_window),
        ),
        _snapshot_tool(
            "sciqlop_window_state",
            "High-level snapshot of the SciQLop main window: panel count, active panel summary.",
            lambda: context.main_window_snapshot(main_window),
        ),
        _describe_panel_tool(main_window),
        _screenshot_panel_tool(main_window),
        _screenshot_plot_tool(main_window),
        _api_reference_tool(),
        _speasy_inventory_tool(),
        _products_tree_tool(),
        _list_virtual_products_tool(),
        _search_literature_tool(),
        _fetch_paper_tool(),
        _wait_for_plot_data_tool(main_window),
        _list_notebooks_tool(),
        _read_notebook_tool(),
        _kernel_vars_tool(),
        _inspect_tool(),
        _describe_tool(),
        _show_figure_tool(),
        _job_status_tool(),
        _list_jobs_tool(),
        _orbit_bodies_frames_tool(),
    ]
    tools.extend(_write_tools(main_window))
    return tools


_NO_ARGS = {"type": "object", "properties": {}, "required": []}


def _snapshot_tool(name: str, description: str, snapshot: Callable[[], Any]) -> Dict[str, Any]:
    """Read-only, argument-less tool returning a GUI-state snapshot as JSON."""
    return _text_tool(name, description, _NO_ARGS,
                      on_main_thread(lambda _payload: _json_content(snapshot())))


def _text_tool(
    name: str,
    description: str,
    schema: Dict[str, Any],
    call: Callable[[Dict[str, Any]], Any],
    gated: bool = False,
    thread: bool = False,
) -> Dict[str, Any]:
    """Wrap a callable as a text tool. ``thread=True`` runs the (synchronous,
    Qt-free) callable in the I/O pool so it never blocks the GUI event loop;
    leave it False for callables that touch Qt and must run on the GUI thread."""

    async def _run(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if thread:
                result = await _in_io_pool(call, payload)
            else:
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


def _json_content(value: Any) -> Dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, indent=1)}]}


def _format_install_result(result: Dict[str, Any]) -> str:
    parts: List[str] = []
    if result.get("installed"):
        parts.append(f"installed and recorded: {', '.join(result['installed'])}")
    if result.get("already_present"):
        parts.append(f"already present: {', '.join(result['already_present'])}")
    if not result.get("ok"):
        parts.append(f"error: {result.get('error', '')}")
    return "\n".join(parts) if parts else "ok (nothing to do)"


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
        panel, error = _resolve_panel(main_window, name)
        if error:
            return error
        return _screenshot_to_content(lambda path: screenshot_api.capture_panel(panel, path))

    return _text_tool(
        "sciqlop_screenshot_panel",
        "Render a PNG screenshot of a SciQLop plot panel. Pass the panel name, or omit to screenshot the active panel.",
        {"type": "object", "properties": {"name": {"type": "string"}}, "required": []},
        lambda payload: _shoot(payload.get("name")),
    )


def _screenshot_plot_tool(main_window) -> Dict[str, Any]:
    @on_main_thread
    def _shoot(name: Optional[str], plot_index: int):
        panel, error = _resolve_panel(main_window, name)
        if error:
            return error
        plots = panel.plots
        if not plots:
            return _error_content("panel has no plots")
        if plot_index < 0 or plot_index >= len(plots):
            return _error_content(f"plot_index {plot_index} out of range (0..{len(plots) - 1})")
        return _screenshot_to_content(plots[plot_index]._impl.save_png)

    return _text_tool(
        "sciqlop_screenshot_plot",
        "Render a PNG screenshot of a single subplot inside a SciQLop panel. plot_index is 0-based. Omit name to target the active panel.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "plot_index": {"type": "integer"},
            },
            "required": ["plot_index"],
        },
        lambda payload: _shoot(payload.get("name"), int(payload["plot_index"])),
    )


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
        thread=True,
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
        thread=True,
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


def _list_virtual_products_tool() -> Dict[str, Any]:
    from SciQLop.user_api.virtual_products import list_virtual_products
    return _text_tool(
        "sciqlop_list_virtual_products",
        (
            "List every virtual product currently registered (via "
            "create_virtual_product or the %%vp cell magic), as full "
            "`//`-joined product-tree paths."
        ),
        _NO_ARGS,
        lambda _: _json_content(list_virtual_products()),
    )


def _search_literature_tool() -> Dict[str, Any]:
    from . import literature
    return _text_tool(
        "sciqlop_search_literature",
        (
            "Search the scientific literature for papers. `source` is 'arxiv' "
            "(free), 'ads' (NASA ADS — needs a configured token), or 'both' "
            "(default). Returns title, authors, year, identifier (arXiv id / ADS "
            "bibcode), DOI, URL and a short abstract. Use sciqlop_fetch_paper to "
            "read a paper's full text. Cite what you use."
        ),
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "source": {"type": "string", "enum": ["arxiv", "ads", "both"]},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
        lambda p: literature.search_literature(
            str(p["query"]), str(p.get("source", "both")), int(p.get("max_results", 5))),
        thread=True,
    )


def _fetch_paper_tool() -> Dict[str, Any]:
    from . import fulltext
    return _text_tool(
        "sciqlop_fetch_paper",
        (
            "Fetch the full text of a paper by arXiv id/URL, DOI, or ADS bibcode "
            "(e.g. '2401.01234', an arxiv.org link, '10.3847/1538-4357/acaf6c', or "
            "'2023ApJ...945...28R') — auto-detected. DOI/bibcode resolution goes "
            "via NASA ADS and only succeeds when an open-access (usually arXiv) "
            "copy exists; paywalled papers with no open-access copy report that "
            "cleanly. Returns cleaned text from the HTML version, falling back to "
            "the PDF. Long papers are truncated — ask for a specific section if "
            "needed."
        ),
        {"type": "object", "properties": {"id_or_url": {"type": "string"}},
         "required": ["id_or_url"]},
        lambda p: fulltext.fetch_paper(str(p["id_or_url"])),
        thread=True,
    )


def _wait_for_plot_data_tool(main_window) -> Dict[str, Any]:
    import time

    async def _wait(name: Optional[str], timeout: float) -> Dict[str, Any]:
        panel, error = _resolve_panel(main_window, name)
        if error:
            return error
        # Poll via the public is_busy() helper so the asyncio loop stays responsive.
        has_plottables = False
        for plot in panel._get_impl_or_raise().plots() or []:
            if plot.plottables():
                has_plottables = True
                break
        if not has_plottables:
            return _error_content("panel has no plottables — call plot_product first")
        deadline = time.monotonic() + max(0.0, float(timeout))
        while True:
            if not panel.is_busy():
                return {"content": [{"type": "text", "text": "ok: all plottables settled"}]}
            if time.monotonic() >= deadline:
                break
            await asyncio.sleep(0.2)
        return {"content": [{"type": "text", "text": f"timeout after {timeout:.1f}s — plottables still busy"}]}

    return _text_tool(
        "sciqlop_wait_for_plot_data",
        (
            "Block until all plottables on a panel have finished fetching data. "
            "Polls the `busy` flag of every graph and reports when the panel has "
            "no plottables. Call this right after `plot_product` and before "
            "`sciqlop_screenshot_panel`, otherwise the screenshot captures an "
            "empty plot. Default timeout 10 seconds. Settling is not success — "
            "check `sciqlop_describe_panel`'s last_error/n_points for each graph "
            "afterward to confirm the fetch actually produced data."
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
        thread=True,
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
        thread=True,
    )


def _kernel_vars_tool() -> Dict[str, Any]:
    def _run(_payload: Dict[str, Any]) -> Any:
        km = _kernel_manager()
        if km is None:
            return _error_content("embedded IPython kernel is not available")
        from . import kernel
        return kernel.kernel_vars(km.shell)
    return _text_tool(
        "sciqlop_kernel_vars",
        "List the user variables currently defined in the SciQLop embedded "
        "kernel (name, type, and a short summary). Read-only.",
        {"type": "object", "properties": {}, "required": []},
        _run,
        thread=True,  # repr() of arbitrary objects must not run on the GUI thread
    )


def _inspect_tool() -> Dict[str, Any]:
    def _run(payload: Dict[str, Any]) -> Any:
        km = _kernel_manager()
        if km is None:
            return _error_content("embedded IPython kernel is not available")
        from . import kernel
        return kernel.inspect_name(km.shell, str(payload["name"]))
    return _text_tool(
        "sciqlop_inspect",
        "Inspect a name in the SciQLop embedded kernel — type, value, and "
        "docstring. Read-only.",
        {"type": "object", "properties": {"name": {"type": "string"}},
         "required": ["name"]},
        _run,
        thread=True,  # object_inspect does file I/O for docstrings; keep off the GUI thread
    )


def _make_resolve_index():
    """Resolve a product identifier to a speasy ParameterIndex.

    `//`-path → ProductsModel node → its speasy_id → flat-inventory lookup;
    otherwise a speasy identifier: a dotted inventory path, or `provider/uid`.
    Returns (index_or_None, note_or_None)."""
    def _flat_lookup(provider: str, uid: str):
        import speasy as spz
        prov = getattr(spz.inventories.flat_inventories, provider, None)
        params = getattr(prov, "parameters", None) if prov is not None else None
        if params and uid in params:
            return params[uid]
        return None

    def _from_speasy_id(spz_id: str):
        provider, _, uid = spz_id.partition("/")
        if uid:
            hit = _flat_lookup(provider, uid)
            if hit is not None:
                return hit
        # dotted inventory path fallback (e.g. cda.AC_H2_CRIS...)
        import speasy as spz
        node = spz.inventories.data_tree
        for part in spz_id.split("."):
            node = getattr(node, part, None)
            if node is None:
                return None
        return node

    def resolve(product: str):
        if "//" in product:
            from SciQLopPlots import ProductsModel
            node = ProductsModel.instance().node([p for p in product.split("//") if p])
            if node is None:
                return None, f"product not found: {product}"
            spz_id = node.metadata("speasy_id") if hasattr(node, "metadata") else None
            if spz_id:
                idx = _from_speasy_id(str(spz_id))
                if idx is not None:
                    return idx, None
            return node, "(describing ProductsModel node metadata; no speasy ParameterIndex found)"
        idx = _from_speasy_id(product)
        if idx is None:
            return None, f"product not found in speasy inventory: {product}"
        return idx, None

    return resolve


def _describe_tool() -> Dict[str, Any]:
    from . import describe

    def _probe_fetch(index, t0: float, t1: float):
        import speasy as spz
        uid = describe._call(index, "spz_uid")
        provider = describe._call(index, "spz_provider")
        spz_id = f"{provider}/{uid}" if provider and uid else (uid or "")
        return spz.get_data(spz_id, t0, t1)

    resolve_index = _make_resolve_index()

    def _run(payload: Dict[str, Any]) -> Any:
        return describe.describe_product(
            str(payload["product"]),
            probe=bool(payload.get("probe", False)),
            start=payload.get("start"), stop=payload.get("stop"),
            resolve_index=resolve_index, probe_fetch=_probe_fetch,
        )

    return _text_tool(
        "sciqlop_describe_product",
        (
            "Describe a product's metadata WITHOUT plotting/fetching it: units, "
            "time coverage, dimensionality, fill value, component labels, plus a "
            "raw-attribute dump. `product` is a `//`-path (from sciqlop_products_tree) "
            "or a speasy id (provider/uid or dotted inventory path) — auto-detected. "
            "Pass `probe=true` (with optional `start`/`stop`, ISO-8601 or POSIX seconds) "
            "to sample a small window and report the REAL shape, fill value, coordinate "
            "frame, median cadence and NaN-gap fraction within that window. Read-only. "
            "Call before sciqlop_fetch."
        ),
        {
            "type": "object",
            "properties": {
                "product": {"type": "string"},
                "probe": {"type": "boolean"},
                "start": {"type": ["string", "number"]},
                "stop": {"type": ["string", "number"]},
            },
            "required": ["product"],
        },
        _run,
        thread=True,  # inventory access / probe fetch block; keep off the GUI thread
    )


def _show_figure_tool() -> Dict[str, Any]:
    from . import figure

    def _run(_payload: Dict[str, Any]) -> Any:
        png = figure.current_figure_png()
        if png is None:
            return _error_content("no active matplotlib figure in the kernel")
        return {"content": [{"type": "image",
                             "data": base64.b64encode(png).decode("ascii"),
                             "mimeType": "image/png"}]}

    return _text_tool(
        "sciqlop_show_figure",
        (
            "Return the current matplotlib figure from the embedded kernel as a PNG. "
            "Use after plotting with matplotlib in sciqlop_exec_python. Read-only; "
            "reports cleanly when there is no active figure."
        ),
        {"type": "object", "properties": {}, "required": []},
        _run,
        thread=True,  # savefig does file/render work; keep off the GUI thread
    )


def _orbit_bodies_frames_tool() -> Dict[str, Any]:
    from . import orbits
    return _text_tool(
        "sciqlop_orbit_bodies_and_frames",
        (
            "List valid body names (spacecraft, planets, small bodies) and frame "
            "names accepted by sciqlop_ephemeris/sciqlop_transform, from the CDPP "
            "3DView service. Cached — call before guessing a body/frame name."
        ),
        {"type": "object", "properties": {}, "required": []},
        lambda _p: orbits.bodies_and_frames(),
        thread=True,  # 3DView HTTP blocks; keep it off the GUI event loop
    )


def _ephemeris_tool() -> Dict[str, Any]:
    from . import orbits
    from speasy.core import http

    def _run(payload: Dict[str, Any]) -> Any:
        km = _kernel_manager()
        if km is None:
            return _error_content("embedded IPython kernel is not available")
        return orbits.fetch_ephemeris(
            str(payload["body"]), payload.get("frame"),
            payload["start"], payload["stop"], payload.get("sampling"),
            str(payload["name"]), km.shell.user_ns,
            overwrite=bool(payload.get("overwrite", False)),
            http_get=http.get,
        )

    return _text_tool(
        "sciqlop_ephemeris",
        (
            "Fetch a spacecraft/planet/small-body's position (km) and velocity "
            "(km/s) into the embedded kernel under `name`, from the CDPP 3DView "
            "service. `body`/`frame` — call sciqlop_orbit_bodies_and_frames first "
            "if unsure of valid names; `frame` defaults to J2000. `start`/`stop` "
            "are ISO-8601 strings or POSIX seconds. `sampling` is the step in "
            "seconds (default 3600). Binds `{'position': ..., 'speed': ...}` "
            "(SpeasyVariable, columns X/Y/Z and Vx/Vy/Vz) — never returns raw "
            "arrays. Errors if `name` exists unless `overwrite=true`."
        ),
        {
            "type": "object",
            "properties": {
                "body": {"type": "string"},
                "frame": {"type": "string"},
                "start": {"type": ["string", "number"]},
                "stop": {"type": ["string", "number"]},
                "sampling": {"type": "integer"},
                "name": {"type": "string"},
                "overwrite": {"type": "boolean"},
            },
            "required": ["body", "start", "stop", "name"],
        },
        _run,
        gated=True,
        thread=True,  # 3DView HTTP blocks; keep it off the GUI event loop
    )


def _transform_tool() -> Dict[str, Any]:
    from . import orbits
    from speasy.core import http

    def _run(payload: Dict[str, Any]) -> Any:
        km = _kernel_manager()
        if km is None:
            return _error_content("embedded IPython kernel is not available")
        return orbits.fetch_transform(
            payload.get("from_frame"), payload.get("to_frame"),
            payload["start"], payload["stop"], payload.get("sampling"),
            str(payload["name"]), km.shell.user_ns,
            overwrite=bool(payload.get("overwrite", False)),
            http_get=http.get,
        )

    return _text_tool(
        "sciqlop_transform",
        (
            "Fetch 3x3 rotation matrices between two coordinate frames (e.g. "
            "GSE->HEEQ) into the embedded kernel under `name`, from the CDPP "
            "3DView service — exact, not an approximation. Does NOT apply the "
            "rotation itself: interpolate the matrix time axis onto your data's "
            "time axis, then `np.einsum('nij,nj->ni', R, vectors)` in "
            "sciqlop_exec_python. `from_frame`/`to_frame` default to J2000/"
            "ECLIPJ2000; call sciqlop_orbit_bodies_and_frames first if unsure "
            "of valid names. `sampling` is the step in seconds (default 3600). "
            "Errors if `name` exists unless `overwrite=true`."
        ),
        {
            "type": "object",
            "properties": {
                "from_frame": {"type": "string"},
                "to_frame": {"type": "string"},
                "start": {"type": ["string", "number"]},
                "stop": {"type": ["string", "number"]},
                "sampling": {"type": "integer"},
                "name": {"type": "string"},
                "overwrite": {"type": "boolean"},
            },
            "required": ["start", "stop", "name"],
        },
        _run,
        gated=True,
        thread=True,  # 3DView HTTP blocks; keep it off the GUI event loop
    )


def _interrupt_kernel_tool() -> Dict[str, Any]:
    def _run(_payload: Dict[str, Any]) -> Any:
        km = _kernel_manager()
        if km is None:
            return _error_content("embedded IPython kernel is not available")
        km.interrupt()
        return "interrupt sent to the embedded kernel"
    return _text_tool(
        "sciqlop_interrupt_kernel",
        "Interrupt the currently running cell in the SciQLop embedded kernel "
        "(raises KeyboardInterrupt). Use to recover a long or stuck cell.",
        {"type": "object", "properties": {}, "required": []},
        _run,
        gated=True,
    )


def _install_package_tool() -> Dict[str, Any]:
    def _run(payload: Dict[str, Any]) -> Any:
        from SciQLop.user_api.packages import install_packages
        packages = [str(p) for p in (payload.get("packages") or [])]
        if not packages:
            return _error_content("no packages given")
        return _format_install_result(install_packages(*packages))

    return _text_tool(
        "sciqlop_install_package",
        (
            "Install one or more Python packages into the active workspace's venv "
            "(via uv) AND record them in the workspace manifest, so they persist "
            "across restarts and survive venv rebuilds. Use this instead of running "
            "`pip install` in sciqlop_exec_python — raw pip installs are NOT recorded "
            "and are wiped when the venv is recreated. Pass PEP 508 specifiers, e.g. "
            "['astropy', 'scipy>=1.11']."
        ),
        {
            "type": "object",
            "properties": {
                "packages": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["packages"],
        },
        _run,
        gated=True,
        thread=True,  # uv install blocks; keep it off the GUI event loop
    )


def _fetch_tool() -> Dict[str, Any]:
    from . import fetch

    def _fetch_one(product_id: str, t0: float, t1: float):
        if "//" in product_id:
            from SciQLop.components.plotting.backend.dependencies import resolve_product_path
            data = resolve_product_path(product_id, t0, t1)
        else:
            import speasy as spz
            data = spz.get_data(product_id, t0, t1)
        if not data:
            raise ValueError(f"no data for {product_id}")
        return list(data) if isinstance(data, (list, tuple)) else [data]

    def _grid(ref, var):
        from speasy.signal.resampling import interpolate
        return interpolate(ref, var)

    def _run(payload: Dict[str, Any]) -> Any:
        km = _kernel_manager()
        if km is None:
            return _error_content("embedded IPython kernel is not available")
        return fetch.fetch_products(
            [str(p) for p in payload["products"]],
            payload["start"], payload["stop"], str(payload["name"]),
            km.shell.user_ns,
            cadence=payload.get("cadence") or None,
            overwrite=bool(payload.get("overwrite", False)),
            preview=bool(payload.get("preview", False)),
            fetch_one=_fetch_one, grid_interpolate=_grid,
        )

    return _text_tool(
        "sciqlop_fetch",
        (
            "Fetch one or more products into the embedded kernel under `name` and "
            "return a compact summary (shape, units, coverage %, min/mean/max) — NOT "
            "the raw arrays. Compute on the handle afterwards with sciqlop_exec_python "
            "(e.g. `name['B_gse'].to_dataframe()`). `products` are `//`-paths "
            "(from sciqlop_products_tree) or speasy spz_uids — auto-detected. "
            "`start`/`stop` are ISO-8601 strings or POSIX seconds. With `cadence` "
            "(e.g. '1min') all products are fill-scrubbed and interpolated onto one "
            "common grid; without it they are bound at native cadence. Errors if "
            "`name` exists unless `overwrite=true`. `preview=true` adds a thumbnail."
        ),
        {
            "type": "object",
            "properties": {
                "products": {"type": "array", "items": {"type": "string"}},
                "start": {"type": ["string", "number"]},
                "stop": {"type": ["string", "number"]},
                "name": {"type": "string"},
                "cadence": {"type": "string"},
                "overwrite": {"type": "boolean"},
                "preview": {"type": "boolean"},
            },
            "required": ["products", "start", "stop", "name"],
        },
        _run,
        gated=True,
        thread=True,  # speasy fetch blocks; keep it off the GUI event loop
    )


def _submit_job_tool() -> Dict[str, Any]:
    def _run(payload: Dict[str, Any]) -> Any:
        job_id = user_api_jobs.submit_job(str(payload["command"]), str(payload.get("name", "")))
        return f"submitted job `{job_id}`"

    return _text_tool(
        "sciqlop_submit_job",
        (
            "Run a shell command as a DETACHED background job that survives "
            "SciQLop closing or crashing (like `nohup ... &`) — use for long "
            "builds, surveys, or downloads. Build the actual work first with "
            "sciqlop_exec_python or a workspace script, then pass the command "
            "that runs it here. Returns a job id — check progress later with "
            "sciqlop_job_status or sciqlop_list_jobs, even in a future session."
        ),
        {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "name": {"type": "string"},
            },
            "required": ["command"],
        },
        _run,
        gated=True,
        thread=True,
    )


def _job_status_tool() -> Dict[str, Any]:
    return _text_tool(
        "sciqlop_job_status",
        (
            "Check a background job's status: 'running', 'done', or 'crashed', "
            "plus exit code and a tail of its output log. Works across SciQLop "
            "restarts — the job keeps running (or its result stays available) "
            "even if SciQLop was closed since it was submitted."
        ),
        {"type": "object", "properties": {"job_id": {"type": "string"}},
         "required": ["job_id"]},
        lambda p: str(user_api_jobs.job_status(str(p["job_id"]))),
        thread=True,
    )


def _list_jobs_tool() -> Dict[str, Any]:
    return _text_tool(
        "sciqlop_list_jobs",
        (
            "List every known background job (including ones submitted in a "
            "prior SciQLop session) with its current status. Use this to "
            "rediscover work you don't remember the job id for."
        ),
        {"type": "object", "properties": {}, "required": []},
        lambda _p: str(user_api_jobs.list_jobs()),
        thread=True,
    )


def _cancel_job_tool() -> Dict[str, Any]:
    def _run(payload: Dict[str, Any]) -> Any:
        user_api_jobs.cancel_job(str(payload["job_id"]))
        return f"sent SIGTERM to job `{payload['job_id']}`"

    return _text_tool(
        "sciqlop_cancel_job",
        "Cancel a running background job (sends SIGTERM to its process).",
        {"type": "object", "properties": {"job_id": {"type": "string"}},
         "required": ["job_id"]},
        _run,
        gated=True,
        thread=True,
    )


def _write_tools(main_window) -> List[Dict[str, Any]]:
    @on_main_thread
    def _set_time_range(name: Optional[str], start: float, stop: float):
        panel, error = _resolve_panel(main_window, name)
        if error:
            return error
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

    return [set_time_range, _create_panel_tool(main_window), _build_panel_tool(main_window),
            _plot_product_tool(main_window),
            _remove_plot_tool(main_window), _remove_graph_tool(main_window), _move_plot_tool(main_window),
            _exec_python_tool(),
            _fetch_tool(), _ephemeris_tool(), _transform_tool(), _submit_job_tool(),
            _cancel_job_tool(), _install_package_tool()] + _notebook_write_tools() + [_run_notebook_cell_tool(), _interrupt_kernel_tool()]


def _resolve_panel(main_window, name: Optional[str]) -> Tuple[Any, Optional[Dict[str, Any]]]:
    """(panel, None) for `name` or the active panel, else (None, error content)."""
    if name:
        panel = context._panel(name)
        if panel is None:
            return None, _error_content(f"panel not found: {name!r}")
        return panel, None
    panel = context._active_panel(main_window)
    if panel is None:
        names = context._panel_names()
        if not names:
            return None, _error_content("no active panel: no panels are open")
        return None, _error_content(
            "no unambiguous active panel — pass name explicitly, one of: "
            + ", ".join(names))
    return panel, None


def _layout_content(panel) -> Dict[str, Any]:
    return _json_content(context.panel_layout(panel, panel.name))


_PANEL_NAME_PROP = {"name": {"type": "string", "description": "Panel name; omit for the active panel."}}


def _describe_panel_tool(main_window) -> Dict[str, Any]:
    @on_main_thread
    def _describe(p: Dict[str, Any]) -> Dict[str, Any]:
        panel, error = _resolve_panel(main_window, p.get("name"))
        return error or _layout_content(panel)

    return _text_tool(
        "sciqlop_describe_panel",
        (
            "Structured layout of a plot panel: every subplot with its 0-based "
            "index, type and axis state, and every graph inside it with its "
            "index, legend name, product path, busy/n_points/last_error data "
            "status. Call it after each change to a panel to confirm the "
            "result instead of guessing indices, and after waiting for data "
            "to check last_error/n_points before assuming a plot has data."
        ),
        {"type": "object", "properties": dict(_PANEL_NAME_PROP), "required": []},
        _describe,
    )


def _plot_product_tool(main_window) -> Dict[str, Any]:
    @on_main_thread
    def _plot(p: Dict[str, Any]) -> Dict[str, Any]:
        from SciQLop.user_api.plot import PlotType
        panel, error = _resolve_panel(main_window, p.get("name"))
        if error:
            return error
        kwargs = {"plot_type": PlotType[p["plot_type"]]} if p.get("plot_type") else {}
        panel.plot_product(p["product"], int(p.get("plot_index", -1)), **kwargs)
        return _layout_content(panel)

    return _text_tool(
        "sciqlop_plot_product",
        (
            "Plot a product from `sciqlop_products_tree` on a panel and return "
            "the resulting layout. plot_index -1 (default) appends a new subplot; "
            "an existing index overlays the product on that subplot. Then call "
            "`sciqlop_wait_for_plot_data` before any screenshot."
        ),
        {
            "type": "object",
            "properties": {
                **_PANEL_NAME_PROP,
                "product": {"type": "string", "description": "`//`-joined product tree path."},
                "plot_index": {"type": "integer", "default": -1},
                "plot_type": {"type": "string", "enum": ["TimeSeries", "Projection", "XY"]},
            },
            "required": ["product"],
        },
        _plot,
        gated=True,
    )


def _remove_plot_tool(main_window) -> Dict[str, Any]:
    @on_main_thread
    def _remove(p: Dict[str, Any]) -> Dict[str, Any]:
        panel, error = _resolve_panel(main_window, p.get("name"))
        if error:
            return error
        panel.remove_plot(int(p["plot_index"]))
        return _layout_content(panel)

    return _text_tool(
        "sciqlop_remove_plot",
        "Remove one subplot (and every graph in it) from a panel; returns the new layout. Remaining subplots slide up.",
        {
            "type": "object",
            "properties": {**_PANEL_NAME_PROP, "plot_index": {"type": "integer"}},
            "required": ["plot_index"],
        },
        _remove,
        gated=True,
    )


def _remove_graph_tool(main_window) -> Dict[str, Any]:
    @on_main_thread
    def _remove(p: Dict[str, Any]) -> Dict[str, Any]:
        panel, error = _resolve_panel(main_window, p.get("name"))
        if error:
            return error
        plot = panel.plots[int(p["plot_index"])]
        plot.remove_graph(plot.graphs[int(p["graph_index"])])
        return _layout_content(panel)

    return _text_tool(
        "sciqlop_remove_graph",
        "Remove one graph from a subplot, keeping the subplot; returns the new layout. Indices come from `sciqlop_describe_panel`.",
        {
            "type": "object",
            "properties": {
                **_PANEL_NAME_PROP,
                "plot_index": {"type": "integer"},
                "graph_index": {"type": "integer"},
            },
            "required": ["plot_index", "graph_index"],
        },
        _remove,
        gated=True,
    )


def _move_plot_tool(main_window) -> Dict[str, Any]:
    @on_main_thread
    def _move(p: Dict[str, Any]) -> Dict[str, Any]:
        panel, error = _resolve_panel(main_window, p.get("name"))
        if error:
            return error
        panel.move_plot(int(p["from_index"]), int(p["to_index"]))
        return _layout_content(panel)

    return _text_tool(
        "sciqlop_move_plot",
        "Reorder subplots: move the subplot at from_index so it sits at to_index (0 = top); returns the new layout.",
        {
            "type": "object",
            "properties": {
                **_PANEL_NAME_PROP,
                "from_index": {"type": "integer"},
                "to_index": {"type": "integer"},
            },
            "required": ["from_index", "to_index"],
        },
        _move,
        gated=True,
    )


def _create_panel_tool(main_window) -> Dict[str, Any]:
    @on_main_thread
    def _create() -> Dict[str, Any]:
        from SciQLop.user_api.plot import create_plot_panel
        panel = create_plot_panel()
        tr = context._time_range_dict(panel) if panel is not None else None
        body = f"created panel `{panel.name}`"
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


def _build_panel_tool(main_window) -> Dict[str, Any]:
    from . import build_panel
    from pydantic import ValidationError

    @on_main_thread
    def _build(p: Dict[str, Any]) -> Dict[str, Any]:
        try:
            spec = build_panel.parse_spec(p)
        except ValidationError as e:
            return _error_content(f"invalid panel spec: {e}")
        unknown = build_panel.unknown_product_paths(spec)
        if unknown:
            return _error_content(
                "unknown product path(s), nothing was created: " + ", ".join(unknown))
        template = build_panel.template_from_spec(spec)
        panel_impl = main_window.new_plot_panel()
        try:
            template.apply(panel_impl)
        except Exception as e:
            main_window.remove_panel(panel_impl)
            return _error_content(f"failed to build panel, removed it: {type(e).__name__}: {e}")
        from SciQLop.user_api.plot import PlotPanel
        return _layout_content(PlotPanel(panel_impl))

    return _text_tool(
        "sciqlop_build_panel",
        (
            "Build a whole new plot panel from a declarative spec in one call: "
            "{time_range: {start, stop} (optional, ISO 8601), plots: "
            "[{products: ['a//b//c', ...], y_log: bool (optional)}, ...]} — one "
            "entry per subplot top to bottom; several products in one entry "
            "overlay on that subplot. Validates every product path against the "
            "products tree before creating anything: an unknown path aborts "
            "with no panel created. Always creates a NEW panel and only makes "
            "TimeSeries subplots; use the incremental tools (sciqlop_plot_product, "
            "sciqlop_move_plot, ...) to edit an existing panel instead. Returns "
            "the same layout as sciqlop_describe_panel."
        ),
        {
            "type": "object",
            "properties": {
                "time_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string"},
                        "stop": {"type": "string"},
                    },
                    "required": ["start", "stop"],
                },
                "plots": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "products": {"type": "array", "items": {"type": "string"}},
                            "y_log": {"type": "boolean"},
                        },
                        "required": ["products"],
                    },
                },
            },
            "required": ["plots"],
        },
        _build,
        gated=True,
    )


def _exec_python_tool() -> Dict[str, Any]:
    async def _run(payload: Dict[str, Any]) -> Dict[str, Any]:
        km = _kernel_manager()
        if km is None:
            return _error_content("embedded IPython kernel is not available")
        try:
            result = await asyncio.wrap_future(km.submit_cell(str(payload["code"])))
        except Exception as e:
            return _error_content(f"{type(e).__name__}: {e}")
        return {"content": [{"type": "text", "text": _format_exec_result(result)}]}

    return {
        "name": "sciqlop_exec_python",
        "description": (
            "Run arbitrary Python in the SciQLop embedded IPython kernel. "
            "The SciQLop `user_api` (sciqlop.user_api.plot, user_api.gui, user_api.catalogs, "
            "user_api.virtual_products), speasy and numpy are all importable. "
            "Prefer this over bespoke tools for anything SciQLop-related. "
            "Cells run on the kernel thread, NOT the Qt GUI thread: touch widgets only "
            "through `user_api`, or the `main_window` / `app` names already in the "
            "namespace — those marshal to the GUI thread. Calling Qt directly on a "
            "widget you got some other way can abort the whole application. "
            "Returns captured stdout/stderr, repr of the last expression, and any exception."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
        },
        "handler": _run,
        "gated": True,
    }


def _truncate_traceback(text: str, head: int = 20, tail: int = 20, max_lines: int = 60) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    omitted = len(lines) - head - tail
    return "\n".join(lines[:head] + [f"  … [{omitted} lines elided] …"] + lines[-tail:])


def _format_exec_result(result: Dict[str, Any]) -> str:
    lines: List[str] = []
    if result.get("stdout"):
        lines.append(f"stdout:\n{result['stdout'].rstrip()}")
    if result.get("stderr"):
        lines.append(f"stderr:\n{result['stderr'].rstrip()}")
    if result.get("result") is not None:
        lines.append(f"result: {result['result']}")
    if not result.get("success") and result.get("error"):
        lines.append(f"error: {_truncate_traceback(str(result['error']))}")
    return "\n\n".join(lines) if lines else "ok (no output)"


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
            cell_schema, _write, gated=True, thread=True,
        ),
        _text_tool(
            "sciqlop_insert_notebook_cell",
            "Insert a new cell at the given index in a workspace notebook. cell_type defaults to 'code'.",
            cell_schema, _insert, gated=True, thread=True,
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
            _delete, gated=True, thread=True,
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
            _create, gated=True, thread=True,
        ),
    ]


def _run_notebook_cell_tool() -> Dict[str, Any]:
    async def _run(payload: Dict[str, Any]) -> Dict[str, Any]:
        km = _kernel_manager()
        if km is None:
            return _error_content("embedded IPython kernel is not available")
        from . import notebooks
        try:
            summary = await asyncio.wrap_future(
                notebooks.run_cell(km, str(payload["path"]), int(payload["index"])),
            )
        except Exception as e:  # noqa: BLE001
            return _error_content(f"{type(e).__name__}: {e}")
        return {"content": [{"type": "text", "text": summary}]}

    return {
        "name": "sciqlop_run_notebook_cell",
        "description": (
            "Run a code cell in a workspace notebook on the SciQLop embedded "
            "kernel (shared with JupyterLab — variables persist). Writes the "
            "cell's outputs back into the .ipynb (JupyterLab reloads) and returns "
            "a summary. path is workspace-relative; index is 0-based."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "index": {"type": "integer"}},
            "required": ["path", "index"],
        },
        "handler": _run,
        "gated": True,
    }


def _kernel_manager():
    try:
        from SciQLop.components.workspaces import workspaces_manager_instance
        mgr = workspaces_manager_instance()
        return getattr(mgr, "_kernel_manager", None)
    except Exception:
        return None
