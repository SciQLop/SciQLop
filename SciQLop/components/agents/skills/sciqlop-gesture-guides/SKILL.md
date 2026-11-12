---
name: sciqlop-gesture-guides
description: Use when asked for an animation, an animated guide, a "show me how", contextual help or onboarding visuals for SciQLop or one of its plugins - making a short looping SVG that shows one manipulation in a simplified window, and plugging it into Help > Guides, the command palette and a contextual "?" button.
---

# SciQLop gesture guides

A guide is one SVG file, animated with CSS, that shows one gesture in a simplified SciQLop window on a
10 to 18 second loop. SciQLop plays it natively (Qt's SVG renderer, in the colours of the current
theme); the same file plays in a browser, on a website or in a README.

SciQLop's own guides and their generators are the reference:
`SciQLop/components/guides/resources/*.svg` and `SciQLop/components/guides/authoring/core/*.py`.

## Register a guide (plugin or core)

```python
from pathlib import Path
from SciQLop.components.guides.registry import Guide, register_guide

register_guide(Guide(
    id="my_plugin.fit",                               # prefix with the plugin's name
    title="Fit a distribution",
    caption="Drag a box around the peak, then press F.",
    path=Path(__file__).parent / "resources" / "fit.svg",
    keywords=("fit", "distribution"),                  # found by the command palette
    contexts=("my_plugin.fit_tool",),                  # where a "?" should open this guide
))
```

In a plugin, do it in `activate(ctx)`: `ctx.contribute("sciqlop.guides", Guide(...))`, or call
`register_guide` there (or in the older `load(main_window)`).
The guide then appears in Help > Guides and as the palette command "Guide: Fit a distribution", and it
leaves with the plugin.

For contextual help, put a button where the question arises:

```python
from SciQLop.components.guides.ui import GuideButton
layout.addWidget(GuideButton("my_plugin.fit_tool"))     # a "?"; hidden while no guide covers the context
```

`show_guides(widget, "my_plugin.fit")` (same module) opens a guide directly. Core contexts a plugin may
also cover with a better guide: `panel.empty`, `panel.time_range`, `panel.drop`, `catalog.mode.view`,
`catalog.mode.jump`, `catalog.mode.edit`, `catalog.events.edit`.

## Draw a guide with the kit

Copy `authoring/core/show_a_catalog.py` (one take: open a pane, drag, show the result) next to your
plugin and change the scene. `SciQLop.components.guides.authoring.kit` gives the parts:

| Part | For |
| --- | --- |
| `base_style(p, "12s")`, `svg(p, label, style, body)` | the file: tokens, shared rules, root element |
| `Clock(T)`: `at`, `path`, `pulse`, `shown`, `hidden`, `lit` | the timeline, written in seconds |
| `keyframes(name, stops)` | one `@keyframes` block from `(percent, css)` stops |
| `window`, `strip`, `panel_frame`, `time_pill`, `combo`, `popup` | SciQLop's window, icon strip, panel, row under the panel, menus |
| `pane`, `products_pane`, `tree_row`, `pane_slide` | a side pane, its rows, its opening |
| `static_plot`, `curve`, `trace`, `SIGNALS`, `span` | plots, realistic signals, catalog events |
| `CURSOR`, `ghost`, `ring`, `keycap`, `step` | the cursor, a dragged item, clicks, held keys, the three step labels |
| `host_page(guides)` | one web page showing several guides (for a website or a review) |

Rules of the style:

- **One gesture, at most three steps**, labelled in plain imperative words. More steps: make two guides.
- **Simplify, never invent.** Show only what the gesture touches, but as it really is: read the code of
  the behaviour first. Real icons (`kit.ICON_PATHS`), real names (products are written as in the tree,
  lower case: `speasy` > `amda` > `ACE` > `imf`), times in UTC.
- **Show the step people miss**, such as opening a side pane from its icon on the left strip.
- **One clock.** Every animated element has class `a` and the loop's duration; its keyframes are moments
  of that loop.
- **Resting state = the result.** Draw everything in its final state; the animation overrides it. A
  viewer that cannot animate then shows a true picture.
- **Own prefix.** Class and keyframe names carry the guide's prefix `p` (core uses `sqa sqc sqd sqe sqj sqm sqn`).

## What Qt's renderer needs

SciQLop converts the file before playing it (`guides/qt_svg.py`): colour variables become the theme's
colours, `@media` blocks are dropped, `#rrggbbaa` is split into colour + opacity. The rest is on the author:

| Do not | Because in Qt (6.11) | Do |
| --- | --- | --- |
| group keyframe stops, `0%, 5% { }` | the whole animation is dropped, silently | one stop per moment (`kit.keyframes` does) |
| animate a group inside a `clip-path` | it is misdrawn | cross-fade views drawn in place; fade panes in (`kit.pane_slide`) |
| `translateX(…)` | not applied | `translate(x, 0px)` |
| place with a CSS `transform` outside keyframes | ignored | the SVG `transform="…"` attribute |
| scale a 1-unit shape by 80 | blurry, edges lost (browsers too) | draw near real size, move each edge with a translate |
| rely on click rings or self-drawing curves | not animated: rings stay hidden, curves appear at once | keep them as extras, never as the message |

## Check it

Nobody can judge an animation from its source. Freeze it at telling moments, as Qt will play it:

```bash
uv run python -m SciQLop.components.guides.authoring.preview my-guide.svg --times 0.4 2.3 7.2 10.5 --out sheet
```

It writes `sheet-light.png` and `sheet-dark.png` and fails if Qt would not animate the file. Look at
both sheets: cursor tip on its target, dragged item by the cursor, no overlapping text, the lit step
matching the action. Add a test that loads the guide with `for_qt` and asserts
`QSvgRenderer(...).animated()` (see `tests/test_guides.py`), since Qt's refusals are silent.
