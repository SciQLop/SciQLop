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
from SciQLop.core.property import SciQLopProperty
from SciQLop.core.mime import decode_mime
from SciQLop.core.mime.types import PRODUCT_LIST_MIME_TYPE, TIME_RANGE_MIME_TYPE
from SciQLop.components.plotting.backend.palette import Palette, make_color_list
from SciQLop.components.plotting.ui.product_search_overlay import ProductSearchOverlay

log = sciqlop_logging.getLogger(__name__)

register_icon("QCP", QIcon("://icons/QCP.png"))


class _plot_product_callback:
    def __init__(self, provider: DataProvider, node):
        self.provider = provider
        self.node = node

    def __call__(self, start, stop):
        try:
            return self.provider._get_data(self.node, start, stop)
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
    def __init__(self, provider: DataProvider, node):
        self.provider = provider
        self.node = node
        self._y_is_descending_ = None

    def _y_is_descending(self, y):
        if self._y_is_descending_ is None:
            self._y_is_descending_ = _y_is_descending(y)
            log.debug(f"y_is_descending: {self._y_is_descending_}")
        return self._y_is_descending_

    def __call__(self, start, stop):
        try:
            x, y, z = self.provider._get_data(self.node, start, stop)
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


def plot_product(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], product: List[str], **kwargs):
    if isinstance(product, list):
        node = ProductsModel.node(product)
        if node is not None:
            provider = providers.get(node.provider())
            log.debug(f"Provider: {provider}")
            if provider is not None:
                product_path_str = "//".join(product)
                log.debug(f"Parameter type: {node.parameter_type()}")
                if node.parameter_type() in (ParameterType.Scalar, ParameterType.Vector, ParameterType.Multicomponents):
                    callback = _plot_product_callback(provider, node)
                    labels = listify(provider.labels(node))
                    log.debug(f"Building plot for {node.name()} with labels: {labels}, kwargs: {kwargs}")
                    r = p.plot(callback, labels=labels, **kwargs)
                    if hasattr(r, '__iter__'):
                        r[1].set_name(node.name())
                    else:
                        r.set_name(node.name())
                    _set_product_path(r, product_path_str)
                    return r
                elif node.parameter_type() == ParameterType.Spectrogram:
                    callback = _specgram_callback(provider, node)
                    log.debug(f"Building spectrogram plot for {node.name()} with kwargs: {kwargs}")
                    r = p.plot(callback, name=node.name(), graph_type=GraphType.ColorMap, y_log_scale=True,
                               z_log_scale=True, **kwargs)
                    _set_product_path(r, product_path_str)
                    return r
    log.debug(f"Product not found: {product}")
    return None


def plot_static_data(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], x, y, z=None, **kwargs):
    if z is not None:
        return p.plot(x, y, z, **kwargs)
    else:
        return p.plot(x, y, **kwargs)


def plot_function(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], f, **kwargs):
    return p.plot(f, **kwargs)


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

    def update_theme(self):
        from SciQLop.components.theming.palette import SCIQLOP_PALETTE
        self.set_theme(_theme_from_palette(SCIQLOP_PALETTE, self))

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
