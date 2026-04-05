# Welcome Page WebEngine Migration — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Qt Widgets-based welcome page with a QWebEngineView rendering a Jinja2 HTML template, using QWebChannel for Python↔JS communication.

**Architecture:** A Python `WelcomeBackend` QObject exposes workspace/example data and actions (open, delete, duplicate, create) as slots. A Jinja2 HTML template renders the page with CSS grid for cards, CSS transitions for hover, and a slide-in details sidebar. JS calls Python slots via QWebChannel. The existing Jinja2 infrastructure from the theming system is reused for template rendering, and palette colors are injected so the page matches the current theme.

**Tech Stack:** PySide6 QWebEngineView + QWebChannel (already a dependency via JupyterLab), Jinja2 (already used for QSS theming), HTML/CSS/JS (no framework — vanilla, keep it simple).

---

## File Structure

### New files
| File | Responsibility |
|------|----------------|
| `SciQLop/components/welcome/backend.py` | `WelcomeBackend(QObject)` — exposes data + actions as slots for QWebChannel |
| `SciQLop/components/welcome/web_welcome_page.py` | `WebWelcomePage(QWidget)` — hosts QWebEngineView + QWebChannel wiring |
| `SciQLop/resources/welcome/welcome.html.j2` | Main Jinja2 HTML template |
| `SciQLop/resources/welcome/welcome.css` | Stylesheet (uses CSS custom properties injected from palette) |
| `SciQLop/resources/welcome/welcome.js` | JS: QWebChannel init, card interactions, details panel toggle |
| `tests/test_welcome_backend.py` | Tests for the backend QObject (data exposure, slot calls) |

### Modified files
| File | Change |
|------|--------|
| `SciQLop/components/welcome/__init__.py` | Export `WebWelcomePage` instead of `WelcomePage` |
| `SciQLop/core/ui/mainwindow.py` | Import `WebWelcomePage` (single line change) |

### Preserved files (no changes, kept for reference/rollback)
All existing widget-based welcome files stay in place. The old `WelcomePage` class remains importable but is no longer wired into the main window. This allows easy rollback if needed.

---

## Chunk 1: Backend QObject

### Task 1: WelcomeBackend — workspace data slots

**Files:**
- Create: `SciQLop/components/welcome/backend.py`
- Create: `tests/test_welcome_backend.py`

The backend exposes all data the HTML page needs as QWebChannel-compatible slots returning JSON-serializable types.

- [ ] **Step 1: Write failing test for workspace listing**

```python
# tests/test_welcome_backend.py
from .fixtures import *
import json


def test_welcome_backend_list_workspaces(qtbot, qapp):
    from SciQLop.components.welcome.backend import WelcomeBackend

    backend = WelcomeBackend()
    result = backend.list_workspaces()
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    # Each entry must have these keys
    for ws in parsed:
        assert "name" in ws
        assert "directory" in ws
        assert "last_used" in ws
        assert "image" in ws
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_welcome_backend.py::test_welcome_backend_list_workspaces -v`
Expected: FAIL — `ImportError: cannot import name 'WelcomeBackend'`

- [ ] **Step 3: Implement WelcomeBackend with list_workspaces**

```python
# SciQLop/components/welcome/backend.py
from __future__ import annotations

import json
import os
from PySide6.QtCore import QObject, Slot, Signal

from SciQLop.components.workspaces.backend.workspaces_manager import workspaces_manager_instance
from SciQLop.components.workspaces.backend.example import Example


def _workspace_to_dict(ws) -> dict:
    return {
        "name": ws.name,
        "directory": str(ws.directory),
        "description": ws.description,
        "last_used": ws.last_used,
        "last_modified": ws.last_modified,
        "image": ws.image if ws.image and os.path.exists(ws.image) else "",
        "is_default": ws.default_workspace,
    }


def _example_to_dict(ex: Example) -> dict:
    return {
        "name": ex.name,
        "description": ex.description,
        "image": ex.image if ex.image and os.path.exists(ex.image) else "",
        "tags": ex.tags,
        "directory": str(ex.directory),
    }


class WelcomeBackend(QObject):
    """Python backend exposed to the welcome page via QWebChannel."""

    workspace_list_changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

    @Slot(result=str)
    def list_workspaces(self) -> str:
        manager = workspaces_manager_instance()
        workspaces = manager.list_workspaces()
        workspaces.sort(key=lambda ws: ws.last_used, reverse=True)
        return json.dumps([_workspace_to_dict(ws) for ws in workspaces])

    @Slot(result=str)
    def list_examples(self) -> str:
        examples = Example.discover()
        return json.dumps([_example_to_dict(ex) for ex in examples])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_welcome_backend.py::test_welcome_backend_list_workspaces -v`
