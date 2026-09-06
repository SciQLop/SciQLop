from __future__ import annotations

from dataclasses import dataclass

from SciQLop.components.command_palette.backend.registry import CommandArg, Completion


def _palette_product_path(raw: str) -> str:
    """Normalize a flat-model mime path for use as a palette completion value.

    Strips the ``root//`` prefix but keeps ``//`` separators so
    ``to_product_path`` can split unambiguously even when a product's display
    name contains ``/`` (AMDA's ``"final / prelim"`` is the historical reason
    the snippet generator stopped using single-slash too — see
    ``snippet-templates-system`` memory).
    """
    if raw.startswith("root//"):
        raw = raw[len("root//"):]
    return raw


@dataclass
class PanelArg(CommandArg):
    name: str = "panel"

    def completions(self, context: dict) -> list[Completion]:
        from SciQLop.core.sciqlop_application import sciqlop_app
        win = sciqlop_app().main_window
        panels = win.plot_panels()
        items = [Completion(value="__new__", display="New panel")]
        items += [Completion(value=name, display=name) for name in panels]
        return items


def _node_stable_id(products_model, path: str) -> str | None:
    from SciQLop.user_api.plot._plots import to_product_path
    node = products_model.node(to_product_path(path))
    if node is None:
        return None
    stable_id = node.metadata("stable_id")
    if stable_id:
        return str(stable_id)
    return None


@dataclass
class ProductArg(CommandArg):
    name: str = "product"

    def __post_init__(self):
        self._flat_model = None

    def _ensure_flat_model(self):
        if self._flat_model is None:
            from SciQLopPlots import ProductsModel, ProductsFlatFilterModel
            self._flat_model = ProductsFlatFilterModel(ProductsModel.instance())
        return self._flat_model

    def completions(self, context: dict) -> list[Completion]:
        return self.filtered_completions("", context, 50) or []

    def filtered_completions(self, query: str, context: dict, max_results: int) -> list[Completion]:
        from SciQLopPlots import QueryParser, ProductsModel
        from PySide6.QtWidgets import QApplication

        flat = self._ensure_flat_model()
        flat.set_query(QueryParser.parse(query))

        app = QApplication.instance()
        if app:
            prev_count = -1
            stable_rounds = 0
            for _ in range(500):
                app.processEvents()
                cur = flat.rowCount()
                if cur == prev_count:
                    stable_rounds += 1
                    if stable_rounds >= 3:
                        break
                else:
                    stable_rounds = 0
                    prev_count = cur

        items = []
        count = min(flat.rowCount(), max_results)
        if count > 0:
            indexes = [flat.index(i, 0) for i in range(count)]
            mime = flat.mimeData(indexes)
            if mime and mime.text():
                for path_text in mime.text().strip().split("\n"):
                    product_path = _palette_product_path(path_text)
                    description = _node_stable_id(ProductsModel, product_path)
                    items.append(Completion(value=product_path, display=product_path, description=description))
        return items


def catalog_arg_value(provider_name: str, catalog_uuid: str) -> str:
    """Value format shared with resolve_catalog_arg -- provider name and
    catalog uuid, not a display path: catalog names aren't unique across
    folders, and the tree's DisplayRole decorates dirty catalogs with a
    trailing ' *', neither of which round-trips safely as an identifier."""
    return f"{provider_name}::{catalog_uuid}"


def resolve_catalog_arg(value: str):
    """Resolve a CatalogArg completion value back to a Catalog, or None."""
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    provider_name, _, uuid = value.partition("::")
    if not uuid:
        return None
    provider = CatalogRegistry.instance().provider_by_name(provider_name)
    if provider is None:
        return None
    for catalog in provider.catalogs():
        if catalog.uuid == uuid:
            return catalog
    return None


@dataclass
class CatalogArg(CommandArg):
    name: str = "catalog"

    def completions(self, context: dict) -> list[Completion]:
        from SciQLop.components.catalogs.backend.registry import CatalogRegistry
        items = []
        for provider in CatalogRegistry.instance().providers():
            for catalog in provider.catalogs():
                path = "/".join([provider.name, *catalog.path, catalog.name])
                items.append(Completion(
                    value=catalog_arg_value(provider.name, catalog.uuid),
                    display=path,
                ))
        return items


@dataclass
class ProviderArg(CommandArg):
    name: str = "provider"

    def completions(self, context: dict) -> list[Completion]:
        from SciQLop.components.catalogs.backend.registry import CatalogRegistry
        from SciQLop.components.catalogs.backend.provider import Capability
        items = []
        for provider in CatalogRegistry.instance().providers():
            if Capability.CREATE_CATALOGS in provider.capabilities():
                items.append(Completion(value=provider.name, display=provider.name))
        return items


@dataclass
class WorkspaceArg(CommandArg):
    name: str = "workspace"

    def completions(self, context: dict) -> list[Completion]:
        from SciQLop.components.workspaces.backend.workspaces_manager import list_existing_workspaces
        return [
            Completion(value=ws.name, display=ws.name)
            for ws in list_existing_workspaces()
        ]


@dataclass
class DockWidgetArg(CommandArg):
    name: str = "dock_widget"

    def completions(self, context: dict) -> list[Completion]:
        from SciQLop.core.sciqlop_application import sciqlop_app
        win = sciqlop_app().main_window
        return [
            Completion(value=dw.windowTitle(), display=dw.windowTitle())
            for dw in win.dock_manager.dockWidgets()
        ]


@dataclass
class TimeRangeArg(CommandArg):
    name: str = "time_range"

    def completions(self, context: dict) -> list[Completion]:
        return [
            Completion(value="1h", display="Last hour"),
            Completion(value="1d", display="Last day"),
            Completion(value="1w", display="Last week"),
            Completion(value="1M", display="Last month"),
        ]
