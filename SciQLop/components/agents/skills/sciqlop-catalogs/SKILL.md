---
name: sciqlop-catalogs
description: Use when the user wants to label, list, create, edit or show events — "mark the magnetopause crossings", "make a catalog of the shocks", "show my events on the panel", "detect intervals where B exceeds 50 nT and save them", "compare these two crossings". Covers SciQLop's catalog API (create, add, edit, remove events) and catalog overlays on plot panels.
---

# Catalogs and events in SciQLop

The `sciqlop_*` tools named here exist only inside SciQLop's chat panel.
There is no catalog tool: everything goes through `sciqlop_exec_python` and
the public API. Call `sciqlop_api_reference('catalogs')` to check signatures
before writing code.

A catalog is a named list of events. An event has a start, a stop, and
metadata (tags, rating, and your own attributes).

## The API

```python
from SciQLop.user_api.catalogs import catalogs

catalogs.list()                               # every catalog path
catalogs.list("Catalogs (cocat-rs)")          # only the user's own and shared ones
cat = catalogs.get("Catalogs (cocat-rs)//shocks")   # a speasy Catalog
for e in cat:
    print(e.start_time, e.stop_time, dict(e.meta))
```

- **Paths** are `"<provider>//<project>//<name>"`, with `//` between levels
  and no single `/` inside a name. The project is named by its id, as
  `catalogs.list()` prints it. Leave it out (`"Catalogs (cocat-rs)//shocks"`)
  to mean the user's default project: their account's own project when signed
  in, "My catalogues" otherwise.
- **Providers:** `Catalogs (cocat-rs)` holds the user's catalogs, in
  projects. Write to the default project unless the user names another one;
  a project shared with the user may be read-only. `Remote` (Speasy/AMDA
  catalogs) is read-only.
- **"All events"**: each open project of `Catalogs (cocat-rs)` lists a
  read-only `"<provider>//<project>//All events"`, every event of the project
  outside the trash. Read it with `get()`; it cannot be written to.
- **The Catalogs panel** groups them differently from paths: "My catalogues"
  (the default project's catalogs, shown directly), "Shared" (projects shared
  with others) and "Reference" (public catalogues, AMDA, plugin lists). A
  path still starts with the provider's name, never with a section's.
- **Write events** as a list of `(start, stop)` or `(start, stop, meta)`
  tuples, a list of speasy events, or a speasy `Catalog`:
  - `catalogs.create(path, events)` makes a new catalog; it raises
    `ValueError` if the path exists.
  - `catalogs.add_events(path, events)` appends; `KeyError` if the catalog
    does not exist.
  - `catalogs.save(path, events)` **replaces all the events** with the ones
    you pass. Events coming from `catalogs.get()` keep their identity and are
    updated, not duplicated.
  - `catalogs.remove_events(path, [events from get()])` removes events.
  - `catalogs.remove(path)` deletes the whole catalog. Ask first.
- **Editing** an event: `get()` the catalog, change the events, `save()` it.
- **Writing to disk:** `Catalogs (cocat-rs)` stores each change as it
  happens, and syncs it to the user's account when signed in.
  `catalogs.persist(path)` is still the portable way to say "save": it does
  nothing more there, and other providers need it; `Remote` raises
  `PermissionError`.
- Reads and writes wait for a catalog whose events are still loading in the
  background (right after startup), so `get()` never returns a half-loaded
  catalog.

## Filtering a catalogue

```python
kept = catalogs.filter("Remote//ICME_multi_catalog", "2019-03")   # a speasy Catalog of the kept events
```

`catalogs.filter(path, text)` keeps what the catalog browser's filter box
would keep for that catalog, in that catalog's provider's language. An empty
text keeps all.

- `Catalogs (cocat-rs)`: plain words (each word part of a tag, the status,
  the author, an attribute value, or the start of the start time), or a
  search in the smart catalogue language below (`tag:shock
  confidence:>=0.7`, `#density:>5`, `OR`, `NOT`). A wrong search raises
  `cocat_rs.QueryError`.
- Every other provider: the events where the text appears in any column as
  the table shows it (dates as `2019-03-14 02:00:00`, values, tags).

Use it to narrow a catalogue before working on it; to make a lasting
selection in `Catalogs (cocat-rs)`, use a smart catalogue (below).

```python
catalogs.filter("Catalogs (cocat-rs)//events", "tag:shock duration:>1h")
```

## Smart catalogues

A smart catalogue's events are those its **search** finds, kept up to date
as the project changes (only in `Catalogs (cocat-rs)`). Its events cannot be
edited one by one: change the search instead.

