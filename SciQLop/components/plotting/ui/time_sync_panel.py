from typing import Optional, List, Union

import time as _time
import numpy as np
from PySide6.QtCore import QMimeData
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QColor
from SciQLopPlots import SciQLopMultiPlotPanel, SciQLopTheme, PlotDragNDropCallback, ProductsModel, SciQLopPlot, \
    ParameterType, GraphType, SciQLopNDProjectionPlot

from SciQLop.components.theming import register_icon
from SciQLop.core import TimeRange
from SciQLop.core import listify
from SciQLop.components import sciqlop_logging
from SciQLop.components.plotting.backend.data_provider import providers, DataProvider
from SciQLop.components.plotting.backend.easy_provider import EasyProvider
from SciQLop.core.graph_context import (
    attach_context, build_speasy_ctx, build_vp_ctx,
    build_static_ctx, build_function_ctx, GraphRichRefs,
    update_knobs,
)
import weakref

from SciQLop.core.plot_hints import apply_plot_hints, combine_hints, merge_hints, PlotHints
from SciQLop.core.property import SciQLopProperty
from SciQLop.core.mime import decode_mime
from SciQLop.core.mime.types import PRODUCT_LIST_MIME_TYPE, TIME_RANGE_MIME_TYPE, CATALOG_LIST_MIME_TYPE
from SciQLop.components.plotting.backend.palette import Palette, make_color_list
from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay
from SciQLop.components.plotting.ui.graph_context_menu import add_graph_context_actions

log = sciqlop_logging.getLogger(__name__)

register_icon("QCP", QIcon("://icons/QCP.png"))


def _variable_is_successful(v) -> bool:
    if v is None:
        return False
    try:
        return len(v) > 0
    except TypeError:
        return True


import shiboken6

_PLOT_REGISTRIES: dict[int, "_PlotHintsRegistry"] = {}


def _plot_key(plot) -> Optional[int]:
    try:
        return int(shiboken6.getCppPointer(plot)[0])
    except Exception:
        return id(plot)


def _graph_key(graph) -> int:
    try:
        return int(shiboken6.getCppPointer(graph)[0])
    except Exception:
        return id(graph)


class _PlotHintsRegistry:
    """Per-plot accumulator of per-graph PlotHints.

    When several products are plotted on one plot (e.g. two line products),
    the y-axis label becomes the comma-joined list of each product's composed
    label. Graphs auto-deregister via their QObject.destroyed signal so
    removing a product cleans up the label without a manual refresh.

    Keyed by C++ pointers (not by Python wrapper identity, which shiboken
    does not preserve across calls).
    """

    def __init__(self, plot):
        self._plot = plot  # strong ref; evicted from _PLOT_REGISTRIES on destroyed
        self._entries: dict[int, PlotHints] = {}

    def register(self, graph, hints: PlotHints) -> int:
        key = _graph_key(graph)
        self._entries[key] = hints
        try:
            graph.destroyed.connect(lambda *_, k=key: self._drop(k))
        except (AttributeError, RuntimeError):
            log.debug("graph has no destroyed signal; leak-resistant cleanup off")
        self._recompute()
        return key

    def update_if_present(self, key: int, hints: PlotHints) -> None:
        if key in self._entries:
            self._entries[key] = hints
            self._recompute()

    def _drop(self, key: int) -> None:
        if self._entries.pop(key, None) is not None:
            self._recompute()

    def _recompute(self) -> None:
        try:
            apply_plot_hints(self._plot, combine_hints(list(self._entries.values())))
        except RuntimeError:
            log.debug("plot already destroyed during hints recompute")


def _get_or_create_registry(plot) -> Optional["_PlotHintsRegistry"]:
    if plot is None:
        return None
    key = _plot_key(plot)
    if key is None:
        return _PlotHintsRegistry(plot)
    reg = _PLOT_REGISTRIES.get(key)
    if reg is not None and not shiboken6.isValid(reg._plot):
        _PLOT_REGISTRIES.pop(key, None)
        reg = None
    if reg is None:
        reg = _PlotHintsRegistry(plot)
        _PLOT_REGISTRIES[key] = reg
        try:
            plot.destroyed.connect(lambda *_, k=key: _PLOT_REGISTRIES.pop(k, None))
        except (AttributeError, RuntimeError):
            log.debug("plot has no destroyed signal; relying on isValid eviction")
    return reg


