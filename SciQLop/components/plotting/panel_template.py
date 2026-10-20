"""Panel model: the one description of "what is in this panel" shared by
every exporter (template files, Python reproducer snippets, Speasy proxy
URL) and importer. ``from_panel`` is the single walker over the Qt objects;
everything else maps to and from this model.
"""
from __future__ import annotations

import copy
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, PrivateAttr, field_validator

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.graph_context import GraphContext, context_of, graph_name
from SciQLop.core.plot_kinds import PLOT_KINDS, TIME_PANEL, TIMESERIES, plot_kind_of
from SciQLop.core.source_kinds import canonical_id, source_kind
from SciQLop.components.plotting.template_formats import format_for, template_suffixes

log = getLogger(__name__)


class TimeRangeModel(BaseModel):
    start: str
    stop: str


class ProductModel(BaseModel):
    """One plottable. ``path`` is the product-tree path (``a//b//c``), empty
    when the graph can't be reproduced from a product (static data, function
    plots). The remaining fields carry the graph's provenance."""
    path: str
    label: str = ""
    kind: Optional[str] = None
    speasy_id: Optional[str] = None
    graph_type: str = ""
    knobs: dict[str, Any] = {}
    y_axis: Optional[Literal["y", "y2"]] = None  # None: where the graph type draws by default

    @field_validator("kind", mode="before")
    @classmethod
    def _canonical_kind(cls, kind):
        """Saved templates may hold the pre-extension-point values ("speasy", "vp", ...)."""
        return canonical_id(kind) if isinstance(kind, str) else kind

    @property
    def is_colormap(self) -> bool:
        return "ColorMap" in self.graph_type


class AxisModel(BaseModel):
    log: bool = False
    range: tuple[float, float] | None = None


class PlotModel(BaseModel):
    """A time-series plot uses the fields below; any other kind keeps everything in ``config``."""
    products: list[ProductModel] = []
    kind: str = TIMESERIES
    config: dict[str, Any] = {}
    y_axis: AxisModel = AxisModel()
    y2_axis: Optional[AxisModel] = None  # None: saved before right axes were kept
    z_axis: AxisModel = AxisModel()


class IntervalModel(BaseModel):
    start: str
    stop: str
    color: str = ""
    label: str = ""


def _restore_axis(axis, model: Optional[AxisModel]) -> None:
    if model is None:
        return
    axis.set_log(model.log)
    if model.range is not None:
        axis.set_range(*model.range)


def _place_on_axis(plot, graph, axis_name: Optional[str]) -> None:
    if axis_name is None:
        return
    target = plot.y2_axis() if axis_name == "y2" else plot.y_axis()
    if graph is not None and graph.y_axis() is not target:
        graph.set_y_axis(target)


def _graph_axis_name(plot, graph) -> str:
    return "y2" if graph.y_axis() is plot.y2_axis() else "y"


def _restore_timeseries(panel, plot_model: PlotModel):
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product, _graph_from_result
    from SciQLopPlots import PlotType as _PlotType
    subplot = None
    for product in plot_model.products:
        if not product.path:
            log.warning(f"Not reproducible from a product, skipping: {product.label}")
            continue
        resolved = resolve_product_path(product.path)
        inputs = {"product_inputs": product.knobs} if product.knobs else {}
        if subplot is None:
            r = plot_product(panel, resolved, plot_type=_PlotType.TimeSeries, **inputs)
            if r is not None:
                subplot = r[0] if hasattr(r, '__iter__') else panel.plots()[-1]
        else:
            r = plot_product(subplot, resolved, **inputs)
        if r is None:
            log.warning(f"Product not found, skipping: {product.path}")
        elif subplot is not None:
            _place_on_axis(subplot, _graph_from_result(r), product.y_axis)
    if subplot is not None:
        _restore_axis(subplot.y_axis(), plot_model.y_axis)
        _restore_axis(subplot.y2_axis(), plot_model.y2_axis)
        _restore_axis(subplot.z_axis(), plot_model.z_axis)
    return subplot


