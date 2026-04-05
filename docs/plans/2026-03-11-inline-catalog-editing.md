# Inline Catalog Creation & Rename Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a placeholder "New Catalog..." node and inline rename to the catalog tree, driven by provider capabilities.

**Architecture:** Add `RENAME_CATALOG` capability and `rename_catalog()` to `CatalogProvider`. Extend `_Node` with an `is_placeholder` flag. Make `CatalogTreeModel` editable (`flags`, `setData`) for placeholder and renameable nodes. Remove context-menu catalog creation from `CatalogBrowser` (replaced by the node).

**Tech Stack:** PySide6 (QAbstractItemModel editing), cocat CRDT library

---

### File Map

| File | Role | Change |
|------|------|--------|
| `SciQLop/components/catalogs/backend/provider.py` | Base provider API | Add `RENAME_CATALOG` enum, `rename_catalog()` method, `catalog_renamed` signal |
| `SciQLop/components/catalogs/ui/catalog_tree.py` | Tree model | Add placeholder node logic, `flags()` editability, `setData()` for rename+create |
| `SciQLop/components/catalogs/ui/catalog_browser.py` | Browser widget | Remove "New Catalog" context menu item + `_on_create_catalog`, wire `activated` for placeholder |
| `SciQLop/plugins/collaborative_catalogs/cocat_provider.py` | CoCat provider | Add `RENAME_CATALOG` capability, implement `rename_catalog()` |
| `SciQLop/components/catalogs/backend/dummy_provider.py` | Test provider | Add `RENAME_CATALOG` capability, implement `rename_catalog()` and `create_catalog()` |
| `tests/test_catalog_provider.py` | Tests | Add tests for all new behavior |

---

### Task 1: Add `RENAME_CATALOG` capability and `rename_catalog()` to provider base

**Files:**
- Modify: `SciQLop/components/catalogs/backend/provider.py:55-65` (Capability enum)
- Modify: `SciQLop/components/catalogs/backend/provider.py:83-90` (signals)
- Modify: `SciQLop/components/catalogs/backend/provider.py:180-182` (after `create_catalog`)
- Test: `tests/test_catalog_provider.py`

- [ ] **Step 1: Write failing test for RENAME_CATALOG capability**

```python
def test_rename_catalog_capability_exists(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import Capability
    assert Capability.RENAME_CATALOG == "rename_catalog"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_provider.py::test_rename_catalog_capability_exists -v`
Expected: FAIL with AttributeError

- [ ] **Step 3: Add RENAME_CATALOG to Capability enum**

In `provider.py`, add after `SAVE_CATALOG`:
```python
    RENAME_CATALOG = "rename_catalog"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_provider.py::test_rename_catalog_capability_exists -v`
Expected: PASS

- [ ] **Step 5: Write failing test for catalog_renamed signal and rename_catalog method**

```python
def test_provider_rename_catalog(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability

    class RenamableProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="Renamable")
            self._cat = Catalog(uuid="cat-1", name="OldName", provider=self)
            self._catalogs = [self._cat]
            self._set_events(self._cat, [])

        def catalogs(self):
            return list(self._catalogs)

        def capabilities(self, catalog=None):
            return {Capability.RENAME_CATALOG}

        def rename_catalog(self, catalog, new_name):
            catalog.name = new_name
            self.catalog_renamed.emit(catalog)

    provider = RenamableProvider()
    cat = provider.catalogs()[0]
    assert cat.name == "OldName"

    received = []
    provider.catalog_renamed.connect(lambda c: received.append(c))
    provider.rename_catalog(cat, "NewName")

    assert cat.name == "NewName"
    assert len(received) == 1
    assert received[0] is cat
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_provider.py::test_provider_rename_catalog -v`
Expected: FAIL with AttributeError on `catalog_renamed`

- [ ] **Step 7: Add catalog_renamed signal and rename_catalog method**

