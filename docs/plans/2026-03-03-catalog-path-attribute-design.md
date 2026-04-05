# Catalog Path Attribute Design

## Goal

Add a `path: list[str]` attribute to `Catalog` so catalogs can be organized hierarchically within each provider. The tree UI displays intermediate folder nodes derived from path segments.

## Decisions

- **Path format:** `list[str]` (e.g. `["MMS", "Magnetosheath"]`)
- **Path semantics:** container only — the catalog `name` is the leaf label
- **Folder nodes:** purely organizational (expand/collapse), not selectable for events
- **Approach:** build folder `_Node`s on-the-fly in `CatalogTreeModel` (Approach A — no new classes)
- **TscatCatalogProvider:** derives `path` from tscat's existing `path__` attribute

## Changes

### 1. `components/catalogs/backend/provider.py`

Add `path: list[str]` field to the `Catalog` dataclass with default `field(default_factory=list)`. Fully backward-compatible.

### 2. `components/catalogs/ui/catalog_tree.py`

- Add `_find_or_create_folder(parent, name, provider)` — finds an existing folder child by name or creates one (`catalog=None`).
- Update `_add_provider_node` — walk each catalog's `path` segments to find/create folder nodes before appending the catalog leaf.
- Update `_on_catalog_added` — same folder resolution logic with proper `beginInsertRows` targeting the correct parent index.
- Update `_on_catalog_removed` — after removing a catalog leaf, prune empty ancestor folder nodes.

### 3. `plugins/tscat_catalogs/tscat_provider.py`

Read `path__` from tscat entities: `getattr(entity, "path__", [])`. Validate it's a `list[str]`, default to `[]`. Pass as `path=` to `Catalog` constructor. May need to adjust iteration to discover catalogs inside tscat folders.

### 4. Tests (`tests/test_catalog_provider.py`)

- Catalogs with `path=["A", "B"]` appear nested under folder nodes
- Folder nodes have `catalog is None`
- Empty folders are pruned on catalog removal
- Catalogs with `path=[]` appear directly under the provider (backward compat)

## Files unchanged

`CatalogBrowser`, `EventTableModel`, `CatalogRegistry`, `CatalogProvider` base class — the existing `catalog is None` check in the browser already handles folder nodes.