def _read_max_zoom(panel) -> float | None:
    # A cleared panel has no plots left to ask; its bar still holds the limit.
    bar = getattr(panel, '_time_range_bar', None)
    if bar is not None:
        return bar.max_range_seconds or None
    for plot in panel.plots():
        limit = plot.time_axis().max_range_size()
        if limit != float('inf'):
            return limit
    return None


TEMPLATE_VERSION = 3
_PER_GRAPH_AXES_VERSION = 2  # the version that started recording which y axis each graph draws on


class PanelNode(BaseModel):
    """A node of the panel tree (spec §5); its kind names a sciqlop.plot_kinds contribution or a panel kind."""
    kind: str
    id: str = ""
    config: dict[str, Any] = {}
    slots: dict[str, list["PanelNode"]] = {}


def _plot_node(plot: PlotModel) -> PanelNode:
    if plot.kind == TIMESERIES:
        return PanelNode(kind=TIMESERIES, config=plot.model_dump(mode="json", exclude={"kind", "config"}))
    return PanelNode(kind=plot.kind, config=plot.config)


def _plot_model_of(node: PanelNode) -> PlotModel:
    if node.kind == TIMESERIES:
        return PlotModel.model_validate(node.config)
    return PlotModel(kind=node.kind, config=node.config)


def _default_axis(product: dict) -> dict:
    graph_type = product.get("graph_type") or ""
    if "y_axis" in product or not graph_type:
        return product
    return {**product, "y_axis": "y2" if "ColorMap" in graph_type else "y"}


def _upgrade(data: dict) -> dict:
    """Version 1 did not say which y axis each graph draws on; a spectrogram
    always drew on y2, any other graph on y."""
    if data.get("version", 1) >= _PER_GRAPH_AXES_VERSION:
        return data
    plots = [{**plot, "products": [_default_axis(p) for p in plot.get("products", [])]}
             for plot in data.get("plots", [])]
    return {**data, "plots": plots, "version": _PER_GRAPH_AXES_VERSION}


def _read_template_data(p: Path) -> dict:
    return format_for(p).loads(p.read_text())