Expected: PASS

- [ ] **Step 5: Write failing test for example listing**

```python
def test_welcome_backend_list_examples(qtbot, qapp):
    from SciQLop.components.welcome.backend import WelcomeBackend

    backend = WelcomeBackend()
    result = backend.list_examples()
    parsed = json.loads(result)
    assert isinstance(parsed, list)
    for ex in parsed:
        assert "name" in ex
        assert "description" in ex
        assert "tags" in ex
```

- [ ] **Step 6: Run test, verify pass**

Run: `uv run pytest tests/test_welcome_backend.py -v`
Expected: PASS (implementation already in step 3)

- [ ] **Step 7: Commit**

```bash
git add SciQLop/components/welcome/backend.py tests/test_welcome_backend.py
git commit -m "feat(welcome): add WelcomeBackend QObject for WebChannel data exposure"
```

### Task 2: WelcomeBackend — action slots

**Files:**
- Modify: `SciQLop/components/welcome/backend.py`
- Modify: `tests/test_welcome_backend.py`

- [ ] **Step 1: Write failing test for create_workspace slot**

```python
def test_welcome_backend_create_workspace(qtbot, qapp):
    from SciQLop.components.welcome.backend import WelcomeBackend

    backend = WelcomeBackend()
    initial = json.loads(backend.list_workspaces())
    backend.create_workspace()
    updated = json.loads(backend.list_workspaces())
    assert len(updated) == len(initial) + 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_welcome_backend.py::test_welcome_backend_create_workspace -v`
Expected: FAIL — `AttributeError: 'WelcomeBackend' object has no attribute 'create_workspace'`

- [ ] **Step 3: Add action slots to WelcomeBackend**

Add to `backend.py`:

```python
    @Slot(str)
    def open_workspace(self, directory: str) -> None:
        manager = workspaces_manager_instance()
        for ws in manager.list_workspaces():
            if str(ws.directory) == directory:
                manager.load_workspace(ws)
                return

    @Slot()
    def create_workspace(self) -> None:
        workspaces_manager_instance().create_workspace()

    @Slot(str)
    def delete_workspace(self, directory: str) -> None:
        workspaces_manager_instance().delete_workspace(directory)
        self.workspace_list_changed.emit()

    @Slot(str)
    def duplicate_workspace(self, directory: str) -> None:
        workspaces_manager_instance().duplicate_workspace(directory)
        self.workspace_list_changed.emit()

    @Slot(str)
    def open_example(self, directory: str) -> None:
        workspaces_manager_instance().load_example(directory)

    @Slot(str, str)
    def update_workspace_field(self, directory: str, field_json: str) -> None:
        """Update a workspace field. field_json is {"field": "name", "value": "new name"}."""
        manager = workspaces_manager_instance()
        update = json.loads(field_json)
        for ws in manager.list_workspaces():
            if str(ws.directory) == directory:
                field, value = update["field"], update["value"]
                if hasattr(ws, field):
                    setattr(ws, field, value)
                break
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_welcome_backend.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/welcome/backend.py tests/test_welcome_backend.py
git commit -m "feat(welcome): add workspace action slots to WelcomeBackend"
```

### Task 3: WelcomeBackend — palette and quickstart data

**Files:**
- Modify: `SciQLop/components/welcome/backend.py`

The HTML page needs the current theme colors and quickstart shortcuts.

- [ ] **Step 1: Add palette and quickstart slots**

```python
    @Slot(result=str)
    def get_palette(self) -> str:
        from SciQLop.components.theming.palette import SCIQLOP_PALETTE
        return json.dumps(SCIQLOP_PALETTE)

    @Slot(result=str)
    def list_quickstart_shortcuts(self) -> str:
        from SciQLop.core.sciqlop_application import sciqlop_app
        shortcuts = sciqlop_app().quickstart_shortcuts
        # Icons can't be serialized — just send name + description
        return json.dumps([
            {"name": name, "description": info.get("description", "")}
            for name, info in shortcuts.items()
        ])

    @Slot(str)
    def run_quickstart(self, name: str) -> None:
        from SciQLop.core.sciqlop_application import sciqlop_app
        shortcuts = sciqlop_app().quickstart_shortcuts
        if name in shortcuts:
            shortcuts[name]["callback"]()
```

