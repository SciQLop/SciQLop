# Catalog Provider API Design

## Goal

Introduce a central catalog provider abstraction in SciQLop so that any backend
(TSCat, CoCat, CSV timetables, etc.) can expose catalogs and events through a
common API. All catalogs become accessible from a single unified UI, with
support for cross-provider operations like copy and drag-and-drop.

## Constraints

- ~100 catalogs per user; individual catalogs range from a few events to 100k+.
- Catalog listing is cheap; event loading must be lazy / range-queryable.
- Some providers are read-only; capabilities vary per provider and per catalog.
- Third-party providers must be able to expose custom capabilities without
  modifying SciQLop.
- Base classes are QObject-derived (signals, Qt parent ownership, thread safety).
- The existing TSCat LightweightManager stays untouched; the new UI runs in
  parallel until it proves itself.

## 1. Core Data Model

### CatalogEvent

Minimal QObject: `uuid`, `start`, `stop`, optional `meta() -> dict[str, Any]`.
No color or tooltip — those are UI concerns. Emits `range_changed` signal.

### Catalog

Plain data object (not QObject): `uuid`, `name`, back-reference to owning
`CatalogProvider`.

### CatalogProvider

QObject ABC. Maintains a sorted event list per catalog internally (stdlib
`bisect`). Subclasses populate via protected methods; the base class handles
range queries.

```
Public query API:
  catalogs() -> list[Catalog]
  events(catalog, start=None, stop=None) -> list[CatalogEvent]

Protected mutation API (used by subclasses):
  _set_events(catalog, events)
  _add_event(catalog, event)
  _remove_event(catalog, event)

Signals:
  catalog_added(Catalog)
  catalog_removed(Catalog)
  events_changed(Catalog)
  error_occurred(str)
```

Range queries use `bisect.bisect_left/right` on the sorted list keyed by
`start`. `_add_event` inserts with `bisect.insort`. This is factored into the
base class so every provider gets efficient range queries for free.

## 2. Registry + Auto-Registration

### CatalogRegistry

Singleton QObject accessible via `CatalogRegistry.instance()`.

```
Signals:
  provider_registered(CatalogProvider)
  provider_unregistered(CatalogProvider)

Methods:
  providers() -> list[CatalogProvider]
  register(provider)
  unregister(provider)
  all_catalogs() -> list[Catalog]
```

### Auto-Registration

`CatalogProvider.__init__()` calls `CatalogRegistry.instance().register(self)`.
Cleanup is tied to `QObject.destroyed` signal, not `__del__`.

A plugin's `load()` just instantiates its provider — no explicit registration:

```python
def load(main_window):
    provider = MyCocatProvider(parent=main_window)
```

### File Location

`SciQLop/components/catalogs/backend/`:
- `provider.py` — `CatalogProvider`, `Catalog`, `CatalogEvent`
- `registry.py` — `CatalogRegistry`

## 3. Capabilities System

### Capability Enum

`str, Enum` so it's both type-safe and open-ended:

```python
class Capability(str, Enum):
    EDIT_EVENTS = "edit_events"
    CREATE_EVENTS = "create_events"
    DELETE_EVENTS = "delete_events"
    CREATE_CATALOGS = "create_catalogs"
    DELETE_CATALOGS = "delete_catalogs"
    EXPORT_EVENTS = "export_events"
    IMPORT_EVENTS = "import_events"
    IMPORT_FILES = "import_files"
```

Third-party providers define their own `str, Enum` subclasses — they
interoperate because the set is `set[str]`.

### Per-Catalog Granularity

```python
def capabilities(self, catalog: Catalog | None = None) -> set[str]: ...
```

Allows mixed providers where some catalogs are read-only and others editable.

### Custom Actions

For capabilities SciQLop doesn't know about, providers expose actions:

```python
@dataclass
class ProviderAction:
    name: str
    callback: Callable[[Catalog], None]
    icon: QIcon | None = None

def actions(self, catalog: Catalog | None = None) -> list[ProviderAction]: ...
```