class PanelTemplate(BaseModel):
    name: str
    description: str = ""
    version: int = TEMPLATE_VERSION
    time_range: Optional[TimeRangeModel] = None
    plots: list[PlotModel]
    intervals: list[IntervalModel] = []
    max_zoom_seconds: float | None = None
    panel_kind: str = TIME_PANEL
    _source_path: str | None = PrivateAttr(default=None)
    _saved_version: int = PrivateAttr(default=TEMPLATE_VERSION)
    _foreign_root: Optional[dict] = PrivateAttr(default=None)  # kept raw: only its kind can read it

    @staticmethod
    def _foreign(name: str, description: str, root: dict) -> PanelTemplate:
        t = PanelTemplate(name=name, description=description, plots=[], panel_kind=root["kind"])
        t._foreign_root = root
        return t

    @staticmethod
    def from_file(path: str) -> PanelTemplate:
        p = Path(path)
        data = _read_template_data(p)
        t = (PanelTemplate.from_tree(data) if data.get("version", 1) >= TEMPLATE_VERSION
             else PanelTemplate.model_validate({**_upgrade(data), "version": TEMPLATE_VERSION}))
        t._source_path = str(p.resolve())
        t._saved_version = data.get("version", 1)
        return t

    def to_file(self, path: str) -> None:
        p = Path(path)
        p.write_text(format_for(p).dumps(self.to_tree()))

    def to_tree(self) -> dict:
        if self._foreign_root is not None:
            return {"version": TEMPLATE_VERSION, "name": self.name, "description": self.description,
                    "panel": self._foreign_root}
        root = PanelNode(kind=TIME_PANEL,
                         config={"time_range": self.time_range.model_dump() if self.time_range else None},
                         slots={"plots": [_plot_node(p) for p in self.plots]})
        return {"version": TEMPLATE_VERSION, "name": self.name, "description": self.description,
                "max_zoom_seconds": self.max_zoom_seconds,
                "intervals": [i.model_dump() for i in self.intervals], "panel": root.model_dump(mode="json")}

    @staticmethod
    def from_tree(data: dict) -> PanelTemplate:
        root = PanelNode.model_validate(data["panel"])
        if root.kind != TIME_PANEL:
            return PanelTemplate._foreign(data["name"], data.get("description", ""), data["panel"])
        time_range = root.config.get("time_range")
        return PanelTemplate(name=data["name"], description=data.get("description", ""),
                             max_zoom_seconds=data.get("max_zoom_seconds"),
                             intervals=data.get("intervals", []),
                             time_range=TimeRangeModel(**time_range) if time_range else None,
                             plots=[_plot_model_of(n) for n in root.slots.get("plots", [])])

    @staticmethod
    def _capture_axis(axis) -> AxisModel:
        r = axis.range()
        return AxisModel(log=axis.log(), range=(r.start(), r.stop()))

    @staticmethod
    def from_panel(panel) -> PanelTemplate:
        if _is_foreign_panel(panel):
            return PanelTemplate._foreign(panel.windowTitle() or panel.objectName(), _description_of(panel),
                                          panel_tree(panel))
        from SciQLop.components.plotting.panel_introspection import ordered_panel_plots
        models = (_saved_plot(plot) for plot in ordered_panel_plots(panel))
        plots = [m for m in models if m is not None]
        return PanelTemplate(
            name=panel.windowTitle() or panel.objectName(),
            description=_description_of(panel),
            time_range=_time_range_model(panel),
            plots=plots,
            max_zoom_seconds=_read_max_zoom(panel),
        )

    def create_panel(self, main_window, source_path: str | None = None):
        from SciQLop.core.panel_kinds import DESCRIPTION_PROPERTY
        if self._foreign_root is not None:
            panel = self._open_foreign(main_window)
            panel.setProperty(DESCRIPTION_PROPERTY, self.description)
            return panel
        panel = main_window.new_plot_panel()
        impl = panel._impl if hasattr(panel, '_impl') else panel
        self.apply(impl)
        impl._template_source_path = source_path or self._source_path
        impl.setProperty(DESCRIPTION_PROPERTY, self.description)
        return panel

    def _open_foreign(self, main_window):
        from SciQLop.components.plotting.ui.placeholder_panel import open_placeholder
        from SciQLop.core.panel_kinds import PANEL_KINDS
        if self.panel_kind in PANEL_KINDS:
            return main_window._open_panel(self.panel_kind, self.name, None,
                                           copy.deepcopy(self._foreign_root.get("config", {})))
        return open_placeholder(main_window, self._foreign_root, name=self.name)

    def apply(self, panel) -> list:
        """Rebuilds the panel; returns what restoring each of ``self.plots`` gave, index-aligned (None: nothing)."""
        if self._foreign_root is not None:
            raise TypeError(f"template {self.name!r} is a {self.panel_kind} template, not a time panel one")
        # Limit and range go first: a graph fetches on its first range change,
        # so plotting at the panel's previous range fetched a wrong window (GH #143).
        panel.clear()
        self._apply_zoom_limit(panel)
        if self.time_range is not None:
            panel.set_time_axis_range(self._time_range())
        restored = [_restore_plot(panel, plot_model) for plot_model in self.plots]
        self._apply_zoom_limit(panel)
        return restored

    def _time_range(self):
        from SciQLop.core import TimeRange as TR
        return TR(datetime.fromisoformat(self.time_range.start).timestamp(),
                  datetime.fromisoformat(self.time_range.stop).timestamp())

    def _apply_zoom_limit(self, panel) -> None:
        """An explicit limit wins; otherwise the panel's current limit is
        raised when it would clamp this template's own range (a shared link
        must restore the view it was taken from)."""
        limit = self.max_zoom_seconds
        if limit is None:
            limit = self._span_beyond_current_limit(panel)
        if limit is None:
            return
        for plot in panel.plots():
            plot.time_axis().set_max_range_size(limit)
        bar = getattr(panel, '_time_range_bar', None)
        if bar is not None:
            bar.max_range_seconds = limit

    def _span_beyond_current_limit(self, panel) -> float | None:
        if self.time_range is None:
            return None
        current = _read_max_zoom(panel)
        tr = self._time_range()
        span = tr.stop() - tr.start()
        return span if current is not None and span > current else None