- [ ] **Step 2: Run tests to verify nothing broke**

Run: `uv run pytest tests/test_welcome_backend.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add SciQLop/components/welcome/backend.py
git commit -m "feat(welcome): add palette and quickstart slots to WelcomeBackend"
```

---

## Chunk 2: HTML Template and Static Assets

### Task 4: Jinja2 HTML template

**Files:**
- Create: `SciQLop/resources/welcome/welcome.html.j2`

The template is rendered server-side (Python) with palette colors injected as CSS custom properties. Card data is loaded client-side via QWebChannel calls.

- [ ] **Step 1: Create the HTML template**

```html
{# SciQLop/resources/welcome/welcome.html.j2 #}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SciQLop Welcome</title>
    <style>
        :root {
            {% for name, color in palette.items() %}
            --palette-{{ name | replace(' ', '-') | lower }}: {{ color }};
            {% endfor %}
        }
    </style>
    <link rel="stylesheet" href="welcome.css">
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
</head>
<body>
    <div id="main">
        <div id="sections">
            <section id="quickstart">
                <h2>Quick start</h2>
                <div class="cards-row" id="quickstart-cards"></div>
            </section>

            <section id="recent-workspaces">
                <div class="section-header">
                    <h2>Recent workspaces</h2>
                    <input type="text" id="workspace-filter" placeholder="Filter...">
                </div>
                <div class="cards-grid" id="workspace-cards"></div>
            </section>

            <section id="examples">
                <div class="section-header">
                    <h2>Examples</h2>
                    <input type="text" id="example-filter" placeholder="Filter...">
                </div>
                <div class="cards-grid" id="example-cards"></div>
            </section>
        </div>

        <aside id="details-panel" class="hidden">
            <h2 id="details-title">Details</h2>
            <hr>
            <div id="details-content"></div>
        </aside>
    </div>

    <script src="welcome.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/resources/welcome/welcome.html.j2
git commit -m "feat(welcome): add Jinja2 HTML template for welcome page"
```

### Task 5: CSS stylesheet

**Files:**
- Create: `SciQLop/resources/welcome/welcome.css`

Uses CSS custom properties (injected from palette) for theme-aware styling. CSS grid for card layout. CSS transitions for hover and details panel slide-in.

- [ ] **Step 1: Create the CSS file**

