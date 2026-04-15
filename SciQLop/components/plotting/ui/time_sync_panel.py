from typing import Optional, List, Union

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
import weakref

from SciQLop.core.plot_hints import apply_plot_hints, combine_hints, merge_hints, PlotHints
from SciQLop.core.property import SciQLopProperty
from SciQLop.core.mime import decode_mime
from SciQLop.core.mime.types import PRODUCT_LIST_MIME_TYPE, TIME_RANGE_MIME_TYPE
from SciQLop.components.plotting.backend.palette import Palette, make_color_list
from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay

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
    if reg is None:
        reg = _PlotHintsRegistry(plot)
        _PLOT_REGISTRIES[key] = reg
        try:
            plot.destroyed.connect(lambda *_, k=key: _PLOT_REGISTRIES.pop(k, None))
        except (AttributeError, RuntimeError):
            log.debug("plot has no destroyed signal; registry leaks until app exit")
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


class _plot_product_callback:
    def __init__(self, provider: DataProvider, node, post_fetch: Optional["_PostFetchHintsApplier"] = None):
        self.provider = provider
        self.node = node
        self._post_fetch = post_fetch

    def __call__(self, start, stop):
        try:
            observer = self._post_fetch.observe if self._post_fetch is not None else None
            return self.provider._get_data(self.node, start, stop, on_variable=observer)
        except Exception as e:
            log.error(f"Error getting data for {self.node}: {e}")
            return []


def _y_is_descending(y):
    if len(y.shape) == 1 and len(y) > 1:
        return np.nanargmin(y) > np.nanargmax(y)
    elif len(y.shape) == 2 and y.shape[0] > 1:
        return np.nanargmin(y[0, :]) > np.nanargmax(y[0, :])
    else:
        return None


class _specgram_callback:
    def __init__(self, provider: DataProvider, node, post_fetch: Optional["_PostFetchHintsApplier"] = None):
        self.provider = provider
        self.node = node
        self._y_is_descending_ = None
        self._post_fetch = post_fetch

    def _y_is_descending(self, y):
        if self._y_is_descending_ is None:
            self._y_is_descending_ = _y_is_descending(y)
            log.debug(f"y_is_descending: {self._y_is_descending_}")
        return self._y_is_descending_

    def __call__(self, start, stop):
        try:
            observer = self._post_fetch.observe if self._post_fetch is not None else None
            x, y, z = self.provider._get_data(self.node, start, stop, on_variable=observer)
            if self._y_is_descending(y):
                if len(y.shape) == 1:
                    y = y[::-1].copy()
                else:
                    y = y[:, ::-1].copy()
                z = z[:, ::-1].copy()
            return x, y, z
        except Exception as e:
            log.error(f"Error getting data for {self.node}: {e}")
            return []


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


def _safe_plot_hints(provider, node) -> PlotHints:
    try:
        return provider.plot_hints(node)
    except Exception:
        log.debug("plot_hints failed for %s", node, exc_info=True)
        return PlotHints()


def _graph_from_result(r):
    return r[1] if hasattr(r, '__iter__') else r


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


def plot_product(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], product: List[str], **kwargs):
    if isinstance(product, list):
        node = ProductsModel.node(product)
        if node is not None:
            provider = providers.get(node.provider())
            log.debug(f"Provider: {provider}")
            if provider is not None:
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
                        if existing_plot is not None:
                            r = (existing_plot, r)
                    _set_product_path(r, product_path_str)
                    callback._post_fetch = _register_graph_hints(provider, node, r, target)
                    return r
                elif node.parameter_type() == ParameterType.Spectrogram:
                    callback = _specgram_callback(provider, node)
                    log.debug(f"Building spectrogram plot for {node.name()} with kwargs: {kwargs}")
                    r = target.plot(callback, name=node.name(), graph_type=GraphType.ColorMap, y_log_scale=True,
                                    z_log_scale=True, **kwargs)
                    if not hasattr(r, '__iter__') and existing_plot is not None:
                        r = (existing_plot, r)
                    _set_product_path(r, product_path_str)
                    callback._post_fetch = _register_graph_hints(provider, node, r, target)
                    return r
    log.debug(f"Product not found: {product}")
    return None


def plot_static_data(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], x, y, z=None, **kwargs):
    target, existing_plot = _resolve_plot_target(p, kwargs)
    if z is not None:
        r = target.plot(x, y, z, **kwargs)
    else:
        r = target.plot(x, y, **kwargs)
    if not hasattr(r, '__iter__') and existing_plot is not None:
        r = (existing_plot, r)
    return r


def plot_function(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], f, **kwargs):
    target, existing_plot = _resolve_plot_target(p, kwargs)
    r = target.plot(f, **kwargs)
    if not hasattr(r, '__iter__') and existing_plot is not None:
        r = (existing_plot, r)
    return r


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
                plot_product(plot, product)


class TimeRangeDnDCallback(PlotDragNDropCallback):
    def __init__(self, parent):
        super().__init__(TIME_RANGE_MIME_TYPE, False, parent)

    def call(self, plot, mime_data: QMimeData):
        time_range = decode_mime(mime_data)
        plot.time_axis().set_range(time_range)


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
        self.add_accepted_mime_type(self._product_plot_callback)
        self.add_accepted_mime_type(self._time_range_plot_callback)
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
        menu.exec(global_pos)

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
