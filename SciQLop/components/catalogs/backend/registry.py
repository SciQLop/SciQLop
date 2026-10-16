"""Catalog providers: the sciqlop.catalog_providers extension point (Tier 3 spec §3.4).

A CatalogProvider registers itself when it is built, under the current owner, so a withdrawn plugin's providers
leave with it. CatalogRegistry keeps its methods and signals, driven by the point.
"""
from __future__ import annotations

import shiboken6
from PySide6.QtCore import QObject, Signal

from SciQLop.core.extensions import ExtensionPoint, current_owner, declare
from SciQLop.user_api.threading import on_main_thread

from .provider import Catalog, CatalogProvider


def provider_key(provider: CatalogProvider) -> str:
    """Providers are instances, and two may share a name: the name keeps error messages readable."""
    return f"{provider.name}#{id(provider):x}"


CATALOG_PROVIDERS = declare(ExtensionPoint(
    "sciqlop.catalog_providers", CatalogProvider, what="catalog provider", key=provider_key,
    doc="Catalog providers; a CatalogProvider registers itself when it is built."))


class CatalogRegistry(QObject):
    """Singleton view of the catalog providers, with the signals the catalog UI listens to."""

    provider_registered = Signal(object)
    provider_unregistered = Signal(object)

    _instance: CatalogRegistry | None = None

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._silenced: set[int] = set()
        self._keys: dict[int, str] = {}
        self._announced: set[int] = set()
        CATALOG_PROVIDERS.signals.added.connect(self._on_added)
        CATALOG_PROVIDERS.signals.removed.connect(self._on_removed)

    @classmethod
    def instance(cls) -> CatalogRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, provider: CatalogProvider) -> None:
        """From any thread (a notebook cell, an agent tool, a labelling pipeline): the owner is captured here."""
        self._contribute(provider, current_owner())

    @on_main_thread
    def _contribute(self, provider: CatalogProvider, owner: str) -> None:
        if id(provider) in self._keys:
            return
        key = provider_key(provider)
        CATALOG_PROVIDERS.contribute(provider, owner=owner)
        self._keys[id(provider)] = key
        provider.destroyed.connect(lambda *_, k=key, i=id(provider): self._remove_silently(k, i))

    @on_main_thread
    def unregister(self, provider: CatalogProvider) -> None:
        key = self._key_of(provider)
        if key in CATALOG_PROVIDERS:
            CATALOG_PROVIDERS.remove(key)

    def _key_of(self, provider: CatalogProvider) -> str:
        """The key it registered under: a provider renamed afterwards (DummyProvider tests do) keeps it."""
        return self._keys.get(id(provider)) or provider_key(provider)

    def _forget_for_tests(self, provider: CatalogProvider) -> None:
        self._remove_silently(self._key_of(provider), id(provider))

    @on_main_thread  # `destroyed` fires on the thread that deletes the provider
    def _remove_silently(self, key: str, ident: int) -> None:
        """A destroyed provider leaves without provider_unregistered: its slots would be handed a dead object."""
        self._keys.pop(ident, None)
        if key not in CATALOG_PROVIDERS or not shiboken6.isValid(CATALOG_PROVIDERS.signals):  # exit-time: the point's QObject may already be gone
            return
        self._silenced.add(ident)
        try:
            CATALOG_PROVIDERS.remove(key)
        finally:
            self._silenced.discard(ident)

    def _on_added(self, provider: CatalogProvider) -> None:
        if shiboken6.isValid(self) and id(provider) not in self._announced:
            self._announced.add(id(provider))
            self.provider_registered.emit(provider)

    def _on_removed(self, provider: CatalogProvider) -> None:
        self._keys.pop(id(provider), None)
        self._announced.discard(id(provider))
        if shiboken6.isValid(self) and id(provider) not in self._silenced:
            self.provider_unregistered.emit(provider)

    def providers(self) -> list[CatalogProvider]:
        return CATALOG_PROVIDERS.list()

    def provider_by_name(self, name: str) -> "CatalogProvider | None":
        return next((p for p in self.providers() if p.name == name), None)

    def all_catalogs(self) -> list[Catalog]:
        return [catalog for provider in self.providers() for catalog in provider.catalogs()]
