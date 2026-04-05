# Catalog Path Attribute Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `path: list[str]` to `Catalog` for hierarchical organization within providers, with folder nodes in the tree UI.

**Architecture:** The `Catalog` dataclass gets a `path` field. `CatalogTreeModel` builds intermediate folder `_Node`s from path segments. `TscatCatalogProvider` reads `path__` from tscat entities. Folder nodes are non-selectable for events (existing `catalog is None` check handles this).

**Tech Stack:** Python, PySide6, dataclasses, tscat_gui

---

### Task 1: Add `path` field to `Catalog` dataclass

**Files:**
- Modify: `SciQLop/components/catalogs/backend/provider.py:63-68`
- Test: `tests/test_catalog_provider.py`

**Step 1: Write the failing test**

Add to `tests/test_catalog_provider.py`:

```python
def test_catalog_path_default(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import Catalog
    cat = Catalog(uuid="cat-1", name="My Catalog")
    assert cat.path == []


def test_catalog_path_explicit(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import Catalog
    cat = Catalog(uuid="cat-1", name="My Catalog", path=["MMS", "Magnetosheath"])
    assert cat.path == ["MMS", "Magnetosheath"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog_provider.py::test_catalog_path_default tests/test_catalog_provider.py::test_catalog_path_explicit -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'path'`

**Step 3: Write minimal implementation**

In `SciQLop/components/catalogs/backend/provider.py`, add import and field:

```python
from dataclasses import dataclass, field
```

Change the `Catalog` dataclass to:

```python
@dataclass
class Catalog:
    uuid: str
    name: str
    provider: CatalogProvider | None = None
    path: list[str] = field(default_factory=list)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalog_provider.py::test_catalog_path_default tests/test_catalog_provider.py::test_catalog_path_explicit -v`
Expected: PASS

**Step 5: Run full test suite to check backward compat**

Run: `pytest tests/test_catalog_provider.py -v`
Expected: All existing tests still PASS

**Step 6: Commit**

```bash
git add SciQLop/components/catalogs/backend/provider.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): add path field to Catalog dataclass"
```

---

### Task 2: Update `CatalogTreeModel` to build folder nodes from paths

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_tree.py`
- Test: `tests/test_catalog_provider.py`

**Step 1: Write the failing tests**

Add to `tests/test_catalog_provider.py`:

```python
def _make_provider_with_paths(qapp):
    """Helper: provider with catalogs at various path depths."""
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, CatalogEvent
    import uuid as _uuid

    class PathProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="PathProvider")
            self._catalogs = [
                Catalog(uuid=str(_uuid.uuid4()), name="Root Cat", provider=self, path=[]),
                Catalog(uuid=str(_uuid.uuid4()), name="Deep Cat", provider=self, path=["A", "B"]),
                Catalog(uuid=str(_uuid.uuid4()), name="Sibling Cat", provider=self, path=["A", "B"]),
                Catalog(uuid=str(_uuid.uuid4()), name="Other Cat", provider=self, path=["A", "C"]),
            ]
            for cat in self._catalogs:
                self._set_events(cat, [])

        def catalogs(self):
            return list(self._catalogs)

    return PathProvider()


