# Command Palette — Design Spec

## Overview

A keyboard-driven command palette for SciQLop, providing fast access to all application actions through fuzzy search. Opens via Ctrl+K (configurable), supports multi-step argument chains with contextual completions, and maintains an LRU history for instant re-execution of previous commands.

## Architecture: Pure Qt Widget Overlay

A `CommandPalette` QWidget parented to the main window — no QWebEngine, no frameless dialogs. Instant show/hide, native keyboard handling, styled through the existing theming system.

## Data Model

### PaletteCommand

```python
@dataclass
class PaletteCommand:
    id: str                    # unique key, e.g. "plot.new_panel"
    name: str                  # display name, e.g. "New plot panel"
    description: str           # short help text
    callback: Callable         # receives resolved args as dict
    args: list[CommandArg]     # argument chain (empty for simple commands)
    icon: QIcon | None = None
    keywords: list[str] = []   # extra fuzzy match terms
    replaces_qaction: str | None = None  # QAction text to suppress during harvest
```

### Completion

```python
@dataclass
class Completion:
    value: str                  # internal value passed to callback
    display: str                # shown in the list
    description: str | None = None
    icon: QIcon | None = None
```

### CommandArg

Abstract base for each step in an argument chain. Subclasses provide contextual completions.

```python
@dataclass
class CommandArg(ABC):
    name: str

    @abstractmethod
    def completions(self, context: dict) -> list[Completion]
```

`context` carries previously resolved args so later steps can adapt (e.g., filtering panels by compatibility with the selected product).

**Built-in arg types:**

| Type | Completions source |
|------|-------------------|
| `ProductArg` | Product tree (all providers) |
| `PanelArg` | Existing panels + "New panel" option |
| `CatalogArg` | Catalog tree (all providers) |
| `DockWidgetArg` | Registered dock widgets |
| `ProviderArg` | Catalog providers with CREATE capability |
| `WorkspaceArg` | Known workspaces |
| `TimeRangeArg` | Preset completions ("Last hour", "Last day", "Last week", "Last month") plus free-text accept — if the user types a value that doesn't match a preset, Enter accepts the raw text as a time range string. The QLineEdit acts as both filter and input. |

### HistoryEntry

```python
@dataclass
class HistoryEntry:
    command_id: str
    resolved_args: dict[str, str]  # serializable values (paths, names)
    timestamp: float
```

## Command Registry

Central registry living on `SciQLopApp`, populated in two phases:

### Phase 1: Explicit registration

Plugins and components register rich commands in their `load()`:

```python
app.command_registry.register(PaletteCommand(
    id="plot.product",
    name="Plot product",
    args=[ProductArg(), PanelArg()],
    callback=do_plot,
))
```

### Phase 2: QAction auto-harvest

After all plugins load, `harvest_qactions(main_window)` walks menus and toolbar, wrapping each QAction as an argless PaletteCommand.

**Deduplication:** A harvested QAction is skipped if its derived ID (`qaction.{menu_path}.{action_text}`) matches an already-registered command ID. Additionally, explicitly registered commands can declare `replaces_qaction: str | None` — a QAction object name or text to suppress during harvest. This is the only reliable dedup mechanism since QAction signal connections cannot be meaningfully compared to registered callbacks.

### Registry API

```python
class CommandRegistry:
    _commands: dict[str, PaletteCommand]
    _history: LRUHistory

    def register(self, command: PaletteCommand) -> None
    def unregister(self, command_id: str) -> None
    def commands(self) -> list[PaletteCommand]
    def harvest_qactions(self, main_window: QMainWindow) -> None
```

**Thread safety:** The registry is only accessed from the Qt main thread. No synchronization needed.

## Palette Widget (UI)

### Layout

- Centered horizontally, anchored near top of main window (VS Code style)
- Width: ~50-60% of window, resizes via `resizeEvent`
- **QLineEdit** at top — placeholder text reflects current step ("Search commands...", "Select product...", "Select panel...")
- **QListView** below — filtered results rendered via custom `QStyledItemDelegate` (icon + name + description + category tag)
- Drop shadow via `QGraphicsDropShadowEffect`

