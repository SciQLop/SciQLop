from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, PrivateAttr

from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)


class TimeRangeModel(BaseModel):
    start: str
    stop: str


class ProductModel(BaseModel):
    path: str
    label: str = ""


class AxisModel(BaseModel):
    log: bool = False
    range: tuple[float, float] | None = None


class PlotModel(BaseModel):
    products: list[ProductModel]
    y_axis: AxisModel = AxisModel()
    z_axis: AxisModel = AxisModel()


class IntervalModel(BaseModel):
    start: str
    stop: str
    color: str = ""
    label: str = ""


def _restore_axis(axis, model: AxisModel) -> None:
    if model.log:
        axis.set_log(True)
    if model.range is not None:
        axis.set_range(*model.range)


def _read_max_zoom(panel) -> float | None:
    for plot in panel.plots():
        limit = plot.time_axis().max_range_size()
        if limit != float('inf'):
            return limit
    return None


class PanelTemplate(BaseModel):
    name: str
    description: str = ""
    version: int = 1
    time_range: TimeRangeModel
    plots: list[PlotModel]
    intervals: list[IntervalModel] = []
    max_zoom_seconds: float | None = None
    _source_path: str | None = PrivateAttr(default=None)

    @staticmethod
    def from_file(path: str) -> PanelTemplate:
        p = Path(path)
        text = p.read_text()
        if p.suffix == '.json':
            t = PanelTemplate.model_validate_json(text)
        elif p.suffix in ('.yaml', '.yml'):
            import yaml
            t = PanelTemplate.model_validate(yaml.safe_load(text))
        else:
            raise ValueError(f"Unsupported file extension: {p.suffix}")
        t._source_path = str(p.resolve())
        return t

    def to_file(self, path: str) -> None:
        p = Path(path)
        if p.suffix == '.json':
            p.write_text(self.model_dump_json(indent=2))
        elif p.suffix in ('.yaml', '.yml'):
            import yaml
            p.write_text(yaml.dump(self.model_dump(), default_flow_style=False, sort_keys=False))
        else:
            raise ValueError(f"Unsupported file extension: {p.suffix}")

    @staticmethod
    def _capture_axis(axis) -> AxisModel:
        r = axis.range()
        return AxisModel(log=axis.log(), range=(r.start(), r.stop()))

    @staticmethod
    def from_panel(panel) -> PanelTemplate:
        tr = panel.time_range
        time_range = TimeRangeModel(
            start=datetime.fromtimestamp(tr.start(), tz=timezone.utc).isoformat(),
            stop=datetime.fromtimestamp(tr.stop(), tz=timezone.utc).isoformat(),
        )
        plots = []
        for plot in panel.plots():
            products = []
            for graph in plot.plottables():
                path = graph.property("sqp_product_path")
                if path:
                    products.append(ProductModel(path=path, label=graph.name))
                else:
                    log.warning(f"Skipping graph without sqp_product_path: {graph.name}")
            if products:
                y_axis = PanelTemplate._capture_axis(plot.y_axis())
                z_axis = PanelTemplate._capture_axis(plot.z_axis())
                plots.append(PlotModel(products=products, y_axis=y_axis, z_axis=z_axis))
        max_zoom = _read_max_zoom(panel)
        return PanelTemplate(
            name=panel.windowTitle() or panel.objectName(),
            time_range=time_range,
            plots=plots,
            max_zoom_seconds=max_zoom,
        )

    def create_panel(self, main_window, source_path: str | None = None):
        panel = main_window.new_plot_panel()
        impl = panel._impl if hasattr(panel, '_impl') else panel
        self.apply(impl)
        impl._template_source_path = source_path or self._source_path
        return panel

    def apply(self, panel) -> None:
        from SciQLop.components.plotting.ui.time_sync_panel import plot_product
        from SciQLopPlots import PlotType as _PlotType
        from SciQLop.core import TimeRange as TR
        panel.clear()
        for plot_model in self.plots:
            subplot = None
            for product in plot_model.products:
                resolved = resolve_product_path(product.path)
                if subplot is None:
                    r = plot_product(panel, resolved, plot_type=_PlotType.TimeSeries)
                    if r is not None:
                        subplot = r[0] if hasattr(r, '__iter__') else panel.plots()[-1]
                    else:
                        log.warning(f"Product not found, skipping: {product.path}")
                else:
                    r = plot_product(subplot, resolved)
                    if r is None:
                        log.warning(f"Product not found, skipping: {product.path}")
            if subplot is not None:
                _restore_axis(subplot.y_axis(), plot_model.y_axis)
                _restore_axis(subplot.z_axis(), plot_model.z_axis)
        if self.max_zoom_seconds is not None:
            for plot in panel.plots():
                plot.time_axis().set_max_range_size(self.max_zoom_seconds)
            if hasattr(panel, '_time_range_bar') and panel._time_range_bar is not None:
                panel._time_range_bar.max_range_seconds = self.max_zoom_seconds
        panel.set_time_axis_range(TR(
            datetime.fromisoformat(self.time_range.start).timestamp(),
            datetime.fromisoformat(self.time_range.stop).timestamp(),
        ))


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
                    results.append(PanelTemplate.from_file(str(f)))
                except Exception:
                    pass
    return results


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
