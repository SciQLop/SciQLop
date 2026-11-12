"""Guide: create a catalog event on a plot.

    python -m SciQLop.components.guides.authoring.core.create_an_event OUT_DIR      -> OUT_DIR/create-an-event.svg

Verified in the code (catalog_chrome.py, panel_manager.py): the panel's "Catalog mode" box has View,
Jump and Edit. In Edit an "Add to:" box names the catalog that receives new events. A new event is
made with Shift+click to start, a move, and a second click to finish (Esc cancels) - not a drag.
"""
import sys
from pathlib import Path

from SciQLop.components.guides.authoring import kit

P, T = "sqe", 14.0
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
HOME, COMBO, EDIT, START, END = (575, 300), (414, 345), (410, 322), (360, 160), (500, 160)
at = lambda seconds: seconds / T * 100
move = lambda xy: f"transform: translate({xy[0]}px, {xy[1]}px);"
CLICK_COMBO, CLICK_EDIT, CLICK_START, CLICK_END, RESET = 1.9, 3.1, 5.4, 8.2, 12.9

WAY = [(0, HOME), (0.6, HOME), (1.8, COMBO), (2.4, COMBO), (3.0, EDIT), (3.8, EDIT), (5.2, START), (5.6, START), (8.0, END), (12.6, END), (T, HOME)]


def pulse(when):
    return [(at(when - 0.02), "transform: scale(.3); opacity: 0;"), (at(when), "transform: scale(.3); opacity: .9;"),
            (at(when + 0.6), "transform: scale(1.5); opacity: 0;"), (100, "transform: scale(1.5); opacity: 0;")]


def shown(start, end, fade=0.3, rest="opacity: 0;"):
    return [(0, rest), (at(start), "opacity: 0;"), (at(start + fade), "opacity: 1;"), (at(end), "opacity: 1;"),
            (at(end + fade), "opacity: 0;"), (100, rest)]


def hidden(start, end, fade=0.3):
    return [(0, "opacity: 1;"), (at(start), "opacity: 1;"), (at(start + fade), "opacity: 0;"), (at(end), "opacity: 0;"),
            (at(end + fade), "opacity: 1;"), (100, "opacity: 1;")]


def lit(start, end):
    return [(0, "opacity: .4;"), (at(start), "opacity: .4;"), (at(start + 0.3), "opacity: 1;"), (at(end), "opacity: 1;"),
            (at(end + 0.3), "opacity: .4;"), (100, "opacity: .4;")]


WIDTH = END[0] - START[0]
STYLE = kit.base_style(P, f"{T:g}s") + f"""
/* Resting state = the result: Edit mode, "Add to" shown, the new event on the plots. */
.{P} .cursor {{ animation-name: {P}-cursor; opacity: 0; }}
.{P} .key {{ animation-name: {P}-key; opacity: 0; }}
.{P} .menu {{ animation-name: {P}-menu; opacity: 0; }}
.{P} .view {{ animation-name: {P}-view; opacity: 0; }}
.{P} .edit, .{P} .target {{ animation-name: {P}-edit; }}
.{P} .draft {{ animation-name: {P}-draft; opacity: 0; transform-box: fill-box; transform-origin: left; }}
.{P} .made {{ animation-name: {P}-made; }}
""" + "".join(f".{P} .k{i} {{ animation-name: {P}-k{i}; }}\n" for i in range(4)) \
    + "".join(f".{P} .s{i} {{ animation-name: {P}-s{i}; }}\n" for i in (1, 2, 3)) \
    + kit.keyframes(f"{P}-cursor", [(at(t), move(xy) + "opacity: 1;") for t, xy in WAY]) \
    + kit.keyframes(f"{P}-key", [(at(t), move(xy) + f"opacity: {1 if 5.0 <= t <= 8.2 else 0};") for t, xy in
                                 [(0, START), (4.9, START), (5.0, START), (5.6, START), (8.0, END), (8.2, END), (8.6, END), (T, END)]]) \
    + kit.keyframes(f"{P}-menu", shown(CLICK_COMBO + 0.05, CLICK_EDIT, fade=0.15)) \
    + kit.keyframes(f"{P}-view", hidden(CLICK_EDIT, RESET, fade=0.15)) \
    + kit.keyframes(f"{P}-edit", shown(CLICK_EDIT + 0.1, RESET, fade=0.3)) \
    + kit.keyframes(f"{P}-draft", [(0, "transform: scaleX(0); opacity: 0;"), (at(CLICK_START), "transform: scaleX(0); opacity: 0;"),
                                   (at(5.6), "transform: scaleX(0.01); opacity: 1;"), (at(8.0), "transform: scaleX(1); opacity: 1;"),
                                   (at(CLICK_END), "transform: scaleX(1); opacity: 1;"), (at(CLICK_END + 0.3), "transform: scaleX(1); opacity: 0;"),
                                   (100, "transform: scaleX(1); opacity: 0;")]) \
    + kit.keyframes(f"{P}-made", shown(CLICK_END, RESET, fade=0.3)) \
    + "".join(kit.keyframes(f"{P}-k{i}", pulse(when)) for i, when in enumerate((CLICK_COMBO, CLICK_EDIT, CLICK_START, CLICK_END))) \
    + kit.keyframes(f"{P}-s1", lit(0.5, 3.6)) + kit.keyframes(f"{P}-s2", lit(4.6, CLICK_END - 0.2)) + kit.keyframes(f"{P}-s3", lit(CLICK_END, RESET - 0.2))


