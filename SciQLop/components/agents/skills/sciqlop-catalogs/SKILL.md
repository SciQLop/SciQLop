---
name: sciqlop-catalogs
description: Use when the user wants to label, list, create, edit or show events — "mark the magnetopause crossings", "make a catalog of the shocks", "show my events on the panel", "detect intervals where B exceeds 50 nT and save them". Covers SciQLop's catalog API (create, add, edit, remove events) and catalog overlays on plot panels.
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

catalogs.list()                       # every catalog path
catalogs.list("My Catalogs")          # only the local ones
cat = catalogs.get("My Catalogs//shocks")   # a speasy Catalog
for e in cat:
    print(e.start_time, e.stop_time, dict(e.meta))
```

- **Paths** are `"<provider>//<name>"`, with `//` between levels and no
  single `/` inside a name.
- **Providers:** `My Catalogs` is the local store and the only one you can
  freely create in. `Shared` (collaborative) is writable only once the user
  has joined a room. `Remote` (Speasy/AMDA catalogs) is read-only.
- **Write events** as a list of `(start, stop)` or `(start, stop, meta)`
  tuples, or a speasy `Catalog`:
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

## Showing a catalog on a panel

```python
overlay = panel.add_catalog_overlay("My Catalogs//shocks")   # draws the events as spans
overlay.show_spans = False      # keep it attached for navigation, stop drawing it
panel.remove_catalog_overlay(overlay)                        # or overlay.remove()
```

`panel` is a `PlotPanel` from `SciQLop.user_api.plot` (for example
`plot_panel("Panel0")`; check with `sciqlop_api_reference('plot')`). The
user switches the panel's catalog mode (View, Jump to the picked event, Edit
to draw new events with Shift+click) from the panel's toolbar or with
Ctrl+Shift+M; there is no API for it.

## Workflow for "find and label events"

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
6. **Tell the user to save.** The API does not write catalogs to disk: they
   live in memory until the user presses Save in the catalog browser, and
   SciQLop warns about unsaved catalogs when it closes.

## Traps

- **Times:** `datetime` (naive means UTC), ISO strings, `numpy.datetime64` or
  epoch seconds as a **float**. A plain `int` epoch raises `TypeError`; write
  `float(t)`.
- **start must not be after stop**, or the write raises `ValueError`.
  start == stop is allowed (an instant).
- **Reserved names:** `start`, `stop`, `author`, `uuid`, `tags`, `products`
  and `rating` are built-in fields, not free attributes. `tags` is a list of
  strings, `rating` an integer, and `author` is always set to "SciQLop".
- **Attribute names** must start with a letter and use only letters, digits
  and `_` (`shock_angle`, not `shock angle`). Others still show in
  `catalogs.get()` but are not saved: they are dropped, with a warning, when
  the catalog is written to disk.
- **Remove overlays with `panel.remove_catalog_overlay` or `overlay.remove()`.**
  Never reach into `panel._impl` or the catalog manager from a cell.
