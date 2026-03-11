# Welcome Page Redesign & AppStore Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the welcome page with a two-column layout (hero + community section) and add an AppStore dock panel with mock data.

**Architecture:** The existing QWebEngineView welcome page gets new backend slots (hero workspace, mock news, mock featured packages, appstore signal) and a restructured HTML/CSS/JS for the two-column layout. A new `SciQLop/components/appstore/` component follows the same QWebEngineView + QWebChannel + Jinja2 pattern. The main window lazily creates the AppStore dock and wires the "Browse all" signal.

**Tech Stack:** PySide6 QWebEngineView + QWebChannel, Jinja2, HTML/CSS/JS (vanilla), Python

**Spec:** `docs/plans/2026-03-11-welcome-redesign-and-appstore-design.md`

---

## Chunk 1: Welcome Page Backend Extensions

### Task 1: Add hero workspace, news, and featured packages slots

**Files:**
- Modify: `SciQLop/components/welcome/backend.py`

The welcome page needs three new data slots and one action slot with a signal.

- [ ] **Step 1: Add mock data constants and new slots to backend.py**

Add after the existing `_discover_examples` function (line 60) and before the `WelcomeBackend` class:

```python
_MOCK_NEWS = [
    {"icon": "\U0001f389", "title": "SciQLop 0.8 released", "date": "2026-03-10"},
    {"icon": "\U0001f4e6", "title": "New MMS data products available", "date": "2026-03-08"},
    {"icon": "\U0001f4a1", "title": "Tip: Use virtual products for derived quantities", "date": "2026-03-05"},
]

_MOCK_FEATURED = [
    {"name": "AMDA Provider", "type": "plugin", "description": "Access AMDA data directly in SciQLop", "author": "IRAP", "tags": ["data-provider", "amda"], "stars": 42},
    {"name": "Wavelet Analysis", "type": "plugin", "description": "Continuous wavelet transform for time series", "author": "LPP", "tags": ["analysis", "wavelets"], "stars": 28},
    {"name": "MMS Mission Study", "type": "workspace", "description": "Pre-configured workspace for MMS data analysis", "author": "IRAP", "tags": ["mms", "magnetosphere"], "stars": 15},
    {"name": "Solar Wind Tutorial", "type": "example", "description": "Introduction to solar wind data analysis with SciQLop", "author": "Community", "tags": ["tutorial", "solar-wind"], "stars": 33},
]
```

Add `appstore_requested` signal to `WelcomeBackend` class (after `quickstart_changed` on line 67):

```python
    appstore_requested = Signal()
```

Add these slots inside the `WelcomeBackend` class, in the "Data slots" section (after `list_quickstart_shortcuts`, before "Action slots"):

```python
    @Slot(result=str)
    def get_hero_workspace(self) -> str:
        workspaces = workspaces_manager_instance().list_workspaces()
        non_default = [ws for ws in workspaces if not ws.default_workspace]
        if not non_default:
            return "null"
        non_default.sort(key=lambda ws: ws.last_used, reverse=True)
        return json.dumps(_workspace_to_dict(non_default[0]))

    @Slot(result=str)
    def list_news(self) -> str:
        return json.dumps(_MOCK_NEWS)

    @Slot(result=str)
    def list_featured_packages(self) -> str:
        return json.dumps(_MOCK_FEATURED)
```

Add this slot in the "Action slots" section (after `run_quickstart`):

```python
    @Slot()
    def open_appstore(self) -> None:
        self.appstore_requested.emit()
```

- [ ] **Step 2: Verify the app still starts**

