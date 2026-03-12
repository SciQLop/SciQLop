# Catalog Browser Icons and Folder Creation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tree node icons and an ergonomic UI for creating folders and catalogs at any nesting level in the catalog browser.

**Architecture:** Three changes layered on the existing `CatalogTreeModel` / `CatalogBrowser` / `CatalogProvider` stack: (1) `NodeType` enum + `node_icon()` on provider, (2) `_PlaceholderType` enum replacing `is_placeholder` bool + per-folder placeholder pairs, (3) context menu additions for folder/catalog creation. Icons come from the existing SciQLopPlots theme icon set via `get_icon()`.

**Tech Stack:** PySide6 (Qt6), Python 3.10+, pytest-qt for testing

**Spec:** `docs/superpowers/specs/2026-03-12-catalog-browser-icons-and-folders-design.md`

---

## Chunk 1: Provider API and Tree Model Core

### Task 1: Add `NodeType` enum and `node_icon()` to `CatalogProvider`

**Files:**
- Modify: `SciQLop/components/catalogs/backend/provider.py:55-66` (after `Capability` enum)
- Test: `tests/test_catalog_provider.py`

- [ ] **Step 1: Write failing tests for NodeType and node_icon**

Add to `tests/test_catalog_provider.py`:

```python
def test_node_type_enum(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import NodeType
    assert NodeType.PROVIDER == "provider"
    assert NodeType.FOLDER == "folder"
    assert NodeType.CATALOG == "catalog"
    assert isinstance(NodeType.PROVIDER, str)


def test_provider_node_icon_default_returns_none(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import NodeType
    provider = _make_dummy_provider(qapp)
    assert provider.node_icon(NodeType.PROVIDER) is None
    assert provider.node_icon(NodeType.FOLDER, path=["X"]) is None
    assert provider.node_icon(NodeType.CATALOG) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_catalog_provider.py::test_node_type_enum tests/test_catalog_provider.py::test_provider_node_icon_default_returns_none -v`
Expected: FAIL — `NodeType` not found

- [ ] **Step 3: Implement NodeType and node_icon**

In `SciQLop/components/catalogs/backend/provider.py`, add after the `Capability` enum (line 66):

```python
class NodeType(str, Enum):
    PROVIDER = "provider"
    FOLDER = "folder"
    CATALOG = "catalog"
```

Add to `CatalogProvider` class body (after `folder_display_name`, around line 134):

```python
def node_icon(self, node_type: NodeType, path: list[str] | None = None) -> QIcon | None:
    """Return a custom icon for a node type, or None for default."""
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_catalog_provider.py::test_node_type_enum tests/test_catalog_provider.py::test_provider_node_icon_default_returns_none -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/catalogs/backend/provider.py tests/test_catalog_provider.py
git commit -m "feat(catalog): add NodeType enum and node_icon() to CatalogProvider"
```

---

