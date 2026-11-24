"""A catalogue's tree icon: its colour swatch, in a shape the provider may choose (a smart
catalogue's funnel), so the colour legend stays while the kind reads without colour."""
from PySide6.QtCore import QModelIndex, QSize, Qt

from .fixtures import *  # noqa: F401,F403
import pytest

pytestmark = pytest.mark.usefixtures("only_this_test_s_catalog_providers")


def _corner_alpha(icon) -> int:
    """Alpha near the top-left corner: outside a dot, inside a funnel's wide top."""
    image = icon.pixmap(QSize(32, 32)).toImage()
    return image.pixelColor(4, 4).alpha()


def test_a_funnel_swatch_fills_where_a_dot_does_not(qapp):
    from SciQLop.components.catalogs.backend.color_palette import catalog_swatch_icon
    assert _corner_alpha(catalog_swatch_icon("u")) == 0
    assert _corner_alpha(catalog_swatch_icon("u", shape="funnel")) > 0


def _find(model, name, parent=QModelIndex()):
    for row in range(model.rowCount(parent)):
        index = model.index(row, 0, parent)
        if model.data(index) == name:
            return index
        found = _find(model, name, index)
        if found is not None:
            return found
    return None


def test_the_tree_shows_the_icon_a_provider_gives_a_catalogue(qapp):
    from SciQLop.components.catalogs.backend.color_palette import catalog_swatch_icon
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel

    given = catalog_swatch_icon("x", shape="funnel")

    class Iconic(DummyProvider):
        def catalog_icon(self, catalog):
            return given

    provider = Iconic(num_catalogs=1, events_per_catalog=0, name="Iconic")
    model = CatalogTreeModel()
    index = _find(model, provider.catalogs()[0].name)
    assert model.data(index, Qt.ItemDataRole.DecorationRole).cacheKey() == given.cacheKey()