Run: `uv run sciqlop`
Expected: App starts, welcome page loads as before (new slots exist but aren't called yet).

- [ ] **Step 3: Commit**

```bash
git add SciQLop/components/welcome/backend.py
git commit -m "feat(welcome): add hero workspace, news, featured packages, and appstore slots"
```

---

## Chunk 2: Welcome Page Two-Column Layout

### Task 2: Restructure HTML template for two-column layout

**Files:**
- Modify: `SciQLop/components/welcome/resources/welcome.html.j2`

Replace the entire template. The new structure is: hero bar (full width) above a two-column flex layout. Left column has quickstart, workspaces, examples. Right column has news and featured plugins.

- [ ] **Step 1: Replace the HTML template**

Write this content to `SciQLop/components/welcome/resources/welcome.html.j2`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SciQLop Welcome</title>
    <style>
        :root {
            {% for name, color in palette.items() %}
            --{{ name }}: {{ color }};
            {% endfor %}
        }
    </style>
    <link rel="stylesheet" href="welcome.css">
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
</head>
<body>
    <div id="hero" class="hidden"></div>

    <div id="columns">
        <div id="left-column">
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

        <div id="right-column">
            <section id="news">
                <h2>What's New</h2>
                <div id="news-list"></div>
            </section>

            <section id="featured">
                <div class="section-header">
                    <h2>Featured</h2>
                    <a href="#" id="browse-all-link" class="browse-link">Browse all &rarr;</a>
                </div>
                <div class="cards-grid cards-grid-small" id="featured-cards"></div>
            </section>
        </div>
    </div>

    <aside id="details-panel" class="hidden">
        <h2 id="details-title">Details</h2>
        <hr>
        <div id="details-content"></div>
    </aside>

    <script src="welcome.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/components/welcome/resources/welcome.html.j2
git commit -m "feat(welcome): restructure HTML template for two-column layout"
```

### Task 3: Update CSS for two-column layout, hero bar, and community section

**Files:**
- Modify: `SciQLop/components/welcome/resources/welcome.css`

Replace the entire CSS. Key changes: remove `#main` flex wrapper, add `#hero` bar, add `#columns` two-column flex, add `#right-column` styles, add news item styles, add featured cards grid (smaller), remove `#sections.with-details` margin rule (details panel is now a pure overlay).

- [ ] **Step 1: Replace the CSS file**

Write this content to `SciQLop/components/welcome/resources/welcome.css`:

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: system-ui, -apple-system, sans-serif;
    background-color: var(--WelcomeBackground, var(--Base));
    color: var(--Text);
    overflow-y: auto;
    overflow-x: hidden;
    padding: 16px;
}

/* --- Hero bar --- */

#hero {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    margin-bottom: 16px;
    border-radius: 8px;
    background: color-mix(in srgb, var(--Highlight) 12%, var(--Window));
    border: 1px solid color-mix(in srgb, var(--Highlight) 30%, var(--Borders));
}

#hero.hidden {
    display: none;
}

#hero .hero-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

#hero .hero-name {
    font-weight: 600;
    font-size: 1em;
}

#hero .hero-sub {
    font-size: 0.85em;
    color: var(--UnselectedText);
}

#hero button {
    padding: 6px 20px;
    border: 1px solid var(--Highlight);
    border-radius: 4px;
    background: var(--Highlight);
    color: var(--HighlightedText);
    cursor: pointer;
    font-size: 0.9em;
    font-weight: 500;
}

#hero button:hover {
    opacity: 0.9;
}

/* --- Two-column layout --- */

#columns {
    display: flex;
    gap: 24px;
    min-height: calc(100vh - 80px);
}

#left-column {
    flex: 6;
    min-width: 0;
}

#right-column {
    flex: 4;
    min-width: 200px;
    border-left: 1px solid var(--Borders);
    padding-left: 24px;
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
    border: 1px solid var(--Borders);
    border-radius: 4px;
    background: var(--Base);
    color: var(--Text);
}

h2 {
    font-size: 1.2em;
    font-weight: 600;
    margin-bottom: 8px;
    color: var(--Text);
}

/* --- Card grid --- */

.cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 200px));
    gap: 12px;
}

.cards-grid-small {
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
}

.cards-row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
}

/* --- Cards --- */

.card {
    border: 1px solid var(--Borders);
    border-radius: 6px;
    background: var(--Window);
    cursor: pointer;
    transition: box-shadow 0.2s ease, transform 0.2s ease;
    box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.25);
    overflow: hidden;
    user-select: none;
}

.card:hover {
    box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.4);
    transform: scale(1.05);
}

.card.selected {
    border-color: var(--Highlight);
    box-shadow: 0 0 0 2px var(--Highlight);
}

.card-image {
    width: 100%;
    height: 120px;
    object-fit: cover;
    background: var(--AlternateBase);
    display: block;
}

.card-image.placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2em;
    color: var(--UnselectedText);
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
    color: var(--UnselectedText);
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
    background: var(--Highlight);
    color: var(--HighlightedText);
    margin-right: 4px;
}

.card-stars {
    font-size: 0.75em;
    color: var(--UnselectedText);
    margin-top: 2px;
}

/* --- Shortcut cards (quickstart) --- */

.shortcut-card {
    width: 100px;
    height: 120px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    border: 1px solid var(--Borders);
    border-radius: 6px;
    background: var(--Window);
    cursor: pointer;
    transition: box-shadow 0.2s ease, transform 0.2s ease;
    box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.25);
    font-size: 0.85em;
    text-align: center;
}

.shortcut-card:hover {
    box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.4);
    transform: scale(1.05);
}

/* --- New workspace card --- */

.card.new-workspace .card-image.placeholder {
    font-size: 3em;
}

/* --- News items --- */

.news-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px;
    border-radius: 4px;
    margin-bottom: 4px;
    font-size: 0.9em;
    background: var(--Window);
    border: 1px solid var(--Borders);
}

.news-item .news-icon {
    font-size: 1.2em;
    flex-shrink: 0;
}

