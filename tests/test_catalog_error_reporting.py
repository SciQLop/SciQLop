"""Provider failures must be visible to the user, not silent (2026-09-06 review).

Before this: `CatalogProvider.error_occurred` was emitted by tscat/cocat and
connected by nobody, and `CatalogBrowser._on_add_event`/`_on_delete`/
`_on_save_clicked` propagated backend exceptions as bare tracebacks with no
user-facing feedback. `CatalogBrowser.provider_error` is the single surface
mainwindow listens to (status bar); this file only checks that surface fires
correctly, not the status bar wiring itself (manual/UI concern).
"""
from .fixtures import *


def test_existing_provider_error_occurred_surfaces(qtbot, qapp):
    """A provider registered *before* the browser exists still gets wired."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    provider = DummyProvider(num_catalogs=0, events_per_catalog=0)
    browser = CatalogBrowser()

    with qtbot.waitSignal(browser.provider_error, timeout=1000) as blocker:
        provider.error_occurred.emit("boom")
    assert blocker.args[0] == "boom"


def test_future_provider_error_occurred_surfaces(qtbot, qapp):
    """A provider registered *after* the browser exists is wired dynamically,
    mirroring how CatalogTreeModel already wires future providers."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    browser = CatalogBrowser()
    provider = DummyProvider(num_catalogs=0, events_per_catalog=0)

    with qtbot.waitSignal(browser.provider_error, timeout=1000) as blocker:
        provider.error_occurred.emit("boom later")
    assert blocker.args[0] == "boom later"


def _select_first_catalog(browser, provider):
    from PySide6.QtCore import QModelIndex
    model = browser._tree_model
    for row in range(model.rowCount(QModelIndex())):
        prov_idx = model.index(row, 0, QModelIndex())
        node = model.node_from_index(prov_idx)
        if node.provider is provider:
            for crow in range(model.rowCount(prov_idx)):
                cat_idx = model.index(crow, 0, prov_idx)
                cat_node = model.node_from_index(cat_idx)
                if cat_node.catalog is not None:
                    proxy_idx = browser._proxy_model.mapFromSource(cat_idx)
                    browser._catalog_tree.setCurrentIndex(proxy_idx)
                    return
    raise AssertionError("no catalog node found to select")


def test_add_event_failure_reports_instead_of_raising(qtbot, qapp, monkeypatch):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0)
    browser = CatalogBrowser()
    _select_first_catalog(browser, provider)

    def _raise(*a, **k):
        raise RuntimeError("backend down")
    monkeypatch.setattr(provider, "add_event", _raise)

    with qtbot.waitSignal(browser.provider_error, timeout=1000) as blocker:
        browser._on_add_event()
    assert "backend down" in blocker.args[0]


def test_delete_failure_reports_instead_of_raising(qtbot, qapp, monkeypatch):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    provider = DummyProvider(num_catalogs=1, events_per_catalog=1)
    browser = CatalogBrowser()
    _select_first_catalog(browser, provider)
    browser._event_table.selectRow(0)

    def _raise(*a, **k):
        raise RuntimeError("delete refused")
    monkeypatch.setattr(provider, "remove_event", _raise)

    with qtbot.waitSignal(browser.provider_error, timeout=1000) as blocker:
        browser._on_delete()
    assert "delete refused" in blocker.args[0]


def test_destroyed_browser_is_forgotten_by_future_provider_registration(qtbot, qapp):
    """Pattern 1 from docs/qt-lifetime-patterns.md: connect a bound method,
    not a lambda closing over self, so Qt auto-disconnects the receiver on
    destruction instead of leaking it (and later crashing calling into it)."""
    import shiboken6
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    browser = CatalogBrowser()
    shiboken6.delete(browser)
    assert not shiboken6.isValid(browser)

    # Must not raise: a lambda closing over `self` would still be connected
    # to CatalogRegistry.provider_registered and call self.provider_error
    # on the now-destroyed browser here.
    DummyProvider(num_catalogs=0, events_per_catalog=0)


