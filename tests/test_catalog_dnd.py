from .fixtures import *
from datetime import datetime, timezone, timedelta


def _make_panel():
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange
    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())
    return panel


def test_encode_decode_catalog_list_round_trip(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.mime import encode_mime, decode_mime
    from SciQLop.core.mime.types import CATALOG_LIST_MIME_TYPE

    provider = DummyProvider(num_catalogs=2, events_per_catalog=1)
    cats = provider.catalogs()

    mime = encode_mime(cats)
    assert mime is not None
    assert mime.hasFormat(CATALOG_LIST_MIME_TYPE)

    decoded = decode_mime(mime)
    assert [c.uuid for c in decoded] == [c.uuid for c in cats]


def test_decode_skips_unknown_catalogs(qtbot, qapp):
    """Decoder must drop entries that no longer exist in the registry."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.mime import encode_mime, decode_mime

    provider = DummyProvider(num_catalogs=1, events_per_catalog=1)
    cat = provider.catalogs()[0]
    mime = encode_mime([cat])

    provider.remove_catalog(cat)

    decoded = decode_mime(mime)
    assert decoded == []


def test_drop_catalog_on_panel_adds_overlay(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.mime import encode_mime

    panel = _make_panel()
    provider = DummyProvider(num_catalogs=1, events_per_catalog=2)
    cat = provider.catalogs()[0]

    mime = encode_mime([cat])
    panel._catalog_plot_callback.call(None, mime)
    assert cat.uuid in panel.catalog_manager.catalog_uuids


def test_drop_multiple_catalogs_on_panel(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.mime import encode_mime

    panel = _make_panel()
    provider = DummyProvider(num_catalogs=3, events_per_catalog=1)
    cats = provider.catalogs()

    mime = encode_mime(cats)
    panel._catalog_plot_callback.call(None, mime)
    for cat in cats:
        assert cat.uuid in panel.catalog_manager.catalog_uuids


def test_tree_model_exposes_drag_for_catalog_nodes(qtbot, qapp):
    from PySide6.QtCore import Qt, QModelIndex
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.core.mime.types import CATALOG_LIST_MIME_TYPE

    provider = DummyProvider(num_catalogs=1, events_per_catalog=1)
    model = CatalogTreeModel()
    assert CATALOG_LIST_MIME_TYPE in model.mimeTypes()

    provider_idx = None
    for row in range(model.rowCount(QModelIndex())):
        idx = model.index(row, 0, QModelIndex())
        node = model.node_from_index(idx)
        if node.provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    catalog_idx = None
    for row in range(model.rowCount(provider_idx)):
        idx = model.index(row, 0, provider_idx)
        node = model.node_from_index(idx)
        if node.catalog is not None:
            catalog_idx = idx
            break
    assert catalog_idx is not None
    assert bool(model.flags(catalog_idx) & Qt.ItemFlag.ItemIsDragEnabled)
    assert not bool(model.flags(provider_idx) & Qt.ItemFlag.ItemIsDragEnabled)

    mime = model.mimeData([catalog_idx])
    assert mime is not None
    assert mime.hasFormat(CATALOG_LIST_MIME_TYPE)
