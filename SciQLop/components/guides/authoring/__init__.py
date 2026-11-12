"""Drawing gesture guides: `kit` holds the parts (window, strip, panes, cursor, clicks, steps, timeline),
`preview` renders a guide the way SciQLop will show it, `core` holds the generators of SciQLop's own guides.

    uv run python -m SciQLop.components.guides.authoring.core.show_a_catalog OUT_DIR
    uv run python -m SciQLop.components.guides.authoring.preview OUT_DIR/show-a-catalog.svg --times 0.3 3.4 9.5 --out sheet
"""
