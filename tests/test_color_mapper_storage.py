from .fixtures import *
from datetime import datetime, timezone


def test_get_default_returns_uniform_mapper(qapp, tmp_path, monkeypatch):
    """When no mapping is stored, get_color_mapper returns a default (column=None) mapper."""
    monkeypatch.setattr(
        "SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR",
        str(tmp_path),
    )
    from SciQLop.components.catalogs.backend.color_mapper_storage import get_color_mapper
    from SciQLop.components.catalogs.backend.provider import Catalog
    cat = Catalog(uuid="test-uuid-1", name="test", provider=None)
    mapper = get_color_mapper(cat)
    assert mapper.column is None


def test_set_and_get_roundtrip_readonly(qapp, tmp_path, monkeypatch):
    """For catalogs with no writable provider, storage falls back to local settings."""
    monkeypatch.setattr(
        "SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR",
        str(tmp_path),
    )
    from SciQLop.components.catalogs.backend.color_mapper_storage import (
        get_color_mapper, set_color_mapper,
    )
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    from SciQLop.components.catalogs.backend.provider import Catalog
    cat = Catalog(uuid="test-uuid-2", name="test", provider=None)
    mapper = ColorMapper(column="class", colormap="plasma")
    set_color_mapper(cat, mapper)
    loaded = get_color_mapper(cat)
    assert loaded.column == "class"
    assert loaded.colormap == "plasma"


def test_set_uniform_removes_stored_mapping(qapp, tmp_path, monkeypatch):
    """Setting column=None removes the stored mapping entry."""
    monkeypatch.setattr(
        "SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR",
        str(tmp_path),
    )
    from SciQLop.components.catalogs.backend.color_mapper_storage import (
        get_color_mapper, set_color_mapper, CatalogColorMappings,
    )
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    from SciQLop.components.catalogs.backend.provider import Catalog
    cat = Catalog(uuid="test-uuid-3", name="test", provider=None)
    set_color_mapper(cat, ColorMapper(column="class"))
    set_color_mapper(cat, ColorMapper())  # reset to uniform
    loaded = get_color_mapper(cat)
    assert loaded.column is None
    with CatalogColorMappings() as s:
        assert cat.uuid not in s.mappings