def _is_foreign_panel(panel) -> bool:
    """Untagged time panels (made directly, as tests and older callers do) still save as time templates."""
    from PySide6.QtWidgets import QWidget
    from SciQLop.core.panel_kinds import panel_kind_of
    return isinstance(panel, QWidget) and panel_kind_of(panel) not in (None, TIME_PANEL)


def _description_of(panel) -> str:
    from SciQLop.core.panel_kinds import DESCRIPTION_PROPERTY
    return panel.property(DESCRIPTION_PROPERTY) or ""


def panel_tree(widget) -> dict:
    """The {kind, config, slots} tree of any panel (spec §5); ValueError when its kind cannot be saved."""
    from SciQLop.components.plotting.ui.placeholder_panel import PlaceholderPanel
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    if isinstance(widget, TimeSyncPanel):
        return PanelTemplate.from_panel(widget).to_tree()["panel"]
    if isinstance(widget, PlaceholderPanel):
        return copy.deepcopy(widget.root)
    return {"kind": (kind := _savable_kind(widget)).id, "config": kind.to_config(widget), "slots": {}}


def _savable_kind(widget):
    from SciQLop.core.panel_kinds import PANEL_KINDS, panel_kind_of
    kind_id = panel_kind_of(widget)
    kind = PANEL_KINDS.get(kind_id) if kind_id in PANEL_KINDS else None
    if kind is None or kind.to_config is None:
        raise ValueError(f"panel kind {kind_id!r} cannot be saved")
    return kind


def _timeseries_model(plot) -> Optional[PlotModel]:
    from SciQLop.components.plotting.panel_introspection import plot_graphs
    graphs = plot_graphs(plot)
    if not graphs:
        return None
    return PlotModel(
        products=[product_model(g).model_copy(update={"y_axis": _graph_axis_name(plot, g)}) for g in graphs],
        y_axis=PanelTemplate._capture_axis(plot.y_axis()),
        y2_axis=PanelTemplate._capture_axis(plot.y2_axis()),
        z_axis=PanelTemplate._capture_axis(plot.z_axis()),
    )


def _saved_plot(plot) -> Optional[PlotModel]:
    from SciQLop.components.plotting.placeholder import placeholder_model
    kept = placeholder_model(plot)
    if kept is not None:
        return kept
    kind = plot_kind_of(plot)
    if kind.id == TIMESERIES:
        return _timeseries_model(plot)
    if kind.to_config is None:
        log.warning(f"a {kind.id} plot is not saved: its plot kind has no to_config")
        return None
    try:
        return PlotModel(kind=kind.id, config=kind.to_config(plot))
    except Exception:
        log.error(f"a {kind.id} plot is not saved: its to_config raised", exc_info=True)
        return None


def _restore_plot(panel, model: PlotModel):
    """A plot kind that is not registered, or whose from_config fails, leaves a placeholder that keeps the node."""
    from SciQLop.components.plotting.placeholder import add_placeholder
    if model.kind == TIMESERIES:
        return _restore_timeseries(panel, model)
    kind = PLOT_KINDS.get(model.kind) if model.kind in PLOT_KINDS else None
    if kind is None or kind.from_config is None:
        return add_placeholder(panel, model)
    plots_before = len(panel.plots())
    try:
        return kind.from_config(panel, model.config)
    except Exception as e:
        log.error(f"restoring a {model.kind} plot failed", exc_info=True)
        _remove_plots_beyond(panel, plots_before)
        return add_placeholder(panel, model, reason=str(e))


