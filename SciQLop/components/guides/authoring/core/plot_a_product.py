"""Guide: plot a product - open the Products pane, drag a product onto an empty panel.

    python -m SciQLop.components.guides.authoring.core.plot_a_product OUT_DIR      -> OUT_DIR/plot-a-product.svg

Verified in the code: side panes start closed and open from their icon on the left strip; a product
dropped on an empty panel is plotted there (drops.py, rule "sciqlop.plot_product").
"""
import sys
from pathlib import Path

from SciQLop.components.guides.authoring import kit

P, T = "sqa", 12.0
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
clock = kit.Clock(T)
HOME, ICON, ROW, DROP = (575, 318), (35, 76), (146, 189), (470, 212)
OPEN, PRESS, RELEASE, RESET = 2.2, 4.6, 7.3, 11.4
X0, X1, Y0, Y1 = 286, 664, 112, 292
TRACES = [("bx", "c1"), ("by", "c2"), ("bz", "c3")]


def drawn(start: float) -> list:
    return [(0, "stroke-dashoffset: 1;"), (clock.at(start), "stroke-dashoffset: 1;"), (clock.at(start + 1.7), "stroke-dashoffset: 0;"),
            (100, "stroke-dashoffset: 0;")]


STYLE = kit.base_style(P, f"{T:g}s") + f"""
/* Resting state = the result: the Products pane open and the product plotted. */
.{P} .cursor {{ animation-name: {P}-cursor; opacity: 0; }}
.{P} .ghost {{ animation-name: {P}-ghost; opacity: 0; }}
.{P} .rowhot {{ animation-name: {P}-rowhot; opacity: 0; }}
.{P} .dzhot {{ animation-name: {P}-dzhot; opacity: 0; }}
.{P} .hint {{ animation-name: {P}-hint; opacity: 0; }}
.{P} .plot {{ animation-name: {P}-plot; }}
.{P} .pane {{ animation-name: {P}-pane; }}
.{P} .tabhot {{ animation-name: {P}-tab; }}
""" + "".join(f".{P} .{name} {{ animation-name: {P}-{name}; }}\n" for name in ("open", "press", "release", "s1", "s2", "s3", "t0", "t1", "t2")) \
    + kit.keyframes(f"{P}-cursor", clock.path([(0, HOME), (0.6, HOME), (1.9, ICON), (2.7, ICON), (4.0, ROW), (4.8, ROW), (7.1, DROP),
                                               (10.8, DROP), (T, HOME)], lambda t: "opacity: 1;")) \
    + kit.keyframes(f"{P}-ghost", clock.path([(0, ROW), (4.7, ROW), (4.8, ROW), (7.1, DROP), (RELEASE, DROP), (RELEASE + 0.3, DROP), (T, DROP)],
                                             lambda t: f"opacity: {1 if 4.8 <= t <= RELEASE else 0};")) \
    + kit.keyframes(f"{P}-pane", kit.pane_slide(clock, OPEN, RESET)) \
    + kit.keyframes(f"{P}-tab", clock.shown((OPEN - 0.1, RESET))) \
    + kit.keyframes(f"{P}-rowhot", clock.shown((3.8, RELEASE), fade=0.25)) \
    + kit.keyframes(f"{P}-dzhot", clock.shown((5.8, RELEASE))) \
    + kit.keyframes(f"{P}-hint", clock.hidden((RELEASE, RESET + 0.2))) \
    + kit.keyframes(f"{P}-plot", clock.shown((RELEASE + 0.1, RESET))) \
    + "".join(kit.keyframes(f"{P}-t{i}", drawn(RELEASE + 0.3 + 0.35 * i)) for i in range(3)) \
    + kit.keyframes(f"{P}-open", clock.pulse(OPEN)) + kit.keyframes(f"{P}-press", clock.pulse(PRESS)) + kit.keyframes(f"{P}-release", clock.pulse(RELEASE)) \
    + kit.keyframes(f"{P}-s1", clock.lit((0.5, 3.2))) + kit.keyframes(f"{P}-s2", clock.lit((3.5, RELEASE))) \
    + kit.keyframes(f"{P}-s3", clock.lit((RELEASE + 0.3, RESET - 0.3)))