The UI surfaces these in context menus without needing to understand them.

## 4. Unified UI

New dock widget alongside the existing LightweightManager.

### Layout

```
┌──────────────────────────────────────────────┐
│ [Filter...]                                  │
├──────────────┬───────────────────────────────┤
│  Catalog     │   Event Table                 │
│  Tree        │   (for selected catalog)      │
│              │                               │
│  - Provider1 │   start | stop | meta...      │
│    - Cat A   │   row 1                       │
│    - Cat B   │   row 2                       │
│  - Provider2 │   ...                         │
│    - Cat C   │                               │
├──────────────┴───────────────────────────────┤
│ [+ Add Event]  [Delete]  [Custom actions...] │
└──────────────────────────────────────────────┘
```

### Catalog Tree (left)

- Tree model: Provider → Catalog, fed from `CatalogRegistry`.
- Reacts to registry signals.
- Filter bar does substring matching on catalog names.
- Context menu populated from `provider.actions(catalog)`.

### Event Table (right)

- Flat table for the selected catalog's events.
- Columns: `start`, `stop`, plus dynamic columns from `meta()` keys.
- Lazy loaded via `provider.events(catalog, start, stop)` based on visible
  time range or on catalog selection.
- Sortable by start time (default) or any column.
- Selecting an event emits a signal for plot integration.

### Toolbar (bottom)

- Capability-driven: buttons appear only if the relevant capability is present.
- Custom `ProviderAction`s appear as additional buttons or overflow menu.

### Plot Integration

- Selected catalog's events (within visible time range) drawn as vertical spans
  on the active plot panel.
- Reuses existing `MultiPlotsVSpanCollection` from SciQLopPlots.
- Editing a span updates the event through the provider if `EDIT_EVENTS` is
  supported.

### File Location

`SciQLop/components/catalogs/ui/`:
- `catalog_browser.py` — main dock widget
- `catalog_tree.py` — left panel tree view + model
- `event_table.py` — right panel table

## 5. Cross-Provider Operations

### Copy / Import

- Source provider has `EXPORT_EVENTS`, target has `IMPORT_EVENTS`.
- The registry or a helper orchestrates: read events from source, call
  `target.import_events(catalog_name, events)`.
- Events transfer as minimal data (start/stop + meta dict). Provider-specific
  metadata transfers as-is in the dict; the target decides what to keep.
- Copy only, not move. Deleting from source is a separate action requiring
  `DELETE_EVENTS`.

```python
def import_events(self, catalog_name: str,
                  events: list[CatalogEvent]) -> Catalog: ...
```

### Drag and Drop

- **Drag catalog** onto a different provider → copy/import flow.
- **Drag events** onto a different catalog → copy those events.
- **Drag files** from file manager → provider with `IMPORT_FILES` handles drop.
- Custom MIME types: `application/x-sciqlop-catalog`,
  `application/x-sciqlop-events`.
- Visual feedback: green drop indicator if target supports the operation,
  forbidden cursor otherwise.

## 6. Error Handling

- Providers raise exceptions from I/O methods; the UI wraps all calls in
  try/except.
- Non-blocking status message in the browser widget (no modal dialogs).
- Full traceback logged via `SciQLopLogging`.
- Errored provider/catalog shown grayed out with warning icon.
- For async errors, providers emit `error_occurred(str)` signal.
- Other providers continue working unaffected.

## 7. Testing Strategy

### Unit Tests (no Qt)

- Sorted event list + bisect range queries.
- Capability checking logic.

### Qt Tests (with QApplication)

- Provider auto-registration/unregistration lifecycle.
- Signal emissions (catalog_added, events_changed, etc.).
- `DummyProvider` — full in-memory implementation for tests and as reference.

### Integration Tests

- Catalog browser with `DummyProvider`: tree populates, event table loads,
  capability-driven buttons show/hide.
- Drag and drop between two `DummyProvider` instances.
- Cross-provider copy flow.

The `DummyProvider` also serves as documentation — a minimal working example
for third-party developers.