class _PostFetchHintsApplier:
    """Refines a graph's hints via provider.plot_hints_from_variable() on the
    first successful fetch, then updates the plot's registry entry — so the
    combined label reflects the richer post-fetch information."""

    def __init__(self, provider: DataProvider, node, registry: Optional["_PlotHintsRegistry"],
                 graph_key: int, base_hints: PlotHints):
        self._provider = provider
        self._node = node
        self._registry_ref = weakref.ref(registry) if registry is not None else None
        self._graph_key = graph_key
        self._base_hints = base_hints
        self._applied = False

    def observe(self, variable) -> None:
        if self._applied:
            return
        if not _variable_is_successful(variable):
            return
        reg = self._registry_ref() if self._registry_ref is not None else None
        if reg is None:
            self._applied = True
            return
        try:
            extra = self._provider.plot_hints_from_variable(self._node, variable)
        except Exception:
            log.debug("plot_hints_from_variable failed for %s", self._node, exc_info=True)
            self._applied = True
            return
        reg.update_if_present(self._graph_key, merge_hints(self._base_hints, extra))
        self._applied = True


class _ProductCallbackBase:
    """Shared state for product-fetch callbacks: provider, node, optional
    post-fetch hints applier, knob state. Subclasses override ``__call__``
    to shape the returned data and handle errors with the right empty value."""

    def __init__(self, provider: DataProvider, node,
                 post_fetch: Optional["_PostFetchHintsApplier"] = None,
                 knob_state=None):
        self.provider = provider
        self.node = node
        self._post_fetch = post_fetch
        self.knob_state = knob_state

    def _knob_values(self):
        return self.knob_state.values if self.knob_state is not None else None

    def _fetch(self, start, stop):
        observer = self._post_fetch.observe if self._post_fetch is not None else None
        return self.provider._get_data(self.node, start, stop,
                                       on_variable=observer,
                                       knobs=self._knob_values())


