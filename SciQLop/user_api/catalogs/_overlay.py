from __future__ import annotations

from typing import Optional

from SciQLop.components.catalogs.backend.panel_manager import PanelCatalogManager
from SciQLop.components.catalogs.backend.provider import Catalog
from SciQLop.user_api.catalogs._service import CatalogService
from SciQLop.user_api.threading import on_main_thread


class CatalogOverlay:
    """User-facing handle for a catalog overlay attached to a plot panel.

    Holds the catalog path and display options (``override_color``) and
    delegates attach/detach operations to the panel's
    ``PanelCatalogManager``.

    Attributes
    ----------
    catalog_path : str
        Fully-qualified catalog path, e.g. ``"My Catalogs//events"``.
    override_color : str or None
        Optional color override for the overlay spans.
    show_spans : bool
        Whether the catalog's events are drawn. Hidden, the catalog stays
        attached, so the panel's Jump mode still jumps to its events.
    """

    def __init__(
        self,
        catalog_path: str,
        catalog: Catalog,
        panel,
        override_color: Optional[str] = None,
    ):
        self._catalog_path = catalog_path
        self._catalog = catalog
        self._panel = panel
        self._override_color = override_color

    @property
    def catalog_path(self) -> str:
        return self._catalog_path

    @property
    def override_color(self) -> Optional[str]:
        return self._override_color

    @property
    @on_main_thread
    def show_spans(self) -> bool:
        return self._manager_overlay().spans_visible

    @show_spans.setter
    @on_main_thread
    def show_spans(self, visible: bool) -> None:
        self._manager_overlay().spans_visible = visible

    def _manager_overlay(self):
        overlay = self._panel._get_impl_or_raise().catalog_manager.overlay(self._catalog.uuid)
        if overlay is None:
            raise RuntimeError(f"{self._catalog_path} is no longer attached to its panel")
        return overlay

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
    show_spans: bool = True,
) -> CatalogOverlay:
    """Attach a catalog overlay to ``panel``.

    Parameters
    ----------
    panel : PlotPanel
        Target plot panel.
    catalog_path : str
        Fully-qualified catalog path, e.g. ``"My Catalogs//events"``.
    override_color : str, optional
        Display color for the overlay spans.
    show_spans : bool, optional
        ``False`` attaches the catalog without drawing its events: the
        panel's Jump mode still jumps to them.

    Returns
    -------
    CatalogOverlay
        Handle for the attached overlay.

    Raises
    ------
    KeyError
        If the provider or catalog is not found.

    Examples
    --------
    >>> overlay = add_catalog_overlay(panel, "My Catalogs//events", override_color="red")
    """
    provider, catalog = _resolve_catalog(catalog_path)
    impl = panel._get_impl_or_raise()
    manager: PanelCatalogManager = impl.catalog_manager
    manager.add_catalog(catalog, show_spans=show_spans)
    if override_color is not None:
        overlay = manager.overlay(catalog.uuid)
        if overlay is not None:
            overlay.color = override_color
    return CatalogOverlay(
        catalog_path=catalog_path,
        catalog=catalog,
        panel=panel,
        override_color=override_color,
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