def _remove_plots_beyond(panel, count: int) -> None:
    for plot in panel.plots()[count:]:
        panel.remove_plot(plot)


def _time_range_model(panel) -> Optional[TimeRangeModel]:
    """None while the panel has no finite range yet (fresh panel before its
    first plot)."""
    r = panel.time_axis_range()
    start, stop = float(r.start()), float(r.stop())
    if not (math.isfinite(start) and math.isfinite(stop)):
        return None
    return TimeRangeModel(
        start=datetime.fromtimestamp(start, tz=timezone.utc).isoformat(),
        stop=datetime.fromtimestamp(stop, tz=timezone.utc).isoformat(),
    )


def product_model(graph) -> ProductModel:
    ctx = context_of(graph)
    if ctx is None:
        return ProductModel(path=graph.property("sqp_product_path") or "",
                            label=graph_name(graph))
    return ProductModel(path=context_product_path(ctx), label=graph_name(graph),
                        kind=ctx.kind, speasy_id=ctx.speasy_id,
                        graph_type=ctx.graph_type, knobs=dict(ctx.knobs))


def context_product_path(ctx: GraphContext) -> str:
    """Product-tree path (``a//b//c``, no implicit ``root``) a graph can be
    re-plotted from, or "" for function/static graphs."""
    return source_kind(ctx.kind).product_path(ctx)


def templates_dir() -> Path:
    d = Path.home() / ".local" / "share" / "sciqlop" / "templates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_templates() -> list[PanelTemplate]:
    d = templates_dir()
    seen_stems: set[str] = set()
    results: list[PanelTemplate] = []
    for ext in template_suffixes():
        for f in sorted(d.glob(f"*{ext}")):
            if f.stem not in seen_stems:
                seen_stems.add(f.stem)
                try:
                    results.append(_load_upgrading_file(f))
                except Exception as e:
                    log.warning(f"Skipping template {f}: {e}")
    return results


def _load_upgrading_file(path: Path) -> PanelTemplate:
    t = PanelTemplate.from_file(str(path))
    if t._saved_version < TEMPLATE_VERSION:
        try:
            t.to_file(str(path))
        except OSError as e:
            log.warning(f"Could not upgrade template {path}: {e}")
    return t


def find_template_file(name: str) -> Path | None:
    d = templates_dir()
    for ext in template_suffixes():
        p = d / f"{name}{ext}"
        if p.exists():
            return p
    return None


def find_template(name: str) -> PanelTemplate | None:
    p = find_template_file(name)
    return PanelTemplate.from_file(str(p)) if p else None


def delete_template(name: str) -> bool:
    p = find_template_file(name)
    if not p:
        return False
    p.unlink()
    png = p.with_suffix('.png')
    if png.exists():
        png.unlink()
    return True


def rename_template(old_name: str, new_name: str) -> bool:
    p = find_template_file(old_name)
    if not p or find_template_file(new_name):
        return False
    t = PanelTemplate.from_file(str(p))
    t.name = new_name
    new_path = p.with_name(f"{new_name}{p.suffix}")
    t.to_file(str(new_path))
    p.unlink()
    old_png = p.with_suffix('.png')
    if old_png.exists():
        old_png.rename(new_path.with_suffix('.png'))
    return True


def preview_path(template_path: str) -> Path:
    return Path(template_path).with_suffix('.png')


def save_preview(widget, template_path: str) -> None:
    from PySide6.QtWidgets import QWidget
    if not isinstance(widget, QWidget):
        return
    pixmap = widget.grab()
    if not pixmap.isNull():
        pixmap.save(str(preview_path(template_path)), "PNG")


def resolve_product_path(path: str) -> list[str]:
    if '//' in path:
        return path.split('//')
    return ['speasy'] + path.split('/')