class _plot_product_callback(_ProductCallbackBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_data_fetched = None

    def __call__(self, start, stop):
        t0 = _time.monotonic() if self.on_data_fetched is not None else 0
        try:
            result = self._fetch(start, stop)
        except Exception as e:
            log.error(f"Error getting data for {self.node}: {e}")
            return []
        if self.on_data_fetched is not None:
            try:
                self.on_data_fetched(result, _time.monotonic() - t0, start, stop)
            except Exception:
                log.debug("on_data_fetched hook raised", exc_info=True)
        return result


def _y_is_descending(y):
    if len(y.shape) == 1 and len(y) > 1:
        return np.nanargmin(y) > np.nanargmax(y)
    elif len(y.shape) == 2 and y.shape[0] > 1:
        return np.nanargmin(y[0, :]) > np.nanargmax(y[0, :])
    else:
        return None


class _specgram_callback(_ProductCallbackBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._y_is_descending_ = None

    def _y_is_descending(self, y):
        if self._y_is_descending_ is None:
            self._y_is_descending_ = _y_is_descending(y)
            log.debug(f"y_is_descending: {self._y_is_descending_}")
        return self._y_is_descending_

    def __call__(self, start, stop):
        try:
            x, y, z = self._fetch(start, stop)
            if self._y_is_descending(y):
                if len(y.shape) == 1:
                    y = y[::-1].copy()
                else:
                    y = y[:, ::-1].copy()
                z = z[:, ::-1].copy()
            return x, y, z
        except Exception as e:
            log.error(f"Error getting data for {self.node}: {e}")
            empty = np.empty(0, dtype=np.float64)
            return empty, empty, empty


def _theme_from_palette(palette: dict[str, str], parent=None) -> SciQLopTheme:
    is_dark = QColor(palette.get("Window", "#ffffff")).lightnessF() < 0.5
    theme = SciQLopTheme.dark(parent) if is_dark else SciQLopTheme.light(parent)
    _MAP = {
        "set_background": "Base",
        "set_foreground": "Text",
        "set_grid": "Mid",
        "set_sub_grid": "Midlight",
        "set_selection": "Highlight",
        "set_legend_border": "Border",
    }
    for setter, key in _MAP.items():
        if key in palette:
            getattr(theme, setter)(QColor(palette[key]))
    if "Base" in palette:
        c = QColor(palette["Base"])
        c.setAlpha(200)
        theme.set_legend_background(c)
    return theme


def _set_product_path(r, product_path_str):
    graph = r[1] if hasattr(r, '__iter__') else r
    graph.setProperty("sqp_product_path", product_path_str)


def _plot_from_result(r, target):
    """Extract the plot object from target.plot()'s return value.

    target.plot() may return a graph (when target is already a SciQLopPlot),
    or a (plot, graph) tuple (when target is a SciQLopMultiPlotPanel that
    created a new subplot). In the first case the plot is the target itself.
    """
    if hasattr(r, '__iter__'):
        return r[0]
    if isinstance(target, SciQLopPlot):
        return target
    return None


def _graph_from_result(r):
    return r[1] if hasattr(r, '__iter__') else r


def _trigger_refetch_impl(graph):
    call = getattr(graph, "call", None)
    if call is None:
        log.debug("graph has no function pipeline — cannot refetch on knob change")
        return
    invalidate = getattr(graph, "invalidate_cache", None)
    if invalidate is not None:
        try:
            invalidate()
        except Exception:
            log.debug("invalidate_cache failed", exc_info=True)
    try:
        # graph.range() returns stale m_range (never updated by axis-driven fetches);
        # read the live x-axis range instead
        current_range = graph.x_axis().range()
        call(current_range)
    except Exception:
        log.debug("could not trigger refetch for knob change", exc_info=True)


def _trigger_refetch(graph):
    from SciQLop.user_api.threading import on_main_thread
    on_main_thread(_trigger_refetch_impl)(graph)


def _attach_knob_state(provider, node, callback, r, target=None):
    specs = []
    try:
        specs = provider.get_knobs(node)
    except Exception:
        log.error("get_knobs failed for %s", node, exc_info=True)
    if not specs:
        return
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector import KnobInspectorExtension
    from SciQLop.components.plotting.ui.knob_inspector.plot_items import create_plot_items
    graph = _graph_from_result(r)
    plot = _plot_from_result(r, target)
    state = GraphKnobState(specs, parent=graph)
    graph._knob_state = state
    callback.knob_state = state
    refetch_slot = lambda *_: _trigger_refetch(graph)
    graph._knobs_slot = refetch_slot
    state.knobs_changed.connect(refetch_slot)
    state.knobs_changed.connect(
        lambda values, g=graph: update_knobs(g, dict(values))
    )
    graph._visual_knob_dispose = None
    if plot is not None:
        graph._visual_knob_dispose = create_plot_items(plot, state)
    if hasattr(graph, "add_inspector_extension"):
        ext = KnobInspectorExtension(state, parent=graph)
        graph._knob_inspector_ext = ext
        graph.add_inspector_extension(ext)
        ext.destroyed.connect(lambda *_: _dispose_graph_knobs(graph))


def _dispose_graph_knobs(graph):
    """Called when a graph's parameters extension is deleted from the inspector.

    Removes the on-plot knob handles (drag spans/lines) and disconnects the
    re-fetch slot. Leaves the graph itself alone — only its parameter UI goes."""
    dispose = getattr(graph, "_visual_knob_dispose", None)
    if dispose is not None:
        dispose()
    graph._visual_knob_dispose = None
    state = getattr(graph, "_knob_state", None)
    slot = getattr(graph, "_knobs_slot", None)
    if state is not None and slot is not None:
        try:
            state.knobs_changed.disconnect(slot)
        except (RuntimeError, TypeError):
            pass
    graph._knobs_slot = None


def _build_knob_reset_action(state, parent):
    from PySide6.QtGui import QAction
    action = QAction("Reset parameters to defaults", parent)

    def _do_reset():
        defaults = {s.name: s.default for s in state.specs}
        state.set_all(defaults)

    action.triggered.connect(_do_reset)
    return action


def _safe_plot_hints(provider, node) -> PlotHints:
    try:
        return provider.plot_hints(node)
    except Exception:
        log.debug("plot_hints failed for %s", node, exc_info=True)
        return PlotHints()


def _register_graph_hints(provider, node, r, target) -> Optional["_PostFetchHintsApplier"]:
    plot = _plot_from_result(r, target)
    registry = _get_or_create_registry(plot)
    if registry is None:
        return None
    base_hints = _safe_plot_hints(provider, node)
    graph_key = registry.register(_graph_from_result(r), base_hints)
    return _PostFetchHintsApplier(provider, node, registry, graph_key, base_hints)


def _resolve_plot_target(p, kwargs):
    """If index targets an existing subplot, plot on that subplot instead of the panel.

    Returns (target, existing_plot_or_None). When target is an existing subplot,
    existing_plot is that subplot so callers can build the (plot, graph) pair.
    """
    index = kwargs.pop("index", None)
    if index is not None and isinstance(p, SciQLopMultiPlotPanel):
        plots = p.plots()
        if 0 <= index < len(plots):
            ptr = plots[index]
            # plot_type is only used by the panel to create the subplot type;
            # strip it when targeting an existing subplot
            kwargs.pop("plot_type", None)
            # plots() returns SciQLopPlotInterfacePtr which lacks patched methods,
            # so find the actual SciQLopPlot child by matching objectName
            name = ptr.objectName()
            for child in p.findChildren(SciQLopPlot):
                if child.objectName() == name:
                    return child, child
            return ptr, ptr
    return p, None


def _post_plot(r, provider, node, callback, target, product_path_str, existing_plot):
    if not hasattr(r, '__iter__') and existing_plot is not None:
        r = (existing_plot, r)
    _set_product_path(r, product_path_str)
    callback._post_fetch = _register_graph_hints(provider, node, r, target)
    _attach_knob_state(provider, node, callback, r, target)
    _attach_graph_context(r, provider, node, target)
    # Pin the ProductsModelNode's Python wrapper to the graph's lifetime.
    # Shiboken can otherwise GC the wrapper between plot setup and the
    # first async data-fetch, taking the C++ node with it (see
    # shiboken-python-subclass-gc-pitfall memory). The callback already
    # references the node via self.node, but the callback's own lifetime
    # depends on the C++ graph holding it, which in turn depends on the
    # graph wrapper surviving; pinning here is the belt-and-suspenders.
    graph = _graph_from_result(r)
    if graph is not None:
        graph._product_node_keepalive = node
        graph._product_callback_keepalive = callback
    return r


def _install_graph_context_ui(plot, graph) -> None:
    """After attach_context: add the GraphContextExtension to the graph's
    inspector node so the read-only "Graph" section appears under it.
    """
    try:
        from SciQLop.components.plotting.ui.graph_context_inspector import (
            GraphContextExtension,
        )
        if hasattr(graph, "add_inspector_extension"):
            ext = GraphContextExtension(graph, parent=graph)
            # Shiboken Python-subclass keepalive: parent= alone is not enough,
            # see memory shiboken-python-subclass-gc-pitfall.md.
            graph._graph_context_ext = ext
            graph.add_inspector_extension(ext)
    except Exception:
        log.warning("graph_context inspector install failed", exc_info=True)


def _attach_graph_context(r, provider, node, target):
    """Attach a GraphContext + rich refs to the graph just produced.

    Only acts on recognized provider types (EasyProvider, Speasy).
    Unknown DataProvider subclasses are skipped — better to attach no
    context than mislabel one.
    """
    try:
        plot, graph = r
        panel_name = target.windowTitle() if hasattr(target, "windowTitle") else ""
        plots = target.plots() if hasattr(target, "plots") else []
        plot_index = next((i for i, p in enumerate(plots)
                           if p.objectName() == plot.objectName()), -1)
        if plot_index == -1:
            log.debug("graph_context: plot %r not in target.plots() — using -1",
                      plot.objectName())
        graph_type = type(graph).__name__
        knobs = {}
        product_path = None
        try:
            if hasattr(node, "path"):
                p = node.path()
                if p:
                    product_path = list(p) if isinstance(p, (list, tuple)) else [str(p)]
        except Exception:
            product_path = None
        if isinstance(provider, EasyProvider):
            ctx = build_vp_ctx(
                graph, panel_name=panel_name, plot_index=plot_index,
                vp_path=provider._path, provider_name=provider.name,
                callback=provider._callback, graph_type=graph_type,
                product_path=product_path,
                knobs=knobs,
            )
            rich = GraphRichRefs(callback=provider._callback,
                                 knobs_model=provider._knobs_model)
            attach_context(graph, ctx, rich)
            _install_graph_context_ui(plot, graph)
            return
        if getattr(provider, "name", None) == "Speasy":
            speasy_id = ""
            if hasattr(node, "metadata"):
                speasy_id = node.metadata("speasy_id") or ""
            ctx = build_speasy_ctx(
                graph, panel_name=panel_name, plot_index=plot_index,
                speasy_id=speasy_id, graph_type=graph_type,
                product_path=product_path,
                knobs=knobs,
            )
            attach_context(graph, ctx)
            _install_graph_context_ui(plot, graph)
            return
        log.debug("graph_context: unknown provider %r — skipping attach",
                  type(provider).__name__)
    except Exception:
        log.warning("attach_graph_context failed", exc_info=True)


def plot_product(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], product: List[str], **kwargs):
    if not isinstance(product, list):
        return None
    node = ProductsModel.node(product)
    if node is None:
        log.debug(f"Product not found: {product}")
        return None
    provider = providers.get(node.provider())
    log.debug(f"Provider: {provider}")
    if provider is None:
        return None
    product_path_str = "//".join(product)
    target, existing_plot = _resolve_plot_target(p, kwargs)
    log.debug(f"Parameter type: {node.parameter_type()}")
    if node.parameter_type() in (ParameterType.Scalar, ParameterType.Vector, ParameterType.Multicomponents):
        callback = _plot_product_callback(provider, node)
        labels = listify(provider.labels(node))
        log.debug(f"Building plot for {node.name()} with labels: {labels}, kwargs: {kwargs}")
        r = target.plot(callback, labels=labels, **kwargs)
        if hasattr(r, '__iter__'):
            r[1].set_name(node.name())
        else:
            r.set_name(node.name())
        return _post_plot(r, provider, node, callback, target, product_path_str, existing_plot)
    if node.parameter_type() == ParameterType.Spectrogram:
        callback = _specgram_callback(provider, node)
        log.debug(f"Building spectrogram plot for {node.name()} with kwargs: {kwargs}")
        r = target.plot(callback, name=node.name(), graph_type=GraphType.ColorMap,
                        y_log_scale=True, z_log_scale=True, **kwargs)
        return _post_plot(r, provider, node, callback, target, product_path_str, existing_plot)
    return None


def plot_static_data(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], x, y, z=None, **kwargs):
    target, existing_plot = _resolve_plot_target(p, kwargs)
    if z is not None:
        r = target.plot(x, y, z, **kwargs)
    else:
        r = target.plot(x, y, **kwargs)
    if not hasattr(r, '__iter__') and existing_plot is not None:
        r = (existing_plot, r)
    try:
        plot, graph = r
        panel_name = target.windowTitle() if hasattr(target, "windowTitle") else ""
        plots = target.plots() if hasattr(target, "plots") else []
        plot_index = next((i for i, _p in enumerate(plots)
                           if _p.objectName() == plot.objectName()), -1)
        ctx = build_static_ctx(graph, panel_name=panel_name,
                               plot_index=plot_index,
                               graph_type=type(graph).__name__)
        attach_context(graph, ctx)
        _install_graph_context_ui(plot, graph)
    except Exception:
        log.warning("attach_context for static data failed", exc_info=True)
    return r


