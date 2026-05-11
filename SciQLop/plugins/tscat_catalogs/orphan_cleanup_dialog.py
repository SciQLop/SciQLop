from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QApplication,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QCursor

from tscat_gui.tscat_driver.model import tscat_model

from .orphans import ORPHAN_CATALOG_UUID, BulkDeleteOrphanEventsAction


class OrphanCleanupDialog(QDialog):
    """Dialog listing tscat orphan events with check-and-delete affordances.

    Reads the orphan list from ``provider._orphan_events`` (cached, refreshed
    off-thread by the provider via ``GetOrphanEventsAction``). Deletion goes
    through ``tscat_model.do(RemoveEntitiesAction(...))`` so the database
    work happens on the driver QThread; the provider's ``_on_action_done``
    hook then triggers another orphan refresh, which fires
    ``events_changed`` and re-populates this dialog.
    """

    def __init__(self, provider, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clean up orphan events")
        self._provider = provider

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.NoSelection)

        layout = QVBoxLayout(self)
        self._summary = QLabel()
        layout.addWidget(self._summary)
        layout.addWidget(self._list)

        btns = QHBoxLayout()
        self._delete_selected = QPushButton("Delete checked")
        self._delete_selected.clicked.connect(self._on_delete_selected)
        self._delete_all = QPushButton("Delete all")
        self._delete_all.clicked.connect(self._on_delete_all)
        cancel = QPushButton("Close")
        cancel.clicked.connect(self.close)
        btns.addWidget(self._delete_selected)
        btns.addWidget(self._delete_all)
        btns.addStretch(1)
        btns.addWidget(cancel)
        layout.addLayout(btns)

        self._provider.events_changed.connect(self._on_events_changed)
        self._populate()

    @Slot(object)
    def _on_events_changed(self, catalog) -> None:
        if getattr(catalog, "uuid", None) == ORPHAN_CATALOG_UUID:
            self._populate()

    def _populate(self) -> None:
        self._list.clear()
        events = list(self._provider._orphan_events)
        self._summary.setText(f"{len(events)} orphan event(s)")
        for ev in events:
            label = (f"{ev.start.isoformat()} → {ev.stop.isoformat()} "
                     f"(uuid={ev.uuid[:8]}…)")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ev.uuid)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._list.addItem(item)

    def orphan_rows(self) -> list[tuple[str, str]]:
        return [
            (self._list.item(i).data(Qt.ItemDataRole.UserRole),
             self._list.item(i).text())
            for i in range(self._list.count())
        ]

    def delete_uuids(self, uuids: list[str] | None) -> None:
        """Bulk-delete orphan events on the driver thread.

        ``uuids=None`` deletes every current orphan (cheaper than enumerating
        them on the main thread when there are tens of thousands).
        """
        self._set_busy(True, status_text="Deleting orphan events…")
        action = BulkDeleteOrphanEventsAction(
            user_callback=lambda _action: self._on_delete_done(),
            uuids=list(uuids) if uuids is not None else None,
        )
        tscat_model.do(action)

    def _set_busy(self, busy: bool, status_text: str | None = None) -> None:
        for btn in (self._delete_selected, self._delete_all):
            btn.setEnabled(not busy)
        if busy:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
            if status_text is not None:
                self._summary.setText(status_text)
        else:
            QApplication.restoreOverrideCursor()
            if status_text is not None:
                self._summary.setText(status_text)

    @Slot()
    def _on_delete_done(self) -> None:
        # The delete itself returned; we're now waiting for the orphan
        # cache to refresh (debounced ~250ms + driver round-trip). Keep
        # the cursor restored so the user knows the deletion landed, but
        # tell them we're still refreshing.
        self._set_busy(False, status_text="Refreshing orphan list…")
        self._provider._dispatch_orphan_refresh()

    def _on_delete_selected(self) -> None:
        uuids = [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.CheckState.Checked
        ]
        if uuids:
            self.delete_uuids(uuids)

    def _on_delete_all(self) -> None:
        self.delete_uuids(None)
