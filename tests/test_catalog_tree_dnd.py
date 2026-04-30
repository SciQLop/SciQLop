"""Drag & drop within the catalog tree: cross-provider import (copy) and
same-provider reorganization (move)."""
from .fixtures import *
from datetime import datetime, timezone
import uuid as _uuid


def _read_only_provider(num_catalogs=1, events_per_catalog=2):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import Capability

    class _ReadOnly(DummyProvider):
        def __init__(self, **kw):
            super().__init__(**kw)
            self._name = "ReadOnly"

        def capabilities(self, catalog=None):
            return set()  # nothing

    return _ReadOnly(num_catalogs=num_catalogs, events_per_catalog=events_per_catalog)


def _rw_provider(name="RW", num_catalogs=0, events_per_catalog=0):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    p = DummyProvider(num_catalogs=num_catalogs, events_per_catalog=events_per_catalog)
    p._name = name
    return p


def _drop_index_for_catalog(model, catalog):
    """Find the QModelIndex of catalog's parent (provider/folder)."""
    from PySide6.QtCore import QModelIndex
    for row in range(model.rowCount(QModelIndex())):
        prov_idx = model.index(row, 0, QModelIndex())
        node = model.node_from_index(prov_idx)
        if node.provider is catalog.provider:
            return prov_idx
    return None


def test_cross_provider_drop_copies_catalog_with_events(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import Capability
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.core.mime import encode_mime
    from PySide6.QtCore import QModelIndex, Qt

    src = _read_only_provider(num_catalogs=1, events_per_catalog=3)
    dst = _rw_provider(name="DestRW")

    src_cat = src.catalogs()[0]
    src_events = src.events(src_cat)

    model = CatalogTreeModel()
    # Drop on the destination provider node
    dst_idx = None
    for row in range(model.rowCount(QModelIndex())):
        idx = model.index(row, 0, QModelIndex())
        if model.node_from_index(idx).provider is dst:
            dst_idx = idx
            break
    assert dst_idx is not None

    mime = encode_mime([src_cat])
    accepted = model.dropMimeData(mime, Qt.DropAction.CopyAction, -1, -1, dst_idx)
    # We return False to suppress Qt auto-removeRows; the actual work succeeded
    # so the dest should now have the catalog.
    assert accepted is False

    new_cats = dst.catalogs()
    assert len(new_cats) == 1
    new_cat = new_cats[0]
    assert new_cat.name == src_cat.name
    assert new_cat.uuid != src_cat.uuid  # copy, new uuid

    new_events = dst.events(new_cat)
    assert len(new_events) == len(src_events)
    assert {e.start for e in new_events} == {e.start for e in src_events}

    # Source untouched
    assert src.catalogs()[0].uuid == src_cat.uuid
    assert len(src.events(src_cat)) == 3


def test_cross_provider_drop_resolves_name_collision(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.core.mime import encode_mime
    from PySide6.QtCore import QModelIndex, Qt

    src = _rw_provider(name="Src", num_catalogs=1, events_per_catalog=1)
    dst = _rw_provider(name="Dst")

    # Pre-create a catalog with the same name at the destination
    src_cat = src.catalogs()[0]
    dst.create_catalog(src_cat.name)

    model = CatalogTreeModel()
    dst_idx = None
    for row in range(model.rowCount(QModelIndex())):
        idx = model.index(row, 0, QModelIndex())
        if model.node_from_index(idx).provider is dst:
            dst_idx = idx
            break

    mime = encode_mime([src_cat])
    model.dropMimeData(mime, Qt.DropAction.CopyAction, -1, -1, dst_idx)

    names = sorted(c.name for c in dst.catalogs())
    assert names == [src_cat.name, f"{src_cat.name} (2)"]


def test_same_provider_drop_moves_catalog_into_folder(qtbot, qapp):
    """Drop within the same provider relocates the catalog (same uuid)."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.core.mime import encode_mime
    from PySide6.QtCore import QModelIndex, Qt

    p = _rw_provider(name="Solo")
    cat = p.create_catalog("A")
    p.create_catalog("placeholder", path=["folder_a"])  # forces folder_a to exist

    original_uuid = cat.uuid

    model = CatalogTreeModel()
    # Find the folder_a node under p
    prov_idx = None
    for row in range(model.rowCount(QModelIndex())):
        idx = model.index(row, 0, QModelIndex())
        if model.node_from_index(idx).provider is p:
            prov_idx = idx
            break
    folder_idx = None
    for row in range(model.rowCount(prov_idx)):
        child = model.index(row, 0, prov_idx)
        n = model.node_from_index(child)
        if n.catalog is None and not n.is_placeholder and n.name == "folder_a":
            folder_idx = child
            break
    assert folder_idx is not None

    mime = encode_mime([cat])
    model.dropMimeData(mime, Qt.DropAction.MoveAction, -1, -1, folder_idx)

    # Same uuid, new path
    moved = next(c for c in p.catalogs() if c.uuid == original_uuid)
    assert moved.path == ["folder_a"]


def test_drop_on_read_only_provider_is_rejected(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.core.mime import encode_mime
    from PySide6.QtCore import QModelIndex, Qt

    src = _rw_provider(name="Src", num_catalogs=1, events_per_catalog=1)
    ro = _read_only_provider(num_catalogs=0)

    src_cat = src.catalogs()[0]
    model = CatalogTreeModel()
    ro_idx = None
    for row in range(model.rowCount(QModelIndex())):
        idx = model.index(row, 0, QModelIndex())
        if model.node_from_index(idx).provider is ro:
            ro_idx = idx
            break
    assert ro_idx is not None

    mime = encode_mime([src_cat])
    assert not model.canDropMimeData(mime, Qt.DropAction.CopyAction, -1, -1, ro_idx)
    # Provider node has no Drop flag
    assert not bool(model.flags(ro_idx) & Qt.ItemFlag.ItemIsDropEnabled)
    # Source provider's catalog count unchanged
    assert ro.catalogs() == []


def test_drop_on_catalog_routes_to_parent_folder(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.core.mime import encode_mime
    from PySide6.QtCore import QModelIndex, Qt

    src = _rw_provider(name="Src", num_catalogs=1, events_per_catalog=1)
    dst = _rw_provider(name="Dst")
    dst_existing = dst.create_catalog("Existing", path=["folder"])

    src_cat = src.catalogs()[0]
    model = CatalogTreeModel()

    # Find dst_existing's index
    dst_idx = None
    for row in range(model.rowCount(QModelIndex())):
        idx = model.index(row, 0, QModelIndex())
        if model.node_from_index(idx).provider is dst:
            dst_idx = idx
            break
    folder_idx = None
    for row in range(model.rowCount(dst_idx)):
        child = model.index(row, 0, dst_idx)
        n = model.node_from_index(child)
        if not n.is_placeholder and n.catalog is None and n.name == "folder":
            folder_idx = child
            break
    cat_idx = model.index(0, 0, folder_idx)

    mime = encode_mime([src_cat])
    model.dropMimeData(mime, Qt.DropAction.CopyAction, -1, -1, cat_idx)

    # New catalog landed in same folder as the catalog we dropped on
    cats_in_folder = [c for c in dst.catalogs() if c.path == ["folder"]]
    assert len(cats_in_folder) == 2
    assert {c.name for c in cats_in_folder} == {"Existing", src_cat.name}