def plot_function(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], f, **kwargs):
    target, existing_plot = _resolve_plot_target(p, kwargs)
    r = target.plot(f, **kwargs)
    if not hasattr(r, '__iter__') and existing_plot is not None:
        r = (existing_plot, r)
    try:
        plot, graph = r
        panel_name = target.windowTitle() if hasattr(target, "windowTitle") else ""
        plots = target.plots() if hasattr(target, "plots") else []
        plot_index = next((i for i, _p in enumerate(plots)
                           if _p.objectName() == plot.objectName()), -1)
        ctx = build_function_ctx(graph, panel_name=panel_name,
                                  plot_index=plot_index,
                                  callback=f,
                                  graph_type=type(graph).__name__)
        attach_context(graph, ctx, GraphRichRefs(callback=f))
        _install_graph_context_ui(plot, graph)
    except Exception:
        log.warning("attach_context for function plot failed", exc_info=True)
    return r


def _trigger_layer_update_impl(renderer, plot):
    try:
        current_range = plot.x_axis().range()
        renderer.update(current_range.start(), current_range.stop())
    except Exception:
        log.debug("layer update failed", exc_info=True)


def _trigger_layer_update(renderer, plot):
    from SciQLop.user_api.threading import on_main_thread
    on_main_thread(_trigger_layer_update_impl)(renderer, plot)