def test_tree_model_folder_nodes(qtbot, qapp):
    """Catalogs with path segments should create intermediate folder nodes."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel

    provider = _make_provider_with_paths(qapp)
    model = CatalogTreeModel()

    # Find our provider node
    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    # Provider should have 2 direct children: "Root Cat" (catalog) and "A" (folder)
    assert model.rowCount(provider_idx) == 2

    # Find folder "A"
    folder_a_idx = None
    root_cat_idx = None
    for i in range(model.rowCount(provider_idx)):
        child_idx = model.index(i, 0, provider_idx)
        node = model.node_from_index(child_idx)
        if node.name == "A" and node.catalog is None:
            folder_a_idx = child_idx
        elif node.name == "Root Cat" and node.catalog is not None:
            root_cat_idx = child_idx
    assert folder_a_idx is not None, "Folder 'A' not found"
    assert root_cat_idx is not None, "Root Cat not found"

    # Folder A should have 2 children: "B" (folder) and "C" (folder)
    assert model.rowCount(folder_a_idx) == 2

    # Find folder "B" under "A"
    folder_b_idx = None
    for i in range(model.rowCount(folder_a_idx)):
        child_idx = model.index(i, 0, folder_a_idx)
        node = model.node_from_index(child_idx)
        if node.name == "B" and node.catalog is None:
            folder_b_idx = child_idx
    assert folder_b_idx is not None, "Folder 'B' not found under 'A'"

    # Folder B should have 2 catalogs: "Deep Cat" and "Sibling Cat"
    assert model.rowCount(folder_b_idx) == 2


def test_tree_model_folder_not_selectable_for_events(qtbot, qapp):
    """Folder nodes should have catalog=None."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel

    provider = _make_provider_with_paths(qapp)
    model = CatalogTreeModel()

    # Find folder "A" under our provider
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            for j in range(model.rowCount(idx)):
                child_idx = model.index(j, 0, idx)
                child = model.node_from_index(child_idx)
                if child.name == "A":
                    assert child.catalog is None
                    return
    pytest.fail("Folder 'A' not found")
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_catalog_provider.py::test_tree_model_folder_nodes tests/test_catalog_provider.py::test_tree_model_folder_not_selectable_for_events -v`
Expected: FAIL — catalogs are added flat, no folder "A" node exists

**Step 3: Implement folder node creation in `CatalogTreeModel`**

In `SciQLop/components/catalogs/ui/catalog_tree.py`, add the `_find_or_create_folder` method and update `_add_provider_node`:

```python
def _find_or_create_folder(self, parent: _Node, name: str, provider: CatalogProvider) -> _Node:
    """Find existing folder child or create a new one."""
    for child in parent.children:
        if child.catalog is None and child.name == name:
            return child
    folder = _Node(name=name, parent=parent, provider=provider)
    parent.children.append(folder)
    return folder

def _add_provider_node(self, provider: CatalogProvider) -> _Node:
    node = _Node(name=provider.name, parent=self._root, provider=provider)
    for cat in provider.catalogs():
        target = node
        for segment in cat.path:
            target = self._find_or_create_folder(target, segment, provider)
        child = _Node(name=cat.name, parent=target, provider=provider, catalog=cat)
        target.children.append(child)
    self._root.children.append(node)

    provider.catalog_added.connect(lambda cat, p=provider, n=node: self._on_catalog_added(p, n, cat))
    provider.catalog_removed.connect(lambda cat, p=provider, n=node: self._on_catalog_removed(p, n, cat))
    return node
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_catalog_provider.py::test_tree_model_folder_nodes tests/test_catalog_provider.py::test_tree_model_folder_not_selectable_for_events -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `pytest tests/test_catalog_provider.py -v`
Expected: All PASS (existing tests use `path=[]` implicitly, so no folder nodes are created)

**Step 6: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_tree.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): build folder nodes from catalog path in tree model"
```

---

### Task 3: Handle dynamic catalog addition with paths

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_tree.py`
- Test: `tests/test_catalog_provider.py`

**Step 1: Write the failing test**

```python
def test_tree_model_dynamic_add_with_path(qtbot, qapp):
    """Dynamically added catalogs with paths should create folder nodes."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, CatalogEvent
    import uuid as _uuid

    class DynProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="DynProvider")
            self._catalogs = []

        def catalogs(self):
            return list(self._catalogs)

        def add_catalog(self, cat):
            self._catalogs.append(cat)
            self._set_events(cat, [])
            self.catalog_added.emit(cat)

    provider = DynProvider()
    model = CatalogTreeModel()

    # Find provider node
    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None
    assert model.rowCount(provider_idx) == 0

    # Add a catalog with path
    cat = Catalog(uuid=str(_uuid.uuid4()), name="New Cat", provider=provider, path=["X", "Y"])
    provider.add_catalog(cat)

    # Provider should now have folder "X"
    assert model.rowCount(provider_idx) == 1
    x_idx = model.index(0, 0, provider_idx)
    assert model.data(x_idx) == "X"

    # "X" should have folder "Y"
    assert model.rowCount(x_idx) == 1
    y_idx = model.index(0, 0, x_idx)
    assert model.data(y_idx) == "Y"

    # "Y" should have "New Cat"
    assert model.rowCount(y_idx) == 1
    cat_idx = model.index(0, 0, y_idx)
    assert model.data(cat_idx) == "New Cat"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog_provider.py::test_tree_model_dynamic_add_with_path -v`
