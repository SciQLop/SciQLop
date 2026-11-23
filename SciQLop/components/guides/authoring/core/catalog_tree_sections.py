"""Guide: the three sections of the catalogue tree.

    python -m SciQLop.components.guides.authoring.core.catalog_tree_sections OUT_DIR      -> OUT_DIR/catalog-tree-sections.svg

Verified in the code (catalogs/ui/catalog_tree.py, sciqlop_cocat/sections.py): the tree's top level is
"My catalogues", "Shared", "Reference", in that order, with the home, collab and catalogue icons. The
person's own project shows inline in My catalogues, its catalogues straight under the section; projects
on the server go to Shared, one folder each; the public catalogues to Reference, in "Public catalogues".
Other providers (AMDA, plugins) can add rows to Reference: they are left out.
"""
import sys
from pathlib import Path

from SciQLop.components.catalogs.backend.provider import Section
from SciQLop.components.catalogs.ui.catalog_tree import SECTION_ICONS, SECTION_LABELS
from SciQLop.components.guides.authoring import kit
from SciQLop.plugins.sciqlop_cocat.public import PUBLIC_FOLDER

P, T = "sqx", 13.0
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
clock = kit.Clock(T)
ICON = (35, 104)
OPEN, RESET = 1.6, 12.2
EXPAND = (3.4, 5.8, 8.2)                    # when each section opens
ARROW = lambda y: (66, y - 4)
ROW_H = 28
CHILDREN = ([("MMS crossings", "c4"), ("Flux ropes", "c2")], [("Storm study", None), ("Solar wind survey", None)], [(PUBLIC_FOLDER, None)])
SECTIONS = (Section.MINE, Section.SHARED, Section.REFERENCE)


def tops():
    """Each section's row y before and after the sections above it open."""
    closed = [106 + ROW_H * i for i in range(3)]
    opened, y = [], 106
    for kids in CHILDREN:
        opened.append(y)
        y += ROW_H * (1 + len(kids))
    return closed, opened


CLOSED, OPENED = tops()
STEP_SPANS = ((0.5, EXPAND[1] - 0.9), (EXPAND[1] - 0.8, EXPAND[2] - 0.9), (EXPAND[2] - 0.8, RESET - 0.4))
HOME = (600, 300)
cursor_stops = [(0, HOME), (0.6, HOME), (1.3, ICON), (2.0, ICON)]
for i, when in enumerate(EXPAND):
    y = OPENED[i]
    cursor_stops += [(when - 0.6, ARROW(y)), (when + 0.4, ARROW(y))]
cursor_stops += [(11.4, ARROW(OPENED[2])), (T, HOME)]


def moves(i):
    """translate stops of section i: it moves down as each section above it opens."""
    stops = [(0, 0)]
    for k in range(i):
        stops += [(EXPAND[k], _shift(k)), (EXPAND[k] + 0.4, _shift(k + 1))]
    stops += [(RESET, _shift(i)), (RESET + 0.4, 0), (T, 0)]
    return [(clock.at(t), f"transform: translate(0px, {dy}px);") for t, dy in stops]


def _shift(opened_above):
    """How far a section moves down once the `opened_above` sections above it are open."""
    return ROW_H * sum(len(CHILDREN[k]) for k in range(opened_above))