In `CatalogProvider` class, add `catalog_renamed` signal alongside existing signals:
```python
    catalog_renamed = Signal(object)
```

Add `rename_catalog` method after `create_catalog`:
```python
    def rename_catalog(self, catalog: Catalog, new_name: str) -> None:
        """Public API: rename a catalog. Override for backend persistence."""
        pass
```

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_provider.py::test_provider_rename_catalog -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add SciQLop/components/catalogs/backend/provider.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): add RENAME_CATALOG capability and catalog_renamed signal"
```

---

### Task 2: Add placeholder node and editability to CatalogTreeModel

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_tree.py`
- Test: `tests/test_catalog_provider.py`

- [ ] **Step 1: Write failing test — placeholder node appears for CREATE_CATALOGS providers**

```python
def test_tree_model_placeholder_node(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1)
    model = CatalogTreeModel()

    # Find our provider node
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            # Should have catalog + placeholder = 2 children
            assert model.rowCount(idx) == 2
            last_idx = model.index(model.rowCount(idx) - 1, 0, idx)
            assert model.data(last_idx) == "New Catalog..."
            return
    pytest.fail("Provider not found")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_provider.py::test_tree_model_placeholder_node -v`
Expected: FAIL (only 1 child, no placeholder)

- [ ] **Step 3: Implement placeholder node**

In `catalog_tree.py`:

Add `is_placeholder` to `_Node.__slots__` and `__init__`:
```python
    __slots__ = ("name", "parent", "children", "provider", "catalog", "is_placeholder")

    def __init__(self, name, parent=None, provider=None, catalog=None, is_placeholder=False):
        ...
        self.is_placeholder = is_placeholder
```

Add helper to check if provider supports create:
```python
    def _supports_create(self, provider: CatalogProvider) -> bool:
        from ..backend.provider import Capability
        return Capability.CREATE_CATALOGS in provider.capabilities()
```

In `_add_provider_node`, after appending the node to root, add a placeholder if the provider supports creation:
```python
        if self._supports_create(provider):
            placeholder = _Node(
                name="New Catalog...", parent=node, provider=provider,
                is_placeholder=True,
            )
            node.children.append(placeholder)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_provider.py::test_tree_model_placeholder_node -v`
Expected: PASS

- [ ] **Step 5: Write failing test — placeholder node is editable**

```python
def test_tree_model_placeholder_is_editable(qtbot, qapp):
    from PySide6.QtCore import Qt
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=0)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            placeholder_idx = model.index(0, 0, idx)
            flags = model.flags(placeholder_idx)
            assert flags & Qt.ItemFlag.ItemIsEditable
            return
    pytest.fail("Provider not found")
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_provider.py::test_tree_model_placeholder_is_editable -v`
Expected: FAIL (ItemIsEditable not set)

- [ ] **Step 7: Implement flags() for editable nodes**

Override `flags()` in `CatalogTreeModel`:
```python
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        node = index.internalPointer()
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if node.is_placeholder:
            return base | Qt.ItemFlag.ItemIsEditable
        if node.catalog is not None:
            from ..backend.provider import Capability
            if (node.provider is not None
                    and Capability.RENAME_CATALOG in node.provider.capabilities()):
                return base | Qt.ItemFlag.ItemIsEditable
        return base
```

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_provider.py::test_tree_model_placeholder_is_editable -v`
Expected: PASS

- [ ] **Step 9: Write failing test — setData on placeholder creates catalog**

```python
def test_tree_model_setdata_placeholder_creates_catalog(qtbot, qapp):
    from PySide6.QtCore import Qt
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=0)
    model = CatalogTreeModel()

    # Find provider and its placeholder
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            assert model.rowCount(idx) == 1  # just placeholder
            placeholder_idx = model.index(0, 0, idx)

            result = model.setData(placeholder_idx, "My Catalog", Qt.ItemDataRole.EditRole)
            assert result is True

            # Provider should now have 1 catalog
            assert len(provider.catalogs()) == 1
            assert provider.catalogs()[0].name == "My Catalog"

            # Tree should have catalog + placeholder = 2 children
            assert model.rowCount(idx) == 2
            return
    pytest.fail("Provider not found")
