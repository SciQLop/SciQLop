from __future__ import annotations
from PySide6.QtCore import QObject, Signal

from .provider import Catalog, CatalogProvider


class CatalogRegistry(QObject):
    """Singleton registry that tracks all CatalogProvider instances."""

    provider_registered = Signal(object)
    provider_unregistered = Signal(object)

    _instance: CatalogRegistry | None = None

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._providers: list[CatalogProvider] = []

    @classmethod
    def instance(cls) -> CatalogRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, provider: CatalogProvider) -> None:
        if provider not in self._providers:
            self._providers.append(provider)
            provider.destroyed.connect(lambda _, p=provider: self._on_destroyed(p))
            self.provider_registered.emit(provider)

    def unregister(self, provider: CatalogProvider) -> None:
        if provider in self._providers:
            self._providers.remove(provider)
            self.provider_unregistered.emit(provider)

    def _on_destroyed(self, provider: CatalogProvider) -> None:
        """Handle provider destruction without emitting signal with dead object."""
        if provider in self._providers:
            self._providers.remove(provider)

    def providers(self) -> list[CatalogProvider]:
        return list(self._providers)

    def all_catalogs(self) -> list[Catalog]:
        result: list[Catalog] = []
        for provider in self._providers:
            result.extend(provider.catalogs())
        return result
