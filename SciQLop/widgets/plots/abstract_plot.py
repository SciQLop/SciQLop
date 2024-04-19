from typing import Protocol, runtime_checkable

from PySide6.QtWidgets import QFrame

from ...backend import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)


@runtime_checkable
class Plot(Protocol):
    _palette_index: int = 0

    def replot(self, *args, **kwargs):
        ...

    def autoscale_x_axis(self):
        ...

    def autoscale_y_axis(self):
        ...


class MetaPlot(type(QFrame), type(Plot)):
    pass