Expected: FAIL — `_on_catalog_added` adds catalogs flat under the provider node

**Step 3: Update `_on_catalog_added` to use folder resolution**

In `SciQLop/components/catalogs/ui/catalog_tree.py`, replace `_on_catalog_added`:

```python
def _on_catalog_added(self, provider: CatalogProvider, pnode: _Node, catalog: object) -> None:
    target = pnode
    target_index = self.createIndex(pnode.row(), 0, pnode)
    for segment in catalog.path:
        existing = None
        for child in target.children:
            if child.catalog is None and child.name == segment:
                existing = child
                break
        if existing is not None:
            target = existing
            target_index = self.createIndex(existing.row(), 0, existing)
        else:
            row = len(target.children)
            self.beginInsertRows(target_index, row, row)
            folder = _Node(name=segment, parent=target, provider=provider)
            target.children.append(folder)
            self.endInsertRows()
            target = folder
            target_index = self.createIndex(folder.row(), 0, folder)

    row = len(target.children)
    self.beginInsertRows(target_index, row, row)
    child = _Node(name=catalog.name, parent=target, provider=provider, catalog=catalog)
    target.children.append(child)
    self.endInsertRows()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalog_provider.py::test_tree_model_dynamic_add_with_path -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_tree.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): handle dynamic catalog addition with path folders"
```

---

### Task 4: Prune empty folders on catalog removal

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_tree.py`
- Test: `tests/test_catalog_provider.py`

**Step 1: Write the failing test**

```python
def test_tree_model_prune_empty_folders(qtbot, qapp):
    """Removing the last catalog in a folder should prune empty ancestor folders."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog
    import uuid as _uuid

    class PruneProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="PruneProvider")
            self._cat = Catalog(
                uuid=str(_uuid.uuid4()), name="Only Cat",
                provider=self, path=["X", "Y"],
            )
            self._catalogs = [self._cat]
            self._set_events(self._cat, [])

        def catalogs(self):
            return list(self._catalogs)

        def remove_catalog(self, cat):
            self._catalogs.remove(cat)
            self.catalog_removed.emit(cat)

    provider = PruneProvider()
    model = CatalogTreeModel()

    # Find provider node
    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None
    assert model.rowCount(provider_idx) == 1  # folder "X"

    # Remove the only catalog
    provider.remove_catalog(provider._cat)

    # Provider should now have 0 children (folders pruned)
    assert model.rowCount(provider_idx) == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog_provider.py::test_tree_model_prune_empty_folders -v`
Expected: FAIL — current `_on_catalog_removed` only searches direct children of the provider node

**Step 3: Update `_on_catalog_removed` with recursive search and pruning**

In `SciQLop/components/catalogs/ui/catalog_tree.py`, replace `_on_catalog_removed`:

```python
def _on_catalog_removed(self, provider: CatalogProvider, pnode: _Node, catalog: object) -> None:
    self._remove_catalog_recursive(pnode, catalog)

def _remove_catalog_recursive(self, node: _Node, catalog: object) -> bool:
    """Find and remove catalog node, then prune empty folders. Returns True if found."""
    for i, child in enumerate(node.children):
        if child.catalog is catalog:
            parent_index = self.createIndex(node.row(), 0, node) if node.parent is not None else QModelIndex()
            self.beginRemoveRows(parent_index, i, i)
            node.children.pop(i)
            self.endRemoveRows()
            # Prune empty folder ancestors
            self._prune_if_empty(node)
            return True
        if child.catalog is None and self._remove_catalog_recursive(child, catalog):
            return True
    return False

def _prune_if_empty(self, node: _Node) -> None:
    """Remove node if it's an empty folder (not provider, not root)."""
    if node.parent is None:
        return
    if node.catalog is not None:
        return  # not a folder
    if node.parent.parent is None:
        return  # node is a provider node, don't prune
    if len(node.children) > 0:
        return  # not empty
    parent = node.parent
    i = parent.children.index(node)
    parent_index = self.createIndex(parent.row(), 0, parent) if parent.parent is not None else QModelIndex()
    self.beginRemoveRows(parent_index, i, i)
    parent.children.pop(i)
    self.endRemoveRows()
    self._prune_if_empty(parent)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalog_provider.py::test_tree_model_prune_empty_folders -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `pytest tests/test_catalog_provider.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_tree.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): prune empty folder nodes on catalog removal"
```

