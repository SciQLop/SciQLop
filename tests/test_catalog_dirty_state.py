from .fixtures import *
import pytest
from datetime import datetime, timezone, timedelta
from SciQLop.components.catalogs.backend.provider import Capability


def test_save_capability_exists(qapp):
    assert hasattr(Capability, "SAVE")
    assert hasattr(Capability, "SAVE_CATALOG")


def test_provider_dirty_signal_and_state(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]

    assert not provider.is_dirty()
    assert not provider.is_dirty(cat)

    with qtbot.waitSignal(provider.dirty_changed, timeout=1000) as blocker:
        provider.mark_dirty(cat)

    assert blocker.args[0].uuid == cat.uuid
    assert blocker.args[1] is True
    assert provider.is_dirty()
    assert provider.is_dirty(cat)


def test_add_event_marks_dirty(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    import uuid as _uuid

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0)
    cat = provider.catalogs()[0]

    event = CatalogEvent(
        uuid=str(_uuid.uuid4()),
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 12, tzinfo=timezone.utc),
    )

    with qtbot.waitSignal(provider.dirty_changed, timeout=1000):
        provider.add_event(cat, event)

    assert provider.is_dirty(cat)


def test_remove_event_marks_dirty(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    event = provider.events(cat)[0]

    with qtbot.waitSignal(provider.dirty_changed, timeout=1000):
        provider.remove_event(cat, event)

    assert provider.is_dirty(cat)


def test_event_range_change_marks_dirty(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    event = provider.events(cat)[0]

    with qtbot.waitSignal(provider.dirty_changed, timeout=1000):
        event.start = datetime(2025, 6, 1, tzinfo=timezone.utc)

    assert provider.is_dirty(cat)