def points(name: str) -> str:
    """The signal across the plot area, in the panel's own coordinates."""
    f = kit.SIGNALS[name]
    return " ".join(f"{X0 + i / 60 * (X1 - X0):.1f},{(Y0 + Y1) / 2 - f(i / 60) * (Y1 - Y0) / 2 * 0.86:.1f}" for i in range(61))


GRID = "".join(f'<line x1="{X0}" y1="{y}" x2="{X1}" y2="{y}" stroke="var(--line)" stroke-dasharray="2 4"/>' for y in (142, 172, 232, 262))
TICKS = "".join(f'<text x="{X0 + dx}" y="310" text-anchor="middle" class="dim small">{t}</text>' for dx, t in ((63, "12:00"), (189, "13:00"), (315, "14:00")))
LEGEND = "".join(f'<line x1="{x}" y1="122" x2="{x + 12}" y2="122" stroke="var(--{c})" stroke-width="2"/><text x="{x + 16}" y="126" class="small">{n}</text>'
                 for x, (n, c) in zip((560, 596, 632), TRACES))
ROWS = "".join([kit.tree_row(106, 0, "speasy", "open"), kit.tree_row(134, 1, "amda", "open"), kit.tree_row(162, 2, "ACE", "open"),
                kit.tree_row(190, 3, "imf"), kit.tree_row(218, 3, "imf_mag", cls="dim"),
                kit.tree_row(246, 2, "MMS1", "closed", cls="dim"), kit.tree_row(274, 1, "cda", "closed", cls="dim")])

BODY = f"""{kit.window(P, active="tree", tab_class="tabhot a")}
{kit.panel_frame()}
<g class="hint a"><rect x="76" y="112" width="590" height="194" rx="8" fill="none" stroke="var(--dim)" stroke-width="1.2" stroke-dasharray="5 5"/>
  <text x="464" y="204" text-anchor="middle" class="dim" style="font-size:13px">Add a product to this panel</text></g>
<rect class="dzhot a" x="76" y="112" width="590" height="194" rx="8" fill="var(--accent-soft)" stroke="var(--accent)" stroke-width="2"/>
<g class="plot a">{GRID}
  <line x1="{X0}" y1="{(Y0 + Y1) // 2}" x2="{X1}" y2="{(Y0 + Y1) // 2}" stroke="var(--line)"/>
  <line x1="{X0}" y1="{Y0}" x2="{X0}" y2="{Y1}" stroke="var(--dim)"/><line x1="{X0}" y1="{Y1}" x2="{X1}" y2="{Y1}" stroke="var(--dim)"/>
  <text x="{X0 - 8}" y="{Y0 + 4}" text-anchor="end" class="dim small">nT</text><text x="{X0 - 8}" y="{(Y0 + Y1) // 2 + 4}" text-anchor="end" class="dim small">0</text>
  {TICKS}{"".join(kit.trace(points(n), c, f"a t{i}") for i, (n, c) in enumerate(TRACES))}{LEGEND}</g>
{kit.TIME_PILL}
{kit.products_pane(ROWS, hot_y=190, pane_class="pane a")}
{kit.strip("tree", "tabhot a")}
{kit.ring("open", 34, 73)}{kit.ring("press", ROW[0], ROW[1] - 3)}{kit.ring("release", *DROP)}
{kit.ghost("imf")}
{kit.CURSOR}
{kit.step(66, 1, "Open the Products pane", "s1")}
{kit.step(276, 2, "Drag a product onto a panel", "s2")}
{kit.step(512, 3, "The data is plotted", "s3")}"""

SVG = kit.svg(P, "Open the Products pane with its icon on the left edge, then drag a product onto a plot panel to plot it.", STYLE, BODY)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "plot-a-product.svg").write_text(SVG)
print(len(SVG))
