"""Guide: where a product can be dropped on a panel that already has plots.

    python -m SciQLop.components.guides.authoring.core.drop_on_a_panel OUT_DIR      -> OUT_DIR/drop-on-a-panel.svg

The three cases are the real ones (SciQLopPlots PlaceHolderManager): the middle of a plot adds the
product to it; its top 15% or bottom 15% opens a blue placeholder, and dropping on that makes a
new plot there. Three takes of 6 s each; the panel goes back to two plots between takes.
"""
import math
import sys
from pathlib import Path

from SciQLop.components.guides.authoring import kit

P, T = "sqd", 18.0
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

# Panel geometry: plots are drawn in a local 412 x 100 box and placed with translate + scaleY.
PX, W, H = 262, 412, 100
TOP, MID_SLOT, LOW = 104, 177.33, 250.67          # the three slots when the panel holds three plots
SMALL = 63.33 / H                                # a plot's height factor in that layout
HOME = (150, 217)                                # the cursor rests on the dragged row
TAKES = [                                        # (edge point that triggers the reaction, drop point)
    ((470, 154), (470, 154)),                    # middle of the first plot
    ((470, 110), (470, 136)),                    # its top edge, then onto the placeholder
    ((470, 198), (470, 209)),                    # its bottom edge, then onto the placeholder
]


def at(take: int, seconds: float) -> float:
    """Percent of the loop for a moment `seconds` into take `take`."""
    return (take * 6.0 + seconds) / T * 100


def curve(f, amplitude=0.8) -> str:
    return " ".join(f"{i / 60 * (W - 16) + 8:.1f},{H / 2 - f(i / 60) * H / 2 * amplitude:.1f}" for i in range(61))


wob = lambda u, k, ph: 0.05 * math.sin(k * u * math.tau + ph)
BX = curve(lambda u: 0.75 * math.tanh((u - 0.5) * 9) + wob(u, 7, 0.3))
BY = curve(lambda u: 0.55 * math.exp(-((u - 0.5) / 0.13) ** 2) - 0.2 + wob(u, 9, 1.1))
BZ = curve(lambda u: -0.6 * math.tanh((u - 0.52) * 7) + 0.1 + wob(u, 6, 2.0))
DENSITY = curve(lambda u: 0.5 / (1 + math.exp(-(u - 0.5) * 14)) - 0.35 + wob(u, 11, 0.7) + 0.5 * wob(u, 23, 2))
BMAG = curve(lambda u: 0.55 - 0.5 * math.exp(-((u - 0.5) / 0.1) ** 2) + wob(u, 8, 1.6))

move = lambda xy: f"transform: translate({xy[0]}px, {xy[1]}px);"
place = lambda y, s=1.0: f"transform: translate({PX}px, {y}px) scale(1, {s:.4f});"


def over_takes(make) -> list:
    return [stop for take in range(3) for stop in make(take)]


def cursor_stops(take):
    edge, drop = TAKES[take]
    return [(at(take, 0), move(HOME)), (at(take, 0.6), move(HOME)), (at(take, 2.0), move(edge)),
            (at(take, 2.6), move(drop)), (at(take, 4.6), move(drop)), (at(take, 5.8), move(HOME))]


def ghost_stops(take):
    edge, drop = TAKES[take]
    return [(at(take, 0), move(HOME) + "opacity: 0;"), (at(take, 0.5), move(HOME) + "opacity: 0;"),
            (at(take, 0.6), move(HOME) + "opacity: 1;"), (at(take, 2.0), move(edge) + "opacity: 1;"),
            (at(take, 2.6), move(drop) + "opacity: 1;"), (at(take, 2.9), move(drop) + "opacity: 1;"),
            (at(take, 3.1), move(drop) + "opacity: 0;"), (at(take, 5.9), move(HOME) + "opacity: 0;")]


def pulse(take, when):
    return [(at(take, when - 0.02), "transform: scale(.3); opacity: 0;"), (at(take, when), "transform: scale(.3); opacity: .9;"),
            (at(take, when + 0.6), "transform: scale(1.5); opacity: 0;")]


