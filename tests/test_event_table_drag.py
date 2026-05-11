import json
from datetime import datetime, timezone

from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
from SciQLop.components.catalogs.backend.provider import CatalogEvent
from SciQLop.components.catalogs.ui.event_table import EventTableModel
from SciQLop.core.mime.types import EVENT_LIST_MIME_TYPE


def test_event_table_model_emits_event_mime(qapp):
    provider = DummyProvider(num_catalogs=0, events_per_catalog=0, name="DragSrc")
    try:
        cat = provider.create_catalog("c")
        provider.add_event(cat, CatalogEvent(
            uuid="ev-1",
            start=datetime(2020, 1, 1, tzinfo=timezone.utc),
            stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
            meta={},
        ))
        provider.add_event(cat, CatalogEvent(
            uuid="ev-2",
            start=datetime(2020, 1, 2, tzinfo=timezone.utc),
            stop=datetime(2020, 1, 2, 1, tzinfo=timezone.utc),
            meta={},
        ))

        model = EventTableModel()
        model.set_context(provider, cat)
        model.set_events(provider.events(cat))

        idx0 = model.index(0, 0)
        idx1 = model.index(1, 0)
        md = model.mimeData([idx0, idx1])
        assert md is not None
        assert md.hasFormat(EVENT_LIST_MIME_TYPE)
        payload = json.loads(bytes(md.data(EVENT_LIST_MIME_TYPE)).decode())
        assert payload["provider"] == "DragSrc"
        assert payload["catalog_uuid"] == cat.uuid
        assert sorted(payload["event_uuids"]) == ["ev-1", "ev-2"]
    finally:
        from SciQLop.components.catalogs.backend.registry import CatalogRegistry
        registry = CatalogRegistry.instance()
        if provider in registry._providers:
            registry._providers.remove(provider)
