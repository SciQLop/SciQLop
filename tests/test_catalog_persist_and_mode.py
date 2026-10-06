"""Agents and notebooks can save catalogs and set a panel's catalog mode.

Both were only reachable from the UI: the catalog browser's Save and the
panel's mode combo. A cell that wrote events left them unsaved, and nothing
told it how to switch a panel to Jump or Edit.
"""
from .fixtures import *
import pytest

from SciQLop.components.catalogs.backend.provider import Capability, Catalog, CatalogProvider

_WRITABLE = {Capability.EDIT_EVENTS, Capability.CREATE_EVENTS, Capability.DELETE_EVENTS}


class _SaveRecorder(CatalogProvider):
    def __init__(self, caps):
        super().__init__(name="PersistProbe")
        self._caps = set(caps)
        self.saved = []
        self._catalog = Catalog(uuid="c0", name="events", provider=self, path=[])
        self._set_events(self._catalog, [])

    def catalogs(self):
        return [self._catalog]

    def capabilities(self, catalog=None):
        return self._caps

    def _do_save(self):
        self.saved.append("provider")

    def _do_save_catalog(self, catalog):
        self.saved.append(catalog.name)


@pytest.fixture
def make_provider(qtbot, qapp):
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    made = []

    def _make(caps):
        provider = _SaveRecorder(caps)
        made.append(provider)
        return provider

    yield _make
    for provider in made:
        CatalogRegistry.instance().unregister(provider)


def _persist(path):
    from SciQLop.user_api.catalogs import catalogs
    catalogs.persist(path)


def test_persist_saves_only_that_catalog_when_the_provider_can(make_provider):
    provider = make_provider(_WRITABLE | {Capability.SAVE, Capability.SAVE_CATALOG})
    provider.mark_dirty(provider.catalogs()[0])
    _persist("PersistProbe//events")
    assert provider.saved == ["events"]
    assert not provider.is_dirty(provider.catalogs()[0])


def test_persist_saves_the_provider_otherwise(make_provider):
    provider = make_provider(_WRITABLE | {Capability.SAVE})
    provider.mark_dirty(provider.catalogs()[0])
    _persist("PersistProbe//events")
    assert provider.saved == ["provider"]
    assert not provider.is_dirty()


def test_persist_does_nothing_for_a_provider_that_stores_changes_itself(make_provider):
    provider = make_provider(_WRITABLE)
    _persist("PersistProbe//events")
    assert provider.saved == []


def test_persist_refuses_a_read_only_catalog(make_provider):
    make_provider(set())
    with pytest.raises(PermissionError):
        _persist("PersistProbe//events")


def test_persist_unknown_catalog_is_a_key_error(make_provider):
    make_provider(_WRITABLE | {Capability.SAVE})
    with pytest.raises(KeyError):
        _persist("PersistProbe//nope")


class _SlowLoader(CatalogProvider):
    """Loads its events in the background, 300 ms after they are first asked for."""

    def __init__(self):
        super().__init__(name="SlowProbe")
        self._catalog = Catalog(uuid="s0", name="events", provider=self, path=[])
        self._requested = False

    def catalogs(self):
        return [self._catalog]

    def capabilities(self, catalog=None):
        return _WRITABLE

    def events(self, catalog, start=None, stop=None):
        if not self._requested:
            self._requested = True
            from PySide6.QtCore import QTimer
            QTimer.singleShot(300, self._finish_loading)
        return super().events(catalog, start, stop)

    def is_loading(self, catalog):
        return catalog.uuid not in self._events

    def _finish_loading(self):
        from datetime import datetime, timezone
        from SciQLop.components.catalogs.backend.provider import CatalogEvent
        day = datetime(2025, 10, 10, tzinfo=timezone.utc)
        self._set_events(self._catalog, [
            CatalogEvent(uuid=f"e{i}", start=day.replace(hour=i), stop=day.replace(hour=i, minute=30))
            for i in (1, 2)])


@pytest.fixture
def slow_provider(main_window, qtbot):
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    provider = _SlowLoader()
    yield provider
    CatalogRegistry.instance().unregister(provider)


def _from_kernel_thread(qtbot, func):
    """Run func off the GUI thread, as a notebook cell or agent call does."""
    import threading
    outcome = {}

    def run():
        try:
            outcome["value"] = func()
        except Exception as e:  # noqa: BLE001
            outcome["error"] = e

    worker = threading.Thread(target=run)
    worker.start()
    qtbot.waitUntil(lambda: not worker.is_alive(), timeout=10000)
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"]


def test_get_waits_for_events_still_loading(slow_provider, qtbot):
    """A catalog read right after startup came back empty: its events were
    still loading in the background."""
    from SciQLop.user_api.catalogs import catalogs
    events = _from_kernel_thread(qtbot, lambda: list(catalogs.get("SlowProbe//events")))
    assert len(events) == 2


def test_add_events_keeps_the_events_still_loading(slow_provider, qtbot):
    """Appending to a catalog that had not loaded yet started from an empty
    list, so the catalog showed only the new event."""
    from SciQLop.user_api.catalogs import catalogs
    _from_kernel_thread(qtbot, lambda: catalogs.add_events(
        "SlowProbe//events", [("2025-10-10T05:00:00", "2025-10-10T05:30:00")]))
    assert len(slow_provider.events(slow_provider.catalogs()[0])) == 3


def test_panel_catalog_mode_round_trips_and_reaches_the_manager(main_window, qtbot):
    from SciQLop.components.catalogs.backend.panel_manager import InteractionMode
    from SciQLop.user_api.plot import create_plot_panel
    panel = create_plot_panel()
    try:
        assert panel.catalog_mode == "view"
        panel.catalog_mode = "jump"
        assert panel.catalog_mode == "jump"
        assert panel._get_impl_or_raise().catalog_manager.mode is InteractionMode.JUMP
        panel.catalog_mode = "EDIT"
        assert panel.catalog_mode == "edit"
    finally:
        panel.close()


def test_panel_catalog_mode_rejects_an_unknown_mode(main_window, qtbot):
    from SciQLop.user_api.plot import create_plot_panel
    panel = create_plot_panel()
    try:
        with pytest.raises(ValueError, match="view, jump, edit"):
            panel.catalog_mode = "zoom"
    finally:
        panel.close()
