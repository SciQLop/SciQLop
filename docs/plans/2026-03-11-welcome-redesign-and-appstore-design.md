# Welcome Page Redesign & AppStore — Design Spec

## Goal

Redesign the welcome page with a two-column layout, hero resume bar, and community section. Add a dedicated AppStore dock panel for browsing community plugins, workspaces, and examples. All community data is mocked — no remote fetching or install workflow.

## Architecture

The welcome page (QWebEngineView + Jinja2 + QWebChannel) gets a two-column layout: left column for user content (resume, workspaces, examples), right column for discovery (news, featured plugins). A new AppStore component follows the same QWebEngineView pattern as a separate dock panel. Both share palette-based theming and card styling.

## Scope

- Welcome page redesign (two-column layout, hero bar, community section)
- AppStore dock panel with mock data (tab bar, search, card grid, detail panel)
- No remote index fetching
- No install/update workflow
- No real community data — hardcoded mock JSON

---

## Welcome Page Redesign

### Layout: Two-Column Split

```
┌──────────────────────────────────────────────────────┐
│  ⚡ Resume: "MMS experiments"  [Open]                 │  ← hero bar
│     Last used 2 hours ago                            │
├──────────────────────────┬───────────────────────────┤
│  Quick Start             │  What's New               │
│  [JupyterLab] [Plot]    │  • SciQLop 0.8 released   │
│                          │  • New MMS data products   │
│  Recent Workspaces       │  • Tip: Virtual products   │
│  [card] [card] [card]    │                           │
│  [card] [card] [card]    │  Featured Plugins          │
│                          │  [card] [card]             │
│  Examples                │  [card] [card]             │
│  [card] [card] [card]    │  Browse all plugins →      │
│  [card] [card] [card]    │                           │
└──────────────────────────┴───────────────────────────┘
```

- Left column (flex: 6): hero bar, quick start, recent workspaces, examples
- Right column (flex: 4): news feed, featured plugins teaser
- Right column has a subtle left border separator
- Details panel slides in as a fixed overlay from the right (unchanged)

### Hero Resume Bar

- Shows the **last-used non-default workspace** with an "Open" button
- If no non-default workspace exists (first-time user), shows a "Create your first workspace" prompt instead
- Spans the full width above both columns
- Accent background color (using `--Highlight` at low opacity)

### Community Section (right column)

#### What's New

A vertical list of news items. Each item is a simple row with an emoji/icon, title, and optional date. Mock data:

```json
[
  {"icon": "🎉", "title": "SciQLop 0.8 released", "date": "2026-03-10"},
  {"icon": "📦", "title": "New MMS data products available", "date": "2026-03-08"},
  {"icon": "💡", "title": "Tip: Use virtual products for derived quantities", "date": "2026-03-05"}
]
```

#### Featured Plugins

A small grid (2 columns) of 3-4 community package cards. Same card style as workspace/example cards but smaller. Below the grid: a "Browse all →" link that opens the AppStore dock panel.

Mock data:

```json
[
  {"name": "AMDA Provider", "type": "plugin", "description": "Access AMDA data directly in SciQLop", "author": "IRAP", "tags": ["data-provider", "amda"], "stars": 42},
  {"name": "Wavelet Analysis", "type": "plugin", "description": "Continuous wavelet transform for time series", "author": "LPP", "tags": ["analysis", "wavelets"], "stars": 28},
  {"name": "MMS Mission Study", "type": "workspace", "description": "Pre-configured workspace for MMS data analysis", "author": "IRAP", "tags": ["mms", "magnetosphere"], "stars": 15},
  {"name": "Solar Wind Tutorial", "type": "example", "description": "Introduction to solar wind data analysis with SciQLop", "author": "Community", "tags": ["tutorial", "solar-wind"], "stars": 33}
]
```

### Backend Changes

`WelcomeBackend` gets new slots and signals:

- `get_hero_workspace() -> str` — returns JSON with same shape as `list_workspaces` entries (`name`, `directory`, `description`, `last_used`, `last_modified`, `image`, `is_default`), filtered to the most recent non-default workspace. Returns `"null"` if no non-default workspace exists.
- `list_news() -> str` — returns mock news JSON
- `list_featured_packages() -> str` — returns mock featured packages JSON
- `open_appstore()` — slot called from JS, emits `appstore_requested` signal

New signal: `appstore_requested = Signal()` — connected in `mainwindow.py` after both welcome page and AppStore dock are created.

### Details Panel Interaction with Two-Column Layout

The details panel is a fixed overlay (`position: fixed; right: 0`) that covers the right column when visible. The left column does NOT shrink — the panel simply overlays. This is the simplest approach and avoids layout reflow. The `#sections.with-details { margin-right: 420px }` rule is removed; instead, clicking outside the panel (on either column) dismisses it.

