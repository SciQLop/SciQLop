"""Find the App Store entry that brings a missing panel kind (plan 2g §2), off the GUI thread."""
from __future__ import annotations

import threading
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal, Slot

from SciQLop.components.plugins.backend.settings import canonical_package_name
from SciQLop.components.plugins.plugin_registry import (compatible_versions, fetch_index, filter_packages,
                                                        latest_version)
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.plot_kinds import plugin_of

log = getLogger(__name__)

PANEL_KINDS_KEY = "sciqlop.panel_kinds"


def _provides(entry: dict, kind_id: str) -> bool:
    latest = latest_version({"versions": compatible_versions(entry)})
    return latest is not None and kind_id in latest.get("provides", {}).get(PANEL_KINDS_KEY, [])


def _named_after(entry: dict, kind_id: str) -> bool:
    return canonical_package_name(entry["name"]) == canonical_package_name(plugin_of(kind_id))


def store_entry_for_kind(kind_id: str, index: list[dict]) -> Optional[dict]:
    """The entry whose latest compatible version provides the kind, else the one named after its id prefix."""
    return (next((e for e in index if _provides(e, kind_id)), None)
            or next((e for e in index if _named_after(e, kind_id) and compatible_versions(e)), None))


class _MainThreadDelivery(QObject):
    """Created on the main thread; a worker emits `ready`, the bound slot runs queued on the main thread
    (the AppStoreBackend._hot_load_requested pattern)."""
    ready = Signal(object, object)  # done, entry

    def __init__(self):
        super().__init__()
        self.ready.connect(self._deliver)

    @Slot(object, object)
    def _deliver(self, done, entry) -> None:
        done(entry)


_delivery: Optional[_MainThreadDelivery] = None


def _main_thread_delivery() -> _MainThreadDelivery:
    global _delivery
    if _delivery is None:
        _delivery = _MainThreadDelivery()
    return _delivery


def _lookup(kind_id: str) -> Optional[dict]:
    try:
        return store_entry_for_kind(kind_id, filter_packages(fetch_index()))
    except Exception as e:
        log.warning(f"Could not look up the plugin for panel kind {kind_id!r} in the App Store: {e}")
        return None


def find_store_entry(kind_id: str, done: Callable[[Optional[dict]], None]) -> None:
    """Call done(entry or None) on the main thread once the store index has been searched; call from the main thread.
    simplify: refetches the index each time a placeholder opens (no cache); cache it if many placeholders open at once."""
    delivery = _main_thread_delivery()
    threading.Thread(target=lambda: delivery.ready.emit(done, _lookup(kind_id)), daemon=True).start()
