from typing import Any, Iterable, Union

from speasy.products.catalog import Catalog as SpeasyCatalog

from SciQLop.user_api.catalogs._service import CatalogService

DateTimeLike = Any
CatalogInput = Union[
    SpeasyCatalog,
    Iterable[tuple[DateTimeLike, DateTimeLike]],
    Iterable[tuple[DateTimeLike, DateTimeLike, dict]],
]

catalogs = CatalogService()

__all__ = ["catalogs", "CatalogInput"]
