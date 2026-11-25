"""Opening a catalogue of 100,000 events and applying a filter's answer stay fast: the table is not
sorted or filtered one Python call per row (Qt's sort proxy called data() about 1.7 million times,
seconds per answer)."""
import time
from datetime import datetime, timedelta, timezone

from .fixtures import *  # noqa: F401,F403
from .helpers import provider_indexes  # noqa: F401

MANY = 100_000
T0 = datetime(2020, 1, 1, tzinfo=timezone.utc)


def _big_catalogue():
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="BigTableProv")
    catalog = provider.catalogs()[0]
    events = [CatalogEvent(uuid=f"e{i}", start=T0 + timedelta(minutes=(i * 7919) % MANY),
                           stop=T0 + timedelta(minutes=(i * 7919) % MANY + 1), meta={"n": i})
              for i in range(MANY)]
    provider._set_events(catalog, events)
    return provider, catalog


def _seconds(action):
    start = time.perf_counter()
    action()
    return time.perf_counter() - start


def _select(browser, catalog):
    model = browser._tree_model
    for prov_idx in provider_indexes(model):
        for row in range(model.rowCount(prov_idx)):
            idx = model.index(row, 0, prov_idx)
            if model.node_from_index(idx).catalog is catalog:
                browser._catalog_tree.setCurrentIndex(browser._proxy_model.mapFromSource(idx))
                return


def test_a_big_catalogue_opens_and_filters_fast(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    provider, catalog = _big_catalogue()
    browser = CatalogBrowser()
    qtbot.addWidget(browser)

    opening = _seconds(lambda: _select(browser, catalog))
    half = {f"e{i}" for i in range(0, MANY, 2)}
    narrowing = _seconds(lambda: browser._event_filter._apply(half))
    widening = _seconds(lambda: browser._event_filter._apply(None))

    print(f"\n100k events: open {opening * 1000:.0f} ms, filter to half {narrowing * 1000:.0f} ms, "
          f"filter off {widening * 1000:.0f} ms")
    assert browser._sort_proxy.rowCount() == MANY
    assert opening < 0.6
    assert narrowing < 0.25 and widening < 0.25
