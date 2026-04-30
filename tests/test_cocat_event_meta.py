"""Tests for CocatCatalogProvider event metadata edition (CRDT writes)."""
import pytest

pytest.importorskip("cocat")


@pytest.fixture
def in_memory_cocat_event(qapp):
    """Build a cocat Event in an in-memory DB (no wire transport)."""
    from cocat.db import DB
    from datetime import datetime, timezone
    db = DB()
    cat = db.create_catalogue(name="t_room", author="test")
    ev = db.create_event(
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        author="test",
    )
    cat.add_events([ev])
    return ev


def test_cocat_event_wraps_attributes_into_meta(qapp, in_memory_cocat_event):
    """CocatEvent must mirror cocat attributes into CatalogEvent.meta."""
    from SciQLop.plugins.collaborative_catalogs.cocat_provider import CocatEvent
    in_memory_cocat_event.set_attributes(rating=4, note="hello")
    wrapper = CocatEvent(in_memory_cocat_event)
    assert wrapper.meta.get("rating") == 4
    assert wrapper.meta.get("note") == "hello"


def test_cocat_event_remote_attribute_change_updates_meta(qtbot, qapp, in_memory_cocat_event):
    """When the underlying cocat event's attributes change, wrapper.meta updates and meta_changed fires."""
    from SciQLop.plugins.collaborative_catalogs.cocat_provider import CocatEvent
    wrapper = CocatEvent(in_memory_cocat_event)
    received = []
    wrapper.meta_changed.connect(received.append)

    in_memory_cocat_event.set_attributes(class_="boundary")
    qapp.processEvents()

    assert wrapper.meta.get("class_") == "boundary"
    assert "class_" in received


def test_provider_set_event_meta_writes_to_cocat(qapp, in_memory_cocat_event):
    """provider.set_event_meta must persist via cocat.set_attributes."""
    from SciQLop.plugins.collaborative_catalogs.cocat_provider import CocatCatalogProvider, CocatEvent

    wrapper = CocatEvent(in_memory_cocat_event)
    provider = CocatCatalogProvider()
    # Not joined to a real room; we exercise the override directly with a stub catalog.
    from SciQLop.components.catalogs.backend.provider import Catalog
    cat = Catalog(uuid="fake-uuid", name="t", provider=provider, path=[])

    provider.set_event_meta(cat, wrapper, "rating", 5)
    qapp.processEvents()

    assert wrapper.meta.get("rating") == 5
    assert in_memory_cocat_event.attributes.get("rating") == 5


def test_provider_remove_event_meta_writes_to_cocat(qapp, in_memory_cocat_event):
    from SciQLop.plugins.collaborative_catalogs.cocat_provider import CocatCatalogProvider, CocatEvent
    from SciQLop.components.catalogs.backend.provider import Catalog

    in_memory_cocat_event.set_attributes(note="hello")
    wrapper = CocatEvent(in_memory_cocat_event)
    assert wrapper.meta["note"] == "hello"

    provider = CocatCatalogProvider()
    cat = Catalog(uuid="fake-uuid", name="t", provider=provider, path=[])

    provider.remove_event_meta(cat, wrapper, "note")
    qapp.processEvents()

    assert "note" not in wrapper.meta
    assert "note" not in in_memory_cocat_event.attributes


def test_cocat_event_remote_attribute_remove_updates_meta(qtbot, qapp, in_memory_cocat_event):
    from SciQLop.plugins.collaborative_catalogs.cocat_provider import CocatEvent

    in_memory_cocat_event.set_attributes(tag="x")
    wrapper = CocatEvent(in_memory_cocat_event)
    received = []
    wrapper.meta_changed.connect(received.append)

    in_memory_cocat_event.remove_attributes(["tag"])
    qapp.processEvents()

    assert "tag" not in wrapper.meta
    assert "tag" in received
