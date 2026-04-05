# Catalog Browser: Icons and Folder Creation UX

## Summary

Add tree node icons to the catalog browser and provide an ergonomic UI for creating folders and catalogs at any nesting level.

## Goals

1. **Visual clarity** — distinguish providers, folders, and catalogs at a glance via icons
2. **Ergonomic creation** — users can create catalogs and folders anywhere in the tree without leaving the tree view
3. **Unlimited nesting** — folder hierarchies of arbitrary depth, backed by the existing `path` attribute on `Catalog`

## Non-goals

- Drag-and-drop reorganization of catalogs between folders
- Renaming folders
- Provider-specific icon overrides in cocat/tscat (the hook is available for future use)

## Design

### 1. Tree node icons

Add `DecorationRole` handling in `CatalogTreeModel.data()`. For each node, query the provider first, then fall back to defaults.

**Provider API addition** (`CatalogProvider`):

```python
class NodeType(str, Enum):
    PROVIDER = "provider"
    FOLDER = "folder"
    CATALOG = "catalog"

def node_icon(self, node_type: NodeType, path: list[str] | None = None) -> QIcon | None:
    """Return a custom icon for a node type, or None for default."""
    return None
```

`NodeType` enum is defined in `provider.py` alongside `Capability`.

**Default icons** from existing SciQLopPlots theme icons via `get_icon()` (auto-adapts to dark/light). These icons are already registered in the `Icons` C++ registry via the `://icons/theme/` Qt resource path and are available through `get_icon(name)` — no additional `register_icon` calls needed.

| Node type | Icon name | Source |
|-----------|-----------|--------|
| Provider | `"dataSourceRoot"` | SciQLopPlots theme |
| Folder (implicit or explicit) | `"folder_open"` | SciQLopPlots theme |
| Catalog | `"catalogue"` | SciQLopPlots theme |
| Placeholder | (none) | — |

**Resolution order in `DecorationRole`:** if placeholder → return `None` (no icon). Otherwise: `provider.node_icon(type, path)` → if `None`, use default from table above.

### 2. Inline placeholders for creation

Every folder node and provider node that supports `CREATE_CATALOGS` gets two placeholder children at the bottom:

1. **"New Catalog..."** — double-click to inline-edit, creates a catalog with the folder's path
2. **"New Folder..."** — double-click to inline-edit, creates an empty implicit folder node

Placeholders are styled italic + gray (as today). No icon on placeholders. This includes explicit folders (e.g. cocat rooms) — if the provider has `CREATE_CATALOGS`, the room folder gets placeholders. Creating a catalog inside a cocat room folder builds `path=["room_id"]`, which the cocat provider's `create_catalog(name, path=["room_id"])` already handles correctly.

**Placeholder type field:** Add `placeholder_type` to `_Node.__slots__`:

```python
class _PlaceholderType(str, Enum):
    NONE = "none"
    CATALOG = "catalog"
    FOLDER = "folder"
```

Replace `is_placeholder: bool` with `placeholder_type: _PlaceholderType`. A node is a placeholder when `placeholder_type != NONE`. This is checked via a property `is_placeholder` for backward compatibility.

**Ordering within a folder's children:** children are inserted in arrival order (no forced sort). Placeholders are always last — "New Catalog..." then "New Folder...".

### 3. `setData()` behavior for placeholders

Two distinct branches in `setData()`:

**Catalog placeholder** (`placeholder_type == CATALOG`):
1. Build `path` by walking from the placeholder's parent node up to (but not including) the provider node, collecting `node.name` at each step, then reversing
2. Call `node.provider.create_catalog(name, path=path)`
3. Return `True` (the `catalog_added` signal handles tree insertion)

**Folder placeholder** (`placeholder_type == FOLDER`):
1. Build `path` the same way as above, then append the new folder name
2. Insert a new `_Node(name=name, parent=parent_node, provider=provider, catalog=None)` before the placeholders using `beginInsertRows`/`endInsertRows`
3. Call `_ensure_placeholders` on the new folder node to add its own placeholder children (also uses `beginInsertRows`/`endInsertRows`)
4. Return `True`

The `_folder_path` helper (already exists in `CatalogTreeModel`) computes the path segments.

### 4. Context menu additions

Right-click on any folder or provider node adds (gated on `CREATE_CATALOGS` capability):
- **"New Catalog"** — triggers inline edit on the "New Catalog..." placeholder of that node
- **"New Folder"** — triggers inline edit on the "New Folder..." placeholder of that node

These appear alongside existing context menu actions (Delete, Save, folder_actions, etc.).

**Filter proxy interaction:** If a filter is active, placeholders may be hidden by the proxy. The context menu action clears the filter before calling `tree.edit()` on the placeholder's proxy index. This is the simplest approach and acceptable since the user is switching from searching to creating.

### 5. Placeholder management in `_Node` / `CatalogTreeModel`

Each provider node and each folder node with a provider that has `CREATE_CATALOGS` gets two placeholders.

**When placeholders are created:**
- `_add_provider_node`: adds placeholders to the provider node and to each initial folder
- `_on_folder_added` / folder creation in `setData`: adds placeholders to newly created folders using `beginInsertRows`/`endInsertRows`
- `_on_catalog_added`: when a new implicit folder is created for a catalog's path, adds placeholders to that folder

**Helper:** `_ensure_placeholders(parent_node, parent_index)` — checks if the node already has placeholder children; if not, inserts them. Called from all the above sites, including `_find_or_create_folder` (used during initial population in `_add_provider_node`).

**Pruning:** `_prune_if_empty` considers a folder empty when `not any(not c.is_placeholder for c in node.children)` (i.e. all remaining children are placeholders). When a folder node is pruned via `beginRemoveRows`/`endRemoveRows`, its placeholder children are removed implicitly as part of the subtree removal — no separate cleanup needed.

## Files to modify

| File | Changes |
|------|---------|
| `SciQLop/components/catalogs/backend/provider.py` | Add `NodeType` enum, add `node_icon()` method to `CatalogProvider` |
| `SciQLop/components/catalogs/ui/catalog_tree.py` | Add `_PlaceholderType`, replace `is_placeholder` bool, add `DecorationRole` in `data()`, add placeholder pair per folder via `_ensure_placeholders`, handle "New Folder..." in `setData()` with path building, update `_prune_if_empty` to skip placeholders |
| `SciQLop/components/catalogs/ui/catalog_browser.py` | Add "New Catalog" / "New Folder" to context menu, clear filter and trigger `tree.edit()` on the right placeholder |

No new files need to be created.

## Testing

- Verify icons appear for all node types (provider, folder, catalog)
- Verify "New Catalog..." placeholder in a subfolder creates a catalog with correct path
- Verify "New Folder..." placeholder creates an empty folder node with its own placeholders
- Verify empty implicit folders are pruned when their last catalog is removed (placeholders don't prevent pruning)
- Verify context menu "New Catalog" / "New Folder" triggers inline edit (including when filter is active)
- Verify provider `node_icon()` override takes precedence over defaults
- Verify cocat room folders get placeholders and catalog creation routes to the correct room
