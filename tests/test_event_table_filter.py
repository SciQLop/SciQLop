"""The catalog browser hosts the selected catalogue's event filter: its provider's delegate, else the
plain text filter. The table keeps what the delegate keeps, a line says how many, each catalogue's
filter is remembered for the session, and "Show only these on the plots" passes the kept events to
the catalogue's overlays."""
from datetime import datetime, timezone

import pytest
from PySide6.QtCore import Qt

from .fixtures import *  # noqa: F401,F403
from .helpers import provider_indexes  # noqa: F401


def _ev(uuid, meta, day=1):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    return CatalogEvent(uuid=uuid, start=datetime(2020, 1, day, tzinfo=timezone.utc),
                        stop=datetime(2020, 1, day, 1, tzinfo=timezone.utc), meta=meta)


def _select(browser, catalog):
    model = browser._tree_model
    for prov_idx in provider_indexes(model):
        for row in range(model.rowCount(prov_idx)):
            idx = model.index(row, 0, prov_idx)
            if model.node_from_index(idx).catalog is catalog:
                browser._catalog_tree.setCurrentIndex(browser._proxy_model.mapFromSource(idx))
                return
    raise AssertionError(f"{catalog.name} not in the tree")


@pytest.fixture
def two(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    provider = DummyProvider(num_catalogs=2, events_per_catalog=0, name="EvFilterHost")
    a, b = provider.catalogs()
    for i, cls in enumerate(["solar_wind", "magnetosheath", "cusp"]):
        provider.add_event(a, _ev(f"a{i}", {"class": cls}, day=i + 1))
    provider.add_event(b, _ev("b0", {"class": "cusp"}))
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    return browser, provider, a, b


def _type(qtbot, browser, text):
    with qtbot.waitSignal(browser._event_filter.changed, timeout=2000):
        browser._event_filter.box.setText(text)


def test_the_default_filter_box_filters_the_table(two, qtbot):
    from SciQLop.components.catalogs.ui.event_filter import PlainTextFilter
    browser, provider, a, b = two
    _select(browser, a)
    assert isinstance(browser._event_filter, PlainTextFilter)
    assert browser._event_filter.box.placeholderText() == "Filter events…"
    _type(qtbot, browser, "magneto")
    assert browser._sort_proxy.rowCount() == 1
    assert browser._filter_count.text() == "1 of 3" and browser._filter_count.isVisibleTo(browser)


def test_the_count_line_hides_when_nothing_is_filtered(two, qtbot):
    browser, provider, a, b = two
    _select(browser, a)
    assert not browser._filter_count.isVisibleTo(browser)
    _type(qtbot, browser, "s")
    _type(qtbot, browser, "")
    assert not browser._filter_count.isVisibleTo(browser) and browser._sort_proxy.rowCount() == 3


def test_each_catalogue_keeps_its_filter_for_the_session(two, qtbot):
    browser, provider, a, b = two
    _select(browser, a)
    _type(qtbot, browser, "cusp")
    _select(browser, b)
    assert browser._event_filter.box.text() == ""   # B had none: it is not A's
    assert browser._sort_proxy.rowCount() == 1
    _select(browser, a)
    assert browser._event_filter.box.text() == "cusp"
    qtbot.waitUntil(lambda: browser._sort_proxy.rowCount() == 1, timeout=2000)


def test_events_arriving_later_are_filtered_too(two, qtbot):
    browser, provider, a, b = two
    _select(browser, a)
    _type(qtbot, browser, "cusp")
    provider.add_event(a, _ev("a9", {"class": "cusp too"}, day=9))
    qtbot.waitUntil(lambda: browser._sort_proxy.rowCount() == 2, timeout=2000)


def test_a_provider_s_own_filter_is_hosted_and_the_previous_one_disposed(qtbot, qapp):
    from PySide6.QtWidgets import QLabel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.ui.event_filter import EventFilter, PlainTextFilter
    disposed = []

    class OnlyFirst(EventFilter):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._widget = QLabel("own filter")
            self._kept = None

        def widget(self):
            return self._widget

        def set_events(self, events):
            self._kept = {events[0].uuid} if events else None
            self.changed.emit()

        def accepts(self, event):
            return self._kept is None or event.uuid in self._kept

        def kept(self):
            return self._kept

        def dispose(self):
            disposed.append(self)

    class Own(DummyProvider):
        def event_filter(self, catalog, parent):
            return OnlyFirst(parent)

    own = Own(num_catalogs=1, events_per_catalog=0, name="OwnFilterProv")
    catalog = own.catalogs()[0]
    for i in range(3):
        own.add_event(catalog, _ev(f"o{i}", {"n": i}, day=i + 1))
    plain = DummyProvider(num_catalogs=1, events_per_catalog=2, name="PlainFilterProv")
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    _select(browser, catalog)
    assert isinstance(browser._event_filter, OnlyFirst)
    assert browser._event_filter.widget().isVisibleTo(browser)
    assert browser._sort_proxy.rowCount() == 1
    _select(browser, plain.catalogs()[0])
    assert len(disposed) == 1 and isinstance(browser._event_filter, PlainTextFilter)
    assert browser._sort_proxy.rowCount() == 2


def test_show_only_these_on_the_plots_is_off_by_default(two):
    browser, provider, a, b = two
    _select(browser, a)
    assert browser._filter_plots.text() == "Show only these on the plots"
    assert not browser._filter_plots.isChecked()


def test_show_only_these_on_the_plots_filters_the_catalogue_s_overlays(two, qtbot):
    browser, provider, a, b = two
    shown = {}

    class Overlay:
        def set_event_filter(self, uuids):
            shown["uuids"] = uuids

    class Manager:
        def overlay(self, uuid):
            return Overlay() if uuid == a.uuid else None

    class Panel:
        catalog_manager = Manager()

    browser._panels.append(Panel())
    _select(browser, a)
    _type(qtbot, browser, "cusp")
    assert "uuids" not in shown                    # off: the plots show everything
    browser._filter_plots.setChecked(True)
    assert shown["uuids"] == {"a2"}
    _type(qtbot, browser, "s")
    assert shown["uuids"] == {"a0", "a1", "a2"}
    browser._filter_plots.setChecked(False)
    assert shown["uuids"] is None


def _own_filter_provider(filter_class, name):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    class Own(DummyProvider):
        def event_filter(self, catalog, parent):
            return filter_class(parent)

    return Own(num_catalogs=1, events_per_catalog=0, name=name)


class _Previewing:
    """A delegate that shows other events in the table, as a search's preview does."""

    @staticmethod
    def make():
        from PySide6.QtWidgets import QLineEdit
        from SciQLop.components.catalogs.ui.event_filter import EventFilter

        class Previewing(EventFilter):
            def __init__(self, parent=None):
                super().__init__(parent)
                self._widget = QLineEdit()

            def widget(self):
                return self._widget

            def set_events(self, events):
                pass

            def accepts(self, event):
                return True

            def kept(self):
                return None

        return Previewing


def test_a_delegate_shows_other_events_read_only_until_it_gives_the_table_back(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    own = _own_filter_provider(_Previewing.make(), "PreviewFilterProv")
    catalog = own.catalogs()[0]
    own.add_event(catalog, _ev("mine", {"n": 1}))
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    _select(browser, catalog)
    assert browser._event_model.flags(browser._event_model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
    preview = [_ev("p1", {"n": 2}, day=2), _ev("p2", {"n": 3}, day=3)]
    browser._event_filter.shown_events.emit(preview)
    assert browser._sort_proxy.rowCount() == 2
    assert not browser._event_model.flags(browser._event_model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
    assert not browser._add_event_action.isVisible() and not browser._delete_action.isVisible()
    own.add_event(catalog, _ev("mine too", {"n": 4}, day=4))   # the catalogue changes meanwhile
    assert browser._sort_proxy.rowCount() == 2                   # the preview stays
    browser._event_filter.shown_events.emit(None)
    assert browser._sort_proxy.rowCount() == 2 and {browser._event_model.event_at(r).uuid for r in range(2)} == \
        {"mine", "mine too"}
    assert browser._event_model.flags(browser._event_model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable


def test_a_provider_asks_to_show_a_catalogue_with_its_filter_box_focused(two, qtbot):
    browser, provider, a, b = two
    browser.show()
    qtbot.waitExposed(browser)
    _select(browser, a)
    provider.open_requested.emit(b)
    assert browser._current_catalog is b
    qtbot.waitUntil(lambda: browser.focusWidget() is browser._event_filter.box, timeout=2000)
