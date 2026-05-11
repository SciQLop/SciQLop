# tests/test_event_dnd.py
from datetime import datetime, timezone
import pytest

from SciQLop.components.catalogs.backend.provider import (
    Capability, CatalogEvent,
)
from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider


def _ev(uuid="u1"):
    return CatalogEvent(
        uuid=uuid,
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={},
    )


@pytest.fixture
def provider(qapp):
    p = DummyProvider(num_catalogs=0, events_per_catalog=0)
    yield p
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    providers = CatalogRegistry.instance()._providers
    if p in providers:
        providers.remove(p)


def test_handle_event_drop_link_keeps_event_in_source(qapp, provider):
    src = provider.create_catalog("src")
    dst = provider.create_catalog("dst")
    e = _ev("u-link")
    provider.add_event(src, e)

    provider.handle_event_drop(target_catalog=dst, events=[e], action="link", source_catalog=src)

    assert any(x.uuid == "u-link" for x in provider.events(src))
    assert any(x.uuid == "u-link" for x in provider.events(dst))


def test_handle_event_drop_move_removes_from_source(qapp, provider):
    src = provider.create_catalog("src")
    dst = provider.create_catalog("dst")
    e = _ev("u-move")
    provider.add_event(src, e)

    provider.handle_event_drop(target_catalog=dst, events=[e], action="move", source_catalog=src)

    assert not any(x.uuid == "u-move" for x in provider.events(src))
    assert any(x.uuid == "u-move" for x in provider.events(dst))


def test_handle_event_drop_duplicate_assigns_new_uuid(qapp, provider):
    src = provider.create_catalog("src")
    dst = provider.create_catalog("dst")
    e = _ev("u-dup")
    provider.add_event(src, e)

    provider.handle_event_drop(target_catalog=dst, events=[e], action="duplicate", source_catalog=src)

    src_uuids = {x.uuid for x in provider.events(src)}
    dst_uuids = {x.uuid for x in provider.events(dst)}
    assert "u-dup" in src_uuids
    assert "u-dup" not in dst_uuids
    assert len(dst_uuids) == 1


def test_cross_provider_drop_always_duplicates(qapp, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from SciQLop.components.catalogs.backend.event_mime import encode_event_list
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel

    a = DummyProvider(num_catalogs=0, events_per_catalog=0, name="A")
    b = DummyProvider(num_catalogs=0, events_per_catalog=0, name="B")
    try:
        cat_a = a.create_catalog("a-cat")
        cat_b = b.create_catalog("b-cat")
        e = _ev("cross")
        a.add_event(cat_a, e)

        model = CatalogTreeModel()
        b_idx = _find_catalog_index(model, b, cat_b)
        assert b_idx.isValid()

        md = encode_event_list("A", cat_a.uuid, [e])
        monkeypatch.setattr(QApplication, "keyboardModifiers", _StubModifiers())
        model.dropMimeData(md, Qt.DropAction.MoveAction, -1, -1, b_idx)

        b_events = b.events(cat_b)
        assert len(b_events) == 1
        assert b_events[0].uuid != "cross"  # duplicated, new UUID
        assert any(x.uuid == "cross" for x in a.events(cat_a))  # source untouched
    finally:
        registry = CatalogRegistry.instance()
        for p in (a, b):
            if p in registry._providers:
                registry._providers.remove(p)


class _StubModifiers:
    def __init__(self, shift=False, ctrl=False):
        from PySide6.QtCore import Qt
        m = Qt.KeyboardModifier.NoModifier
        if shift:
            m |= Qt.KeyboardModifier.ShiftModifier
        if ctrl:
            m |= Qt.KeyboardModifier.ControlModifier
        self._m = m

    def __call__(self):
        return self._m


def _find_catalog_index(model, provider, catalog):
    from PySide6.QtCore import QModelIndex
    for row in range(model.rowCount()):
        prov_idx = model.index(row, 0)
        if prov_idx.internalPointer().provider is provider:
            for r in range(model.rowCount(prov_idx)):
                cidx = model.index(r, 0, prov_idx)
                if cidx.internalPointer().catalog is catalog:
                    return cidx
    return QModelIndex()


@pytest.fixture
def tree_with_two_catalogs(qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel

    p = DummyProvider(num_catalogs=0, events_per_catalog=0, name="DropTest")
    src = p.create_catalog("src")
    dst = p.create_catalog("dst")
    e = _ev("u-dispatcher")
    p.add_event(src, e)

    model = CatalogTreeModel()
    yield model, p, src, dst, e

    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    registry = CatalogRegistry.instance()
    if p in registry._providers:
        registry._providers.remove(p)


def test_dropmime_dispatch_link_default(tree_with_two_catalogs, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from SciQLop.components.catalogs.backend.event_mime import encode_event_list

    model, provider, src, dst, ev = tree_with_two_catalogs
    md = encode_event_list(provider.name, src.uuid, [ev])

    target_idx = _find_catalog_index(model, provider, dst)
    assert target_idx.isValid()

    monkeypatch.setattr(QApplication, "keyboardModifiers", _StubModifiers())
    handled = model.dropMimeData(md, Qt.DropAction.MoveAction, -1, -1, target_idx)
    assert handled is False
    assert any(x.uuid == "u-dispatcher" for x in provider.events(src))
    assert any(x.uuid == "u-dispatcher" for x in provider.events(dst))


def test_dropmime_dispatch_move_with_shift(tree_with_two_catalogs, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from SciQLop.components.catalogs.backend.event_mime import encode_event_list

    model, provider, src, dst, ev = tree_with_two_catalogs
    md = encode_event_list(provider.name, src.uuid, [ev])

    target_idx = _find_catalog_index(model, provider, dst)
    assert target_idx.isValid()

    monkeypatch.setattr(QApplication, "keyboardModifiers", _StubModifiers(shift=True))
    model.dropMimeData(md, Qt.DropAction.MoveAction, -1, -1, target_idx)
    assert not any(x.uuid == "u-dispatcher" for x in provider.events(src))
    assert any(x.uuid == "u-dispatcher" for x in provider.events(dst))


def test_dropmime_dispatch_duplicate_with_ctrl(tree_with_two_catalogs, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from SciQLop.components.catalogs.backend.event_mime import encode_event_list

    model, provider, src, dst, ev = tree_with_two_catalogs
    md = encode_event_list(provider.name, src.uuid, [ev])

    target_idx = _find_catalog_index(model, provider, dst)
    assert target_idx.isValid()

    monkeypatch.setattr(QApplication, "keyboardModifiers", _StubModifiers(ctrl=True))
    model.dropMimeData(md, Qt.DropAction.MoveAction, -1, -1, target_idx)
    src_uuids = {x.uuid for x in provider.events(src)}
    dst_uuids = {x.uuid for x in provider.events(dst)}
    assert "u-dispatcher" in src_uuids
    assert "u-dispatcher" not in dst_uuids
    assert len(dst_uuids) == 1


def test_handle_event_drop_link_is_idempotent(qapp, provider):
    """Linking an event already present in the target catalog is a no-op."""
    src = provider.create_catalog("src")
    dst = provider.create_catalog("dst")
    e = _ev("u-link-twice")
    provider.add_event(src, e)
    provider.add_event(dst, e)  # already linked

    provider.handle_event_drop(target_catalog=dst, events=[e], action="link", source_catalog=src)

    dst_events = [x for x in provider.events(dst) if x.uuid == "u-link-twice"]
    assert len(dst_events) == 1, f"link must dedupe, got {len(dst_events)} copies"
