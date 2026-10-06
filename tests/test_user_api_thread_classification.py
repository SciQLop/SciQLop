"""Every public user_api function either runs on the GUI thread or is known not to need it.

Cells call the user_api from the kernel thread. A new public function that touches
Qt without `@on_main_thread` is a crash waiting for its first cell (SciQLop#147).
This test makes each one a decision: decorate it, or list it below with the reason.
Only static analysis: nothing is imported or run.
"""
import ast
import pathlib

USER_API = pathlib.Path(__file__).parent.parent / "SciQLop" / "user_api"

# Whole modules that never touch Qt: computation, typing, data and helpers.
QT_FREE_MODULES = {
    "_annotations/__init__.py",
    "data_types.py",
    "dsp/__init__.py",
    "dsp/_arrays.py",
    "dsp/_background.py",
    "dsp/_speasy.py",
    "layers/_introspection.py",
    "layers/types.py",
    "plot/protocol.py",
    "templates.py",
    "threading.py",
    "virtual_products/validation.py",
    "virtual_products/report.py",
    # ipywidgets live in the kernel, not in Qt.
    "virtual_products/ipywidgets_binding.py",
}

NOT_MARSHALED_ON_PURPOSE = {
    # Plain Python state, set once by a GUI-thread constructor.
    "catalogs/_overlay.py": {"CatalogOverlay.catalog_path", "CatalogOverlay.override_color"},
    "layers/_provider.py": {"LayerProvider.callback", "LayerProvider.get_knobs", "LayerProvider.path",
                            "LayerProvider.resolve_scope", "LayerProvider.update_callback"},
    "layers/registry.py": {"LayerRegistry.get", "LayerRegistry.register", "MutableCallback.callback"},
    "plot/_graphic_primitives.py": {"StraightLine.orientation"},
    # Read the intervals kept from the last set_intervals call, not the C++ timeline.
    "plot/_timeline.py": {"Interval.duration", "Timeline.interval"},
    "plot/_graphs.py": {"Histogram2D.x_bin_edges", "Histogram2D.y_bin_edges",
                        "ensure_arrays_of_double", "is_array_of_double", "validate_histogram_bins"},
    "plot/_plots.py": {"is_meta_object_instance", "is_product", "is_projection_plot",
                       "is_time_series_plot", "is_xy_plot", "to_product_path"},
    "virtual_products/__init__.py": {"VirtualProduct.path", "VirtualProduct.product_type",
                                     "list_virtual_products"},
    "virtual_products/registry.py": {"MutableCallback.callback", "VPRegistry.get", "VPRegistry.register"},
    # Only call marshaled functions, or reach Qt through sciqlop_app()'s proxy.
    "gui/__init__.py": {"get_main_window"},
    "themes/__init__.py": {"apply_theme", "current_theme", "list_themes"},
    "plot/_fluent.py": {"PanelBuilder.histogram2d", "PanelBuilder.layer", "PanelBuilder.linear_y",
                        "PanelBuilder.log_y", "PanelBuilder.panel", "PanelBuilder.plot",
                        "PanelBuilder.subplot", "PanelBuilder.time_range", "PanelBuilder.y_range",
                        "new_panel", "panel"},
    "plot/_speasy_backend.py": {"SciQLopBackend.colormap", "SciQLopBackend.line"},
    "magics/__init__.py": {"register_all_magics"},
    "magics/install_magic.py": {"install_magic"},
    "magics/job_magic.py": {"job_magic"},
    "magics/plot_magic.py": {"create_plot_panel", "plot_magic", "plot_panel"},
    "magics/timerange_magic.py": {"timerange_magic"},
    "magics/workspace_magic.py": {"workspace_magic"},
    "layers/magic.py": {"layer_magic"},
    "layers/__init__.py": {"register_layer"},
    "virtual_products/magic.py": {"vp_magic"},
    "virtual_products/debug.py": {"handle_debug"},
    # Register product-tree nodes through the marshaled add_product_node (#138).
    "virtual_products/__init__.py#registration": {"create_virtual_product"},
    "virtual_products/registry.py#registration": {"register_virtual_product"},
    # Called by marshaled user_api methods with a raw impl, never from cells.
    "plot/_graphs.py#internal": {"to_plottable"},
    "plot/_plots.py#internal": {"plot_product_or_raise", "to_plot"},
    # Driven by the layer machinery on the GUI thread.
    "layers/_renderer.py": {"LayerRenderer.clear", "LayerRenderer.data_aware", "LayerRenderer.dispose",
                            "LayerRenderer.last_error", "LayerRenderer.setup_data_binding",
                            "LayerRenderer.update"},
    # Out-of-process work: jobs and package installs never touch Qt.
    "jobs.py": {"cancel_job", "job_status", "list_jobs", "submit_job"},
    "packages.py": {"install_packages"},
}


def _exempt() -> set[str]:
    return {f"{key.split('#')[0]}::{name}"
            for key, names in NOT_MARSHALED_ON_PURPOSE.items() for name in names}


def _is_marshaled(node) -> bool:
    return any("main_thread" in ast.unparse(d) for d in node.decorator_list)


def _public_functions(nodes, owner=""):
    for node in nodes:
        if isinstance(node, ast.ClassDef):
            yield from _public_functions(node.body, f"{node.name}.")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                yield node, f"{owner}{node.name}"


def _unmarshaled() -> set[str]:
    found = set()
    for path in USER_API.rglob("*.py"):
        module = path.relative_to(USER_API).as_posix()
        if module.startswith("docs/") or module in QT_FREE_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found |= {f"{module}::{name}" for node, name in _public_functions(tree.body)
                  if not _is_marshaled(node)}
    return found


def test_every_public_user_api_function_is_classified():
    unclassified = _unmarshaled() - _exempt()
    assert not unclassified, (
        "public user_api functions without @on_main_thread: decorate them, or add them to "
        f"NOT_MARSHALED_ON_PURPOSE with the reason they are safe: {sorted(unclassified)}")


def test_exemptions_still_exist():
    stale = _exempt() - _unmarshaled()
    assert not stale, f"exempt but now decorated or gone, drop them from the list: {sorted(stale)}"
