"""Guide: show a catalog's events on a panel.

    python -m SciQLop.components.guides.authoring.core.show_a_catalog OUT_DIR      -> OUT_DIR/show-a-catalog.svg

Verified in the code: the Catalogs pane's tree gives a catalog as a drag (catalog_tree.py), and the
drop rule "sciqlop.catalogs.overlay" overlays it on the panel dropped on (core_kinds.py).
"""
import sys
from pathlib import Path

from SciQLop.components.guides.authoring import kit

P, T = "sqc", 12.0
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
HOME, ICON, ROW, DROP = (575, 318), (35, 104), (150, 133), (470, 205)
at = lambda seconds: seconds / T * 100
move = lambda xy: f"transform: translate({xy[0]}px, {xy[1]}px);"
OPEN, PRESS, RELEASE, RESET = 2.2, 4.6, 7.3, 11.4      # the moments everything else is timed from


def pulse(when):
    return [(at(when - 0.02), "transform: scale(.3); opacity: 0;"), (at(when), "transform: scale(.3); opacity: .9;"),
            (at(when + 0.6), "transform: scale(1.5); opacity: 0;"), (100, "transform: scale(1.5); opacity: 0;")]


def shown(start, end, fade=0.3, rest="opacity: 0;"):
    return [(0, rest), (at(start), "opacity: 0;"), (at(start + fade), "opacity: 1;"), (at(end), "opacity: 1;"),
            (at(end + fade), "opacity: 0;"), (100, rest)]


def lit(start, end):
    return [(0, "opacity: .4;"), (at(start), "opacity: .4;"), (at(start + 0.3), "opacity: 1;"), (at(end), "opacity: 1;"),
            (at(end + 0.3), "opacity: .4;"), (100, "opacity: .4;")]


SPANS = [(292, 26), (430, 58), (598, 30)]
STYLE = kit.base_style(P, f"{T:g}s") + f"""
/* Resting state = the result: the Catalogs pane open and the events drawn on the panel. */
.{P} .cursor {{ animation-name: {P}-cursor; opacity: 0; }}
.{P} .ghost {{ animation-name: {P}-ghost; opacity: 0; }}
.{P} .rowhot {{ animation-name: {P}-rowhot; opacity: 0; }}
.{P} .dzhot {{ animation-name: {P}-dzhot; opacity: 0; }}
.{P} .pane {{ animation-name: {P}-pane; }}
.{P} .tabhot {{ animation-name: {P}-tab; }}
.{P} .open {{ animation-name: {P}-open; }} .{P} .press {{ animation-name: {P}-press; }} .{P} .release {{ animation-name: {P}-release; }}
.{P} .s1 {{ animation-name: {P}-s1; }} .{P} .s2 {{ animation-name: {P}-s2; }} .{P} .s3 {{ animation-name: {P}-s3; }}
""" + "".join(f".{P} .ev{i} {{ animation-name: {P}-ev{i}; }}\n" for i in range(len(SPANS))) \
    + kit.keyframes(f"{P}-cursor", [(0, move(HOME) + "opacity: 1;"), (at(0.6), move(HOME) + "opacity: 1;"), (at(1.9), move(ICON) + "opacity: 1;"),
                                    (at(2.7), move(ICON) + "opacity: 1;"), (at(4.0), move(ROW) + "opacity: 1;"), (at(4.8), move(ROW) + "opacity: 1;"),
                                    (at(7.1), move(DROP) + "opacity: 1;"), (at(10.8), move(DROP) + "opacity: 1;"), (100, move(HOME) + "opacity: 1;")]) \
    + kit.keyframes(f"{P}-ghost", [(0, move(ROW) + "opacity: 0;"), (at(4.7), move(ROW) + "opacity: 0;"), (at(4.8), move(ROW) + "opacity: 1;"),
                                   (at(7.1), move(DROP) + "opacity: 1;"), (at(RELEASE), move(DROP) + "opacity: 1;"),
                                   (at(RELEASE + 0.3), move(DROP) + "opacity: 0;"), (100, move(DROP) + "opacity: 0;")]) \
    + kit.keyframes(f"{P}-pane", kit.pane_slide(kit.Clock(T), OPEN, RESET)) \
    + kit.keyframes(f"{P}-tab", shown(OPEN - 0.1, RESET)) \
    + kit.keyframes(f"{P}-rowhot", shown(3.8, RELEASE, fade=0.25)) \
    + kit.keyframes(f"{P}-dzhot", shown(5.8, RELEASE, fade=0.3)) \
    + kit.keyframes(f"{P}-open", pulse(OPEN)) + kit.keyframes(f"{P}-press", pulse(PRESS)) + kit.keyframes(f"{P}-release", pulse(RELEASE)) \
    + "".join(kit.keyframes(f"{P}-ev{i}", shown(RELEASE + 0.3 + 0.35 * i, RESET - 0.2, fade=0.5)) for i in range(len(SPANS))) \
    + kit.keyframes(f"{P}-s1", lit(0.5, 3.2)) + kit.keyframes(f"{P}-s2", lit(3.5, RELEASE)) + kit.keyframes(f"{P}-s3", lit(RELEASE + 0.3, RESET - 0.3))

DOT = '<circle cx="{x}" cy="{y}" r="4" fill="var(--{c})"/>'
ROWS = "".join([kit.tree_row(106, 0, "My Catalogs", "open"),
                DOT.format(x=84, y=130, c="c4"), kit.tree_row(134, 1, "MMS crossings"),
                DOT.format(x=84, y=158, c="c2"), kit.tree_row(162, 1, "Flux ropes", cls="dim"),
                kit.tree_row(190, 0, "Shared", "closed", cls="dim")])

BODY = f"""{kit.window(P, active="catalogue", tab_class="tabhot a")}
{kit.panel_frame()}
{kit.static_plot(76, 104, 592, {"bx": "c1", "by": "c2", "bz": "c3"})}
{kit.static_plot(76, 214, 592, {"density": "c3"})}
{"".join(kit.span(x, w, cls=f"a ev{i}") for i, (x, w) in enumerate(SPANS))}
<rect class="dzhot a" x="68" y="100" width="608" height="218" rx="8" fill="var(--accent-soft)" stroke="var(--accent)" stroke-width="2"/>
{kit.TIME_PILL}
{kit.pane("Catalogs", ROWS, hot_y=134, pane_class="pane a")}
{kit.strip("catalogue", "tabhot a")}
{kit.ring("open", 34, 101)}{kit.ring("press", ROW[0], ROW[1] - 3)}{kit.ring("release", *DROP)}
{kit.ghost("MMS crossings", width=112)}
{kit.CURSOR}
{kit.step(66, 1, "Open the Catalogs pane", "s1")}
{kit.step(272, 2, "Drag a catalog onto a panel", "s2")}
{kit.step(494, 3, "Its events show on the plots", "s3")}"""

SVG = kit.svg(P, "Open the Catalogs pane from the left edge and drag a catalog onto a panel: its events are drawn as coloured spans across the plots.", STYLE, BODY)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "show-a-catalog.svg").write_text(SVG)
print(len(SVG))