```

- [ ] **Step 10: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_provider.py::test_tree_model_setdata_placeholder_creates_catalog -v`
Expected: FAIL (setData not implemented or returns False)

- [ ] **Step 11: Implement setData and create_catalog on DummyProvider**

First, add `create_catalog` to `DummyProvider` in `dummy_provider.py`:
```python
    def create_catalog(self, name: str) -> Catalog | None:
        cat = Catalog(
            uuid=str(_uuid.uuid4()),
            name=name,
            provider=self,
            path=[],
        )
        self._catalogs.append(cat)
        self._set_events(cat, [])
        self.catalog_added.emit(cat)
        return cat
```

Then implement `setData` in `CatalogTreeModel`:
```python
    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        node = index.internalPointer()
        name = value.strip() if isinstance(value, str) else str(value).strip()
        if not name:
            return False
        if node.is_placeholder:
            node.provider.create_catalog(name)
            return True
        if node.catalog is not None and node.provider is not None:
            from ..backend.provider import Capability
            if Capability.RENAME_CATALOG in node.provider.capabilities():
                node.provider.rename_catalog(node.catalog, name)
                node.name = name
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole])
                return True
        return False
```

- [ ] **Step 12: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_provider.py::test_tree_model_setdata_placeholder_creates_catalog -v`
Expected: PASS

- [ ] **Step 13: Write failing test — setData on catalog node renames it**

```python
def test_tree_model_setdata_renames_catalog(qtbot, qapp):
    from PySide6.QtCore import Qt
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability

    class RenamableProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="Renamable")
            self._cat = Catalog(uuid="cat-1", name="OldName", provider=self)
            self._catalogs = [self._cat]
            self._set_events(self._cat, [])

        def catalogs(self):
            return list(self._catalogs)

        def capabilities(self, catalog=None):
            return {Capability.RENAME_CATALOG}

        def rename_catalog(self, catalog, new_name):
            catalog.name = new_name
            self.catalog_renamed.emit(catalog)

    provider = RenamableProvider()
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            cat_idx = model.index(0, 0, idx)
            assert model.data(cat_idx) == "OldName"

            result = model.setData(cat_idx, "NewName", Qt.ItemDataRole.EditRole)
            assert result is True
            assert model.data(cat_idx) == "NewName"
            assert provider.catalogs()[0].name == "NewName"
            return
    pytest.fail("Provider not found")
```

- [ ] **Step 14: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_provider.py::test_tree_model_setdata_renames_catalog -v`
Expected: PASS (already implemented in step 11)

- [ ] **Step 15: Write failing test — empty/whitespace edit is rejected**

```python
def test_tree_model_setdata_rejects_empty_name(qtbot, qapp):
    from PySide6.QtCore import Qt
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=0)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            placeholder_idx = model.index(0, 0, idx)
            assert model.setData(placeholder_idx, "", Qt.ItemDataRole.EditRole) is False
            assert model.setData(placeholder_idx, "   ", Qt.ItemDataRole.EditRole) is False
            assert len(provider.catalogs()) == 0
            return
    pytest.fail("Provider not found")
```

- [ ] **Step 16: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_provider.py::test_tree_model_setdata_rejects_empty_name -v`
Expected: PASS (already handled by `if not name: return False`)

- [ ] **Step 17: Write test — placeholder node renders with italic font**

```python
def test_tree_model_placeholder_italic(qtbot, qapp):
    from PySide6.QtCore import Qt
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=0)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            placeholder_idx = model.index(0, 0, idx)
            font = model.data(placeholder_idx, Qt.ItemDataRole.FontRole)
            assert font is not None
            assert font.italic()
            return
    pytest.fail("Provider not found")
