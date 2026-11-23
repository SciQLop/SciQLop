"""Guide: write a virtual product in a notebook cell with %%vp, then plot it.

    python -m SciQLop.components.guides.authoring.core.write_a_virtual_product OUT_DIR      -> OUT_DIR/write-a-virtual-product.svg

Verified in the code: %%vp registers the cell's function as a virtual product at the path given by
--path, else at the function's name (user_api/virtual_products/magic.py), so it shows in the Products
tree under that name and is dragged onto a panel like any product. The cell is the tutorial's
"tunable_sine" (examples/tutorials/SciQLop/15-SciQLopParameterizedVirtualProducts.ipynb), trimmed.
"""
import math
import sys
from pathlib import Path

from SciQLop.components.guides.authoring import kit

P, T = "sqv", 13.0
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
clock = kit.Clock(T)
HOME, RUN, ICON, ROW, DROP = (600, 300), (640, 92), (35, 76), (128, 131), (470, 252)
RUN_AT, OPEN, PRESS, RELEASE, RESET = 1.9, 3.8, 5.4, 7.6, 12.2

CODE = ["%%vp",
        "def tunable_sine(start, stop, frequency: float = 0.01,",
        "                 amplitude: float = 1.0) -> Scalar[\"signal\"]:",
        "    t = np.arange(start, stop, 5.0)",
        "    return t, amplitude * np.sin(2 * np.pi * frequency * t)"]
CHAR = 6.3   # advance of the monospace font at 10.5 px, for the indents
SINE = " ".join(f"{276 + i / 80 * 384:.1f},{254 - 40 * math.sin(i / 80 * 5 * math.tau):.1f}" for i in range(81))

STYLE = kit.base_style(P, f"{T:g}s") + f"""
/* Resting state = the result: the cell has run, the product is in the tree and plotted. */
.{P} .code text {{ font-family: monospace; font-size: 10.5px; }}
.{P} .cursor {{ animation-name: {P}-cursor; opacity: 0; }}
.{P} .ghost {{ animation-name: {P}-ghost; opacity: 0; }}
.{P} .pane {{ animation-name: {P}-pane; }}
.{P} .tabhot {{ animation-name: {P}-tab; }}
.{P} .newrow {{ animation-name: {P}-newrow; }}
.{P} .rowhot {{ animation-name: {P}-rowhot; opacity: 0; }}
.{P} .dzhot {{ animation-name: {P}-dzhot; opacity: 0; }}
.{P} .empty {{ animation-name: {P}-empty; opacity: 0; }}
.{P} .unrun {{ animation-name: {P}-unrun; opacity: 0; }}
.{P} .ran {{ animation-name: {P}-ran; }}
.{P} .key {{ animation-name: {P}-key; opacity: 0; }}
.{P} .sine {{ animation-name: {P}-sine; }}
""" + "".join(f".{P} .{n} {{ animation-name: {P}-{n}; }}\n" for n in ("run", "open", "press", "release", "s1", "s2", "s3")) \
    + kit.keyframes(f"{P}-cursor", clock.path([(0, HOME), (0.6, HOME), (1.5, RUN), (2.6, RUN), (3.6, ICON), (4.3, ICON), (5.2, ROW),
                                               (PRESS, ROW), (7.4, DROP), (11.4, DROP), (T, HOME)], lambda t: "opacity: 1;")) \
    + kit.keyframes(f"{P}-ghost", clock.path([(0, ROW), (PRESS - 0.05, ROW), (PRESS, ROW), (7.4, DROP), (RELEASE, DROP), (RELEASE + 0.3, DROP), (T, DROP)],
                                             lambda t: f"opacity: {1 if PRESS <= t <= RELEASE else 0};")) \
    + kit.keyframes(f"{P}-pane", kit.pane_slide(clock, OPEN, RESET)) \
    + kit.keyframes(f"{P}-tab", clock.shown((OPEN - 0.1, RESET))) \
    + kit.keyframes(f"{P}-newrow", clock.shown((RUN_AT + 0.2, RESET + 0.4))) \
    + kit.keyframes(f"{P}-rowhot", clock.shown((5.0, RELEASE), fade=0.25)) \
    + kit.keyframes(f"{P}-dzhot", clock.shown((6.4, RELEASE))) \
    + kit.keyframes(f"{P}-empty", clock.hidden((RELEASE, RESET))) \
    + kit.keyframes(f"{P}-unrun", clock.hidden((RUN_AT, RESET))) \
    + kit.keyframes(f"{P}-ran", clock.shown((RUN_AT, RESET))) \
    + kit.keyframes(f"{P}-key", clock.shown((RUN_AT - 0.5, RUN_AT + 0.5), fade=0.2)) \
    + kit.keyframes(f"{P}-sine", clock.shown((RELEASE + 0.2, RESET), fade=0.8)) \
    + kit.keyframes(f"{P}-run", clock.pulse(RUN_AT)) + kit.keyframes(f"{P}-open", clock.pulse(OPEN)) \
    + kit.keyframes(f"{P}-press", clock.pulse(PRESS)) + kit.keyframes(f"{P}-release", clock.pulse(RELEASE)) \
    + kit.keyframes(f"{P}-s1", clock.lit((0.5, 3.0))) + kit.keyframes(f"{P}-s2", clock.lit((3.3, RELEASE))) \
    + kit.keyframes(f"{P}-s3", clock.lit((RELEASE + 0.2, RESET - 0.3)))

