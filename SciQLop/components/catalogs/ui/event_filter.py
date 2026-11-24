"""The filter above a catalogue's events in the catalog browser. A provider may supply its own
(CatalogProvider.event_filter, internal for now: not a plugin API yet); PlainTextFilter serves the
others. The browser hosts the delegate's widget, keeps the rows it accepts, and remembers its state
per catalogue for the session.

Threading: everything here lives on the GUI thread. accepts() only reads a result computed
beforehand; matching, anything proportional to the number of events, runs in a LatestOnly worker on
plain data (never the events themselves: they are Qt objects of the GUI thread)."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QLineEdit, QWidget

from ..backend.event_text import event_text, text_keeps
from .latest_only import LatestOnly

DEBOUNCE_MS = 150


class EventFilter(QObject):
    """What the browser asks of a filter delegate."""
    changed = Signal()  # the kept events changed: the table filters again

    def widget(self) -> QWidget:
        raise NotImplementedError

    def set_events(self, events: list) -> None:
        """The catalogue's events, at first and after each change."""
        raise NotImplementedError

    def accepts(self, event) -> bool:
        """Cheap, GUI thread: reads the last result, computes nothing."""
        raise NotImplementedError

    def kept(self) -> set[str] | None:
        """The uuids kept; None when nothing is filtered out."""
        raise NotImplementedError

    def state(self) -> Any:
        """What the browser remembers for this catalogue for the session; None: nothing typed."""
        return None

    def restore(self, state: Any) -> None:
        """Back to a remembered state."""

    def clear(self) -> None:
        """Empty, at once: nothing filtered out."""

    def dispose(self) -> None:
        """Stop the work in flight; the browser then deletes the widget."""


class BackgroundEventFilter(EventFilter):
    """An EventFilter whose matching runs off the GUI thread: a subclass says what plain data the
    events give (prepare, GUI thread) and how a query keeps them (match, any thread, pure); typing is
    debounced and only the answer to the last query is applied."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._data = None
        self._kept: set[str] | None = None
        self._worker = LatestOnly(self)
        self._worker.done.connect(self._apply)
        self._worker.failed.connect(lambda _why: self._apply(None))
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self.refilter)

    # ---- for subclasses ----

    def query(self) -> str:
        raise NotImplementedError

    def prepare(self, events: list):
        raise NotImplementedError

    @staticmethod
    def match(data, query: str) -> set[str] | None:
        raise NotImplementedError

    # ---- EventFilter ----

    def set_events(self, events: list) -> None:
        self._data = self.prepare(events)
        if self.query().strip():
            self.refilter()

    def accepts(self, event) -> bool:
        return self._kept is None or event.uuid in self._kept

    def kept(self) -> set[str] | None:
        return self._kept

    def dispose(self) -> None:
        self._debounce.stop()
        self._worker.stop()

    # ---- the work ----

    def query_edited(self) -> None:
        self._debounce.start()

    def refilter(self) -> None:
        self._debounce.stop()
        query, data, match = self.query(), self._data, self.match
        if not query.strip() or data is None:
            return self._apply(None)
        self._worker.submit(lambda: match(data, query))

    def _apply(self, kept: set[str] | None) -> None:
        self._kept = kept
        self.changed.emit()


class PlainTextFilter(BackgroundEventFilter):
    """Today's filter: a case-insensitive piece of text, matched against every column as the table
    shows it."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.box = QLineEdit()
        self.box.setPlaceholderText("Filter events…")
        self.box.setClearButtonEnabled(True)
        self.box.setToolTip("Filter the event table; matches any column.")
        self.box.textChanged.connect(lambda _text: self.query_edited())

    def widget(self) -> QWidget:
        return self.box

    def query(self) -> str:
        return self.box.text()

    def prepare(self, events: list):
        return [(event.uuid, event_text(event)) for event in events]

    @staticmethod
    def match(data, query: str) -> set[str] | None:
        return text_keeps(data, query)

    def state(self):
        return self.box.text() or None

    def restore(self, state) -> None:
        self.box.setText(state or "")
        self.refilter()

    def clear(self) -> None:
        self.box.blockSignals(True)
        self.box.clear()
        self.box.blockSignals(False)
        self.refilter()
