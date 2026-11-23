"""Guide: colour a catalog's events by the value of one of their attributes.

    python -m SciQLop.components.guides.authoring.core.color_events_by_attribute OUT_DIR      -> OUT_DIR/color-events-by-attribute.svg

Verified in the code: the catalog tree's right-click menu ends with the panel toggle, "Set color…" and the
"Color by…" submenu (catalog_browser.py, color_menus.py). The submenu lists "Uniform (default)", then one
entry per attribute of the events (sorted; Catalogs (cocat-rs) gives "rating" and "tags"). A numeric
attribute maps through a colormap, "viridis" by default (color_mapper.py).
"""
import sys
from pathlib import Path

from SciQLop.components.catalogs.backend.provider import Section
from SciQLop.components.catalogs.ui.catalog_tree import SECTION_LABELS
from SciQLop.components.guides.authoring import kit

P, T = "sqk", 13.0
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
clock = kit.Clock(T)
HOME, ROW = (600, 300), (150, 131)
MENU_X, MENU_Y, MENU_W = 156, 140, 196
MENU_ROWS = [kit.ui("Rename…"), kit.ui("Delete catalog…"), "Remove from panel 'Panel 1'", kit.ui("Set color…"), kit.ui("Color by…")]
COLOR_BY = (MENU_X + 60, MENU_Y + 18 + 22 * 4 - 4)
SUB_X, SUB_Y, SUB_W = MENU_X + MENU_W - 4, MENU_Y + 22 * 4, 128
SUB_ROWS = [kit.ui("Uniform (default)"), "rating", "tags"]
RATING = (SUB_X + 40, SUB_Y + 18 + 22 * 1 - 4)
RIGHT_CLICK, HOVER, PICK, RESET = 2.0, 3.4, 5.6, 12.2

VIRIDIS = ("#440154", "#3b528b", "#21918c", "#5ec962", "#fde725")
EVENTS = [(292, 24, 1), (352, 40, 4), (430, 54, 0), (522, 30, 3), (600, 28, 2)]   # x, width, rating 0..4
PLOTS = ((104, 100), (214, 100))


def band(x, width, color, cls):
    return f'<g class="{cls}">' + "".join(
        f'<rect x="{x}" y="{y}" width="{width}" height="{h}" fill="{color}" fill-opacity=".3"/>'
        f'<path d="M{x} {y} v{h} M{x + width} {y} v{h}" stroke="{color}" stroke-width="1.5"/>' for y, h in PLOTS) + "</g>"


STYLE = kit.base_style(P, f"{T:g}s") + f"""
/* Resting state = the result: every event coloured by its rating. */
.{P} .cursor {{ animation-name: {P}-cursor; opacity: 0; }}
.{P} .menu {{ animation-name: {P}-menu; opacity: 0; }}
.{P} .sub {{ animation-name: {P}-sub; opacity: 0; }}
.{P} .key {{ animation-name: {P}-key; opacity: 0; }}
.{P} .uniform {{ animation-name: {P}-uniform; opacity: 0; }}
""" + "".join(f".{P} .ev{i} {{ animation-name: {P}-ev{i}; }}\n" for i in range(len(EVENTS))) \
    + "".join(f".{P} .{n} {{ animation-name: {P}-{n}; }}\n" for n in ("rc", "pick", "s1", "s2", "s3")) \
    + kit.keyframes(f"{P}-cursor", clock.path([(0, HOME), (0.6, HOME), (1.7, ROW), (2.6, ROW), (3.2, COLOR_BY), (4.2, COLOR_BY),
                                               (4.6, (SUB_X + 20, COLOR_BY[1])), (5.3, RATING), (11.4, RATING), (T, HOME)],
                                              lambda t: "opacity: 1;")) \
    + kit.keyframes(f"{P}-menu", clock.shown((RIGHT_CLICK + 0.1, PICK), fade=0.15)) \
    + kit.keyframes(f"{P}-sub", clock.shown((HOVER + 0.2, PICK), fade=0.15)) \
    + kit.keyframes(f"{P}-key", clock.shown((RIGHT_CLICK - 0.4, RIGHT_CLICK + 0.5), fade=0.2)) \
    + kit.keyframes(f"{P}-uniform", clock.hidden((PICK + 0.2, RESET), fade=0.5)) \
    + "".join(kit.keyframes(f"{P}-ev{i}", clock.shown((PICK + 0.3 + 0.25 * i, RESET), fade=0.5)) for i in range(len(EVENTS))) \
    + kit.keyframes(f"{P}-rc", clock.pulse(RIGHT_CLICK)) + kit.keyframes(f"{P}-pick", clock.pulse(PICK)) \
    + kit.keyframes(f"{P}-s1", clock.lit((0.6, HOVER - 0.3))) + kit.keyframes(f"{P}-s2", clock.lit((HOVER - 0.2, PICK + 0.2))) \
    + kit.keyframes(f"{P}-s3", clock.lit((PICK + 0.3, RESET - 0.4)))

DOT = '<circle cx="{x}" cy="{y}" r="4" fill="var(--{c})"/>'
ROWS = "".join([kit.tree_row(106, 0, kit.ui(SECTION_LABELS[Section.MINE]), "open"),
                DOT.format(x=84, y=130, c="c4"), kit.tree_row(134, 1, "MMS crossings"),
                DOT.format(x=84, y=158, c="c2"), kit.tree_row(162, 1, "Flux ropes", cls="dim"),
                kit.tree_row(190, 0, kit.ui(SECTION_LABELS[Section.REFERENCE]), "closed", cls="dim")])
CHECK = f'<path d="M{SUB_X + 112} {SUB_Y + 14} l3 3 l6 -7" fill="none" stroke="var(--fg)" stroke-width="1.4"/>'

BODY = f"""{kit.window(P, active="catalogue")}
{kit.panel_frame(x=252, title_x=258)}
{kit.static_plot(268, 104, 400, {"bx": "c1", "by": "c2", "bz": "c3"})}
{kit.static_plot(268, 214, 400, {"density": "c3"})}
<g class="uniform a">{"".join(band(x, w, "var(--c4)", "") for x, w, _ in EVENTS)}</g>
{"".join(band(x, w, VIRIDIS[r], f"a ev{i}") for i, (x, w, r) in enumerate(EVENTS))}
{kit.time_pill(474)}
{kit.pane(kit.ui("Catalogs"), ROWS, hot_y=134, hot_class="")}
{kit.popup(MENU_X, MENU_Y, MENU_W, MENU_ROWS, hot=4, cls="menu a")}
<g class="menu a"><path d="M{MENU_X + MENU_W - 14} {MENU_Y + 104} l4 4 l-4 4" fill="none" stroke="var(--dim)" stroke-width="1.3"/></g>
<g class="sub a">{kit.popup(SUB_X, SUB_Y, SUB_W, SUB_ROWS, hot=1)}{CHECK}</g>
{kit.ring("rc", *ROW)}{kit.ring("pick", *RATING)}
<g transform="translate({ROW[0] + 10} {ROW[1] - 56})">{kit.keycap("Right-click", cls="key a")}</g>
{kit.CURSOR}
{kit.step(58, 1, "Right-click a catalog", "s1")}
{kit.step(258, 2, "Color by…, then an attribute", "s2")}
{kit.step(500, 3, "Events follow its value", "s3")}"""

SVG = kit.svg(P, "Right-click a catalog in the Catalogs pane, open Color by… and pick an attribute such as rating: "
              "each event on the plots takes the colour of its value.", STYLE, BODY)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "color-events-by-attribute.svg").write_text(SVG)
print(len(SVG))