```

- [ ] **Step 18: Add FontRole and ForegroundRole for placeholder in data()**

In `CatalogTreeModel.data()`, add handling for `FontRole` and `ForegroundRole`:
```python
        if role == Qt.ItemDataRole.FontRole:
            node = index.internalPointer()
            if node.is_placeholder:
                from PySide6.QtGui import QFont
                font = QFont()
                font.setItalic(True)
                return font
            return None
        if role == Qt.ItemDataRole.ForegroundRole:
            node = index.internalPointer()
            if node.is_placeholder:
                from PySide6.QtGui import QColor
                return QColor(128, 128, 128)
            return None
```

- [ ] **Step 19: Run all new tests**

Run: `uv run pytest tests/test_catalog_provider.py -k "placeholder or rename" -v`
Expected: All PASS

- [ ] **Step 20: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_tree.py SciQLop/components/catalogs/backend/dummy_provider.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): add placeholder node and inline editing to tree model"
```

---

### Task 3: Implement rename_catalog in CocatCatalogProvider

**Files:**
- Modify: `SciQLop/plugins/collaborative_catalogs/cocat_provider.py`
- Test: `tests/test_catalog_provider.py`

- [ ] **Step 1: Write failing test**

```python
def test_cocat_provider_has_rename_capability(qtbot, qapp):
    import importlib
    spec = importlib.util.spec_from_file_location(
        "cocat_provider",
        "SciQLop/plugins/collaborative_catalogs/cocat_provider.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from SciQLop.components.catalogs.backend.provider import Capability
    caps = mod.CocatCatalogProvider.capabilities(None)
    assert Capability.RENAME_CATALOG in caps
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_provider.py::test_cocat_provider_has_rename_capability -v`
Expected: FAIL

- [ ] **Step 3: Add RENAME_CATALOG and implement rename_catalog**

In `cocat_provider.py`, add `RENAME_CATALOG` to capabilities:
```python
    def capabilities(self, catalog: Catalog | None = None) -> set[str]:
        return {
            Capability.EDIT_EVENTS,
            Capability.CREATE_EVENTS,
            Capability.DELETE_EVENTS,
            Capability.CREATE_CATALOGS,
            Capability.RENAME_CATALOG,
        }
```

Add `rename_catalog` method:
```python
    def rename_catalog(self, catalog: Catalog, new_name: str) -> None:
        cocat_cat = self._room.get_catalogue(catalog.name)
        cocat_cat.name = new_name
        catalog.name = new_name
        self.catalog_renamed.emit(catalog)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_provider.py::test_cocat_provider_has_rename_capability -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/plugins/collaborative_catalogs/cocat_provider.py tests/test_catalog_provider.py
git commit -m "feat(cocat): add catalog rename support"
```

---

### Task 4: Update CatalogBrowser — remove context menu creation, wire placeholder activation

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py`
- Test: `tests/test_catalog_provider.py`

- [ ] **Step 1: Remove _on_create_catalog and context menu "New Catalog" item**

In `catalog_browser.py`, remove the `_on_create_catalog` method and the "New Catalog" context menu item (the lines added earlier):

Remove from `_on_tree_context_menu`:
```python
        if Capability.CREATE_CATALOGS in caps and node.catalog is None:
            create_action = menu.addAction("New Catalog")
            create_action.triggered.connect(lambda: self._on_create_catalog(node.provider))
```

Remove the `_on_create_catalog` method entirely.

Remove the `QInputDialog` import (no longer needed).

- [ ] **Step 2: Wire double-click on placeholder to start editing**

In `CatalogBrowser.__init__`, after the tree view setup, connect `doubleClicked`:
```python
        self._catalog_tree.doubleClicked.connect(self._on_tree_double_clicked)
```

Add the handler:
```python
    def _on_tree_double_clicked(self, proxy_index: QModelIndex) -> None:
        source_index = self._proxy_model.mapToSource(proxy_index)
        node = self._tree_model.node_from_index(source_index)
        if node.is_placeholder:
            self._catalog_tree.edit(proxy_index)
