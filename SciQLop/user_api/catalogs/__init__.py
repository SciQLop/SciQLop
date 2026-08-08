"""Catalog user API — CRUD operations on SciQLop catalogs from Python/Jupyter.

Usage::

    from SciQLop.user_api.catalogs import catalogs

    # List all catalogs
    catalogs.list()

    # List catalogs under a specific provider ("My Catalogs" is the local
    # tscat store; "Remote" is read-only)
    catalogs.list("My Catalogs")

    # Get a catalog as a speasy Catalog object
    cat = catalogs.get("My Catalogs//my_catalog")

    # Save events (creates the catalog if it doesn't exist)
    catalogs.save("My Catalogs//my_catalog", [
        ("2020-01-01", "2020-01-02"),
        ("2020-02-01", "2020-02-03", {"label": "storm"}),
    ])

    # Strict create (raises ValueError if already exists)
    catalogs.create("My Catalogs//new_catalog", existing_speasy_catalog)

    # Append events to an existing catalog
    catalogs.add_events("My Catalogs//my_catalog", [("2020-03-01", "2020-03-02")])

    # Remove specific events (pass events from get())
    cat = catalogs.get("My Catalogs//my_catalog")
    catalogs.remove_events("My Catalogs//my_catalog", [cat[0]])

    # Delete an entire catalog
    catalogs.remove("My Catalogs//my_catalog")

Paths use ``//`` as separator: ``"provider//optional//sub//path//catalog_name"``.
Drag-and-drop from the catalog tree generates these paths automatically.

Input data for ``save``/``create`` accepts a ``speasy.Catalog``, an iterable of
``(start, stop)`` tuples, or an iterable of ``(start, stop, meta_dict)`` tuples.
"""

from typing import Any, Iterable, Union

from speasy.products.catalog import Catalog as SpeasyCatalog

from SciQLop.user_api.catalogs._service import CatalogService
from SciQLop.user_api.catalogs._overlay import (
    CatalogOverlay,
    add_catalog_overlay,
    remove_catalog_overlay,
)

DateTimeLike = Any
CatalogInput = Union[
    SpeasyCatalog,
    Iterable[tuple[DateTimeLike, DateTimeLike]],
    Iterable[tuple[DateTimeLike, DateTimeLike, dict]],
]

catalogs = CatalogService()

__all__ = [
    "catalogs",
    "CatalogInput",
    "CatalogOverlay",
    "add_catalog_overlay",
    "remove_catalog_overlay",
]
