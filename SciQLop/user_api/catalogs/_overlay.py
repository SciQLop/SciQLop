from __future__ import annotations

from typing import Optional

from SciQLop.components.catalogs.backend.panel_manager import PanelCatalogManager
from SciQLop.components.catalogs.backend.provider import Catalog
from SciQLop.user_api.catalogs._service import CatalogService
from SciQLop.user_api.threading import on_main_thread


class CatalogOverlay:
    """User-facing handle for a catalog overlay attached to a plot panel.

    Holds the catalog path and display options (``override_color`` and
    ``label``) and delegates attach/detach operations to the panel's
    ``PanelCatalogManager``.

    Attributes
    ----------
    catalog_path : str
        Fully-qualified catalog path, e.g. ``"My Catalogs//events"``.
    override_color : str or None
        Optional color override for the overlay spans.
    label : str or None
        Optional human-readable label for the overlay.
    """

    def __init__(
        self,
        catalog_path: str,
        catalog: Catalog,
        panel,
        override_color: Optional[str] = None,
        label: Optional[str] = None,
    ):
        self._catalog_path = catalog_path
        self._catalog = catalog
        self._panel = panel
        self._override_color = override_color
        self._label = label

    @property
    def catalog_path(self) -> str:
        return self._catalog_path

    @property
    def override_color(self) -> Optional[str]:
        return self._override_color

    @property
    def label(self) -> Optional[str]:
        return self._label

    @on_main_thread
    def remove(self) -> None:
        """Detach this overlay from its panel."""
        remove_catalog_overlay(self._panel, self)


def _resolve_catalog(path: str):
    """Resolve a catalog path to a ``(provider, catalog)`` pair."""
    service = CatalogService()
    return service._resolve(path)


@on_main_thread
def add_catalog_overlay(
    panel,
    catalog_path: str,
    *,
    override_color: Optional[str] = None,
    label: Optional[str] = None,
) -> CatalogOverlay:
    """Attach a catalog overlay to ``panel``.

    Parameters
    ----------
    panel : PlotPanel
        Target plot panel.
    catalog_path : str
        Fully-qualified catalog path, e.g. ``"My Catalogs//events"``.
    override_color : str, optional
        Reserved display color for the overlay.
    label : str, optional
        Human-readable label for the overlay.

    Returns
    -------
    CatalogOverlay
        Handle for the attached overlay.

    Raises
    ------
    KeyError
        If the provider or catalog is not found.
    """
    provider, catalog = _resolve_catalog(catalog_path)
    impl = panel._get_impl_or_raise()
    manager: PanelCatalogManager = impl.catalog_manager
    manager.add_catalog(catalog)
    return CatalogOverlay(
        catalog_path=catalog_path,
        catalog=catalog,
        panel=panel,
        override_color=override_color,
        label=label,
    )


@on_main_thread
def remove_catalog_overlay(panel, overlay: CatalogOverlay) -> None:
    """Detach ``overlay`` from ``panel``.

    Parameters
    ----------
    panel : PlotPanel
        Panel the overlay is attached to.
    overlay : CatalogOverlay
        Overlay handle returned by :func:`add_catalog_overlay`.
    """
    impl = panel._get_impl_or_raise()
    manager: PanelCatalogManager = impl.catalog_manager
    manager.remove_catalog(overlay._catalog)