def wire_layer_renderer(target, func, specs=None, initial_knobs=None,
                        panel=None, scope: str = "auto"):
    """Create a LayerRenderer, wire knobs + range listener, return the renderer.

    `scope` controls where spans render and where the inspector node lives:
    "panel" → spans on every plot in the panel + inspector node under panel,
    "plot"  → spans on `target` only + inspector node under that plot,
    "auto"  → "plot" if data-aware, "panel" otherwise."""
    from SciQLop.user_api.layers._renderer import LayerRenderer
    from SciQLop.user_api.layers._introspection import extract_data_type
    from SciQLop.user_api.knobs import extract_specs_from_callback
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector import KnobInspectorExtension, LayerExtension

    data_type = extract_data_type(func)
    if scope == "auto":
        scope = "plot" if data_type is not None else "panel"
    if scope == "panel" and panel is None:
        from SciQLop.user_api.layers._renderer import _find_panel
        panel = _find_panel(target)
        if panel is None:
            scope = "plot"

    renderer = LayerRenderer(target, func, data_type=data_type,
                             scope=scope, panel=panel, parent=target)
    renderer._visual_knob_dispose = None
    title = getattr(func, "__name__", "Layer")
    knob_host = panel if scope == "panel" and panel is not None else target
    ext = None

    if specs is None:
        specs = extract_specs_from_callback(func)
    if specs:
        from SciQLop.components.plotting.ui.knob_inspector.plot_items import create_plot_items
        state = GraphKnobState(specs, parent=renderer)
        renderer._knob_state = state
        if initial_knobs:
            state.set_all(initial_knobs)
        renderer._knobs_slot = lambda *_: _trigger_layer_update(renderer, target)
        state.knobs_changed.connect(renderer._knobs_slot)
        if hasattr(knob_host, "add_inspector_extension"):
            ext = KnobInspectorExtension(state, parent=renderer, title=title)
            renderer._knob_inspector_ext = ext
            knob_host.add_inspector_extension(ext)
        renderer._visual_knob_dispose = create_plot_items(target, state)
    else:
        if hasattr(knob_host, "add_inspector_extension"):
            ext = LayerExtension(parent=renderer, title=title)
            renderer._layer_ext = ext
            knob_host.add_inspector_extension(ext)

    if renderer.data_aware:
        renderer.setup_data_binding()
    else:
        renderer._range_slot = lambda new_range: renderer.update(new_range.start(), new_range.stop())
        # Cache the x_axis QObject here, while the plot is alive. During
        # the panel-destroy cascade `target.x_axis()` would go through
        # the Shiboken wrapper that calls QWidget::sharedPainter() on a
        # half-destructed plot and segfaults — see LayerRenderer.dispose.
        renderer._x_axis = target.x_axis()
        renderer._x_axis.range_changed.connect(renderer._range_slot)

    if not hasattr(target, "_layer_renderers"):
        target._layer_renderers = []
    target._layer_renderers.append(renderer)

    if ext is not None:
        ext.destroyed.connect(lambda *_: _dispose_layer(renderer, target))

    try:
        current_range = target.x_axis().range()
        renderer.update(current_range.start(), current_range.stop())
    except Exception:
        log.debug("initial layer render skipped — no valid range yet")

    return renderer