def combo(x, width, label_class, label, y=330):
    return (f'<rect x="{x}" y="{y}" width="{width}" height="22" rx="6" fill="var(--win)" stroke="var(--line)"/>'
            f'<text x="{x + 9}" y="{y + 15}" class="small {label_class}">{label}</text>'
            f'<path d="M{x + width - 15} {y + 9} l4 4 l4 -4" fill="none" stroke="var(--dim)" stroke-width="1.3"/>')


MENU = (f'<g class="menu a"><rect x="374" y="256" width="72" height="72" rx="8" fill="var(--shadow)" transform="translate(0 2)"/>'
        f'<rect x="374" y="256" width="72" height="72" rx="8" fill="var(--win)" stroke="var(--line)"/>'
        f'<rect x="378" y="306" width="64" height="20" rx="5" fill="var(--accent-soft)"/>'
        + "".join(f'<text x="386" y="{y}" class="small">{t}</text>' for y, t in ((274, "View"), (297, "Jump"), (320, "Edit"))) + "</g>")

BODY = f"""{kit.window(P)}
{kit.panel_frame()}
{kit.static_plot(76, 104, 592, {"bx": "c1", "by": "c2", "bz": "c3"})}
{kit.static_plot(76, 214, 592, {"density": "c3"})}
{kit.span(150, 34)}{kit.span(590, 40)}
{kit.span(START[0], WIDTH, cls="made a")}
<g class="draft a">{"".join(f'<rect x="{START[0]}" y="{y}" width="{WIDTH}" height="100" fill="var(--c4)" fill-opacity=".12" stroke="var(--c4)" stroke-width="1.5" stroke-dasharray="5 4"/>' for y in (104, 214))}</g>
{kit.time_pill()}
<text x="300" y="345" class="small dim">Catalog mode:</text>
{combo(374, 72, "view a", "View")}
<text x="383" y="345" class="small edit a">Edit</text>
<g class="target a"><text x="458" y="345" class="small dim">Add to:</text>{combo(500, 118, "", "MMS crossings")}</g>
{MENU}
{kit.ring("k0", 410, 341)}{kit.ring("k1", 410, 317)}{kit.ring("k2", *START)}{kit.ring("k3", *END)}
{kit.keycap("Shift", cls="key a")}
{kit.CURSOR}
{kit.step(58, 1, "Set Catalog mode to Edit", "s1")}
{kit.step(262, 2, "Shift+click, then move", "s2")}
{kit.step(458, 3, "Click again: the event is added", "s3")}"""

SVG = kit.svg(P, "Set the panel's Catalog mode to Edit, hold Shift and click on a plot to start an event, move, and click again to add it to the catalog named in Add to.", STYLE, BODY)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "create-an-event.svg").write_text(SVG)
print(len(SVG))