```css
/* SciQLop/resources/welcome/welcome.css */

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: system-ui, -apple-system, sans-serif;
    background-color: var(--palette-base);
    color: var(--palette-text);
    overflow-y: auto;
    overflow-x: hidden;
}

#main {
    display: flex;
    min-height: 100vh;
}

#sections {
    flex: 1;
    padding: 16px;
    overflow-y: auto;
    transition: margin-right 0.2s ease;
}

#sections.with-details {
    margin-right: 420px;
}

/* --- Sections --- */

section {
    margin-bottom: 24px;
}

.section-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 8px;
}

.section-header h2 {
    flex: 1;
}

.section-header input {
    max-width: 200px;
    padding: 4px 8px;
    border: 1px solid var(--palette-mid);
    border-radius: 4px;
    background: var(--palette-base);
    color: var(--palette-text);
}

h2 {
    font-size: 1.2em;
    font-weight: 600;
    margin-bottom: 8px;
    color: var(--palette-text);
}

/* --- Card grid --- */

.cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 200px));
    gap: 12px;
}

.cards-row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
}

/* --- Cards --- */

.card {
    width: 200px;
    border: 1px solid var(--palette-mid);
    border-radius: 6px;
    background: var(--palette-window);
    cursor: pointer;
    transition: box-shadow 0.15s ease, transform 0.15s ease;
    box-shadow: 1px 1px 4px rgba(0, 0, 0, 0.1);
    overflow: hidden;
    user-select: none;
}

.card:hover {
    box-shadow: 3px 3px 12px rgba(0, 0, 0, 0.2);
    transform: scale(1.03);
}

.card.selected {
    border-color: var(--palette-highlight);
    box-shadow: 0 0 0 2px var(--palette-highlight);
}

.card-image {
    width: 100%;
    height: 120px;
    object-fit: cover;
    background: var(--palette-mid);
    display: block;
}

.card-image.placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2em;
    color: var(--palette-dark);
}

.card-body {
    padding: 8px;
}

.card-name {
    font-size: 0.9em;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.card-tags {
    font-size: 0.75em;
    color: var(--palette-dark);
    margin-top: 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.card-badge {
    display: inline-block;
    font-size: 0.7em;
    padding: 1px 6px;
    border-radius: 3px;
    background: var(--palette-highlight);
    color: var(--palette-highlighted-text);
    margin-right: 4px;
}

/* --- Shortcut cards (quickstart) --- */

.shortcut-card {
    width: 100px;
    height: 100px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    border: 1px solid var(--palette-mid);
    border-radius: 6px;
    background: var(--palette-window);
    cursor: pointer;
    transition: box-shadow 0.15s ease;
    box-shadow: 1px 1px 4px rgba(0, 0, 0, 0.1);
    font-size: 0.85em;
    text-align: center;
}

.shortcut-card:hover {
    box-shadow: 3px 3px 12px rgba(0, 0, 0, 0.2);
}

/* --- New workspace card --- */

.card.new-workspace .card-image.placeholder {
    font-size: 3em;
}

/* --- Details panel --- */

#details-panel {
    position: fixed;
    top: 0;
    right: 0;
    width: 420px;
    height: 100vh;
    background: var(--palette-window);
    border-left: 1px solid var(--palette-mid);
    padding: 16px;
    overflow-y: auto;
    transform: translateX(100%);
    transition: transform 0.2s ease;
    z-index: 10;
}

#details-panel.visible {
    transform: translateX(0);
}

#details-panel.hidden {
    transform: translateX(100%);
}

#details-panel h2 {
    margin-bottom: 8px;
}

#details-panel hr {
    border: none;
    border-top: 1px solid var(--palette-mid);
    margin-bottom: 12px;
}

.details-field {
    display: flex;
    gap: 12px;
    margin-bottom: 8px;
    align-items: baseline;
}

.details-field label {
    min-width: 100px;
    font-weight: 500;
    font-size: 0.9em;
    color: var(--palette-dark);
}

.details-field span,
.details-field input,
.details-field textarea {
    flex: 1;
    font-size: 0.9em;
}

.details-field input,
.details-field textarea {
    padding: 4px 8px;
    border: 1px solid var(--palette-mid);
    border-radius: 4px;
    background: var(--palette-base);
    color: var(--palette-text);
}

.details-actions {
    margin-top: 24px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.details-actions button {
    padding: 8px 16px;
    border: 1px solid var(--palette-mid);
    border-radius: 4px;
    background: var(--palette-button);
    color: var(--palette-button-text);
    cursor: pointer;
    font-size: 0.9em;
}

.details-actions button:hover {
    background: var(--palette-highlight);
    color: var(--palette-highlighted-text);
}

.details-actions button.danger:hover {
    background: #c0392b;
    color: white;
}
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/resources/welcome/welcome.css
git commit -m "feat(welcome): add CSS for welcome page with theme variables"
```

### Task 6: JavaScript — QWebChannel bridge and interactions

**Files:**
- Create: `SciQLop/resources/welcome/welcome.js`

Initializes QWebChannel, fetches data from Python backend, renders cards, handles click/double-click/filter interactions, and manages the details sidebar.

- [ ] **Step 1: Create the JS file**

