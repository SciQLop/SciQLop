# Welcome Panel Improvements — Implementation Plan

## Phase 1: Fix existing issues (current sprint)

### 1.1 Dynamic grid columns in CardsCollection ✓
- Override `resizeEvent` in `CardsCollection` (`section.py`)
- Compute `columns = max(1, available_width // (card_width + spacing))`
- Re-place cards only when column count actually changes
- Override `minimumSizeHint` to allow shrinking to 1 column (reflow instead of horizontal scroll)
- Invalidate card animation geometry cache on relayout (`card.invalidate_animation_cache()`)
- Whole welcome page wrapped in `QScrollArea` for vertical scrolling when content overflows

### 1.2 Fix QuickStart / detail panel interaction ✓
- Disconnected QuickStartSection's `show_detailed_description` signal from WelcomePage
- ShortcutCards now only fire their callback, no longer affect the detail panel

### 1.3 Fix workspace description binding ✓
- `recent_workspaces.py:103` — `textChanged` takes no args; lambda now reads `toPlainText()`

### 1.4 Fix tag colors for theme compatibility ✓
- Replaced hardcoded `<font color="black/blue">` with `<a>` tags that use the palette's link color

## Phase 2: UX enhancements

### 2.1 Add "New workspace" card ✓
- `NewWorkspaceCard` with "add" icon, added first in Recent Workspaces
- Clicking creates and opens a new workspace directly (no detail panel)
- `CardsCollection.add_card` now accepts `connect_detail=False` to skip detail panel signal

### 2.2 Context-aware detail panel header ✓
- `register_delegate` now accepts a `title` parameter
- `DetailedDescription` updates its header label from `title_for(widget)` on each selection
- Workspace → "Workspace details", Example → "Example details"

### 2.3 Workspace badges ✓
- "Active" badge on the currently loaded workspace card
- "Default" badge on the default workspace card
- Badges use `palette(highlight)`/`palette(highlighted-text)` for theme-aware styling

### 2.4 Double-click to open, single-click to select ✓
- Added `double_clicked` signal to `Card` base class
- `WorkSpaceCard`: double-click opens workspace (if no workspace already loaded)
- `ExampleCard`: double-click opens example
- Shortcuts keep single-click behavior (they're actions, not selectable items)

### 2.5 Search/filter bar ✓
- `Card.filter_text()` base method, overridden in `WorkSpaceCard` (name + description) and `ExampleCard` (name + tags)
- `CardsCollection.filter_cards(text)` — only places cards matching the query (case-insensitive substring)
- `WelcomeSection` accepts `filterable=True` to show a filter input in the header row
- Enabled on Recent Workspaces and Examples sections

## Phase 3: DPI awareness — skipped
- Qt6 handles high-DPI scaling natively; manual scaling was over-inflating card sizes
- Reverted `dpi_scale()` — original pixel sizes work correctly across DPI settings

## Phase 4: Keyboard navigation ✓
- Cards have `StrongFocus` policy (Tab navigable)
- Enter emits `clicked` (select), Shift+Enter emits `double_clicked` (open)
- Arrow keys navigate within the grid (Left/Right for adjacent, Up/Down for rows)
- `CardsCollection` event filter handles arrow key routing between visible cards
