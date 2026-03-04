from .fixtures import *
import pytest


def test_color_for_uuid_returns_qcolor(qapp):
    from SciQLop.components.catalogs.backend.color_palette import color_for_catalog
    color = color_for_catalog("test-uuid-1234")
    from PySide6.QtGui import QColor
    assert isinstance(color, QColor)
    assert color.alpha() > 0


def test_color_is_consistent(qapp):
    from SciQLop.components.catalogs.backend.color_palette import color_for_catalog
    c1 = color_for_catalog("uuid-abc")
    c2 = color_for_catalog("uuid-abc")
    assert c1 == c2


def test_different_uuids_can_differ(qapp):
    from SciQLop.components.catalogs.backend.color_palette import color_for_catalog
    colors = {color_for_catalog(f"uuid-{i}").name() for i in range(12)}
    # at least several distinct colors from 12 different UUIDs
    assert len(colors) >= 6
