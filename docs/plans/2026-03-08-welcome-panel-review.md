# Welcome Panel Review — Issues & Improvements

## Usability Issues

### 1. ShortcutCards trigger detail panel for nothing
- `quickstart.py:18` — clicking a ShortcutCard fires the callback AND emits `show_detailed_description`
- No delegate registered for `ShortcutCard`, so the detail panel shows stale or empty content
- **Fix**: QuickStartSection should not use `CardsCollection`, or should not connect to `show_detailed_description`

### 2. Fixed 6-column grid doesn't adapt to window size
- `section.py:17` — `_columns = 6` hardcoded
- Cards cluster left on wide screens, clip on narrow ones
- **Fix**: Compute columns dynamically in `resizeEvent` → `columns = max(1, width // (card_width + spacing))`

### 3. Fixed card sizes don't scale with DPI
- `card.py:76-77` — hardcoded pixel dimensions (100x120, 160x180, 200x220)
- Looks tiny on HiDPI, too large on low-res
- **Fix**: Scale dimensions using `QScreen.devicePixelRatio()` or logical DPI

### 4. "Detailed description" header is generic
- `detailed_description.py:14` — always says "Detailed description"
- **Fix**: Pass context-aware title from the delegate or card type

### 5. Workspace description textChanged signal mismatch
- `recent_workspaces.py:103` — `QTextEdit.textChanged` takes no arguments, but lambda expects `x`
- Description edits silently fail
- **Fix**: Use `self._description.toPlainText()` inside the lambda

### 6. No "Create new workspace" action
- No way to create a workspace from the welcome page
- **Fix**: Add a "+" card or button in the Recent Workspaces section

### 7. No visual distinction for default workspace
- `recent_workspaces.py:33` — `default_workspace` property set but never styled
- Fields are disabled without explanation
- **Fix**: Add a badge/overlay or distinct card style for default workspaces

### 8. Tags ignore theme colors
- `ExamplesView.py:28` — hardcoded `<font color="blue">` / `<font color="black">`
- Unreadable in dark mode
- **Fix**: Use palette colors or stylesheet classes

### 9. No keyboard navigation
- Cards are QFrames, not focusable
- **Fix**: Add focus policy, tab order, Enter-to-open

### 10. Hover animation geometry can go stale
- `card.py:91-114` — fast enter/leave can leave `_initial_geometry` wrong
- **Fix**: Cancel running animation before starting a new one, or reset geometry on leave