def _dispose_layer(renderer, target):
    """Called when the layer's inspector extension is deleted.

    Tears down visual knob items, the renderer's spans/hlines/markers, and
    drops the renderer from the plot's bookkeeping list."""
    dispose = getattr(renderer, "_visual_knob_dispose", None)
    if dispose is not None:
        dispose()
    renderer._visual_knob_dispose = None
    renderers = getattr(target, "_layer_renderers", None)
    if renderers is not None and renderer in renderers:
        renderers.remove(renderer)
    try:
        renderer.dispose()
    except RuntimeError:
        pass


def attach_layer(plot, product: list[str], panel=None):
    from SciQLop.user_api.layers._provider import _layer_providers

    node = ProductsModel.node(product)
    if node is None:
        return None
    provider = _layer_providers.get(node.provider())
    if provider is None:
        return None

    return wire_layer_renderer(plot, provider.callback,
                                specs=provider.get_knobs(), panel=panel,
                                scope=provider.resolve_scope())


class ProductDnDCallback(PlotDragNDropCallback):
    def __init__(self, parent):
        super().__init__(PRODUCT_LIST_MIME_TYPE, True, parent)

    def call(self, plot, mime_data: QMimeData):
        log.debug(f"ProductDnDCallback: {mime_data}")
        for product in decode_mime(mime_data):
            log.debug(f"ProductDnDCallback: {product}")
            node = ProductsModel.node(product)
            if node is not None:
                log.debug(f"ProductDnDCallback: {node}")
                from SciQLop.user_api.layers._provider import LAYER_META_KEY
                if node.metadata().get(LAYER_META_KEY) == "true":
                    attach_layer(plot, product, panel=self.parent())
                else:
                    plot_product(plot, product)


