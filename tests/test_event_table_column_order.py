"""The table's meta columns follow the catalogue's own column order when it has one (a VOTable's
FIELD order: IVOA VOTable 1.5 §2), then any other key, sorted; without one, all sorted."""
from .fixtures import *  # noqa: F401,F403
from datetime import datetime, timedelta, timezone

from PySide6.QtCore import Qt

from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
from SciQLop.components.catalogs.backend.provider import CatalogEvent
from SciQLop.components.catalogs.ui.event_table import EventTableModel

T0 = datetime(2020, 1, 1, tzinfo=timezone.utc)
COLUMNS = [f"Col {i}" for i in range(1, 13)]


class _Ordered(DummyProvider):
    def __init__(self, columns):
        self._columns = columns
        super().__init__(num_catalogs=1, events_per_catalog=0)
        meta = {**{c: f"v{i}" for i, c in enumerate(COLUMNS)}, "zeta": 1, "alpha": 2}
        self._set_events(self.catalogs()[0], [CatalogEvent(uuid="e0", start=T0, stop=T0 + timedelta(hours=1),
                                                           meta=meta)])

    def columns(self, catalog):
        return self._columns


def _headers(model):
    return [model.headerData(c, Qt.Orientation.Horizontal) for c in range(model.columnCount())]


def _model(provider):
    catalog = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, catalog)
    model.set_events(provider.events(catalog))
    return model


def test_the_catalogue_column_order_comes_first_then_other_keys_sorted(qapp):
    model = _model(_Ordered(["Start Time", *COLUMNS]))
    assert _headers(model) == ["Start (UTC)", "Stop (UTC)", *COLUMNS, "alpha", "zeta"]


def test_without_a_column_order_the_keys_are_sorted(qapp):
    model = _model(_Ordered([]))
    assert _headers(model)[2:] == sorted([*COLUMNS, "alpha", "zeta"])


def test_the_base_provider_has_no_column_order(qapp):
    provider = DummyProvider(num_catalogs=1, events_per_catalog=1)
    assert provider.columns(provider.catalogs()[0]) == []


def test_a_new_key_goes_among_the_other_keys(qapp):
    provider = _Ordered(COLUMNS)
    model = _model(provider)
    catalog = provider.catalogs()[0]
    provider.set_event_meta(catalog, provider.events(catalog)[0], "beta", 3)
    assert _headers(model)[2:] == [*COLUMNS, "alpha", "beta", "zeta"]