def test_add_event_refresh_failure_reports_instead_of_raising(qtbot, qapp, monkeypatch):
    """add_event() synchronously emits events_changed, which
    _on_events_changed (itself guarded, see the signal-failure test below)
    turns into the one and only refresh read -- _on_add_event no longer
    does its own second, redundant read (2026-09-06 final review: the two
    reads used to run back-to-back for every add/delete, doing the
    expensive model reset twice). A backend that fails on that refresh
    must still report instead of raising."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0)
    browser = CatalogBrowser()
    _select_first_catalog(browser, provider)

    def _raise(*a, **k):
        raise RuntimeError("refresh failed")
    monkeypatch.setattr(provider, "events", _raise)

    with qtbot.waitSignal(browser.provider_error, timeout=1000) as blocker:
        browser._on_add_event()
    assert "refresh failed" in blocker.args[0]


def test_delete_refresh_failure_reports_instead_of_raising(qtbot, qapp, monkeypatch):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    provider = DummyProvider(num_catalogs=1, events_per_catalog=1)
    browser = CatalogBrowser()
    _select_first_catalog(browser, provider)
    browser._event_table.selectRow(0)

    def _raise(*a, **k):
        raise RuntimeError("refresh failed")
    monkeypatch.setattr(provider, "events", _raise)

    with qtbot.waitSignal(browser.provider_error, timeout=1000) as blocker:
        browser._on_delete()
    assert "refresh failed" in blocker.args[0]


def test_add_event_refreshes_the_table_exactly_once(qtbot, qapp, monkeypatch):
    """add_event() already synchronously emits events_changed (provider.py's
    _emit_events_changed), which the connected browser turns into a refresh
    via _on_events_changed -- _on_add_event's own extra explicit read+reset
    right after was a second, redundant one for every single add
    (2026-09-06 final review, found by holistically re-reviewing the whole
    8-step span rather than each commit in isolation)."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0)
    browser = CatalogBrowser()
    _select_first_catalog(browser, provider)

    calls = []
    real = provider.events
    def _counting(*a, **k):
        calls.append(1)
        return real(*a, **k)
    monkeypatch.setattr(provider, "events", _counting)

    browser._on_add_event()

    assert len(calls) == 1, f"expected exactly one refresh read, got {len(calls)}"


def test_delete_refreshes_the_table_exactly_once(qtbot, qapp, monkeypatch):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    browser = CatalogBrowser()
    _select_first_catalog(browser, provider)
    browser._event_table.selectRow(0)

    calls = []
    real = provider.events
    def _counting(*a, **k):
        calls.append(1)
        return real(*a, **k)
    monkeypatch.setattr(provider, "events", _counting)

    browser._on_delete()

    assert len(calls) == 1, f"expected exactly one refresh read, got {len(calls)}"


def test_events_changed_signal_failure_reports_instead_of_raising(qtbot, qapp, monkeypatch):
    """_on_events_changed is a standalone signal slot (fires on async load
    completion or a peer's edit in a shared cocat catalog, not just as a
    side effect of a local browser action) and had no guard at all --
    unlike _on_add_event/_on_delete, which happen to catch synchronously
    because their own provider call is inside a try (2026-09-06 final
    review, found by holistically re-reviewing the whole 8-step span)."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    provider = DummyProvider(num_catalogs=1, events_per_catalog=1)
    browser = CatalogBrowser()
    _select_first_catalog(browser, provider)

    def _raise(*a, **k):
        raise RuntimeError("peer sync failed")
    monkeypatch.setattr(provider, "events", _raise)

    with qtbot.waitSignal(browser.provider_error, timeout=1000) as blocker:
        browser._on_events_changed(browser._current_catalog)
    assert "peer sync failed" in blocker.args[0]


def test_save_failure_reports_instead_of_raising(qtbot, qapp, monkeypatch):
    from PySide6.QtCore import QModelIndex
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0)
    browser = CatalogBrowser()

    def _raise(*a, **k):
        raise RuntimeError("save failed")
    monkeypatch.setattr(provider, "save", _raise)

    model = browser._tree_model
    prov_idx = None
    for row in range(model.rowCount(QModelIndex())):
        idx = model.index(row, 0, QModelIndex())
        if model.node_from_index(idx).provider is provider:
            prov_idx = idx
            break
    assert prov_idx is not None
    proxy_idx = browser._proxy_model.mapFromSource(prov_idx)

    with qtbot.waitSignal(browser.provider_error, timeout=1000) as blocker:
        browser._on_save_clicked(proxy_idx)
    assert "save failed" in blocker.args[0]
