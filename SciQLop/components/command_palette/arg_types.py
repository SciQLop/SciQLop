from __future__ import annotations

from dataclasses import dataclass

from SciQLop.components.command_palette.backend.registry import CommandArg, Completion


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
        from SciQLopPlots import QueryParser
        from PySide6.QtWidgets import QApplication

        flat = self._ensure_flat_model()
        flat.set_query(QueryParser.parse(query))

        app = QApplication.instance()
        if app:
            app.processEvents()

        items = []
        count = min(flat.rowCount(), max_results)
        if count > 0:
            indexes = [flat.index(i, 0) for i in range(count)]
            mime = flat.mimeData(indexes)
            paths = mime.text().strip().split("\n") if mime else []
            for i, idx in enumerate(indexes):
                display_name = flat.data(idx)
                path = paths[i] if i < len(paths) else display_name
                items.append(Completion(value=path, display=path))
        return items


@dataclass
class CatalogArg(CommandArg):
    name: str = "catalog"

    def completions(self, context: dict) -> list[Completion]:
        from SciQLop.core.sciqlop_application import sciqlop_app
        win = sciqlop_app().main_window
        browser = win.catalogs_browser
        model = browser._tree_model
        items = []
        for i in range(model.rowCount()):
            _collect_tree_items(model, model.index(i, 0), items, "")
        return items


def _collect_tree_items(model, parent_index, items, prefix):
    text = model.data(parent_index)
    path = f"{prefix}/{text}" if prefix else text
    if model.rowCount(parent_index) == 0:
        items.append(Completion(value=path, display=path))
    else:
        for row in range(model.rowCount(parent_index)):
            _collect_tree_items(model, model.index(row, 0, parent_index), items, path)


@dataclass
class ProviderArg(CommandArg):
    name: str = "provider"

    def completions(self, context: dict) -> list[Completion]:
        from SciQLop.components.catalogs.backend.registry import CatalogRegistry
        from SciQLop.components.catalogs.backend.catalog_provider import CatalogProviderCapabilities
        items = []
        for provider in CatalogRegistry.instance().providers():
            if CatalogProviderCapabilities.CREATE_CATALOGS in provider.capabilities:
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
