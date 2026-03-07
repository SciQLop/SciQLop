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


def test_save_clears_dirty(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=2, events_per_catalog=3)
    cats = provider.catalogs()
    event0 = provider.events(cats[0])[0]
    event1 = provider.events(cats[1])[0]

    event0.start = datetime(2025, 6, 1, tzinfo=timezone.utc)
    event1.start = datetime(2025, 6, 1, tzinfo=timezone.utc)

    assert provider.is_dirty(cats[0])
    assert provider.is_dirty(cats[1])

    signals = []
    provider.dirty_changed.connect(lambda cat, dirty: signals.append((cat.uuid, dirty)))

    provider.save()

    assert not provider.is_dirty(cats[0])
    assert not provider.is_dirty(cats[1])
    assert not provider.is_dirty()
    # Should have emitted dirty_changed(cat, False) for each dirty catalog
    false_signals = [(uuid, d) for uuid, d in signals if not d]
    assert len(false_signals) == 2


def test_tree_shows_dirty_indicator(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = CatalogTreeModel()

    # Find the catalog node
    provider_idx = model.index(model.rowCount() - 1, 0)  # last provider added
    cat_idx = model.index(0, 0, provider_idx)

    # Before marking dirty
    name_before = model.data(cat_idx, Qt.ItemDataRole.DisplayRole)
    assert not name_before.endswith(" *")

    # Mark dirty
    provider.mark_dirty(cat)

    name_after = model.data(cat_idx, Qt.ItemDataRole.DisplayRole)
    assert name_after.endswith(" *")

    # Provider node should also show dirty
    provider_name = model.data(provider_idx, Qt.ItemDataRole.DisplayRole)
    assert provider_name.endswith(" *")


def test_tree_clears_dirty_on_save(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = CatalogTreeModel()

    provider_idx = model.index(model.rowCount() - 1, 0)
    cat_idx = model.index(0, 0, provider_idx)

    provider.mark_dirty(cat)
    provider.save()

    name_after_save = model.data(cat_idx, Qt.ItemDataRole.DisplayRole)
    assert not name_after_save.endswith(" *")

    provider_name = model.data(provider_idx, Qt.ItemDataRole.DisplayRole)
    assert not provider_name.endswith(" *")