### Relationship to Earlier AppStore Plan

This spec **supersedes** `docs/plans/2026-03-08-welcome-panel-appstore.md`. The earlier plan's phased approach (Phase 1-4) and `CommunityPackage(BaseModel)` model are deferred. This spec implements the UI shell with mock data as a prerequisite — the data model and remote fetching will be designed when the UI is validated.

---

## AppStore Dock Panel

### Component Structure

New component at `SciQLop/components/appstore/` following the same pattern as the welcome page:

```
SciQLop/components/appstore/
├── __init__.py              # exports AppStorePage
├── backend.py               # AppStoreBackend(QObject) with mock data
├── web_appstore_page.py     # QWebEngineView + QWebChannel widget
└── resources/
    ├── appstore.html.j2     # Jinja2 template
    ├── appstore.css          # Styles (shares card design with welcome)
    └── appstore.js           # Tab switching, search, filtering, detail panel
```

### Layout: Tab Bar + Card Grid

```
┌──────────────────────────────────────────────────────┐
│  [All] [Plugins] [Workspaces] [Examples]             │  ← tab bar
├──────────────────────────────────────────────────────┤
│  🔍 Search plugins, workspaces, examples...  Sort: ▾ │
│  [mms] [solar-wind] [analysis] [data-provider]       │  ← tag chips
├──────────────────────────────────────────────────────┤
│  [card] [card] [card] [card]                         │
│  [card] [card] [card] [card]                         │
│  [card] [card]                                       │
└──────────────────────────────────────────────────────┘
```

### Tab Bar

- Horizontal tabs: All | Plugins | Workspaces | Examples
- Active tab highlighted with `--Highlight` bottom border
- Clicking a tab filters the card grid by package type
- "All" shows everything

### Search and Filtering

- Text search filters by name, description, tags (client-side, same pattern as welcome page)
- Tag chips shown above grid, clickable to toggle filter (multi-select, OR logic — show items matching any active tag)
- Tags combine with text search (AND — item must match both text query and at least one active tag)
- Active tag chips get `--Highlight` background to indicate selection
- Sort dropdown: Popular (by stars, default), Recent, Name (alphabetical)
- All filtering is client-side on the mock data

### Card Grid

- Same `auto-fill` CSS grid as welcome page
- Each card shows: type icon/emoji placeholder, name, type badge, star count
- Same hover shadow/scale as welcome cards

### Detail Panel

Slide-in panel from the right (same CSS pattern as welcome page details):

- **Name** + type badge (Plugin / Workspace / Example)
- **Author** (name, organization)
- **Description** (paragraph)
- **Tags** (chips)
- **Stats** (stars, downloads — mocked)
- **Version**
- **Screenshot** placeholder
- **Install button** (disabled/mock — shows "Install" but does nothing yet)

### Backend

`AppStoreBackend(QObject)` with slots:

- `list_packages(category: str) -> str` — returns mock packages as JSON array. Pass empty string `""` for all categories, or `"plugin"`, `"workspace"`, `"example"` to filter by type.
- `get_package_detail(name: str) -> str` — returns full detail JSON for a single package by name
- `list_tags() -> str` — returns JSON array of all unique tags extracted from mock data

### Mock Data

Hardcoded in `backend.py` as a Python list of dicts:

```python
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
```

---

## Shared Design System

### Common Card CSS

Both welcome page and AppStore use the same card styling. Options:

1. **Duplicate** — each page has its own CSS with the same card rules. Simple, no coupling.
2. **Shared CSS file** — extract `common.css` to a shared location, both pages reference it.

Recommendation: **duplicate for now**. The card styles are ~30 lines of CSS. When a third page needs them, extract then.

### Palette Integration

Both pages inject palette colors via Jinja2 `{% for name, color in palette.items() %}` in `:root`. Same mechanism, same variable names.

---

## Integration

### Main Window

- Import `AppStorePage` from `SciQLop.components.appstore`
- Create **lazily** on first request (not at startup) — `_appstore` starts as `None`, created and docked when first needed
- Add "Plugin Store" entry in Tools menu that triggers `_show_appstore()`
- Connect `self.welcome.backend.appstore_requested` to `_show_appstore()` after welcome page is created
- `_show_appstore()` creates the dock panel on first call, then shows/focuses it

### Signal Flow: "Browse all →"

1. User clicks "Browse all →" in welcome page JS
2. JS calls `backend.open_appstore()`
3. Python slot emits a signal
4. Main window slot shows/focuses the AppStore dock panel

---

## Out of Scope

- Remote index fetching (future: GitHub-hosted JSON)
- Install/update workflow (future: pip install, zip extract)
- Real community data
- User ratings/reviews
- Plugin dependency resolution
- Version checking / update notifications
- Publishing tools