def shown(take, start, end, fade=0.3):
    return [(at(take, start), "opacity: 0;"), (at(take, start + fade), "opacity: 1;"),
            (at(take, end), "opacity: 1;"), (at(take, end + fade), "opacity: 0;")]


def only(take, stops, rest):
    """Stops for one take, resting at `rest` for the remainder of the loop."""
    return [(0, rest), *stops, (100, rest)]


def reflow(y_small, takes):
    """A plot at full height, squeezed to the three-plot layout while a take holds a placeholder or a new plot."""
    full = place(TOP if y_small[0] < 200 else 214)
    stops = [(0, full)]
    for take, y in zip(takes, y_small):
        stops += [(at(take, 2.0), full), (at(take, 2.35), place(y, SMALL)), (at(take, 5.2), place(y, SMALL)), (at(take, 5.7), full)]
    return stops + [(100, full)]


def drawn(take):
    return [(0, "stroke-dashoffset: 1;"), (at(take, 3.1), "stroke-dashoffset: 1;"),
            (at(take, 4.3), "stroke-dashoffset: 0;"), (100, "stroke-dashoffset: 0;")]


STYLE = kit.base_style(P, f"{T:g}s") + f"""
/* Resting state = the panel with its two plots and the three rules lit: true without animation. */
.{P} .cursor {{ animation-name: {P}-cursor; opacity: 0; }}
.{P} .ghost {{ animation-name: {P}-ghost; opacity: 0; }}
.{P} .rowhot {{ animation-name: {P}-rowhot; opacity: 0; }}
.{P} .press {{ animation-name: {P}-press; }}
.{P} .p1 {{ animation-name: {P}-p1; transform: translate({PX}px, {TOP}px); }}
.{P} .p2 {{ animation-name: {P}-p2; transform: translate({PX}px, 214px); }}
.{P} .hot, .{P} .extra, .{P} .hold, .{P} .made {{ opacity: 0; }}
.{P} .frame {{ fill: none; stroke: var(--line); vector-effect: non-scaling-stroke; }}
.{P} .zero {{ stroke: var(--line); stroke-dasharray: 2 4; vector-effect: non-scaling-stroke; }}
""" + "".join(f".{P} .{name}{i} {{ animation-name: {P}-{name}{i}; }}\n" for name in ("rel", "s", "draw") for i in range(3)) \
    + "".join(f".{P} .{name} {{ animation-name: {P}-{name}; }}\n" for name in ("hot", "extra", "hold1", "hold2", "made1", "made2")) \
    + kit.keyframes(f"{P}-cursor", [*[(pct, css + "opacity: 1;") for pct, css in over_takes(cursor_stops)], (100, move(HOME) + "opacity: 1;")]) \
    + kit.keyframes(f"{P}-ghost", [*over_takes(ghost_stops), (100, move(HOME) + "opacity: 0;")]) \
    + kit.keyframes(f"{P}-rowhot", over_takes(lambda t: shown(t, 0.3, 2.9, fade=0.2))) \
    + kit.keyframes(f"{P}-press", over_takes(lambda t: pulse(t, 0.5))) \
    + "".join(kit.keyframes(f"{P}-rel{t}", only(t, pulse(t, 2.9), "transform: scale(.3); opacity: 0;")) for t in range(3)) \
    + "".join(kit.keyframes(f"{P}-s{t}", only(t, [(at(t, 0.2), "opacity: .4;"), (at(t, 0.5), "opacity: 1;"), (at(t, 5.5), "opacity: 1;"), (at(t, 5.8), "opacity: .4;")], "opacity: .4;")) for t in range(3)) \
    + "".join(kit.keyframes(f"{P}-draw{t}", drawn(t)) for t in range(3)) \
    + kit.keyframes(f"{P}-hot", only(0, shown(0, 1.6, 2.9, fade=0.25), "opacity: 0;")) \
    + kit.keyframes(f"{P}-extra", only(0, shown(0, 2.9, 5.2, fade=0.4), "opacity: 0;")) \
    + "".join(kit.keyframes(f"{P}-hold{t}", only(t, shown(t, 2.05, 2.9, fade=0.3), "opacity: 0;")) for t in (1, 2)) \
    + "".join(kit.keyframes(f"{P}-made{t}", only(t, shown(t, 2.9, 5.2, fade=0.4), "opacity: 0;")) for t in (1, 2)) \
    + kit.keyframes(f"{P}-p1", reflow([MID_SLOT, TOP], [1, 2])) \
    + kit.keyframes(f"{P}-p2", reflow([LOW, LOW], [1, 2]))


