# SciQLop AppStore — Design Plan

## Concept

A community hub for discovering and installing plugins, workspaces, and examples shared by the SciQLop community. Integrated into the welcome panel and available as a standalone view.

## Architecture

### Data model

```python
class CommunityPackage(BaseModel):
    name: str
    author: str
    description: str
    type: Literal["plugin", "workspace", "example"]
    tags: list[str]
    version: str
    thumbnail_url: str
    download_url: str
    stars: int = 0
    downloads: int = 0
```

### Index hosting

- Static JSON index on GitHub (e.g. `sciqlop-community/index.json`)
- No server infrastructure needed initially
- Contributors submit PRs to add/update packages
- CI validates submissions (schema, URL reachability, metadata)

### Package formats

- **Plugins**: pip-installable Python packages or plain directories
- **Workspaces**: zip archives of workspace directories (workspace.json + notebooks + assets)
- **Examples**: same as workspace archives but with example.json

## Implementation phases

### Phase 1 — Community section on welcome page

Add a fourth `WelcomeSection` to `WelcomePage`:
```
WelcomePage
├── Quick Start
├── Recent Workspaces
├── Examples (local/built-in)
└── Community (NEW)
    ├── Featured cards (curated subset from index)
    └── "Browse all →" button
```

- New `CommunitySection(WelcomeSection)` in `components/welcome/sections/`
- Fetches index JSON on startup (async, cached)
- Shows a few featured/popular items as cards
- Reuses `Card` + `CardsCollection` pattern
- Detail delegate shows: description, author, stats, install button

### Phase 2 — Install/import workflow

- **Plugins**: download to `~/.local/share/sciqlop/plugins/`, register in `SciQLopPluginsSettings.plugins`
- **Workspaces**: download + extract to workspaces directory (adapt `duplicate_workspace` for remote sources)
- **Examples**: download to community examples directory, discovered alongside built-in ones
- Track installed packages in `CommunitySettings(ConfigEntry)`

### Phase 3 — Full AppStore view

- Dedicated `AppStorePage` dock widget (like welcome page)
- Category tabs: Plugins / Workspaces / Examples
- Search bar + tag filtering
- Sort by: popular, recent, name
- Installed vs. available toggle
- Accessible from welcome page and menu bar

### Phase 4 — Updates & publishing

- Version checking for installed community packages
- Update notifications (badge on Community section)
- CLI or UI tool for packaging and submitting to the index
- Rating/feedback mechanism (GitHub issues or discussions)

## Key decisions

1. **Static index** — no backend server, GitHub-hosted JSON, CI-validated
2. **Reuse delegate pattern** — `register_delegate(CommunityCard)` for detail views
3. **Reuse settings system** — `CommunitySettings(ConfigEntry)` for installed packages
4. **No custom format** — standard pip packages and zip archives
5. **Graceful offline** — cache index locally, show cached content when offline
