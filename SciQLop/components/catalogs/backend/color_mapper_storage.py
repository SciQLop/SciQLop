from __future__ import annotations

from typing import ClassVar

from SciQLop.components.settings.backend.entry import ConfigEntry, SettingsCategory
from .color_mapper import ColorMapper
from .provider import Catalog


class CatalogColorMappings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.CATALOGS
    subcategory: ClassVar[str] = "Color Mappings"
    mappings: dict[str, str] = {}  # {catalog_uuid: ColorMapper JSON}


def get_color_mapper(catalog: Catalog) -> ColorMapper:
    with CatalogColorMappings() as settings:
        json_str = settings.mappings.get(catalog.uuid)
    if json_str is not None:
        return ColorMapper.model_validate_json(json_str)
    return ColorMapper()


def set_color_mapper(catalog: Catalog, mapper: ColorMapper) -> None:
    with CatalogColorMappings() as settings:
        if mapper.column is None:
            settings.mappings.pop(catalog.uuid, None)
        else:
            settings.mappings[catalog.uuid] = mapper.model_dump_json()