```

- [ ] **Step 3: Make catalog browser ignore placeholder selection**

In `_on_catalog_selected`, add an early return for placeholder nodes:
```python
        if node.is_placeholder:
            return
```

- [ ] **Step 4: Write test — placeholder selection doesn't populate event table**

```python
def test_catalog_browser_placeholder_selection_ignored(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=5)
    browser = CatalogBrowser()
    qtbot.addWidget(browser)

    # Select the placeholder node (last child of provider)
    tree = browser._catalog_tree
    proxy = tree.model()
    for i in range(proxy.rowCount()):
        idx = proxy.index(i, 0)
        src = proxy.mapToSource(idx)
        node = browser._tree_model.node_from_index(src)
        if node.provider is provider:
            last_child = proxy.index(proxy.rowCount(idx) - 1, 0, idx)
            tree.setCurrentIndex(last_child)
            break

    # Event table should be empty (placeholder doesn't represent a catalog)
    assert browser._event_model.rowCount() == 0
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_provider.py::test_catalog_browser_placeholder_selection_ignored -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_browser.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): wire placeholder activation and remove context menu creation"
```

---

### Task 5: Connect catalog_renamed signal in tree model

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_tree.py`
- Test: `tests/test_catalog_provider.py`

- [ ] **Step 1: Write failing test — rename via provider updates tree display**

```python
def test_tree_model_rename_via_provider_updates_display(qtbot, qapp):
    from PySide6.QtCore import Qt
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability

    class ExtRenamable(CatalogProvider):
        def __init__(self):
            super().__init__(name="ExtRenamable")
            self._cat = Catalog(uuid="cat-1", name="Before", provider=self)
            self._catalogs = [self._cat]
            self._set_events(self._cat, [])

        def catalogs(self):
            return list(self._catalogs)

        def capabilities(self, catalog=None):
            return {Capability.RENAME_CATALOG}

        def rename_catalog(self, catalog, new_name):
            catalog.name = new_name
            self.catalog_renamed.emit(catalog)

    provider = ExtRenamable()
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            cat_idx = model.index(0, 0, idx)
            assert model.data(cat_idx) == "Before"

            # Rename externally (e.g. from another collaborator via CRDT)
            provider.rename_catalog(provider._cat, "After")

            assert model.data(cat_idx) == "After"
            return
    pytest.fail("Provider not found")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_provider.py::test_tree_model_rename_via_provider_updates_display -v`
Expected: FAIL (tree still shows "Before" because node.name wasn't updated)

- [ ] **Step 3: Connect catalog_renamed signal in _add_provider_node**

In `_add_provider_node`, add a connection for `catalog_renamed`:
```python
        on_renamed = lambda cat, p=provider, n=node: self._on_catalog_renamed(p, n, cat)
        provider.catalog_renamed.connect(on_renamed)
```

Add to the stored connections list:
```python
        self._provider_connections[id(provider)] = [
            (provider.catalog_added, on_added),
            (provider.catalog_removed, on_removed),
            (provider.dirty_changed, on_dirty),
            (provider.catalog_renamed, on_renamed),
        ]
```

Add the handler:
```python
    def _on_catalog_renamed(self, provider: CatalogProvider, pnode: _Node, catalog: object) -> None:
        cat_node = self._find_catalog_node(pnode, catalog)
        if cat_node is not None:
            cat_node.name = catalog.name
            idx = self.createIndex(cat_node.row(), 0, cat_node)
            self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_provider.py::test_tree_model_rename_via_provider_updates_display -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_tree.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): sync tree display on catalog_renamed signal"
```

---

### Task 6: Run full test suite and verify

- [ ] **Step 1: Run all catalog tests**

Run: `uv run pytest tests/test_catalog_provider.py -v`
Expected: All PASS

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: All PASS (no regressions)

- [ ] **Step 3: Final commit if any fixups needed**