.news-item .news-text {
    flex: 1;
}

.news-item .news-date {
    font-size: 0.8em;
    color: var(--UnselectedText);
    flex-shrink: 0;
}

/* --- Browse link --- */

.browse-link {
    font-size: 0.9em;
    color: var(--Highlight);
    text-decoration: none;
    cursor: pointer;
    white-space: nowrap;
}

.browse-link:hover {
    text-decoration: underline;
}

/* --- Details panel (overlay) --- */

#details-panel {
    position: fixed;
    top: 0;
    right: 0;
    width: 420px;
    height: 100vh;
    background: var(--Window);
    border-left: 1px solid var(--Borders);
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
    border-top: 1px solid var(--Borders);
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
    color: var(--UnselectedText);
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
    border: 1px solid var(--Borders);
    border-radius: 4px;
    background: var(--Base);
    color: var(--Text);
}

.details-actions {
    margin-top: 24px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.details-actions button {
    padding: 8px 16px;
    border: 1px solid var(--Borders);
    border-radius: 4px;
    background: var(--Button);
    color: var(--ButtonText);
    cursor: pointer;
    font-size: 0.9em;
}

.details-actions button:hover {
    background: var(--Highlight);
    color: var(--HighlightedText);
}

.details-actions button.danger:hover {
    background: #c0392b;
    color: white;
}
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/components/welcome/resources/welcome.css
git commit -m "feat(welcome): update CSS for two-column layout with hero and community"
```

### Task 4: Update JavaScript for hero, news, featured, and two-column interactions

**Files:**
- Modify: `SciQLop/components/welcome/resources/welcome.js`

Replace the entire JS. Key changes: add `loadHero()`, `loadNews()`, `loadFeatured()` functions, update `init()` to call them, update click handler to work with new DOM structure (no `#sections` wrapper), wire "Browse all" link to `backend.open_appstore()`.

- [ ] **Step 1: Replace the JS file**

Write this content to `SciQLop/components/welcome/resources/welcome.js`:

```javascript
let backend = null;
let selectedCard = null;

// --- Initialization ---

function init() {
    new QWebChannel(qt.webChannelTransport, function(channel) {
        backend = channel.objects.backend;
        loadHero();
        loadQuickstart();
        loadWorkspaces();
        loadExamples();
        loadNews();
        loadFeatured();

        backend.workspace_list_changed.connect(function() {
            loadWorkspaces();
            loadHero();
        });
        backend.quickstart_changed.connect(loadQuickstart);

        document.getElementById("browse-all-link").addEventListener("click", function(e) {
            e.preventDefault();
            backend.open_appstore();
        });
    });
}

// --- Hero ---

function loadHero() {
    backend.get_hero_workspace(function(json_str) {
        const hero = document.getElementById("hero");
        const ws = JSON.parse(json_str);
        if (!ws) {
            hero.classList.add("hidden");
            hero.innerHTML = '';
            return;
        }
        hero.classList.remove("hidden");
        hero.innerHTML =
            '<div class="hero-info">' +
                '<span class="hero-name">\u26A1 Resume: ' + escapeHtml(ws.name) + '</span>' +
                '<span class="hero-sub">Last used: ' + escapeHtml(ws.last_used) + '</span>' +
            '</div>' +
            '<button id="hero-open">Open</button>';
        document.getElementById("hero-open").addEventListener("click", function() {
            backend.open_workspace(ws.directory);
        });
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
            if (s.icon) {
                const img = document.createElement("img");
                img.src = s.icon;
                img.style.width = "48px";
                img.style.height = "48px";
                card.appendChild(img);
            }
            const label = document.createElement("span");
            label.textContent = s.name;
            card.appendChild(label);
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

        container.appendChild(createNewWorkspaceCard());

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

function loadNews() {
    backend.list_news(function(json_str) {
        const news = JSON.parse(json_str);
        const container = document.getElementById("news-list");
        container.innerHTML = "";
        news.forEach(function(item) {
            const row = document.createElement("div");
            row.className = "news-item";
            row.innerHTML =
                '<span class="news-icon">' + item.icon + '</span>' +
                '<span class="news-text">' + escapeHtml(item.title) + '</span>' +
                '<span class="news-date">' + escapeHtml(item.date || "") + '</span>';
            container.appendChild(row);
        });
    });
}

function loadFeatured() {
    backend.list_featured_packages(function(json_str) {
        const packages = JSON.parse(json_str);
        const container = document.getElementById("featured-cards");
        container.innerHTML = "";
        packages.forEach(function(pkg) {
            container.appendChild(createFeaturedCard(pkg));
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
        imageHtml = '<div class="card-image placeholder">\uD83D\uDCC1</div>';
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
        imageHtml = '<div class="card-image placeholder">\uD83D\uDCD6</div>';
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

var TYPE_ICONS = {plugin: "\uD83D\uDD0C", workspace: "\uD83D\uDCC1", example: "\uD83D\uDCD6"};

function createFeaturedCard(pkg) {
    const card = document.createElement("div");
    card.className = "card";
    card.dataset.name = pkg.name.toLowerCase();
    card.dataset.tags = (pkg.tags || []).join(" ").toLowerCase();

    const icon = TYPE_ICONS[pkg.type] || "\uD83D\uDCE6";
    card.innerHTML =
        '<div class="card-image placeholder">' + icon + '</div>' +
        '<div class="card-body">' +
            '<span class="card-badge">' + escapeHtml(pkg.type) + '</span>' +
            '<span class="card-name">' + escapeHtml(pkg.name) + '</span>' +
            '<div class="card-stars">\u2B50 ' + pkg.stars + '</div>' +
        '</div>';

    card.addEventListener("click", function() {
        selectCard(card);
        showFeaturedDetails(pkg);
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
}

function showFeaturedDetails(pkg) {
    const panel = document.getElementById("details-panel");
    document.getElementById("details-title").textContent = pkg.type.charAt(0).toUpperCase() + pkg.type.slice(1) + " details";

    const tagsHtml = (pkg.tags || []).map(function(t) {
        return '<span class="card-badge">' + escapeHtml(t) + '</span>';
    }).join(" ");

    const content = document.getElementById("details-content");
    content.innerHTML =
        '<div class="details-field"><label>Name</label><span>' + escapeHtml(pkg.name) + '</span></div>' +
        '<div class="details-field"><label>Type</label><span>' + escapeHtml(pkg.type) + '</span></div>' +
        '<div class="details-field"><label>Author</label><span>' + escapeHtml(pkg.author) + '</span></div>' +
        '<div class="details-field"><label>Description</label><span>' + escapeHtml(pkg.description || "") + '</span></div>' +
        '<div class="details-field"><label>Tags</label><span>' + tagsHtml + '</span></div>' +
        '<div class="details-field"><label>Stars</label><span>\u2B50 ' + pkg.stars + '</span></div>' +
        '<div class="details-actions">' +
            '<button onclick="backend.open_appstore()">View in Store</button>' +
        '</div>';

    panel.classList.remove("hidden");
    panel.classList.add("visible");
}

function hideDetails() {
    const panel = document.getElementById("details-panel");
    panel.classList.remove("visible");
    panel.classList.add("hidden");
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
    var wsFilter = document.getElementById("workspace-filter");
    if (wsFilter) {
        wsFilter.addEventListener("input", function() {
            filterCards("workspace-cards", this.value);
        });
    }
    var exFilter = document.getElementById("example-filter");
    if (exFilter) {
        exFilter.addEventListener("input", function() {
            filterCards("example-cards", this.value);
        });
    }

    document.body.addEventListener("click", function(e) {
        if (!e.target.closest(".card, .shortcut-card, #details-panel, #hero")) {
            hideDetails();
        }
    });
});

function filterCards(containerId, query) {
    query = query.toLowerCase();
    var container = document.getElementById(containerId);
    var cards = container.querySelectorAll(".card");
    cards.forEach(function(card) {
        var name = card.dataset.name || "";
        var tags = card.dataset.tags || "";
        var match = !query || name.includes(query) || tags.includes(query);
        card.style.display = match ? "" : "none";
    });
}

// --- Utilities ---

function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function escapeAttr(str) {
    return str.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

// --- Start ---
init();
```

- [ ] **Step 2: Test the welcome page manually**

Run: `uv run sciqlop`

Check:
- Hero bar shows at top with the most recent non-default workspace name and "Open" button
- Left column: Quick start shortcuts, Recent workspaces grid, Examples grid — all work as before
- Right column: "What's New" shows 3 mock news items, "Featured" shows 4 mock cards with type badges and stars
- "Browse all →" link is visible (clicking it does nothing yet — AppStore not wired)
- Clicking a workspace card shows details panel as overlay
- Clicking empty space hides the details panel
- Filter inputs work

- [ ] **Step 3: Commit**

```bash
git add SciQLop/components/welcome/resources/welcome.js
git commit -m "feat(welcome): add JS for hero, news, featured sections and two-column interactions"
```

---

## Chunk 3: AppStore Backend and Widget

### Task 5: Create AppStore backend with mock data

**Files:**
- Create: `SciQLop/components/appstore/__init__.py`
- Create: `SciQLop/components/appstore/backend.py`

- [ ] **Step 1: Create the __init__.py**

```python
# SciQLop/components/appstore/__init__.py
from .web_appstore_page import AppStorePage
```

Note: `web_appstore_page.py` doesn't exist yet — this will be created in Task 6. Create `__init__.py` now so we can work on backend.py independently.

- [ ] **Step 2: Create backend.py with mock data and slots**

Write this to `SciQLop/components/appstore/backend.py`:

```python
from __future__ import annotations

import json

from PySide6.QtCore import QObject, Slot

MOCK_PACKAGES = [
    {"name": "AMDA Provider", "type": "plugin", "author": "IRAP", "description": "Access AMDA data directly in SciQLop", "tags": ["data-provider", "amda"], "version": "1.2.0", "stars": 42, "downloads": 156},
    {"name": "Wavelet Analysis", "type": "plugin", "author": "LPP", "description": "Continuous wavelet transform for time series", "tags": ["analysis", "wavelets"], "version": "0.9.1", "stars": 28, "downloads": 89},
    {"name": "CDAWeb Provider", "type": "plugin", "author": "NASA/GSFC", "description": "CDAWeb data access integration", "tags": ["data-provider", "cdaweb"], "version": "2.0.0", "stars": 21, "downloads": 203},
    {"name": "Boundary Detection", "type": "plugin", "author": "LPP", "description": "Automatic detection of magnetopause and bow shock crossings", "tags": ["analysis", "boundaries", "mms"], "version": "0.3.0", "stars": 9, "downloads": 34},
    {"name": "MMS Mission Study", "type": "workspace", "author": "IRAP", "description": "Pre-configured workspace for MMS magnetospheric data analysis", "tags": ["mms", "magnetosphere"], "version": "1.0.0", "stars": 15, "downloads": 67},
    {"name": "Solar Wind Analysis", "type": "workspace", "author": "Community", "description": "Workspace for solar wind parameter studies", "tags": ["solar-wind", "heliophysics"], "version": "1.1.0", "stars": 12, "downloads": 45},
    {"name": "Solar Wind Tutorial", "type": "example", "author": "Community", "description": "Step-by-step introduction to solar wind data analysis with SciQLop", "tags": ["tutorial", "solar-wind", "beginner"], "version": "1.0.0", "stars": 33, "downloads": 312},
    {"name": "Virtual Products Guide", "type": "example", "author": "IRAP", "description": "Learn to create derived quantities using virtual products", "tags": ["tutorial", "virtual-product"], "version": "1.0.0", "stars": 19, "downloads": 128},
    {"name": "MMS Reconnection Events", "type": "example", "author": "Community", "description": "Catalog of magnetic reconnection events observed by MMS", "tags": ["mms", "reconnection", "catalog"], "version": "2.1.0", "stars": 24, "downloads": 91},
]


class AppStoreBackend(QObject):
    """Python backend exposed to the AppStore page via QWebChannel."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

    @Slot(str, result=str)
    def list_packages(self, category: str = "") -> str:
        if category:
            filtered = [p for p in MOCK_PACKAGES if p["type"] == category]
        else:
            filtered = MOCK_PACKAGES
        return json.dumps(filtered)

    @Slot(str, result=str)
    def get_package_detail(self, name: str) -> str:
        for p in MOCK_PACKAGES:
            if p["name"] == name:
                return json.dumps(p)
        return "null"

    @Slot(result=str)
    def list_tags(self) -> str:
        tags = set()
        for p in MOCK_PACKAGES:
            tags.update(p.get("tags", []))
        return json.dumps(sorted(tags))
```

- [ ] **Step 3: Commit**

```bash
git add SciQLop/components/appstore/__init__.py SciQLop/components/appstore/backend.py
git commit -m "feat(appstore): add AppStoreBackend with mock package data"
```

### Task 6: Create AppStore widget (QWebEngineView)

**Files:**
- Create: `SciQLop/components/appstore/web_appstore_page.py`

- [ ] **Step 1: Create the widget**

Write this to `SciQLop/components/appstore/web_appstore_page.py`:

```python
from __future__ import annotations

import os

from PySide6.QtCore import QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from jinja2 import Environment, FileSystemLoader

from SciQLop.components.theming.palette import SCIQLOP_PALETTE
from .backend import AppStoreBackend

_RESOURCES = os.path.join(os.path.dirname(__file__), "resources")


def _render_template() -> str:
    env = Environment(loader=FileSystemLoader(_RESOURCES))
    template = env.get_template("appstore.html.j2")
    return template.render(palette=SCIQLOP_PALETTE)


class AppStorePage(QWidget):
    """AppStore page rendered as HTML via QWebEngineView."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Plugin Store")

        self._backend = AppStoreBackend(self)
        self._channel = QWebChannel(self)
        self._channel.registerObject("backend", self._backend)

        self._view = QWebEngineView(self)
        self._view.page().setWebChannel(self._channel)
        self._view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        html = _render_template()
        self._view.setHtml(html, QUrl.fromLocalFile(os.path.join(_RESOURCES, "appstore.html")))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/components/appstore/web_appstore_page.py
git commit -m "feat(appstore): add AppStorePage widget with QWebEngineView"
```

---

## Chunk 4: AppStore HTML, CSS, and JS

### Task 7: Create AppStore HTML template

**Files:**
- Create: `SciQLop/components/appstore/resources/appstore.html.j2`

- [ ] **Step 1: Create the HTML template**

Write this to `SciQLop/components/appstore/resources/appstore.html.j2`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SciQLop Plugin Store</title>
    <style>
        :root {
            {% for name, color in palette.items() %}
            --{{ name }}: {{ color }};
            {% endfor %}
        }
    </style>
    <link rel="stylesheet" href="appstore.css">
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
</head>
<body>
    <div id="tab-bar">
        <button class="tab active" data-category="">All</button>
        <button class="tab" data-category="plugin">Plugins</button>
        <button class="tab" data-category="workspace">Workspaces</button>
        <button class="tab" data-category="example">Examples</button>
    </div>

    <div id="toolbar">
        <input type="text" id="search-input" placeholder="Search plugins, workspaces, examples...">
        <select id="sort-select">
            <option value="stars">Popular</option>
            <option value="name">Name</option>
        </select>
    </div>

    <div id="tag-chips"></div>

    <div class="cards-grid" id="package-cards"></div>

    <aside id="details-panel" class="hidden">
        <h2 id="details-title">Details</h2>
        <hr>
        <div id="details-content"></div>
    </aside>

    <script src="appstore.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/components/appstore/resources/appstore.html.j2
git commit -m "feat(appstore): add Jinja2 HTML template"
```

### Task 8: Create AppStore CSS

**Files:**
- Create: `SciQLop/components/appstore/resources/appstore.css`

- [ ] **Step 1: Create the CSS**

Write this to `SciQLop/components/appstore/resources/appstore.css`:

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: system-ui, -apple-system, sans-serif;
    background-color: var(--WelcomeBackground, var(--Base));
    color: var(--Text);
    overflow-y: auto;
    overflow-x: hidden;
    padding: 16px;
}

/* --- Tab bar --- */

#tab-bar {
    display: flex;
    gap: 0;
    border-bottom: 2px solid var(--Borders);
    margin-bottom: 12px;
}

.tab {
    padding: 8px 20px;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    color: var(--UnselectedText);
    cursor: pointer;
    font-size: 0.95em;
    font-weight: 500;
}

.tab:hover {
    color: var(--Text);
}

.tab.active {
    color: var(--Highlight);
    border-bottom-color: var(--Highlight);
}

/* --- Toolbar --- */

#toolbar {
    display: flex;
    gap: 12px;
    margin-bottom: 12px;
    align-items: center;
}

#search-input {
    flex: 1;
    padding: 6px 12px;
    border: 1px solid var(--Borders);
    border-radius: 4px;
    background: var(--Base);
    color: var(--Text);
    font-size: 0.9em;
}

#sort-select {
    padding: 6px 12px;
    border: 1px solid var(--Borders);
    border-radius: 4px;
    background: var(--Base);
    color: var(--Text);
    font-size: 0.9em;
}

/* --- Tag chips --- */

#tag-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 16px;
}

.tag-chip {
    padding: 3px 12px;
    border-radius: 12px;
    border: 1px solid var(--Borders);
    background: var(--Window);
    color: var(--Text);
    font-size: 0.82em;
    cursor: pointer;
    user-select: none;
    transition: background 0.15s ease, color 0.15s ease;
}

.tag-chip:hover {
    background: var(--AlternateBase);
}

.tag-chip.active {
    background: var(--Highlight);
    color: var(--HighlightedText);
    border-color: var(--Highlight);
}

/* --- Card grid --- */

.cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 200px));
    gap: 12px;
}

/* --- Cards (duplicated from welcome for independence) --- */

.card {
    border: 1px solid var(--Borders);
    border-radius: 6px;
    background: var(--Window);
    cursor: pointer;
    transition: box-shadow 0.2s ease, transform 0.2s ease;
    box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.25);
    overflow: hidden;
    user-select: none;
}

.card:hover {
    box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.4);
    transform: scale(1.05);
}

.card.selected {
    border-color: var(--Highlight);
    box-shadow: 0 0 0 2px var(--Highlight);
}

.card-image {
    width: 100%;
    height: 100px;
    object-fit: cover;
    background: var(--AlternateBase);
    display: block;
}

.card-image.placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2em;
    color: var(--UnselectedText);
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

.card-badge {
    display: inline-block;
    font-size: 0.7em;
    padding: 1px 6px;
    border-radius: 3px;
    background: var(--Highlight);
    color: var(--HighlightedText);
    margin-right: 4px;
}

.card-stars {
    font-size: 0.75em;
    color: var(--UnselectedText);
    margin-top: 2px;
}

/* --- Details panel --- */

#details-panel {
    position: fixed;
    top: 0;
    right: 0;
    width: 420px;
    height: 100vh;
    background: var(--Window);
    border-left: 1px solid var(--Borders);
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
    border-top: 1px solid var(--Borders);
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
    color: var(--UnselectedText);
}

.details-field span {
    flex: 1;
    font-size: 0.9em;
}

.details-actions {
    margin-top: 24px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.details-actions button {
    padding: 8px 16px;
    border: 1px solid var(--Borders);
    border-radius: 4px;
    background: var(--Button);
    color: var(--ButtonText);
    cursor: pointer;
    font-size: 0.9em;
}

.details-actions button:hover {
    background: var(--Highlight);
    color: var(--HighlightedText);
}

.details-actions button.install {
    background: var(--Highlight);
    color: var(--HighlightedText);
    border-color: var(--Highlight);
}

.details-actions button.install:hover {
    opacity: 0.9;
}
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/components/appstore/resources/appstore.css
git commit -m "feat(appstore): add CSS with tab bar, tag chips, card grid, detail panel"
```

### Task 9: Create AppStore JavaScript

**Files:**
- Create: `SciQLop/components/appstore/resources/appstore.js`

- [ ] **Step 1: Create the JS file**

Write this to `SciQLop/components/appstore/resources/appstore.js`:

```javascript
let backend = null;
let selectedCard = null;
let allPackages = [];
let activeTags = new Set();
let activeCategory = "";
let activeSort = "stars";

var TYPE_ICONS = {plugin: "\uD83D\uDD0C", workspace: "\uD83D\uDCC1", example: "\uD83D\uDCD6"};

// --- Initialization ---

function init() {
    new QWebChannel(qt.webChannelTransport, function(channel) {
        backend = channel.objects.backend;
        loadTags();
        loadPackages();
    });
}

// --- Data loading ---

function loadTags() {
    backend.list_tags(function(json_str) {
        var tags = JSON.parse(json_str);
        var container = document.getElementById("tag-chips");
        container.innerHTML = "";
        tags.forEach(function(tag) {
            var chip = document.createElement("span");
            chip.className = "tag-chip";
            chip.textContent = tag;
            chip.dataset.tag = tag;
            chip.addEventListener("click", function() {
                if (activeTags.has(tag)) {
                    activeTags.delete(tag);
                    chip.classList.remove("active");
                } else {
                    activeTags.add(tag);
                    chip.classList.add("active");
                }
                renderCards();
            });
            container.appendChild(chip);
        });
    });
}

function loadPackages() {
    backend.list_packages("", function(json_str) {
        allPackages = JSON.parse(json_str);
        renderCards();
    });
}

// --- Rendering ---

function renderCards() {
    var query = (document.getElementById("search-input").value || "").toLowerCase();
    var container = document.getElementById("package-cards");
    container.innerHTML = "";

    var filtered = allPackages.filter(function(pkg) {
        if (activeCategory && pkg.type !== activeCategory) return false;

        if (activeTags.size > 0) {
            var pkgTags = pkg.tags || [];
            var hasTag = false;
            activeTags.forEach(function(t) {
                if (pkgTags.indexOf(t) !== -1) hasTag = true;
            });
            if (!hasTag) return false;
        }

        if (query) {
            var text = (pkg.name + " " + pkg.description + " " + (pkg.tags || []).join(" ")).toLowerCase();
            if (text.indexOf(query) === -1) return false;
        }

        return true;
    });

    filtered.sort(function(a, b) {
        if (activeSort === "stars") return b.stars - a.stars;
        if (activeSort === "name") return a.name.localeCompare(b.name);
        return 0;
    });

    filtered.forEach(function(pkg) {
        container.appendChild(createPackageCard(pkg));
    });
}

// --- Card creation ---

function createPackageCard(pkg) {
    var card = document.createElement("div");
    card.className = "card";
    card.dataset.name = pkg.name.toLowerCase();
    card.dataset.tags = (pkg.tags || []).join(" ").toLowerCase();

    var icon = TYPE_ICONS[pkg.type] || "\uD83D\uDCE6";
    card.innerHTML =
        '<div class="card-image placeholder">' + icon + '</div>' +
        '<div class="card-body">' +
            '<span class="card-badge">' + escapeHtml(pkg.type) + '</span>' +
            '<span class="card-name">' + escapeHtml(pkg.name) + '</span>' +
            '<div class="card-stars">\u2B50 ' + pkg.stars + ' &middot; ' + pkg.downloads + ' downloads</div>' +
        '</div>';

    card.addEventListener("click", function() {
        selectCard(card);
        showPackageDetails(pkg);
    });
    return card;
}

// --- Details panel ---

function showPackageDetails(pkg) {
    var panel = document.getElementById("details-panel");
    document.getElementById("details-title").textContent = pkg.name;

    var tagsHtml = (pkg.tags || []).map(function(t) {
        return '<span class="card-badge">' + escapeHtml(t) + '</span>';
    }).join(" ");

    var content = document.getElementById("details-content");
    content.innerHTML =
        '<div class="details-field"><label>Type</label><span><span class="card-badge">' + escapeHtml(pkg.type) + '</span></span></div>' +
        '<div class="details-field"><label>Author</label><span>' + escapeHtml(pkg.author) + '</span></div>' +
        '<div class="details-field"><label>Version</label><span>' + escapeHtml(pkg.version) + '</span></div>' +
        '<div class="details-field"><label>Description</label><span>' + escapeHtml(pkg.description) + '</span></div>' +
        '<div class="details-field"><label>Tags</label><span>' + tagsHtml + '</span></div>' +
        '<div class="details-field"><label>Stars</label><span>\u2B50 ' + pkg.stars + '</span></div>' +
        '<div class="details-field"><label>Downloads</label><span>' + pkg.downloads + '</span></div>' +
        '<div class="details-actions">' +
            '<button class="install">Install (coming soon)</button>' +
        '</div>';

    panel.classList.remove("hidden");
    panel.classList.add("visible");
}

function hideDetails() {
    var panel = document.getElementById("details-panel");
    panel.classList.remove("visible");
    panel.classList.add("hidden");
    if (selectedCard) {
        selectedCard.classList.remove("selected");
        selectedCard = null;
    }
}

// --- Selection ---

function selectCard(card) {
    if (selectedCard) selectedCard.classList.remove("selected");
    selectedCard = card;
    card.classList.add("selected");
}

// --- Event listeners ---

document.addEventListener("DOMContentLoaded", function() {
    // Tab switching
    document.querySelectorAll(".tab").forEach(function(tab) {
        tab.addEventListener("click", function() {
            document.querySelector(".tab.active").classList.remove("active");
            tab.classList.add("active");
            activeCategory = tab.dataset.category;
            renderCards();
        });
    });

    // Search
    document.getElementById("search-input").addEventListener("input", function() {
        renderCards();
    });

    // Sort
    document.getElementById("sort-select").addEventListener("change", function() {
        activeSort = this.value;
        renderCards();
    });

    // Click outside to deselect
    document.body.addEventListener("click", function(e) {
        if (!e.target.closest(".card, #details-panel, .tag-chip, .tab, #toolbar")) {
            hideDetails();
        }
    });
});

// --- Utilities ---

function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// --- Start ---
init();
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/components/appstore/resources/appstore.js
git commit -m "feat(appstore): add JS for tabs, search, tag filtering, sort, detail panel"
```

---

## Chunk 5: Main Window Integration

### Task 10: Wire AppStore into main window

**Files:**
- Modify: `SciQLop/core/ui/mainwindow.py`

The AppStore dock panel is created lazily. A "Plugin Store" menu entry and the welcome page "Browse all" signal both trigger `_show_appstore()`.

- [ ] **Step 1: Add lazy AppStore creation and wiring**

In `SciQLop/core/ui/mainwindow.py`, add at the end of `_setup_ui` method (before `self._center_and_maximise_on_screen()` on line 165):

```python
        self._appstore = None
        self.toolsMenu.addAction("Plugin Store", self._show_appstore)
        self.welcome.backend.appstore_requested.connect(self._show_appstore)
```

Add a new method to the `SciQLopMainWindow` class (before `_update_usage`):

```python
    def _show_appstore(self):
        if self._appstore is None:
            from SciQLop.components.appstore import AppStorePage
            self._appstore = AppStorePage()
            self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, self._appstore)
        else:
            dw = self.dock_manager.findDockWidget(self._appstore.windowTitle())
            if dw:
                dw.toggleView(True)
                dw.raise_()
```

- [ ] **Step 2: Test the full integration**

Run: `uv run sciqlop`

Check:
- Welcome page loads with two-column layout
- Hero bar shows last-used workspace
- "Browse all →" in right column opens AppStore dock panel
- Tools menu → "Plugin Store" opens AppStore dock panel
- AppStore shows tab bar, search, tag chips, card grid with mock data
- Clicking a card shows detail panel with name, author, version, description, tags, stats
- Tab switching filters cards
- Search filters cards
- Tag chips filter cards (multi-select OR)
- Sort dropdown works (Popular, Name)
- Clicking outside a card closes detail panel

- [ ] **Step 3: Commit**

```bash
git add SciQLop/core/ui/mainwindow.py
git commit -m "feat(appstore): wire AppStore dock panel into main window with lazy creation"
```
