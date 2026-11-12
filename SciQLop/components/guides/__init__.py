"""Gesture guides: short looping animations that each teach one manipulation.

A guide is one SVG file animated with CSS. The same file plays in a browser (website, README) and,
converted by `qt_svg.for_qt`, in Qt's own SVG renderer inside SciQLop.

- `registry`: the `sciqlop.guides` extension point, `Guide`, `register_guide`.
- `ui`: `show_guides` (the Help > Guides window) and `GuideButton` (a "?" that opens the guide of a context).
- `authoring`: the kit that draws guides in SciQLop's style, for the core guides and for plugins.
"""
