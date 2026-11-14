"""Past versions of CoCat projects, shown read-only beside the live ones.

A version comes from the server in one download (cocat_rs.Project.at): no socket, no cache on disk,
nothing merged into the live project. Its catalogues and events get uuids of their own here, since
SciQLop tells catalogues and events apart by uuid and the live ones keep theirs.
"""
from __future__ import annotations

from SciQLop.components.catalogs import Catalog, CatalogEvent, CatalogProvider, ProviderAction

from .convert import rows_of, subpath_of

PROVIDER_NAME = "Past versions (cocat-rs)"


class VersionsProvider(CatalogProvider):
    def __init__(self, parent=None):
        self._versions: dict[str, tuple[str, object]] = {}  # key -> (title, cocat_rs past project)
        self._catalogs: dict[str, Catalog] = {}
        super().__init__(name=PROVIDER_NAME, parent=parent,
                         description="Projects as they were at a saved version, read-only.")

    def show(self, key: str, title: str, project) -> None:
        if key in self._versions:
            return
        self._versions[key] = (title, project)
        self.folder_added.emit([key])
        for cocat_cat in project.catalogues():
            self._show_catalogue(key, cocat_cat)

    def _show_catalogue(self, key: str, cocat_cat) -> None:
        catalog = Catalog(uuid=f"{key}/{cocat_cat.uuid}", name=cocat_cat.name, provider=self,
                          path=[key, *subpath_of(cocat_cat.attributes)])
        self._catalogs[catalog.uuid] = catalog
        events = [CatalogEvent(uuid=f"{key}/{row.uuid}", start=row.start, stop=row.stop, meta=row.meta,
                               parent=self)
                  for row in rows_of(cocat_cat.event_arrays(attributes=True))]
        self._set_events(catalog, events)
        self.catalog_added.emit(catalog)

    def close_version(self, key: str) -> None:
        title, project = self._versions.pop(key)
        for catalog in [c for c in self._catalogs.values() if c.path[0] == key]:
            del self._catalogs[catalog.uuid]
            CatalogProvider.remove_catalog(self, catalog)
        self.folder_removed.emit([key])
        project.close()

    def catalogs(self) -> list[Catalog]:
        return list(self._catalogs.values())

    def capabilities(self, catalog: Catalog | None = None) -> set[str]:
        return set()

    def create_catalog(self, name: str, path: list[str] | None = None) -> Catalog:
        raise PermissionError("A past version is read-only")

    def folder_display_name(self, path: list[str]) -> str | None:
        shown = self._versions.get(path[0]) if len(path) == 1 else None
        return shown[0] if shown else None

    def folder_actions(self, path: list[str]) -> list[ProviderAction]:
        if len(path) != 1 or path[0] not in self._versions:
            return []
        return [ProviderAction(name="Close", callback=lambda p: self.close_version(p[0]))]

    async def close(self) -> None:
        for key in list(self._versions):
            self.close_version(key)
