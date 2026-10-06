---
name: sciqlop-clarify
description: Use when about to start a larger task in SciQLop — an analysis, a new virtual product, a labeling or event-detection campaign, a plugin, or any request whose wording leaves the data, the time range, the physics or the deliverable open. Gives the questions worth asking the user first, by task, and how to ask them without slowing the user down.
---

# Settle what the user wants before acting

A science request is often short and leaves real choices open. Guessing
costs more than asking: a wrong product or definition means fetching,
computing and plotting the wrong thing, then starting over. One good
question up front is cheaper.

## How to ask

- **Ask only what changes the result.** Skip a question whose answer you can
  read from the screen (`sciqlop_describe_panel`, `sciqlop_active_panel`),
  find in the data, or redo cheaply.
- **One round, at most three questions.** Put the most consequential first.
- **Offer your pick with each question,** so the user can answer "yes" or
  "the second one". For example: "Which proton velocity: Wind/3DP (25 s, what
  is on Panel0) or Wind/SWE (92 s)? I'd use 3DP."
- **Use the agent's question tool when it has one;** it shows as choices in
  the panel. Otherwise ask in your reply and stop until the user answers.
- **Restate the plan before starting,** in one or two sentences: what you
  will fetch, compute and deliver. The user can correct it at a glance.
- **For a short or clear request, don't ask.** Make the obvious choice, state
  it in one line, and go.

## What to settle, by task

**Data**
- Which product: mission, instrument, survey or burst. If several products
  fit, name the candidates (see the `sciqlop-finding-data` skill).
- Which time interval, if it is not the panel's current one.
- Coordinate frame (GSE, GSM, RTN, ...) when vectors are involved.

**Computation** (virtual products, analyses)
- The exact definition. "Module of the difference" of two vectors on
  different time grids already needs a choice: which grid to interpolate
  onto.
- Units of the result, and whether to keep or fill gaps (NaN stays NaN
  unless the user says otherwise).
- Parameters with no obvious value: window length, threshold, smoothing.
  Propose one and make it a knob, so the user can change it on the plot.

**Event detection and catalogs**
- The criterion: threshold, duration, how close two events must be to merge.
- Which catalog to write to, new or existing, and whether to save it to disk
  (`catalogs.persist`). Saving `My Catalogs` also saves the user's own
  pending edits.

**Deliverable**
- A plot on the current panel, a new panel, a virtual product reusable from
  the product tree, a notebook the user keeps, or a catalog.
- When the user says "in a notebook": a new notebook or an existing one, and
  where in it.

**Before anything hard to undo**
- Deleting a catalog or events, overwriting a notebook cell, installing a
  package, or saving a store that holds the user's edits: say what will
  change and wait for a yes.

## Then follow the task's own skill

Once the plan is agreed, use the matching skill: `sciqlop-finding-data`,
`sciqlop-virtual-products`, `sciqlop-catalogs`, `sciqlop-troubleshooting` or
`sciqlop-plugin-design`.