```python
catalogs.create_smart("Catalogs (cocat-rs)//strong shocks", "tag:shock confidence:>=0.7")
catalogs.create_smart("Catalogs (cocat-rs)//recent", "created:now-7d",
                      source="Catalogs (cocat-rs)//shocks")   # search one catalogue only
catalogs.search_of(path)              # the search line, None for a plain catalogue
catalogs.set_search(path, "tag:wave") # a plain catalogue becomes smart
catalogs.freeze(path, "strong shocks, fixed")   # a normal copy of what it holds now; returns its path
catalogs.remove_search(path)          # keeps the events it lists, stops adding events
catalogs.rule_of(path) / catalogs.set_rule(path, {...})   # the stored JSON rule
```

- **Search syntax** (one line, the same as the catalog tree's editor and the
  CoCat web app): `field:value`, with `>`, `>=`, `<`, `<=`, `=` (exact) after
  the colon; terms side by side mean AND, `OR` and `NOT` and brackets combine
  them. Fields: `start`, `stop`, `duration`, `tag`, `status`, `confidence`,
  `author`, `catalogue`, `created`, `origin`, `product`, ... and any attribute
  as `#key` (`#density:>10`). Times: `start:>2020-01-01`, `created:now-7d`.
  `_exists_:field` tests presence: `NOT _exists_:catalogue` is "in no
  catalogue".
- A wrong search raises `cocat_rs.QueryError` (a `ValueError`) with
  `.position`, `.length` and `.suggestion` ("did you mean author?"): fix it
  and try again rather than guessing.
- `rating` is not a search field: SciQLop's rating 1-10 is `confidence` 0-1
  (`rating >= 7` is `confidence:>=0.7`).
- Searches cannot look at data values (no "where Bz < -5 nT"): compute such
  intervals in Python and `create()` a normal catalogue.
- For merging, shifting or windows, use a JSON rule with `set_rule`; ask the
  user before writing one by hand.

## Showing a catalog on a panel

```python
overlay = panel.add_catalog_overlay("Catalogs (cocat-rs)//shocks")   # draws the events as spans
overlay.show_spans = False      # keep it attached for navigation, stop drawing it
panel.remove_catalog_overlay(overlay)                        # or overlay.remove()
```

`panel` is a `PlotPanel` from `SciQLop.user_api.plot` (for example
`plot_panel("Panel0")`; check with `sciqlop_api_reference('plot')`).

`panel.catalog_mode` sets how the overlays react, like the panel's mode combo
and Ctrl+Shift+M:
- `"view"`: clicking an event selects it.
- `"jump"`: picking an event in the catalog browser moves the panel to it.
  Set this when the user wants to step through the events.
- `"edit"`: the user draws new events with Shift+click and moves the spans of
  editable catalogs.

## Workflow for "find and label events"

0. Settle the criterion, the target catalog and whether to save before
   starting (see the `sciqlop-clarify` skill).
1. Fetch the data with `sciqlop_fetch` and compute the criterion with
   `sciqlop_exec_python` (threshold, jump, rotation, ...).
2. Turn it into intervals: start and stop times, merging samples closer than
   a sensible gap. Print how many you found and a few of them.
3. Check the result with the user before writing anything when the
   criterion was not fully specified. Never invent event times: every event
   must come from data you computed.
4. Write with `catalogs.create(...)`, or `add_events` for an existing catalog.
   Put what you used in the metadata, for example
   `{"criterion": "Bt > 50 nT", "product": "<tree path>"}`.
5. Overlay it on the panel and take a screenshot to check the spans sit on
   the features.
6. **The catalog is stored as you write it**, and synced to the user's account
   when signed in. So write only once the user agrees with the events, and
   remove a catalog you made by mistake (ask first). Call
   `catalogs.persist(path)` at the end all the same.

## Traps

- **Times:** `datetime` (naive means UTC), ISO strings, `numpy.datetime64` or
  epoch seconds as a **float**. A plain `int` epoch raises `TypeError`; write
  `float(t)`.
- **start must not be after stop**, or the write raises `ValueError`.
  start == stop is allowed (an instant).
- **Reserved names:** `start`, `stop`, `uuid`, `tags`, `products` and
  `rating` are built-in fields, not free attributes. `tags` is a list of
  strings, `rating` an integer from 1 to 10 (stored as a confidence: it comes
  back rounded to a whole number). `catalogs.get()` returns both when set.
  The event's author is set by SciQLop (the signed-in account); an `author`
  key you pass is kept as a plain attribute.
- **Attribute names:** use letters, digits and `_`, starting with a letter
  (`shock_angle`, not `shock angle`), as the catalog browser asks.
- **Remove overlays with `panel.remove_catalog_overlay` or `overlay.remove()`.**
  Never reach into `panel._impl` or the catalog manager from a cell.
