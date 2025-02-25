from SciQLop.widgets.plots.time_span import TimeSpan
from SciQLop.widgets.plots.time_sync_panel import TimeSyncPanel
from SciQLop.backend import TimeRange, sciqlop_logging
from .event import Event

from PySide6.QtCore import Slot, Signal

log = sciqlop_logging.getLogger(__name__)

class EventSpan(TimeSpan):
    selected_sig = Signal(str)
    delete_me = Signal(str)

    def __init__(self, event: Event, plot_panel: TimeSyncPanel, parent=None, visible=True, read_only=False, color=None):
        super().__init__(plot_panel, event.range, visible=visible,
                         read_only=read_only, color=color, tool_tip=event.tooltip)

        self._event = event
        self.range_changed.connect(self._range_changed)
        event.color_changed.connect(self.set_color)
        event.selection_changed.connect(self._selection_changed)
        self.delete_requested.connect(self._delete_requested)
        self.selection_changed.connect(self._notify_selected)

    @Slot()
    def set_color(self, color):
        log.debug(f"Setting color {color}")
        self.color = color

    @property
    def uuid(self):
        return self._event.uuid

    @property
    def catalog_uid(self):
        return self._event.catalog_uid

    @Slot()
    def _selection_changed(self, selected: bool):
        self.change_selection(selected)

    @Slot()
    def _range_changed(self, new_range: TimeRange):
        self._event.set_range(new_range)
        self.tooltip = self._event.tooltip

    @Slot()
    def _delete_requested(self):
        self.delete_me.emit(self._event.uuid)

    def _notify_selected(self, selected: bool):
        if selected:
            self.selected_sig.emit(self._event.uuid)