---

### Task 5: Update `TscatCatalogProvider` to read `path__`

**Files:**
- Modify: `SciQLop/plugins/tscat_catalogs/tscat_provider.py`

**Step 1: Update `catalogs()` method**

In `TscatCatalogProvider.catalogs()`, extract `path__` from each entity:

```python
def catalogs(self) -> list[Catalog]:
    if self._catalog_cache is not None:
        return list(self._catalog_cache)
    self._catalog_cache = []
    self._known_uuids = set()
    for row in range(self._root_model.rowCount()):
        idx = self._root_model.index(row, 0)
        entity = idx.data(EntityRole)
        if entity is None:
            continue
        name = idx.data()
        if name == "Trash":
            continue
        path = getattr(entity, "path__", None)
        if not isinstance(path, list) or not all(isinstance(s, str) for s in path):
            path = []
        cat = Catalog(
            uuid=entity.uuid,
            name=name if name else getattr(entity, "name", entity.uuid),
            provider=self,
            path=path,
        )
        self._catalog_cache.append(cat)
        self._known_uuids.add(entity.uuid)
    return list(self._catalog_cache)
```

Note: the `TscatRootModel` may expose catalogs at top level or nested in folders. If catalogs inside tscat folders are not visible at the top level of `self._root_model`, this iteration will miss them. In that case, a recursive walk of the tscat root model is needed:

```python
def _collect_catalogs_recursive(self, parent_model, parent_index=None):
    """Recursively walk TscatRootModel to find all catalog entities."""
    catalogs = []
    row_count = parent_model.rowCount(parent_index) if parent_index else parent_model.rowCount()
    for row in range(row_count):
        idx = parent_model.index(row, 0, parent_index) if parent_index else parent_model.index(row, 0)
        entity = idx.data(EntityRole)
        name = idx.data()
        if name == "Trash":
            continue
        if entity is not None:
            catalogs.append((entity, name))
        # Recurse into children (folders)
        if parent_model.rowCount(idx) > 0:
            catalogs.extend(self._collect_catalogs_recursive(parent_model, idx))
    return catalogs
```

Verify at implementation time which approach is needed by checking whether `self._root_model.rowCount()` returns only top-level items or all catalogs.

**Step 2: Run the application manually to verify tscat catalogs appear with correct hierarchy**

Run: `python -m SciQLop.app`
Expected: TSCat catalogs that have `path__` set should appear nested in folders in the CatalogBrowser tree.

**Step 3: Commit**

```bash
git add SciQLop/plugins/tscat_catalogs/tscat_provider.py
git commit -m "feat(catalogs): read path__ from tscat entities into Catalog.path"
```

---

### Task 6: Update `DummyProvider` to support paths (optional, for testing)

**Files:**
- Modify: `SciQLop/components/catalogs/backend/dummy_provider.py`

**Step 1: Add optional `paths` parameter to `DummyProvider`**

```python
class DummyProvider(CatalogProvider):
    def __init__(self, num_catalogs: int = 1, events_per_catalog: int = 100,
                 paths: list[list[str]] | None = None,
                 parent: QObject | None = None):
        super().__init__(name="DummyProvider", parent=parent)
        self._catalogs: list[Catalog] = []
        base = datetime(2020, 1, 1, tzinfo=timezone.utc)
        for c in range(num_catalogs):
            path = paths[c] if paths and c < len(paths) else []
            cat = Catalog(
                uuid=str(_uuid.uuid4()),
                name=f"Catalog-{c}",
                provider=self,
                path=path,
            )
            ...
```

**Step 2: Run full test suite**

Run: `pytest tests/test_catalog_provider.py -v`
Expected: All PASS (default `paths=None` means `path=[]` for all, backward compat)

**Step 3: Commit**

```bash
git add SciQLop/components/catalogs/backend/dummy_provider.py
git commit -m "feat(catalogs): add paths parameter to DummyProvider"
```