def plot(cls: str, traces: str, extra: str = "") -> str:
    return (f'<g class="{cls} a"><rect class="frame" width="{W}" height="{H}" rx="3"/>'
            f'<line class="zero" x1="8" y1="{H / 2}" x2="{W - 8}" y2="{H / 2}"/>{traces}{extra}</g>')


def trace(points: str, color: str, cls: str = "") -> str:
    return f'<polyline class="trace {cls}" pathLength="1" stroke="var(--{color})" points="{points}"/>'


def new_plot(take: int, y: float) -> str:
    """The placeholder SciQLop shows while the product hovers an edge, then the plot the drop makes."""
    return (f'<rect class="hold{take} a" x="{PX}" y="{y}" width="{W}" height="63.33" rx="3" fill="var(--accent-soft)" stroke="var(--accent)" stroke-width="1.5"/>'
            f'<g class="made{take} a" transform="translate({PX} {y}) scale(1 {SMALL:.4f})"><rect class="frame" width="{W}" height="{H}" rx="3" style="fill:var(--win)"/>'
            f'<line class="zero" x1="8" y1="{H / 2}" x2="{W - 8}" y2="{H / 2}"/>{trace(BMAG, "c4", f"a draw{take}")}</g>')


ROWS = "".join([kit.tree_row(106, 0, "speasy", "open"), kit.tree_row(134, 1, "amda", "open"), kit.tree_row(162, 2, "ACE", "open"),
                kit.tree_row(190, 3, "imf", cls="dim"), kit.tree_row(218, 3, "imf_mag"),
                kit.tree_row(246, 2, "MMS1", "closed", cls="dim"), kit.tree_row(274, 1, "cda", "closed", cls="dim")])

BODY = f"""{kit.window(P, active="tree")}
<text x="258" y="78" class="title">Panel 1</text>
<line x1="258" y1="84" x2="304" y2="84" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/>
<rect x="252" y="96" width="432" height="226" rx="10" fill="none" stroke="var(--line)"/>
{new_plot(1, TOP)}
{new_plot(2, MID_SLOT)}
{plot("p1", trace(BX, "c1") + trace(BY, "c2") + trace(BZ, "c3"),
      f'<g class="extra a">{trace(BMAG, "c4", "a draw0")}</g>'
      f'<rect class="hot a" x="0" y="0" width="{W}" height="{H}" rx="3" fill="var(--accent-soft)" stroke="var(--accent)" stroke-width="2"/>')}
{plot("p2", trace(DENSITY, "c3"))}
<rect x="474" y="330" width="210" height="22" rx="11" fill="var(--side)" stroke="var(--line)"/>
<text x="488" y="345" class="small dim">2019-03-01 12:00 UTC</text><text x="642" y="345" class="small">3h</text>
<g clip-path="url(#{P}-body)">{kit.products_pane(ROWS, hot_y=218)}</g>
{kit.ring("press", 146, 214)}
{"".join(kit.ring(f"rel{t}", *TAKES[t][1]) for t in range(3))}
{kit.ghost("imf_mag", width=78)}
{kit.CURSOR}
{kit.step(58, 1, "Middle of a plot: added to it", "s0")}
{kit.step(284, 2, "Top edge: new plot above", "s1")}
{kit.step(494, 3, "Bottom edge: new plot below", "s2")}"""

SVG = kit.svg(P, "Dropping a product on the middle of a plot adds it to that plot; on its top or bottom edge, "
              "a blue placeholder opens and the drop makes a new plot there.", STYLE, BODY)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "drop-on-a-panel.svg").write_text(SVG)
print(len(SVG))
