---
name: sciqlop-finding-data
description: Use when you must locate a product before using it — "plot the magnetic field of MMS1", "which instrument measures the solar wind density", "is there data on this date", survey versus burst, or when a product path is unknown or plot_product says it is not in the products tree. Covers browsing the product tree, reading a product's metadata, and checking coverage and cadence before plotting or fetching.
---

# Finding data in SciQLop

The `sciqlop_*` tools named here exist only inside SciQLop's chat panel. Read
`AGENTS.md` first for the plotting workflow.

## Two ways to name a product

SciQLop shows products in a **product tree** with display names, joined by
`//`:

    speasy//amda//Parameters//Wind//3DP//ion - moments//alpha//velocity GSE

Speasy names the same product by provider and uid: `amda/wind3dp_plsp_va`.

- `sciqlop_plot_product`, `Depends(...)` in virtual products,
  `sciqlop_fetch` and `sciqlop_describe_product` all take the **tree path**.
  Use it everywhere. A leading `root//`, as `sciqlop_describe_panel` prints
  it, is accepted.
- Speasy uids are only for calling `speasy.get_data("provider/uid", ...)`
  yourself, which you rarely need. Do not hunt for them.
- Always use the full `//` path exactly as the tree gives it. Display names
  can contain a `/` (AMDA's "final / prelim"), so a path split on single `/`
  can point somewhere else.

## Workflow

1. **Browse the tree.** `sciqlop_products_tree('')` lists the providers. Pass
   a `//` path to go one level down. A folder lists every child with no
   limit, so pick the mission and instrument early on large providers such
   as `speasy//cda`. Each leaf line shows its full path and its type
   (Scalar, Vector, Multicomponents, Spectrogram).
2. **Shortlist and describe.** For each candidate, call
   `sciqlop_describe_product(product="<tree path>")`. It reads metadata
   without fetching: units, coverage (`start`/`stop`), labels, fill value,
   description and the raw attributes. Choose on the description, units and
   coordinate frame, not on the name alone.
3. **Check coverage against the time the user wants.** A product whose
   coverage ends before the requested range plots nothing, without an
   error. Only Speasy products report coverage; none means unknown, not
   empty.
4. **Check cadence when it matters.** Call `sciqlop_describe_product` with
   `probe=true` and the user's `start`/`stop`. It samples that window and
   reports the real shape, fill value, frame, median cadence in seconds and
   the share of the window lost to gaps. Without `start`/`stop` it samples
   the last day of coverage, which may not be the user's period.
5. **Then use it:** plot it, fetch it with `sciqlop_fetch`, or declare it as
   a virtual-product input.

## Choosing between candidates

- The same quantity often exists under several providers and datasets. Prefer
  the one the user names. Otherwise compare units, cadence, coordinate frame
  and description, and say which one you picked and why.
- Survey versus burst, high versus low resolution: tell them apart by the
  dataset name, the description and the probed cadence. For a range of days,
  a burst product is huge and full of gaps; prefer survey unless asked.
- Coordinate frames (GSE, GSM, RTN, ...) are usually in the name or the
  description. Check before combining two vectors.
- Virtual products appear in the tree too. `sciqlop_list_virtual_products`
  lists them; `sciqlop_describe_product` only shows their tree metadata.

## Traps

- **Never guess a path.** Display names and uids differ, and a plausible path
  that is not in the tree fails. Get every path from `sciqlop_products_tree`.
- **`sciqlop_speasy_inventory`** browses Speasy's own inventory with dotted
  names. Its uids are not tree paths; use it only when the tree lacks
  something.
- **Inside SciQLop, `speasy.amda`, `speasy.cda`, ... are `None`.** Call
  `speasy.get_data("amda/<uid>", start, stop)`, or better, `sciqlop_fetch`
  with the tree path.
- **`sciqlop_fetch`'s coverage %** is the share of finite samples in the
  window you fetched, not the product's availability.
- **Times:** pass ISO-8601 strings (`"2025-10-10T06:00:00"`, read as UTC) or
  epoch seconds.