class TimeRangeDnDCallback(PlotDragNDropCallback):
    def __init__(self, parent):
        super().__init__(TIME_RANGE_MIME_TYPE, False, parent)

    def call(self, plot, mime_data: QMimeData):
        time_range = decode_mime(mime_data)
        plot.time_axis().set_range(time_range)


class CatalogDnDCallback(PlotDragNDropCallback):
    def __init__(self, parent):
        super().__init__(CATALOG_LIST_MIME_TYPE, False, parent)

    def call(self, plot, mime_data: QMimeData):
        catalogs = decode_mime(mime_data)
        if not catalogs:
            return
        manager = self.parent().catalog_manager
        for cat in catalogs:
            manager.add_catalog(cat)


class TimeSyncPanel(SciQLopMultiPlotPanel):

    def __init__(self, name: str, parent=None, time_range: Optional[TimeRange] = None,
                 show_search_overlay: bool = True):
        super().__init__(parent, synchronize_x=False, synchronize_time=True)
        self.setObjectName(name)
        self.setWindowTitle(name)
        self._parent_node = None
        self._template_source_path: str | None = None
        self._product_plot_callback = ProductDnDCallback(self)
        self._time_range_plot_callback = TimeRangeDnDCallback(self)
        self._catalog_plot_callback = CatalogDnDCallback(self)
        self.add_accepted_mime_type(self._product_plot_callback)
        self.add_accepted_mime_type(self._time_range_plot_callback)
        self.add_accepted_mime_type(self._catalog_plot_callback)
        self.set_color_palette(make_color_list(Palette()))
        self.update_theme()
        if time_range is not None:
            self.time_range = time_range

        from SciQLop.components.catalogs.backend.panel_manager import PanelCatalogManager
        self._catalog_manager = PanelCatalogManager(self)
        self.installEventFilter(self)
        self.plot_added.connect(self._install_filter_on_plot)
        self.plot_added.connect(self._apply_theme_to_plot)

        self._search_overlay = None
        if show_search_overlay:
            self._search_overlay = ProductSearchOverlay(self.viewport())
            self._search_overlay.product_selected.connect(self._on_overlay_product_selected)
            self.plot_added.connect(self._dismiss_search_overlay)
            self._search_overlay.raise_()
            self._search_overlay.focus_search()

    def _on_overlay_product_selected(self, product_path: list[str]):
        from SciQLopPlots import PlotType
        plot_product(self, product_path, plot_type=PlotType.TimeSeries)

    def _dismiss_search_overlay(self, _plot=None):
        if self._search_overlay is not None:
            self._search_overlay.hide()
            self._search_overlay.deleteLater()
            self._search_overlay = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._search_overlay is not None:
            self._search_overlay.setGeometry(self.viewport().geometry())

    def _apply_theme_to_plot(self, plot):
        # Workaround: SciQLopNDProjectionPlot doesn't override set_theme/theme,
        # so we reach into its inner SciQLopPlot children directly.
        # Remove once SciQLopPlots implements set_theme on SciQLopNDProjectionPlot.
        theme = self.theme()
        if theme is None:
            return
        for child in plot.findChildren(SciQLopPlot):
            child.set_theme(theme)

    def update_theme(self):
        from SciQLop.components.theming.palette import SCIQLOP_PALETTE
        self.set_theme(_theme_from_palette(SCIQLOP_PALETTE, self))
        for plot in self.plots():
            self._apply_theme_to_plot(plot)

    @property
    def catalog_manager(self):
        return self._catalog_manager

    def _install_filter_on_plot(self, plot):
        plot.installEventFilter(self)
        for child in plot.findChildren(QWidget):
            child.installEventFilter(self)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.ContextMenu:
            self._show_context_menu(event.globalPos())
            return True
        return super().eventFilter(obj, event)

    def _show_context_menu(self, global_pos):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        self._catalog_manager.build_catalogs_menu(menu)
        menu.addSeparator()
        menu.addAction("Export as PNG\u2026", self._export_png)
        menu.addAction("Export as PDF\u2026", self._export_pdf)
        menu.addSeparator()
        if self._template_source_path:
            menu.addAction("Update template", self._update_template)
        menu.addAction("Save as template\u2026", self._quick_save_template)
        menu.addAction("Export template\u2026", self._export_template)
        self._append_knob_reset_actions(menu)
        add_graph_context_actions(menu, self)
        menu.exec(global_pos)

    def _append_knob_reset_actions(self, menu):
        actions = []
        for plot in self.plots():
            for child in plot.children():
                state = getattr(child, "_knob_state", None)
                if state is not None and state.specs:
                    label = child.name() if hasattr(child, "name") else "graph"
                    a = _build_knob_reset_action(state, parent=menu)
                    a.setText(f"Reset parameters: {label}")
                    actions.append(a)
        if actions:
            menu.addSeparator()
            for a in actions:
                menu.addAction(a)

    def _export_png(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Export as PNG",
            f"{self.windowTitle()}.png",
            "PNG (*.png)",
        )
        if path:
            self.save_png(path)

    def _export_pdf(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Export as PDF",
            f"{self.windowTitle()}.pdf",
            "PDF (*.pdf)",
        )
        if path:
            self.save_pdf(path)

    def _update_template(self):
        self._save_template_with_preview(self._template_source_path)

    def _save_template_with_preview(self, path, name=None):
        from SciQLop.components.plotting.panel_template import PanelTemplate, save_preview
        t = PanelTemplate.from_panel(self)
        if name:
            t.name = name
        t.to_file(path)
        save_preview(self, path)

    def _quick_save_template(self):
        from PySide6.QtWidgets import QInputDialog
        from SciQLop.components.plotting.panel_template import templates_dir
        name, ok = QInputDialog.getText(
            self, "Save as template", "Template name:",
            text=self.windowTitle(),
        )
        if ok and name.strip():
            path = str(templates_dir() / f"{name.strip()}.json")
            self._save_template_with_preview(path, name.strip())
            self._template_source_path = path

    def _export_template(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Export panel template",
            f"{self.windowTitle()}.json",
            "JSON (*.json);;YAML (*.yaml *.yml)",
        )
        if path:
            self._save_template_with_preview(path)

    @SciQLopProperty(TimeRange)
    def time_range(self) -> TimeRange:
        return self.time_axis_range()

    @time_range.setter
    def time_range(self, time_range: TimeRange):
        self.set_time_axis_range(time_range)

    def __repr__(self):
        return f"TimeSyncPanel: {self.name}"

    @SciQLopProperty(str)
    def icon(self) -> str:
        return "QCP"