### State Machine

```
IDLE → (Ctrl+K) → COMMAND_SELECT → (pick command) →
  if no args: execute → IDLE
  if args: ARG_SELECT(step=0) → (pick arg) → ARG_SELECT(step=1) → ... → execute → IDLE
```

### Key Bindings (within the palette)

| Key | Action |
|-----|--------|
| Escape | Back one step, or close if at COMMAND_SELECT |
| Enter | Select highlighted item |
| Up/Down | Navigate list |
| Typing | Fuzzy filter current list |
| Backspace on empty | Back one step |
| Ctrl+K | Close (toggle) |

### Initial View (COMMAND_SELECT)

Shows two groups, fuzzy-filtered together:
1. **Recent** (LRU history) — displayed as full chain: "Plot product → B_gsm → Panel 1". Re-executes entire chain in one Enter.
2. **Commands** — all registered commands.

History entries get a small score bonus to surface near the top on short/empty queries.

## Fuzzy Matching

Lightweight Python implementation (~50 lines), no dependencies.

**Scoring:** subsequence matching with bonuses for:
- Consecutive character matches
- Match at word boundaries (after `/`, `_`, space, camelCase transitions)
- Match at start of string

**Highlighting:** matched characters rendered in bold/accent color by the delegate.

## History & Persistence

- **LRU behavior:** re-executing a command+args combo moves it to front, no duplicates
- **Storage:** `~/.config/sciqlop/command_palette_history.json` — standalone JSON rather than ConfigEntry because history is a cache (append-heavy, not user-edited), while ConfigEntry is for user-facing settings
- **Lifecycle:** `LRUHistory` loads from disk on first access (lazy), saves after each mutation (append/promote). This avoids data loss on crash without needing explicit save-on-close.
- **Max size:** configurable via settings (default 50), oldest evicted
- **Stale entries:** if a referenced panel/catalog no longer exists, entry shown dimmed or skipped. Command itself still appears — just args may need re-selection.

## Settings

```python
class CommandPaletteSettings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.APPLICATION
    subcategory: ClassVar[str] = "Command Palette"

    keybinding: str = "Ctrl+K"
    max_history_size: int = 50
```

Follows the existing Pydantic ConfigEntry pattern — auto-persisted to `~/.config/sciqlop/commandpalettesettings.yaml`.

## Code Organization

```
SciQLop/components/command_palette/
    __init__.py
    backend/
        registry.py      — CommandRegistry, PaletteCommand, CommandArg base + built-in arg types
        history.py        — LRU history, JSON persistence
        fuzzy.py          — scoring/matching function
        harvester.py      — QAction auto-discovery + dedup
    ui/
        palette_widget.py — CommandPalette widget, state machine, QLineEdit + QListView
        delegate.py       — custom QStyledItemDelegate for rendering results
    settings.py           — CommandPaletteSettings
```

## Integration Points

1. **`SciQLopApp`** — owns the `CommandRegistry` instance (accessible app-wide)
2. **`SciQLopMainWindow`** — creates `CommandPalette` as child widget, wires `QShortcut` for keybinding, calls `harvest_qactions()` after all plugins load
3. **Plugins** — register rich commands via `SciQLopApp.instance().command_registry.register(...)` in `load()`
4. **Welcome page** — news entry announcing the feature

## Built-in Commands (Day One)

### Auto-harvested (argless)

- Toggle dock widgets (Product Tree, Catalog Browser, Properties, Logs, Settings, Workspace Manager)
- Reload stylesheets
- Start Jupyter console
- Open Plugin Store
- Toggle fullscreen

### Explicitly registered (with argument chains)

| Command | Args chain |
|---------|-----------|
| New plot panel | — |
| Plot product | ProductArg → PanelArg |
| Remove panel | PanelArg |
| Set time range | TimeRangeArg |
| Create catalog | ProviderArg |
| Open catalog | CatalogArg |
| Start JupyterLab | — |
| Switch workspace | WorkspaceArg |

Plugins can register additional commands (e.g., collaborative catalogs: "Join room" with RoomArg).