```javascript
// SciQLop/resources/welcome/welcome.js

let backend = null;
let selectedCard = null;

// --- Initialization ---

function init() {
    new QWebChannel(qt.webChannelTransport, function(channel) {
        backend = channel.objects.backend;
        loadQuickstart();
        loadWorkspaces();
        loadExamples();

        backend.workspace_list_changed.connect(loadWorkspaces);
    });
}

// --- Data loading ---

function loadQuickstart() {
    backend.list_quickstart_shortcuts(function(json_str) {
        const shortcuts = JSON.parse(json_str);
        const container = document.getElementById("quickstart-cards");
        container.innerHTML = "";
        shortcuts.forEach(function(s) {
            const card = document.createElement("div");
            card.className = "shortcut-card";
            card.title = s.description;
            card.textContent = s.name;
            card.addEventListener("click", function() {
                backend.run_quickstart(s.name);
            });
            container.appendChild(card);
        });
    });
}

function loadWorkspaces() {
    backend.list_workspaces(function(json_str) {
        const workspaces = JSON.parse(json_str);
        const container = document.getElementById("workspace-cards");
        container.innerHTML = "";

        // "New workspace" card
        const newCard = createNewWorkspaceCard();
        container.appendChild(newCard);

        workspaces.forEach(function(ws) {
            container.appendChild(createWorkspaceCard(ws));
        });
    });
}

function loadExamples() {
    backend.list_examples(function(json_str) {
        const examples = JSON.parse(json_str);
        const container = document.getElementById("example-cards");
        container.innerHTML = "";
        examples.forEach(function(ex) {
            container.appendChild(createExampleCard(ex));
        });
    });
}

// --- Card creation ---

function createNewWorkspaceCard() {
    const card = document.createElement("div");
    card.className = "card new-workspace";
    card.innerHTML =
        '<div class="card-image placeholder">+</div>' +
        '<div class="card-body"><span class="card-name">New workspace</span></div>';
    card.addEventListener("click", function() {
        backend.create_workspace();
    });
    return card;
}

function createWorkspaceCard(ws) {
    const card = document.createElement("div");
    card.className = "card";
    card.dataset.name = ws.name.toLowerCase();
    card.dataset.directory = ws.directory;

    let imageHtml;
    if (ws.image) {
        imageHtml = '<img class="card-image" src="file://' + ws.image + '">';
    } else {
        imageHtml = '<div class="card-image placeholder"></div>';
    }

    let badges = "";
    if (ws.is_default) badges += '<span class="card-badge">Default</span>';

    card.innerHTML =
        imageHtml +
        '<div class="card-body">' +
            badges +
            '<span class="card-name">' + escapeHtml(ws.name) + '</span>' +
        '</div>';

    card.addEventListener("click", function(e) {
        selectCard(card);
        showWorkspaceDetails(ws);
    });
    card.addEventListener("dblclick", function() {
        backend.open_workspace(ws.directory);
    });
    return card;
}

function createExampleCard(ex) {
    const card = document.createElement("div");
    card.className = "card";
    card.dataset.name = ex.name.toLowerCase();
    card.dataset.tags = (ex.tags || []).join(" ").toLowerCase();

    let imageHtml;
    if (ex.image) {
        imageHtml = '<img class="card-image" src="file://' + ex.image + '">';
    } else {
        imageHtml = '<div class="card-image placeholder"></div>';
    }

    const tagsHtml = (ex.tags || []).length > 0
        ? '<div class="card-tags">Tags: ' + escapeHtml(ex.tags.join(", ")) + '</div>'
        : '';

    card.innerHTML =
        imageHtml +
        '<div class="card-body">' +
            '<span class="card-name">' + escapeHtml(ex.name) + '</span>' +
            tagsHtml +
        '</div>';

    card.addEventListener("click", function() {
        selectCard(card);
        showExampleDetails(ex);
    });
    card.addEventListener("dblclick", function() {
        backend.open_example(ex.directory);
    });
    return card;
}

// --- Details panel ---

function showWorkspaceDetails(ws) {
    const panel = document.getElementById("details-panel");
    document.getElementById("details-title").textContent = "Workspace details";

    const content = document.getElementById("details-content");
    content.innerHTML =
        '<div class="details-field"><label>Name</label><span>' + escapeHtml(ws.name) + '</span></div>' +
        '<div class="details-field"><label>Last used</label><span>' + escapeHtml(ws.last_used) + '</span></div>' +
        '<div class="details-field"><label>Last modified</label><span>' + escapeHtml(ws.last_modified) + '</span></div>' +
        '<div class="details-field"><label>Description</label><span>' + escapeHtml(ws.description || "") + '</span></div>' +
        '<div class="details-actions">' +
            '<button onclick="backend.open_workspace(\'' + escapeAttr(ws.directory) + '\')">Open workspace</button>' +
            '<button onclick="backend.duplicate_workspace(\'' + escapeAttr(ws.directory) + '\')">Duplicate workspace</button>' +
            (ws.is_default ? '' :
                '<button class="danger" onclick="confirmDelete(\'' + escapeAttr(ws.directory) + '\', \'' + escapeAttr(ws.name) + '\')">Delete workspace</button>') +
        '</div>';

    panel.classList.remove("hidden");
    panel.classList.add("visible");
    document.getElementById("sections").classList.add("with-details");
}

function showExampleDetails(ex) {
    const panel = document.getElementById("details-panel");
    document.getElementById("details-title").textContent = "Example details";

    const content = document.getElementById("details-content");
    content.innerHTML =
        '<div class="details-field"><label>Name</label><span>' + escapeHtml(ex.name) + '</span></div>' +
        '<div class="details-field"><label>Description</label><span>' + escapeHtml(ex.description || "") + '</span></div>' +
        '<div class="details-actions">' +
            '<button onclick="backend.open_example(\'' + escapeAttr(ex.directory) + '\')">Open example</button>' +
        '</div>';

    panel.classList.remove("hidden");
    panel.classList.add("visible");
    document.getElementById("sections").classList.add("with-details");
}

function hideDetails() {
    const panel = document.getElementById("details-panel");
    panel.classList.remove("visible");
    panel.classList.add("hidden");
    document.getElementById("sections").classList.remove("with-details");
    if (selectedCard) {
        selectedCard.classList.remove("selected");
        selectedCard = null;
    }
}

function confirmDelete(directory, name) {
    if (confirm("Delete workspace '" + name + "'?")) {
        backend.delete_workspace(directory);
        hideDetails();
    }
}

// --- Selection ---

function selectCard(card) {
    if (selectedCard) selectedCard.classList.remove("selected");
    selectedCard = card;
    card.classList.add("selected");
}

// --- Filtering ---

document.addEventListener("DOMContentLoaded", function() {
    const wsFilter = document.getElementById("workspace-filter");
    if (wsFilter) {
        wsFilter.addEventListener("input", function() {
            filterCards("workspace-cards", this.value);
        });
    }
    const exFilter = document.getElementById("example-filter");
    if (exFilter) {
        exFilter.addEventListener("input", function() {
            filterCards("example-cards", this.value);
        });
    }

    // Click on empty space hides details
    document.getElementById("sections").addEventListener("click", function(e) {
        if (e.target === this || e.target.tagName === "SECTION") {
            hideDetails();
        }
    });
});

function filterCards(containerId, query) {
    query = query.toLowerCase();
    const container = document.getElementById(containerId);
    const cards = container.querySelectorAll(".card");
    cards.forEach(function(card) {
        const name = card.dataset.name || "";
        const tags = card.dataset.tags || "";
        const match = !query || name.includes(query) || tags.includes(query);
        card.style.display = match ? "" : "none";
    });
}

// --- Utilities ---

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function escapeAttr(str) {
    return str.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

// --- Start ---
init();
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/resources/welcome/welcome.js
git commit -m "feat(welcome): add JS for QWebChannel bridge and card interactions"
```