CELL = (f'<rect x="252" y="62" width="432" height="104" rx="8" fill="var(--side)" stroke="var(--line)"/>'
        f'<text x="262" y="84" class="small dim unrun a">[ ]:</text><text x="262" y="84" class="small dim ran a">[1]:</text>'
        f'<g class="code">' + "".join(f'<text x="{290 + CHAR * (len(line) - len(line.lstrip()))}" y="{84 + 18 * i}">{line.lstrip()}</text>' for i, line in enumerate(CODE)) + "</g>")
ROWS = (kit.tree_row(106, 0, "speasy", "closed")
        + f'<g class="newrow a">{kit.tree_row(134, 0, "tunable_sine")}</g>')
PANEL = (f'<rect x="252" y="178" width="432" height="144" rx="10" fill="none" stroke="var(--line)"/>'
         f'<g class="empty a"><rect x="268" y="190" width="400" height="120" rx="8" fill="none" stroke="var(--dim)" stroke-width="1.2" stroke-dasharray="5 5"/>'
         f'<text x="468" y="254" text-anchor="middle" class="dim" style="font-size:13px">{kit.ui("Add a product to this panel")}</text></g>'
         f'<rect class="dzhot a" x="268" y="190" width="400" height="120" rx="8" fill="var(--accent-soft)" stroke="var(--accent)" stroke-width="2"/>'
         f'<line x1="276" y1="254" x2="660" y2="254" stroke="var(--line)" stroke-dasharray="2 4"/>'
         f'<g class="sine a">{kit.trace(SINE, "c1", "solid")}</g>')

BODY = f"""{kit.window(P, active="tree", tab_class="tabhot a")}
{CELL}
{PANEL}
{kit.time_pill(474)}
{kit.products_pane(ROWS, hot_y=134, pane_class="pane a")}
{kit.strip("tree", "tabhot a")}
{kit.ring("run", *RUN)}{kit.ring("open", ICON[0], ICON[1] - 3)}{kit.ring("press", ROW[0], ROW[1] - 3)}{kit.ring("release", *DROP)}
<g transform="translate({RUN[0] - 88} {RUN[1] - 50})">{kit.keycap("Shift+Enter", cls="key a")}</g>
{kit.ghost("tunable_sine", width=98)}
{kit.CURSOR}
{kit.step(66, 1, "Run a %%vp cell", "s1")}
{kit.step(240, 2, "Drag the new product onto a panel", "s2")}
{kit.step(530, 3, "It is plotted", "s3")}"""

SVG = kit.svg(P, "Run a notebook cell that starts with %%vp: its function becomes a product in the Products pane, "
              "under its own name. Drag it onto a panel to plot it.", STYLE, BODY)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "write-a-virtual-product.svg").write_text(SVG)
print(len(SVG))
