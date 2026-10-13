"""One axis of a plot: what the Properties panel edits per axis."""
from SciQLop.core.colors import to_qcolor
from ._thread_safety import on_main_thread, _qt_property


class Axis:
    """Looked up from its plot on each access rather than held, so a handle
    never outlives the axis it points to."""

    def __init__(self, plot, name: str):
        self._plot = plot
        self._name = name

    def _get_impl_or_raise(self):
        return self._plot._resolve_axis(self._name)

    label = _qt_property("label", "set_label", to_qt=str)
    label_font = _qt_property("label_font", "set_label_font")
    label_color = _qt_property("label_color", "set_label_color", to_qt=to_qcolor)
    tick_labels_visible = _qt_property("tick_labels_visible", "set_tick_labels_visible", to_qt=bool)
    tick_label_font = _qt_property("tick_label_font", "set_tick_label_font")
    tick_label_color = _qt_property("tick_label_color", "set_tick_label_color", to_qt=to_qcolor)
    autoscale_margin = _qt_property("autoscale_margin", "set_autoscale_margin", to_qt=float,
                                   doc="Space kept around the data when autoscaling, "
                                       "as a fraction of the range (0.05 = 5 %).")

    @property
    @on_main_thread
    def autoscale_percentile(self) -> tuple[float, float]:
        """The (low, high) percentiles of the data the axis fits to when it
        autoscales, so outliers do not squash the rest."""
        impl = self._get_impl_or_raise()
        return impl.autoscale_percentile_low(), impl.autoscale_percentile_high()

    @autoscale_percentile.setter
    @on_main_thread
    def autoscale_percentile(self, bounds: tuple[float, float]) -> None:
        low, high = bounds
        impl = self._get_impl_or_raise()
        impl.set_autoscale_percentile_low(float(low))
        impl.set_autoscale_percentile_high(float(high))

    def _repr_pretty_(self, p, cycle):
        p.text(f"Axis({self._name!r})")