---

## Chunk 3: WebWelcomePage Widget and Wiring

### Task 7: WebWelcomePage QWidget

**Files:**
- Create: `SciQLop/components/welcome/web_welcome_page.py`

This widget hosts the QWebEngineView, sets up QWebChannel, renders the Jinja2 template with palette colors, and loads the result.

- [ ] **Step 1: Create the widget**

```python
# SciQLop/components/welcome/web_welcome_page.py
from __future__ import annotations

import os

from PySide6.QtCore import QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from jinja2 import Environment, FileSystemLoader

from SciQLop.components.theming.palette import SCIQLOP_PALETTE
from .backend import WelcomeBackend

_RESOURCES = os.path.join(os.path.dirname(__file__), "..", "..", "resources", "welcome")


def _render_template() -> str:
    env = Environment(loader=FileSystemLoader(_RESOURCES))
    template = env.get_template("welcome.html.j2")
    return template.render(palette=SCIQLOP_PALETTE)


class WebWelcomePage(QWidget):
    """Welcome page rendered as HTML via QWebEngineView."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Welcome")

        self._backend = WelcomeBackend(self)
        self._channel = QWebChannel(self)
        self._channel.registerObject("backend", self._backend)

        self._view = QWebEngineView(self)
        self._view.page().setWebChannel(self._channel)

        html = _render_template()
        self._view.setHtml(html, QUrl.fromLocalFile(os.path.join(_RESOURCES, "welcome.html")))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

    @property
    def backend(self) -> WelcomeBackend:
        return self._backend
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/components/welcome/web_welcome_page.py
git commit -m "feat(welcome): add WebWelcomePage widget with QWebEngineView + QWebChannel"
```

### Task 8: Wire into main window

**Files:**
- Modify: `SciQLop/components/welcome/__init__.py`
- Modify: `SciQLop/core/ui/mainwindow.py` (single import change)