### Task 2: Add `_PlaceholderType` enum and refactor `_Node` in tree model

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_tree.py:1-39` (`_Node` class)
- Test: `tests/test_catalog_provider.py`

**Context:** The `_Node` class uses `__slots__` with `is_placeholder: bool`. We replace it with `placeholder_type: _PlaceholderType` and add an `is_placeholder` property for backward compat. All existing code that checks `node.is_placeholder` continues to work.

- [ ] **Step 1: Write failing test for _PlaceholderType**

```python
def test_placeholder_type_enum(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import _PlaceholderType
    assert _PlaceholderType.NONE == "none"
    assert _PlaceholderType.CATALOG == "catalog"
    assert _PlaceholderType.FOLDER == "folder"


def test_node_placeholder_property(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import _Node, _PlaceholderType
    regular = _Node(name="test")
    assert not regular.is_placeholder
    cat_ph = _Node(name="New Catalog...", placeholder_type=_PlaceholderType.CATALOG)
    assert cat_ph.is_placeholder
    folder_ph = _Node(name="New Folder...", placeholder_type=_PlaceholderType.FOLDER)
    assert folder_ph.is_placeholder
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_catalog_provider.py::test_placeholder_type_enum tests/test_catalog_provider.py::test_node_placeholder_property -v`
Expected: FAIL — `_PlaceholderType` not found

- [ ] **Step 3: Implement _PlaceholderType and refactor _Node**

In `SciQLop/components/catalogs/ui/catalog_tree.py`, add before `_Node` class:

```python
from enum import Enum

class _PlaceholderType(str, Enum):
    NONE = "none"
    CATALOG = "catalog"
    FOLDER = "folder"
```

Replace the `_Node` class with:

```python
class _Node:
    """Internal tree node: root -> provider -> folder -> catalog."""

    __slots__ = ("name", "parent", "children", "provider", "catalog",
                 "placeholder_type", "is_explicit_folder")

    def __init__(
        self,
        name: str,
        parent: _Node | None = None,
        provider: CatalogProvider | None = None,
        catalog: Catalog | None = None,
        placeholder_type: _PlaceholderType = _PlaceholderType.NONE,
        is_explicit_folder: bool = False,
    ):
        self.name = name
        self.parent = parent
        self.children: list[_Node] = []
        self.provider = provider
        self.catalog = catalog
        self.placeholder_type = placeholder_type
        self.is_explicit_folder = is_explicit_folder

    @property
    def is_placeholder(self) -> bool:
        return self.placeholder_type != _PlaceholderType.NONE

    def row(self) -> int:
        if self.parent is not None:
            return self.parent.children.index(self)
        return 0
```

Update the existing placeholder creation in `_add_provider_node` (line ~85-89). Change:

```python
is_placeholder=True,
```

to:

```python
placeholder_type=_PlaceholderType.CATALOG,
```

- [ ] **Step 4: Run ALL existing tests to verify nothing broke**

Run: `uv run pytest tests/test_catalog_provider.py tests/test_catalog_dirty_state.py -v`
Expected: ALL PASS (backward compat via `is_placeholder` property)

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_tree.py tests/test_catalog_provider.py
git commit -m "refactor(catalog): replace is_placeholder bool with _PlaceholderType enum"
```

---

### Task 3: Add `DecorationRole` icon handling to `CatalogTreeModel.data()`

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_tree.py:320-359` (`data()` method)
- Test: `tests/test_catalog_provider.py`

**Context:** `get_icon(name)` from `SciQLop.components.theming.icons` returns a `QIcon` with colors adapted to the current theme. Icons `"dataSourceRoot"`, `"folder_open"`, `"catalogue"` exist in SciQLopPlots' `://icons/theme/` resources.

- [ ] **Step 1: Write failing tests for DecorationRole**

```python
def test_tree_icon_provider_node(qtbot, qapp):
    """Provider nodes should have a DecorationRole icon."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon

    provider = DummyProvider(num_catalogs=1)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            icon = model.data(idx, Qt.ItemDataRole.DecorationRole)
            assert isinstance(icon, QIcon)
            return
    pytest.fail("Provider node not found")


def test_tree_icon_catalog_node(qtbot, qapp):
    """Catalog nodes should have a DecorationRole icon."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon

    provider = DummyProvider(num_catalogs=1)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            cat_idx = model.index(0, 0, idx)
            icon = model.data(cat_idx, Qt.ItemDataRole.DecorationRole)
            assert isinstance(icon, QIcon)
            return
    pytest.fail("Provider node not found")


def test_tree_icon_folder_node(qtbot, qapp):
    """Folder nodes should have a DecorationRole icon."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon

    provider = DummyProvider(num_catalogs=1, paths=[["FolderA"]])
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            folder_idx = model.index(0, 0, idx)
            assert model.data(folder_idx) == "FolderA"
            icon = model.data(folder_idx, Qt.ItemDataRole.DecorationRole)
            assert isinstance(icon, QIcon)
            return
    pytest.fail("Provider node not found")


def test_tree_icon_placeholder_none(qtbot, qapp):
    """Placeholder nodes should NOT have a DecorationRole icon."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt

    provider = DummyProvider(num_catalogs=0)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            # Last child should be a placeholder
            last_row = model.rowCount(idx) - 1
            assert last_row >= 0
            ph_idx = model.index(last_row, 0, idx)
            ph_node = model.node_from_index(ph_idx)
            assert ph_node.is_placeholder
            icon = model.data(ph_idx, Qt.ItemDataRole.DecorationRole)
            assert icon is None
            return
    pytest.fail("Provider node not found")


def test_tree_icon_provider_override(qtbot, qapp):
    """Provider's node_icon() should take precedence over defaults."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability, NodeType
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon, QPixmap

    custom_icon = QIcon(QPixmap(16, 16))

    class IconProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="IconProvider")

        def catalogs(self):
            return []

        def capabilities(self, catalog=None):
            return set()

        def node_icon(self, node_type, path=None):
            if node_type == NodeType.PROVIDER:
                return custom_icon
            return None

    provider = IconProvider()
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            icon = model.data(idx, Qt.ItemDataRole.DecorationRole)
            assert icon is custom_icon
            return
    pytest.fail("IconProvider not found")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_catalog_provider.py::test_tree_icon_provider_node tests/test_catalog_provider.py::test_tree_icon_catalog_node tests/test_catalog_provider.py::test_tree_icon_folder_node tests/test_catalog_provider.py::test_tree_icon_placeholder_none tests/test_catalog_provider.py::test_tree_icon_provider_override -v`
Expected: FAIL — `data()` returns `None` for `DecorationRole`

- [ ] **Step 3: Implement DecorationRole in data()**

In `CatalogTreeModel.data()`, add a new block before the `return None` at the end (after the `DIRTY_PROVIDER_ROLE` block):

```python
if role == Qt.ItemDataRole.DecorationRole:
    node = index.internalPointer()
    if node.is_placeholder:
        return None
    from ..backend.provider import NodeType
    from ...theming.icons import get_icon
    node_type = self._node_type(node)
    if node.provider is not None:
        custom = node.provider.node_icon(node_type, self._folder_path(node) if node_type == NodeType.FOLDER else None)
        if custom is not None:
            return custom
    icon_map = {
        NodeType.PROVIDER: "dataSourceRoot",
        NodeType.FOLDER: "folder_open",
        NodeType.CATALOG: "catalogue",
    }
    icon_name = icon_map.get(node_type)
    return get_icon(icon_name) if icon_name else None
```

Add helper method `_node_type` to `CatalogTreeModel`:

```python
def _node_type(self, node: _Node) -> NodeType:
    from ..backend.provider import NodeType
    if node.catalog is not None:
        return NodeType.CATALOG
    if node.parent is self._root:
        return NodeType.PROVIDER
    return NodeType.FOLDER
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_catalog_provider.py -k "test_tree_icon" -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite to check nothing broke**

Run: `uv run pytest tests/test_catalog_provider.py tests/test_catalog_dirty_state.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_tree.py tests/test_catalog_provider.py
git commit -m "feat(catalog): add tree node icons via DecorationRole"
```

---

## Chunk 2: Placeholder Pairs and Folder Creation

### Task 4: Add `_ensure_placeholders` and per-folder placeholder pairs

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_tree.py`
- Test: `tests/test_catalog_provider.py`

**Context:** Currently only provider nodes get a single "New Catalog..." placeholder. After this task, every provider and folder node (when provider has `CREATE_CATALOGS`) gets two placeholders: "New Catalog..." and "New Folder...". The `_ensure_placeholders` helper inserts them idempotently.

- [ ] **Step 1: Write failing tests**

```python
def test_provider_has_two_placeholders(qtbot, qapp):
    """Provider node with CREATE_CATALOGS should have both catalog and folder placeholders."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=0)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            assert model.rowCount(idx) == 2
            ph0 = model.node_from_index(model.index(0, 0, idx))
            ph1 = model.node_from_index(model.index(1, 0, idx))
            assert ph0.placeholder_type == _PlaceholderType.CATALOG
            assert ph1.placeholder_type == _PlaceholderType.FOLDER
            return
    pytest.fail("Provider not found")


def test_folder_has_two_placeholders(qtbot, qapp):
    """Folder nodes under a CREATE_CATALOGS provider should have both placeholders."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, paths=[["FolderA"]])
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            # First child is FolderA
            folder_idx = model.index(0, 0, idx)
            folder_node = model.node_from_index(folder_idx)
            assert folder_node.name == "FolderA"
            # FolderA should have: Catalog-0, "New Catalog...", "New Folder..."
            row_count = model.rowCount(folder_idx)
            assert row_count == 3
            last = model.node_from_index(model.index(row_count - 1, 0, folder_idx))
            second_last = model.node_from_index(model.index(row_count - 2, 0, folder_idx))
            assert second_last.placeholder_type == _PlaceholderType.CATALOG
            assert last.placeholder_type == _PlaceholderType.FOLDER
            return
    pytest.fail("Provider not found")


def test_dynamic_folder_gets_placeholders(qtbot, qapp):
    """Dynamically created folders (via catalog_added with path) should get placeholders."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability
    import uuid as _uuid

    class CreateProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="CreateProvider")
            self._catalogs = []

        def catalogs(self):
            return list(self._catalogs)

        def capabilities(self, catalog=None):
            return {Capability.CREATE_CATALOGS}

        def add_catalog(self, cat):
            self._catalogs.append(cat)
            self._set_events(cat, [])
            self.catalog_added.emit(cat)

    provider = CreateProvider()
    model = CatalogTreeModel()

    # Find provider index
    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.node_from_index(idx).provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    # Add catalog with path — creates folder dynamically
    cat = Catalog(uuid=str(_uuid.uuid4()), name="Cat1", provider=provider, path=["NewFolder"])
    provider.add_catalog(cat)

    # Find folder
    folder_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.name == "NewFolder" and not child.is_placeholder:
            folder_idx = child_idx
            break
    assert folder_idx is not None

    # Folder should have: Cat1, "New Catalog...", "New Folder..."
    count = model.rowCount(folder_idx)
    assert count == 3
    last = model.node_from_index(model.index(count - 1, 0, folder_idx))
    assert last.placeholder_type == _PlaceholderType.FOLDER
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_catalog_provider.py::test_provider_has_two_placeholders tests/test_catalog_provider.py::test_folder_has_two_placeholders tests/test_catalog_provider.py::test_dynamic_folder_gets_placeholders -v`
Expected: FAIL — only one placeholder exists, no folder placeholder

- [ ] **Step 3: Implement _ensure_placeholders and update all creation sites**

Add `_ensure_placeholders` to `CatalogTreeModel`:

```python
def _ensure_placeholders(self, node: _Node, node_index: QModelIndex) -> None:
    """Add catalog and folder placeholder children if not already present and provider supports creation."""
    if node.provider is None or not self._supports_create(node.provider):
        return
    has_cat_ph = any(c.placeholder_type == _PlaceholderType.CATALOG for c in node.children)
    has_folder_ph = any(c.placeholder_type == _PlaceholderType.FOLDER for c in node.children)
    to_add = []
    if not has_cat_ph:
        to_add.append(_Node(name="New Catalog...", parent=node, provider=node.provider,
                            placeholder_type=_PlaceholderType.CATALOG))
    if not has_folder_ph:
        to_add.append(_Node(name="New Folder...", parent=node, provider=node.provider,
                            placeholder_type=_PlaceholderType.FOLDER))
    if to_add:
        start = len(node.children)
        self.beginInsertRows(node_index, start, start + len(to_add) - 1)
        node.children.extend(to_add)
        self.endInsertRows()
```

**Update `_add_provider_node`:** Replace the old single-placeholder logic (lines ~84-89):

```python
# Old:
if self._supports_create(provider):
    placeholder = _Node(
        name="New Catalog...", parent=node, provider=provider,
        is_placeholder=True,
    )
    node.children.append(placeholder)

# New:
if self._supports_create(provider):
    node.children.append(_Node(name="New Catalog...", parent=node, provider=provider,
                                placeholder_type=_PlaceholderType.CATALOG))
    node.children.append(_Node(name="New Folder...", parent=node, provider=provider,
                                placeholder_type=_PlaceholderType.FOLDER))
```

Also add placeholders to folders created during initial population. In `_find_or_create_folder`, after creating a new folder node, add placeholders:

```python
def _find_or_create_folder(self, parent: _Node, name: str, provider: CatalogProvider) -> _Node:
    for child in parent.children:
        if child.catalog is None and child.name == name and not child.is_placeholder:
            return child
    folder = _Node(name=name, parent=parent, provider=provider)
    parent.children.append(folder)
    if self._supports_create(provider):
        folder.children.append(_Node(name="New Catalog...", parent=folder, provider=provider,
                                      placeholder_type=_PlaceholderType.CATALOG))
        folder.children.append(_Node(name="New Folder...", parent=folder, provider=provider,
                                      placeholder_type=_PlaceholderType.FOLDER))
    return folder
```

**Update `_on_catalog_added`:** After each folder's `self.endInsertRows()` call (line ~190), call `_ensure_placeholders` on the new folder. This must be **after** `endInsertRows()`, not inside the begin/end bracket:

```python
# After self.endInsertRows() for the folder insertion:
self._ensure_placeholders(folder, self.createIndex(folder.row(), 0, folder))
```

**Update `_on_folder_added`:** After creating explicit folders (lines ~217-223), call `_ensure_placeholders`:

```python
# After creating folder in the loop:
self._ensure_placeholders(folder, self.createIndex(folder.row(), 0, folder))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_catalog_provider.py::test_provider_has_two_placeholders tests/test_catalog_provider.py::test_folder_has_two_placeholders tests/test_catalog_provider.py::test_dynamic_folder_gets_placeholders -v`
Expected: PASS

- [ ] **Step 5: Update existing tests that assumed single placeholder**

Some existing tests may check exact row counts on provider nodes (e.g. `model.rowCount(provider_idx) == 0` for a provider with no catalogs). These now return `2` (two placeholders). Find and update them:

Run: `uv run pytest tests/test_catalog_provider.py tests/test_catalog_dirty_state.py -v`

Fix any row count assertions that now fail due to the extra placeholder. For example, tests checking `rowCount == 0` for empty providers with `CREATE_CATALOGS` should now expect `2`.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_tree.py tests/test_catalog_provider.py
git commit -m "feat(catalog): add placeholder pairs (catalog + folder) to all folders"
```

---

### Task 5: Update `_prune_if_empty` to skip placeholders

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_tree.py:260-278` (`_prune_if_empty`)
- Test: `tests/test_catalog_provider.py`

- [ ] **Step 1: Write failing test**

```python
def test_prune_folder_with_only_placeholders(qtbot, qapp):
    """Folder with only placeholder children should be pruned when catalog is removed."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability
    import uuid as _uuid

    class PruneProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="PruneProvider")
            self._catalogs = []

        def catalogs(self):
            return list(self._catalogs)

        def capabilities(self, catalog=None):
            return {Capability.CREATE_CATALOGS, Capability.DELETE_CATALOGS}

        def add_catalog(self, cat):
            self._catalogs.append(cat)
            self._set_events(cat, [])
            self.catalog_added.emit(cat)

        def remove_catalog(self, catalog):
            self._catalogs = [c for c in self._catalogs if c.uuid != catalog.uuid]
            super().remove_catalog(catalog)

    provider = PruneProvider()
    model = CatalogTreeModel()

    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.node_from_index(idx).provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    # Add catalog in a folder
    cat = Catalog(uuid=str(_uuid.uuid4()), name="TempCat", provider=provider, path=["TempFolder"])
    provider.add_catalog(cat)

    # Verify folder exists
    non_placeholder_children = [
        model.node_from_index(model.index(r, 0, provider_idx))
        for r in range(model.rowCount(provider_idx))
        if not model.node_from_index(model.index(r, 0, provider_idx)).is_placeholder
    ]
    assert any(c.name == "TempFolder" for c in non_placeholder_children)

    # Remove catalog — folder should be pruned (only placeholders remain)
    provider.remove_catalog(cat)

    non_placeholder_children = [
        model.node_from_index(model.index(r, 0, provider_idx))
        for r in range(model.rowCount(provider_idx))
        if not model.node_from_index(model.index(r, 0, provider_idx)).is_placeholder
    ]
    assert not any(c.name == "TempFolder" for c in non_placeholder_children)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_provider.py::test_prune_folder_with_only_placeholders -v`
Expected: FAIL — folder not pruned because `len(node.children) > 0` (placeholders still present)

- [ ] **Step 3: Update _prune_if_empty**

In `_prune_if_empty`, change the emptiness check from:

```python
if len(node.children) > 0:
    return  # not empty
```

to:

```python
if any(not c.is_placeholder for c in node.children):
    return  # has real children
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_catalog_provider.py::test_prune_folder_with_only_placeholders -v`
Expected: PASS

Run: `uv run pytest tests/test_catalog_provider.py tests/test_catalog_dirty_state.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_tree.py tests/test_catalog_provider.py
git commit -m "fix(catalog): prune folders that contain only placeholders"
```

---

### Task 6: Handle "New Catalog..." placeholder `setData` with path building

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_tree.py:361-378` (`setData`)
- Test: `tests/test_catalog_provider.py`

**Context:** Currently `setData` on a placeholder calls `node.provider.create_catalog(name)` with no path. It needs to build the path from the parent chain.

- [ ] **Step 1: Write failing test**

```python
def test_setdata_catalog_placeholder_builds_path(qtbot, qapp):
    """Creating a catalog via placeholder in a subfolder should pass the correct path."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt

    provider = DummyProvider(num_catalogs=1, paths=[["ProjectA"]])
    model = CatalogTreeModel()

    # Find the folder "ProjectA" under this provider
    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.node_from_index(idx).provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    folder_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.name == "ProjectA" and not child.is_placeholder:
            folder_idx = child_idx
            break
    assert folder_idx is not None

    # Find the "New Catalog..." placeholder in the folder
    ph_idx = None
    for r in range(model.rowCount(folder_idx)):
        child_idx = model.index(r, 0, folder_idx)
        child = model.node_from_index(child_idx)
        if child.placeholder_type == _PlaceholderType.CATALOG:
            ph_idx = child_idx
            break
    assert ph_idx is not None

    # Edit placeholder with a name
    result = model.setData(ph_idx, "NewCatalog", Qt.ItemDataRole.EditRole)
    assert result is True

    # The created catalog should have path=["ProjectA"]
    created = [c for c in provider.catalogs() if c.name == "NewCatalog"]
    assert len(created) == 1
    assert created[0].path == ["ProjectA"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_provider.py::test_setdata_catalog_placeholder_builds_path -v`
Expected: FAIL — path is `[]` instead of `["ProjectA"]`

- [ ] **Step 3: Update setData for catalog placeholder path building**

In `setData()`, change the placeholder branch from:

```python
if node.is_placeholder:
    node.provider.create_catalog(name)
    return True
```

to:

```python
if node.placeholder_type == _PlaceholderType.CATALOG:
    path = self._folder_path(node.parent)
    node.provider.create_catalog(name, path=path if path else None)
    return True
```

Note: `_folder_path` walks from the node up to the provider node, collecting name segments and reversing. When called on a provider node (parent.parent is None), the while loop exits immediately and returns `[]`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_catalog_provider.py::test_setdata_catalog_placeholder_builds_path -v`
Expected: PASS

Run: `uv run pytest tests/test_catalog_provider.py tests/test_catalog_dirty_state.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_tree.py tests/test_catalog_provider.py
git commit -m "feat(catalog): catalog placeholder setData builds path from parent chain"
```

---

### Task 7: Handle "New Folder..." placeholder `setData`

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_tree.py` (`setData`)
- Test: `tests/test_catalog_provider.py`

- [ ] **Step 1: Write failing test**

```python
def test_setdata_folder_placeholder_creates_folder(qtbot, qapp):
    """Editing a folder placeholder should create a new folder node with its own placeholders."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt

    provider = DummyProvider(num_catalogs=0)
    model = CatalogTreeModel()

    # Find provider
    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.node_from_index(idx).provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    # Find the "New Folder..." placeholder
    folder_ph_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.placeholder_type == _PlaceholderType.FOLDER:
            folder_ph_idx = child_idx
            break
    assert folder_ph_idx is not None

    # Edit to create folder
    result = model.setData(folder_ph_idx, "MyFolder", Qt.ItemDataRole.EditRole)
    assert result is True

    # Provider node should now have: "MyFolder", "New Catalog...", "New Folder..."
    found_folder = False
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.name == "MyFolder" and not child.is_placeholder:
            found_folder = True
            # The new folder should have its own placeholders
            assert model.rowCount(child_idx) == 2
            ph0 = model.node_from_index(model.index(0, 0, child_idx))
            ph1 = model.node_from_index(model.index(1, 0, child_idx))
            assert ph0.placeholder_type == _PlaceholderType.CATALOG
            assert ph1.placeholder_type == _PlaceholderType.FOLDER
            break
    assert found_folder


def test_setdata_nested_folder_creation(qtbot, qapp):
    """Creating a folder inside another folder should work."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt

    provider = DummyProvider(num_catalogs=1, paths=[["OuterFolder"]])
    model = CatalogTreeModel()

    # Find OuterFolder
    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.node_from_index(idx).provider is provider:
            provider_idx = idx
            break

    outer_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.name == "OuterFolder" and not child.is_placeholder:
            outer_idx = child_idx
            break
    assert outer_idx is not None

    # Find folder placeholder in OuterFolder
    folder_ph_idx = None
    for r in range(model.rowCount(outer_idx)):
        child_idx = model.index(r, 0, outer_idx)
        child = model.node_from_index(child_idx)
        if child.placeholder_type == _PlaceholderType.FOLDER:
            folder_ph_idx = child_idx
            break
    assert folder_ph_idx is not None

    # Create nested folder
    result = model.setData(folder_ph_idx, "InnerFolder", Qt.ItemDataRole.EditRole)
    assert result is True

    # Find InnerFolder inside OuterFolder
    found = False
    for r in range(model.rowCount(outer_idx)):
        child_idx = model.index(r, 0, outer_idx)
        child = model.node_from_index(child_idx)
        if child.name == "InnerFolder" and not child.is_placeholder:
            found = True
            assert model.rowCount(child_idx) == 2  # placeholders
            break
    assert found
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_catalog_provider.py::test_setdata_folder_placeholder_creates_folder tests/test_catalog_provider.py::test_setdata_nested_folder_creation -v`
Expected: FAIL — folder placeholder `setData` falls through to `return False`

- [ ] **Step 3: Implement folder placeholder handling in setData**

In `setData()`, add a branch for folder placeholders after the catalog placeholder branch:

```python
if node.placeholder_type == _PlaceholderType.FOLDER:
    parent = node.parent
    parent_index = self.createIndex(parent.row(), 0, parent) if parent.parent is not None else QModelIndex()
    # Insert before placeholders
    insert_row = next(
        (i for i, c in enumerate(parent.children) if c.is_placeholder),
        len(parent.children)
    )
    folder = _Node(name=name, parent=parent, provider=node.provider)
    self.beginInsertRows(parent_index, insert_row, insert_row)
    parent.children.insert(insert_row, folder)
    self.endInsertRows()
    folder_index = self.createIndex(insert_row, 0, folder)
    self._ensure_placeholders(folder, folder_index)
    return True
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_catalog_provider.py::test_setdata_folder_placeholder_creates_folder tests/test_catalog_provider.py::test_setdata_nested_folder_creation -v`
Expected: PASS

Run: `uv run pytest tests/test_catalog_provider.py tests/test_catalog_dirty_state.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_tree.py tests/test_catalog_provider.py
git commit -m "feat(catalog): folder creation via 'New Folder...' placeholder"
```

---

## Chunk 3: Context Menu and Browser Integration

### Task 8: Add "New Catalog" / "New Folder" to context menu in CatalogBrowser

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py:346-391` (`_on_tree_context_menu`)
- Test: `tests/test_catalog_provider.py`

- [ ] **Step 1: Write failing test**

```python
def test_trigger_placeholder_edit_clears_filter(qtbot, qapp):
    """_trigger_placeholder_edit should clear the filter bar and attempt to edit."""
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.ui.catalog_tree import _PlaceholderType
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, paths=[["FolderA"]])
    browser = CatalogBrowser()
    qtbot.addWidget(browser)

    model = browser._tree_model

    # Set a filter
    browser._filter_bar.setText("something")
    assert browser._filter_bar.text() == "something"

    # Find the catalog placeholder in FolderA
    provider_node = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        n = model.node_from_index(idx)
        if n.provider is provider:
            provider_node = n
            break
    assert provider_node is not None

    folder_node = next(c for c in provider_node.children if c.name == "FolderA" and not c.is_placeholder)
    cat_ph = next(c for c in folder_node.children if c.placeholder_type == _PlaceholderType.CATALOG)

    browser._trigger_placeholder_edit(cat_ph)
    assert browser._filter_bar.text() == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_provider.py::test_trigger_placeholder_edit_clears_filter -v`
Expected: FAIL — `_trigger_placeholder_edit` does not exist

- [ ] **Step 3: Implement context menu additions**

Add helper method to `CatalogBrowser`:

```python
def _trigger_placeholder_edit(self, placeholder_node) -> None:
    """Clear filter and trigger inline edit on a placeholder node."""
    self._filter_bar.clear()
    source_index = self._tree_model.createIndex(placeholder_node.row(), 0, placeholder_node)
    proxy_index = self._proxy_model.mapFromSource(source_index)
    if proxy_index.isValid():
        self._catalog_tree.edit(proxy_index)
```

In `CatalogBrowser._on_tree_context_menu`, add after the existing folder actions block and before the save actions block:

```python
# Creation actions (folder or provider node, gated on CREATE_CATALOGS)
if node.catalog is None and not node.is_placeholder:
    if Capability.CREATE_CATALOGS in caps:
        from .catalog_tree import _PlaceholderType
        cat_ph = next((c for c in node.children if c.placeholder_type == _PlaceholderType.CATALOG), None)
        folder_ph = next((c for c in node.children if c.placeholder_type == _PlaceholderType.FOLDER), None)
        if cat_ph is not None:
            new_cat_action = menu.addAction("New Catalog")
            new_cat_action.triggered.connect(lambda checked, ph=cat_ph: self._trigger_placeholder_edit(ph))
        if folder_ph is not None:
            new_folder_action = menu.addAction("New Folder")
            new_folder_action.triggered.connect(lambda checked, ph=folder_ph: self._trigger_placeholder_edit(ph))
```

- [ ] **Step 4: Run all tests**

Run: `uv run pytest tests/test_catalog_provider.py tests/test_catalog_dirty_state.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_browser.py tests/test_catalog_provider.py
git commit -m "feat(catalog): add New Catalog/New Folder to context menu"
```

---

### Task 9: Final integration test and cleanup

**Files:**
- Test: `tests/test_catalog_provider.py`

- [ ] **Step 1: Write end-to-end integration test**

```python
def test_full_folder_catalog_creation_workflow(qtbot, qapp):
    """End-to-end: create folder, create catalog inside it, verify path, remove, verify pruned."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability
    from PySide6.QtCore import Qt
    import uuid as _uuid

    class WorkflowProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="WorkflowProvider")
            self._catalogs = []

        def catalogs(self):
            return list(self._catalogs)

        def capabilities(self, catalog=None):
            return {Capability.CREATE_CATALOGS, Capability.DELETE_CATALOGS}

        def create_catalog(self, name, path=None):
            cat = Catalog(uuid=str(_uuid.uuid4()), name=name, provider=self, path=path or [])
            self._catalogs.append(cat)
            self._set_events(cat, [])
            self.catalog_added.emit(cat)
            return cat

        def remove_catalog(self, catalog):
            self._catalogs = [c for c in self._catalogs if c.uuid != catalog.uuid]
            super().remove_catalog(catalog)

    provider = WorkflowProvider()
    model = CatalogTreeModel()

    # Find provider
    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.node_from_index(idx).provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    # Step 1: Create folder via placeholder
    folder_ph_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.placeholder_type == _PlaceholderType.FOLDER:
            folder_ph_idx = child_idx
            break
    assert folder_ph_idx is not None
    model.setData(folder_ph_idx, "MyProject", Qt.ItemDataRole.EditRole)

    # Find folder
    folder_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.name == "MyProject" and not child.is_placeholder:
            folder_idx = child_idx
            break
    assert folder_idx is not None

    # Step 2: Create catalog inside folder via placeholder
    cat_ph_idx = None
    for r in range(model.rowCount(folder_idx)):
        child_idx = model.index(r, 0, folder_idx)
        child = model.node_from_index(child_idx)
        if child.placeholder_type == _PlaceholderType.CATALOG:
            cat_ph_idx = child_idx
            break
    assert cat_ph_idx is not None
    model.setData(cat_ph_idx, "MyCatalog", Qt.ItemDataRole.EditRole)

    # Verify catalog was created with correct path
    created = [c for c in provider.catalogs() if c.name == "MyCatalog"]
    assert len(created) == 1
    assert created[0].path == ["MyProject"]

    # Step 3: Remove catalog — folder should be pruned
    provider.remove_catalog(created[0])
    non_ph_children = [
        model.node_from_index(model.index(r, 0, provider_idx))
        for r in range(model.rowCount(provider_idx))
        if not model.node_from_index(model.index(r, 0, provider_idx)).is_placeholder
    ]
    assert not any(c.name == "MyProject" for c in non_ph_children), "Folder should be pruned"
```

- [ ] **Step 2: Write explicit folder placeholder test**

```python
def test_explicit_folder_gets_placeholders(qtbot, qapp):
    """Explicit folders (like cocat rooms) should get placeholders when provider supports creation."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability
    import uuid as _uuid

    class RoomProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="RoomProvider")
            self._catalogs = []

        def catalogs(self):
            return list(self._catalogs)

        def capabilities(self, catalog=None):
            return {Capability.CREATE_CATALOGS}

        def create_catalog(self, name, path=None):
            cat = Catalog(uuid=str(_uuid.uuid4()), name=name, provider=self, path=path or [])
            self._catalogs.append(cat)
            self._set_events(cat, [])
            self.catalog_added.emit(cat)
            return cat

    provider = RoomProvider()
    model = CatalogTreeModel()

    # Simulate room creation (explicit folder)
    provider.folder_added.emit(["room-1"])

    # Find provider
    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.node_from_index(idx).provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    # Find room folder
    room_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.name == "room-1" and child.is_explicit_folder:
            room_idx = child_idx
            break
    assert room_idx is not None

    # Room should have two placeholders
    count = model.rowCount(room_idx)
    assert count == 2
    ph0 = model.node_from_index(model.index(0, 0, room_idx))
    ph1 = model.node_from_index(model.index(1, 0, room_idx))
    assert ph0.placeholder_type == _PlaceholderType.CATALOG
    assert ph1.placeholder_type == _PlaceholderType.FOLDER

    # Creating a catalog via placeholder should route with path=["room-1"]
    from PySide6.QtCore import Qt
    model.setData(model.index(0, 0, room_idx), "RoomCatalog", Qt.ItemDataRole.EditRole)
    created = [c for c in provider.catalogs() if c.name == "RoomCatalog"]
    assert len(created) == 1
    assert created[0].path == ["room-1"]
```

- [ ] **Step 3: Run integration tests**

Run: `uv run pytest tests/test_catalog_provider.py::test_full_folder_catalog_creation_workflow tests/test_catalog_provider.py::test_explicit_folder_gets_placeholders -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_catalog_provider.py
git commit -m "test(catalog): add end-to-end folder/catalog creation workflow test"
```
