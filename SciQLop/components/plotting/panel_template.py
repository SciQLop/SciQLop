"""Panel model: the one description of "what is in this panel" shared by
every exporter (template files, Python reproducer snippets, Speasy proxy
URL) and importer. ``from_panel`` is the single walker over the Qt objects;
everything else maps to and from this model.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, PrivateAttr, field_validator

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.graph_context import GraphContext, context_of, graph_name
from SciQLop.core.plot_kinds import PLOT_KINDS, TIME_PANEL, TIMESERIES, plot_kind_of, plugin_of
from SciQLop.core.source_kinds import canonical_id, source_kind

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
_V2 = 2


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
    if data.get("version", 1) >= _V2:
        return data
    plots = [{**plot, "products": [_default_axis(p) for p in plot.get("products", [])]}
             for plot in data.get("plots", [])]
    return {**data, "plots": plots, "version": _V2}


def _read_template_data(p: Path) -> dict:
    import json
    if p.suffix == '.json':
        return json.loads(p.read_text())
    if p.suffix in ('.yaml', '.yml'):
        return _load_yaml(p.read_text())
    raise ValueError(f"Unsupported file extension: {p.suffix}")


def _load_yaml(text: str):
    """Templates saved before 0.14.2 wrote ranges as !!python/tuple, which
    safe_load rejects; read those as plain lists."""
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_constructor("tag:yaml.org,2002:python/tuple", Loader.construct_sequence)
    return yaml.load(text, Loader=Loader)


class PanelTemplate(BaseModel):
    name: str
    description: str = ""
    version: int = TEMPLATE_VERSION
    time_range: Optional[TimeRangeModel] = None
    plots: list[PlotModel]
    intervals: list[IntervalModel] = []
    max_zoom_seconds: float | None = None
    _source_path: str | None = PrivateAttr(default=None)
    _saved_version: int = PrivateAttr(default=TEMPLATE_VERSION)

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
        if p.suffix == '.json':
            import json
            p.write_text(json.dumps(self.to_tree(), indent=2))
        elif p.suffix in ('.yaml', '.yml'):
            import yaml
            p.write_text(yaml.dump(self.to_tree(), default_flow_style=False, sort_keys=False))
        else:
            raise ValueError(f"Unsupported file extension: {p.suffix}")

    def to_tree(self) -> dict:
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
            raise ValueError(f"panel kind {root.kind!r} needs plugin {plugin_of(root.kind)!r} (panel kinds other "
                             f"than {TIME_PANEL} are not supported yet)")
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
        from SciQLop.components.plotting.panel_introspection import ordered_panel_plots
        models = (_saved_plot(plot) for plot in ordered_panel_plots(panel))
        plots = [m for m in models if m is not None]
        return PanelTemplate(
            name=panel.windowTitle() or panel.objectName(),
            time_range=_time_range_model(panel),
            plots=plots,
            max_zoom_seconds=_read_max_zoom(panel),
        )

    def create_panel(self, main_window, source_path: str | None = None):
        panel = main_window.new_plot_panel()
        impl = panel._impl if hasattr(panel, '_impl') else panel
        self.apply(impl)
        impl._template_source_path = source_path or self._source_path
        return panel

    def apply(self, panel) -> None:
        # Limit and range go first: a graph fetches on its first range change,
        # so plotting at the panel's previous range fetched a wrong window (GH #143).
        panel.clear()
        self._apply_zoom_limit(panel)
        if self.time_range is not None:
            panel.set_time_axis_range(self._time_range())
        for plot_model in self.plots:
            _restore_plot(panel, plot_model)
        self._apply_zoom_limit(panel)

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
    return PlotModel(kind=kind.id, config=kind.to_config(plot))


def _restore_plot(panel, model: PlotModel):
    """A plot kind that is not registered, or whose from_config fails, leaves a placeholder that keeps the node."""
    from SciQLop.components.plotting.placeholder import add_placeholder
    if model.kind == TIMESERIES:
        return _restore_timeseries(panel, model)
    kind = PLOT_KINDS.get(model.kind) if model.kind in PLOT_KINDS else None
    if kind is None or kind.from_config is None:
        return add_placeholder(panel, model)
    try:
        return kind.from_config(panel, model.config)
    except Exception as e:
        log.error(f"restoring a {model.kind} plot failed", exc_info=True)
        return add_placeholder(panel, model, reason=str(e))


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


_TEMPLATE_EXTENSIONS = ('.json', '.yaml', '.yml')


def templates_dir() -> Path:
    d = Path.home() / ".local" / "share" / "sciqlop" / "templates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_templates() -> list[PanelTemplate]:
    d = templates_dir()
    seen_stems: set[str] = set()
    results: list[PanelTemplate] = []
    for ext in _TEMPLATE_EXTENSIONS:
        for f in sorted(d.glob(f"*{ext}")):
            if f.stem not in seen_stems:
                seen_stems.add(f.stem)
                try:
                    results.append(_load_upgrading_file(f))
                except Exception:
                    pass
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
    for ext in _TEMPLATE_EXTENSIONS:
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
