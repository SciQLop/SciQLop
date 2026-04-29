from .backend.provider import CatalogEvent, Catalog, CatalogProvider, Capability, ProviderAction
from .backend.registry import CatalogRegistry
from .backend.overlay import CatalogOverlay
from .backend.panel_manager import PanelCatalogManager, InteractionMode
from .backend.color_palette import color_for_catalog
from .backend import catalog_mime  # noqa: F401  registers the MIME encoder/decoder

__all__ = [
    "CatalogEvent",
    "Catalog",
    "CatalogProvider",
    "Capability",
    "ProviderAction",
    "CatalogRegistry",
    "CatalogOverlay",
    "PanelCatalogManager",
    "InteractionMode",
    "color_for_catalog",
]
