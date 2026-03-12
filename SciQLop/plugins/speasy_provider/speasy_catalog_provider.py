import speasy as spz
from speasy.core.inventory.indexes import CatalogIndex, TimetableIndex, SpeasyIndex

from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, CatalogEvent
from SciQLop.components import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)


def _walk_inventory(node, path: list[str]):
    """Yield (path, index_node) for all CatalogIndex and TimetableIndex leaves."""
    for name, child in node.__dict__.items():
        if not name or not child:
            continue
        display = child.name if hasattr(child, "name") else name
        if isinstance(child, (CatalogIndex, TimetableIndex)):
            yield path + [display], child
        elif isinstance(child, SpeasyIndex):
            yield from _walk_inventory(child, path + [display])


def _speasy_id(index_node) -> str:
    return f"{index_node.spz_provider()}/{index_node.spz_uid()}"


def _make_catalog_events(data, catalog_uuid: str) -> list[CatalogEvent]:
    events = []
    for i, ev in enumerate(data):
        meta = ev.meta if hasattr(ev, "meta") else {}
        events.append(CatalogEvent(
            uuid=f"{catalog_uuid}:{i}",
            start=ev.start_time,
            stop=ev.stop_time,
            meta=meta,
        ))
    return events


class SpeasyCatalogProvider(CatalogProvider):
    def __init__(self, parent=None):
        # Must init before super().__init__ which triggers registry registration
        # and the tree model immediately calls catalogs()
        self._catalog_list: list[Catalog] = []
        self._speasy_ids: dict[str, str] = {}
        super().__init__(name="Speasy Catalogs", parent=parent)
        self._build_catalog_list()
        for cat in self._catalog_list:
            self.catalog_added.emit(cat)

    def _build_catalog_list(self):
        for source_name, source_node in spz.inventories.tree.__dict__.items():
            if not source_name or not source_node or not isinstance(source_node, SpeasyIndex):
                continue
            for path, index_node in _walk_inventory(source_node, [source_name]):
                sid = _speasy_id(index_node)
                cat = Catalog(uuid=sid, name=path[-1], provider=self, path=path[:-1])
                self._catalog_list.append(cat)
                self._speasy_ids[sid] = sid

    def catalogs(self) -> list[Catalog]:
        return list(self._catalog_list)

    def events(self, catalog, start=None, stop=None) -> list[CatalogEvent]:
        if catalog.uuid not in self._events:
            self._load_events(catalog)
        return super().events(catalog, start, stop)

    def _load_events(self, catalog: Catalog):
        sid = self._speasy_ids.get(catalog.uuid)
        if sid is None:
            return
        try:
            data = spz.get_data(sid)
            if data is not None:
                self._set_events(catalog, _make_catalog_events(data, catalog.uuid))
            else:
                log.warning(f"No data returned for {sid}")
        except Exception:
            log.error(f"Failed to load events for {sid}", exc_info=True)