- [ ] **Step 1: Update the welcome module export**

In `SciQLop/components/welcome/__init__.py`, change:
```python
from .web_welcome_page import WebWelcomePage as WelcomePage
```

This keeps the public name `WelcomePage` so `mainwindow.py` needs no change beyond possibly adjusting the import (check if it imports `WelcomePage` by name — if so, no change needed).

- [ ] **Step 2: Verify mainwindow import**

Check `SciQLop/core/ui/mainwindow.py` — it should import `WelcomePage` from `SciQLop.components.welcome`. If so, the `__init__.py` alias handles it. No change needed in mainwindow.

- [ ] **Step 3: Run the app manually to verify**

Run: `uv run sciqlop`

Check:
- Welcome page loads with themed cards
- Clicking a workspace shows the details sidebar with slide-in animation
- Double-clicking opens the workspace
- Filter bars work
- Quick start shortcuts work
- "New workspace" card works
- Delete/duplicate buttons work

- [ ] **Step 4: Commit**

```bash
git add SciQLop/components/welcome/__init__.py
git commit -m "feat(welcome): wire WebWelcomePage as default welcome page"
```

---

## Chunk 4: Example discovery fix and filesystem watching

### Task 9: Example discovery in backend

**Files:**
- Modify: `SciQLop/components/welcome/backend.py`

The current `ExamplesView` discovers examples by globbing `../../../examples/*/*.json` relative to its own file. The backend needs the same discovery logic.

- [ ] **Step 1: Check how Example.discover() works or add it**

If `Example` doesn't have a `discover()` class method, add the glob-based discovery to the backend:

```python
import glob

def _discover_examples() -> list[Example]:
    examples_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "examples"
    )
    results = []
    for json_file in sorted(glob.glob(os.path.join(examples_dir, "*", "*.json"))):
        try:
            results.append(Example(json_file))
        except Exception:
            pass
    return results
```

Update `list_examples` to use `_discover_examples()`.

- [ ] **Step 2: Verify examples load in the HTML page**

Run: `uv run sciqlop` and check the Examples section.

- [ ] **Step 3: Commit**

```bash
git add SciQLop/components/welcome/backend.py
git commit -m "fix(welcome): add example discovery to WelcomeBackend"
```

### Task 10: Filesystem watching for workspace changes

**Files:**
- Modify: `SciQLop/components/welcome/backend.py`

The old `RecentWorkspaces` section used `QFileSystemWatcher` on the workspaces directory to refresh when workspaces are created/deleted externally. Add the same to the backend.

- [ ] **Step 1: Add filesystem watcher**

In `WelcomeBackend.__init__`:

```python
from PySide6.QtCore import QFileSystemWatcher
from SciQLop.components.workspaces.backend.settings import SciQLopWorkspacesSettings

self._watcher = QFileSystemWatcher([SciQLopWorkspacesSettings().workspaces_dir], self)
self._watcher.directoryChanged.connect(lambda: self.workspace_list_changed.emit())
```

The JS side already connects `backend.workspace_list_changed` → `loadWorkspaces()`.

- [ ] **Step 2: Verify by creating a workspace from another window/terminal**

- [ ] **Step 3: Commit**

```bash
git add SciQLop/components/welcome/backend.py
git commit -m "feat(welcome): watch workspace directory for external changes"
```

---

## Notes

### What this plan does NOT cover (future work)
- **News/updates section** — add a new `<section>` in the template + a backend slot that fetches a remote JSON feed
- **Featured plugins / AppStore** — see `docs/plans/2026-03-08-welcome-panel-appstore.md`; the HTML template makes adding new sections trivial
- **Editable workspace fields in details panel** — the current plan shows read-only details; making name/description editable requires `<input>` fields + `update_workspace_field` calls (backend slot already exists)
- **Quickstart icons** — QIcon can't be serialized to HTML; options: save icon PNGs to a temp dir and serve as `file://` URLs, or use SVG icon names mapped to inline SVGs

### Rollback strategy
The old widget-based `WelcomePage` class is preserved. To revert, change `__init__.py` back to:
```python
from .welcome_page import WelcomePage
```

### Palette key mapping
The CSS custom properties use palette keys from `SCIQLOP_PALETTE`. Common keys: `base`, `text`, `window`, `mid`, `dark`, `highlight`, `highlighted-text`, `button`, `button-text`. Verify the exact key names from a light/dark palette YAML file before finalizing the CSS.