STYLE = kit.base_style(P, f"{T:g}s") + f"""
/* Resting state = the result: the three sections open. */
.{P} .cursor {{ animation-name: {P}-cursor; opacity: 0; }}
.{P} .pane {{ animation-name: {P}-pane; }}
.{P} .tabhot {{ animation-name: {P}-tab; }}
""" + "".join(f".{P} .m{i} {{ animation-name: {P}-m{i}; }} .{P} .kids{i} {{ animation-name: {P}-kids{i}; }} "
              f".{P} .shut{i} {{ animation-name: {P}-shut{i}; opacity: 0; }} .{P} .x{i} {{ animation-name: {P}-x{i}; }} "
              f".{P} .s{i} {{ animation-name: {P}-s{i}; }}\n" for i in range(3)) \
    + kit.keyframes(f"{P}-cursor", clock.path(cursor_stops, lambda t: "opacity: 1;")) \
    + kit.keyframes(f"{P}-pane", kit.pane_slide(clock, OPEN, RESET)) \
    + kit.keyframes(f"{P}-tab", clock.shown((OPEN - 0.1, RESET))) \
    + kit.keyframes(f"{P}-ro", clock.pulse(OPEN)) \
    + "".join(kit.keyframes(f"{P}-m{i}", moves(i)) for i in range(3)) \
    + "".join(kit.keyframes(f"{P}-kids{i}", clock.shown((EXPAND[i] + 0.2, RESET))) for i in range(3)) \
    + "".join(kit.keyframes(f"{P}-shut{i}", clock.hidden((EXPAND[i], RESET + 0.4), fade=0.05)) for i in range(3)) \
    + "".join(kit.keyframes(f"{P}-x{i}", clock.pulse(EXPAND[i])) for i in range(3)) \
    + "".join(kit.keyframes(f"{P}-s{i}", clock.lit(span)) for i, span in enumerate(STEP_SPANS))
STYLE += f".{P} .ro {{ animation-name: {P}-ro; }}\n"


def section_block(i):
    """Section i drawn at its open place, shifted up by the rows above that are still shut."""
    y = OPENED[i]
    rows = kit.section_row(y, SECTION_ICONS[SECTIONS[i]], kit.ui(SECTION_LABELS[SECTIONS[i]]), arrow=None)
    rows += f'<path d="M62 {y-7} l8 0 l-4 6 z" fill="var(--dim)"/>'
    rows += f'<path class="shut{i} a" d="M61 {y-11} h12 v12 h-12 z" fill="var(--side)"/><path class="shut{i} a" d="M63 {y-9} l6 4 l-6 4 z" fill="var(--dim)"/>'
    kids = ""
    for k, (name, colour) in enumerate(CHILDREN[i]):
        ky = y + ROW_H * (k + 1)
        if colour:
            kids += f'<circle cx="84" cy="{ky - 4}" r="4" fill="var(--{colour})"/>' + kit.tree_row(ky, 1, name)
        else:
            kids += kit.tree_row(ky, 1, kit.ui(name) if name == PUBLIC_FOLDER else name, "closed")
    shift = OPENED[i] - CLOSED[i]
    return (f'<g transform="translate(0 {-shift})"><g class="m{i} a" style="transform: translate(0px, {shift}px)">'
            f'{rows}<g class="kids{i} a">{kids}</g></g></g>')


ROWS = "".join(section_block(i) for i in range(3))

BODY = f"""{kit.window(P, active="catalogue", tab_class="tabhot a")}
{kit.panel_frame(x=252, title_x=258)}
{kit.static_plot(268, 104, 400, {"bx": "c1", "by": "c2", "bz": "c3"})}
{kit.static_plot(268, 214, 400, {"density": "c3"})}
{kit.time_pill(474)}
{kit.pane(kit.ui("Catalogs"), ROWS, hot_y=None, pane_class="pane a")}
{kit.strip("catalogue", "tabhot a")}
{kit.ring("ro", ICON[0], ICON[1] - 3)}{"".join(kit.ring(f"x{i}", *ARROW(OPENED[i])) for i in range(3))}
{kit.CURSOR}
{kit.step(58, 1, "My catalogues: your own", "s0")}
{kit.step(262, 2, "Shared: with other people", "s1")}
{kit.step(478, 3, "Reference: read-only lists", "s2")}"""

SVG = kit.svg(P, "The Catalogs pane has three sections: My catalogues holds your own catalogues, Shared the projects "
              "shared with other people, Reference the read-only lists such as the public catalogues.", STYLE, BODY)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "catalog-tree-sections.svg").write_text(SVG)
print(len(SVG))
