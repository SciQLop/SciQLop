"""Guide: resize, move and delete a catalog event on a plot.

    python -m SciQLop.components.guides.authoring.core.edit_an_event OUT_DIR      -> OUT_DIR/edit-an-event.svg

Verified in the code: in Edit mode the spans stop being read-only (overlay.py -> span.set_read_only),
so an edge can be dragged to resize and the body to move, and the change is written to the catalog.
The panel's right-click menu starts with the event's entries (event_menu.py); "Delete" is enabled
in Edit mode only.
"""
import sys
from pathlib import Path

from SciQLop.components.guides.authoring import kit

P, T = "sqm", 15.0
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
clock = kit.Clock(T)
Y = 160
X0, W0, W1, X1 = 300, 80, 140, 240                 # start x and width, width after the resize, x after the move
HOME, EDGE, EDGE_TO = (575, 300), (X0 + W0, Y), (X0 + W1, Y)
BODY_FROM, BODY_TO = (X0 + W1 // 2, Y), (X1 + W1 // 2, Y)
MENU_X, MENU_Y = BODY_TO[0] + 8, Y - 12
DELETE = (MENU_X + 44, MENU_Y + 18 + 22 * 5 - 2)
GRAB1, DROP1, GRAB2, DROP2, MENU, CLICK_DELETE, RESET = 1.8, 3.1, 4.4, 5.9, 6.9, 8.6, 13.6
MENU_ROWS = ["Event: 13:23:01", "Edit attributes…", "Show in Catalogs", "Zoom to event", "Copy start and stop", "Delete"]

# The band is drawn 100 wide and stretched a little; drawn 1 wide and stretched 80x, browsers blur it.
band = lambda x, width: f"transform: translate({x}px, 0px) scale({width / 100}, 1);"
edge = lambda x: f"transform: translate({x}px, 0px);"
STAGES = [(0, X0, W0), (2.0, X0, W0), (3.0, X0, W1), (4.6, X0, W1), (5.8, X1, W1), (RESET, X1, W1), (RESET + 0.05, X0, W0), (T, X0, W0)]
STYLE = kit.base_style(P, f"{T:g}s") + f"""
/* Resting state = the panel in Edit mode with the event where it started, and the three rules lit. */
.{P} .cursor {{ animation-name: {P}-cursor; opacity: 0; }}
.{P} .band {{ animation-name: {P}-band; {band(X0, W0)} }}
.{P} .left {{ animation-name: {P}-left; {edge(X0)} }}
.{P} .right {{ animation-name: {P}-right; {edge(X0 + W0)} }}
.{P} .gone {{ animation-name: {P}-gone; }}
.{P} .menu {{ animation-name: {P}-menu; opacity: 0; }}
.{P} .key {{ animation-name: {P}-key; opacity: 0; }}
""" + "".join(f".{P} .s{i} {{ animation-name: {P}-s{i}; }}\n" for i in (1, 2, 3)) \
    + kit.keyframes(f"{P}-cursor", clock.path([(0, HOME), (0.6, HOME), (1.6, EDGE), (2.0, EDGE), (3.0, EDGE_TO), (3.3, EDGE_TO), (4.2, BODY_FROM),
                                               (4.6, BODY_FROM), (5.8, BODY_TO), (7.4, BODY_TO), (8.4, DELETE), (12.6, DELETE), (T, HOME)],
                                              lambda t: "opacity: 1;")) \
    + kit.keyframes(f"{P}-band", [(clock.at(t), band(x, w)) for t, x, w in STAGES]) \
    + kit.keyframes(f"{P}-left", [(clock.at(t), edge(x)) for t, x, w in STAGES]) \
    + kit.keyframes(f"{P}-right", [(clock.at(t), edge(x + w)) for t, x, w in STAGES]) \
    + kit.keyframes(f"{P}-gone", clock.hidden((CLICK_DELETE + 0.2, RESET + 0.3), fade=0.5)) \
    + kit.keyframes(f"{P}-menu", clock.shown((MENU + 0.1, CLICK_DELETE), fade=0.15)) \
    + kit.keyframes(f"{P}-key", clock.shown((MENU - 0.4, MENU + 0.5), fade=0.2))

STYLE += "".join(f".{P} .{name} {{ animation-name: {P}-{name}; }}\n" for name in ("g1", "d1", "g2", "d2", "rc", "del")) \
    + kit.keyframes(f"{P}-g1", clock.pulse(GRAB1)) + kit.keyframes(f"{P}-d1", clock.pulse(DROP1)) \
    + kit.keyframes(f"{P}-g2", clock.pulse(GRAB2)) + kit.keyframes(f"{P}-d2", clock.pulse(DROP2)) \
    + kit.keyframes(f"{P}-rc", clock.pulse(MENU)) + kit.keyframes(f"{P}-del", clock.pulse(CLICK_DELETE)) \
    + kit.keyframes(f"{P}-s1", clock.lit((0.5, DROP1 + 0.2))) + kit.keyframes(f"{P}-s2", clock.lit((3.6, DROP2 + 0.2))) \
    + kit.keyframes(f"{P}-s3", clock.lit((MENU - 0.5, 9.6)))

EVENT = '<g class="gone a">' + "".join(
    f'<rect class="band a" y="{y}" width="100" height="100" fill="var(--c4)" opacity=".22"/>'
    f'<path class="left a" d="M0 {y} v100" stroke="var(--c4)" stroke-width="1.5"/>'
    f'<path class="right a" d="M0 {y} v100" stroke="var(--c4)" stroke-width="1.5"/>' for y in (104, 214)) + "</g>"

BODY = f"""{kit.window(P)}
{kit.panel_frame()}
{kit.static_plot(76, 104, 592, {"bx": "c1", "by": "c2", "bz": "c3"})}
{kit.static_plot(76, 214, 592, {"density": "c3"})}
{kit.span(130, 34)}{kit.span(590, 40)}
{EVENT}
{kit.time_pill()}
<text x="300" y="345" class="small dim">Catalog mode:</text>
{kit.combo(374, 72, "Edit")}
<text x="458" y="345" class="small dim">Add to:</text>{kit.combo(500, 118, "MMS crossings")}
{kit.popup(MENU_X, MENU_Y, 156, MENU_ROWS, hot=5, cls="menu a", dim=(0,))}
{kit.ring("g1", *EDGE)}{kit.ring("d1", *EDGE_TO)}{kit.ring("g2", *BODY_FROM)}{kit.ring("d2", *BODY_TO)}{kit.ring("rc", *BODY_TO)}
{kit.ring("del", DELETE[0], DELETE[1] - 2)}
<g transform="translate({BODY_TO[0] - 104} {BODY_TO[1] - 40})">{kit.keycap("Right-click", cls="key a")}</g>
{kit.CURSOR}
{kit.step(58, 1, "Drag an edge to resize", "s1")}
{kit.step(262, 2, "Drag the middle to move", "s2")}
{kit.step(476, 3, "Right-click, then Delete", "s3")}"""

SVG = kit.svg(P, "In Edit mode, drag an edge of an event to resize it, drag its middle to move it, or right-click it and choose Delete.", STYLE, BODY)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "edit-an-event.svg").write_text(SVG)
print(len(SVG))
