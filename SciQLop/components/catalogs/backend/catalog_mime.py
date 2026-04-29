from __future__ import annotations

import json
from PySide6.QtCore import QMimeData

from SciQLop.core.mime import register_mime
from SciQLop.core.mime.types import CATALOG_LIST_MIME_TYPE

from .provider import Catalog
from .registry import CatalogRegistry


def _encode_catalog_list(catalogs: list[Catalog]) -> QMimeData:
    payload = [(c.provider.name if c.provider else "", c.uuid) for c in catalogs]
    md = QMimeData()
    md.setData(CATALOG_LIST_MIME_TYPE, json.dumps(payload).encode("utf-8"))
    return md


def _decode_catalog_list(mime: QMimeData) -> list[Catalog]:
    raw = bytes(mime.data(CATALOG_LIST_MIME_TYPE))
    if not raw:
        return []
    payload = json.loads(raw.decode("utf-8"))
    registry = CatalogRegistry.instance()
    by_provider: dict[str, dict[str, Catalog]] = {}
    for provider in registry.providers():
        by_provider[provider.name] = {c.uuid: c for c in provider.catalogs()}
    result: list[Catalog] = []
    for provider_name, uuid in payload:
        cat = by_provider.get(provider_name, {}).get(uuid)
        if cat is not None:
            result.append(cat)
    return result


register_mime(
    obj_type=list,
    mime_type=CATALOG_LIST_MIME_TYPE,
    encoder=_encode_catalog_list,
    decoder=_decode_catalog_list,
    nested_type=Catalog,
)
