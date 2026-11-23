"""Guide: move and zoom a plot with the wheel, then fit it with M.

    python -m SciQLop.components.guides.authoring.core.plot_keys_and_wheel OUT_DIR      -> OUT_DIR/plot-keys-and-wheel.svg

Verified in the code (SciQLopPlots SciQLopPlot::wheelEvent): over the plot the wheel moves in time,
Ctrl+wheel zooms the time axis, Shift+wheel the vertical one; over an axis the wheel zooms that axis.
M rescales the axis under the cursor, else the selected ones, else the plot's axes; L toggles the log
scale of the axis under the cursor; H hides the selection (rescale_hovered_or_selected_axes and its
siblings). The keys act on the plot that has the keyboard focus, which a plot takes on a click
(StrongFocus, plotting/ui/plot_shortcuts.py), hence the click before M.
"""
import sys
from pathlib import Path

from SciQLop.components.guides.authoring import kit

P, T = "sqw", 15.0
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
clock = kit.Clock(T)
X0, X1, Y0, Y1 = 100, 668, 112, 304
CX, CY = 384, (Y0 + Y1) / 2
HOME, OVER, AXIS = (600, 290), (CX, 150), (90, 150)
PAN, ZOOM, AXIS_ZOOM, CLICK, KEY_M, RESET = 2.0, 4.0, 6.6, 8.8, 9.4, 13.6
SX, SY, SHIFT = 1.8, 1.8, -120


def screen_curve(name, sx, sy, shift):
    """The signal as the plot shows it after moving by `shift` and zooming by sx, sy about the centre, cut
    to the plot box: one polyline per stretch inside it."""
    pieces, piece = [], []
    for i in range(81):
        x = X0 + i / 80 * (X1 - X0)
        u = ((x - CX) / sx + CX - shift - X0) / (X1 - X0)
        y = CY - sy * kit.SIGNALS[name](u) * 72
        if Y0 + 2 <= y <= Y1 - 2:
            piece.append(f"{x:.0f},{y:.1f}")
        elif piece:
            pieces.append(piece)
            piece = []
    return pieces + [piece] * bool(piece)


def frame(sx, sy, shift):
    return "".join(f'<polyline class="curve" stroke="var(--{color})" points="{" ".join(piece)}"/>'
                   for name, color in (("bx", "c1"), ("bz", "c3")) for piece in screen_curve(name, sx, sy, shift) if len(piece) > 1)


# (seconds, view) at each turn of the loop; between two of them the view moves in STEPS drawings.
TURNS = [(0, (1, 1, 0)), (PAN, (1, 1, 0)), (PAN + 0.9, (1, 1, SHIFT)), (ZOOM, (1, 1, SHIFT)), (ZOOM + 0.9, (SX, 1, SHIFT)),
         (AXIS_ZOOM, (SX, 1, SHIFT)), (AXIS_ZOOM + 0.9, (SX, SY, SHIFT)), (KEY_M, (SX, SY, SHIFT)), (KEY_M + 0.5, (SX, 1, SHIFT)),
         (RESET, (SX, 1, SHIFT)), (RESET + 0.6, (1, 1, 0)), (T, (1, 1, 0))]
STEPS = 4


def flip_book():
    """(start, end, view) of each drawing: held views, and the in-between ones of each move."""
    pages = []
    for (t0, v0), (t1, v1) in zip(TURNS, TURNS[1:]):
        if v0 == v1:
            pages.append((t0, t1, v0))
            continue
        for k in range(STEPS):
            f = (k + 1) / STEPS
            pages.append((t0 + (t1 - t0) * k / STEPS, t0 + (t1 - t0) * (k + 1) / STEPS, tuple(a + (b - a) * f for a, b in zip(v0, v1))))
    return pages


PAGES = flip_book()


STYLE = kit.base_style(P, f"{T:g}s") + f"""
/* Resting state = the plot as it starts. */
.{P} .cursor {{ animation-name: {P}-cursor; opacity: 0; }}
""" + "".join(f".{P} .f{i} {{ animation-name: {P}-f{i}; opacity: {int(i == 0)}; }}\n" for i in range(len(PAGES))) \
    + "".join(f".{P} .{n} {{ animation-name: {P}-{n}; opacity: 0; }}\n" for n in ("kwheel", "kctrl", "kaxis", "km")) \
    + "".join(f".{P} .{n} {{ animation-name: {P}-{n}; }}\n" for n in ("click", "s1", "s2", "s3")) \
    + kit.keyframes(f"{P}-cursor", clock.path([(0, HOME), (0.6, HOME), (1.6, OVER), (5.6, OVER), (6.3, AXIS), (7.8, AXIS), (8.6, OVER),
                                               (12.8, OVER), (T, HOME)], lambda t: "opacity: 1;")) \
    + "".join(kit.keyframes(f"{P}-f{i}", clock.shown((start, end), fade=0.01)) for i, (start, end, _) in enumerate(PAGES)) \
    + kit.keyframes(f"{P}-kwheel", clock.shown((PAN - 0.3, PAN + 1.2), fade=0.2)) \
    + kit.keyframes(f"{P}-kctrl", clock.shown((ZOOM - 0.3, ZOOM + 1.2), fade=0.2)) \
    + kit.keyframes(f"{P}-kaxis", clock.shown((AXIS_ZOOM - 0.3, AXIS_ZOOM + 1.2), fade=0.2)) \
    + kit.keyframes(f"{P}-km", clock.shown((KEY_M - 0.3, KEY_M + 1.0), fade=0.2)) \
    + kit.keyframes(f"{P}-click", clock.pulse(CLICK)) \
    + kit.keyframes(f"{P}-s1", clock.lit((1.2, 5.3))) + kit.keyframes(f"{P}-s2", clock.lit((5.6, 8.0))) \
    + kit.keyframes(f"{P}-s3", clock.lit((8.3, RESET - 0.4)))

# simplify: the moves are a flip book of curves cut to the plot, not a transform: Qt cannot clip an animated
# group. Smoother moves need more STEPS, and the file grows with them.
CURVES = "".join(f'<g class="f{i} a">{frame(*view)}</g>' for i, (_, _, view) in enumerate(PAGES))
TICKS = "".join(f'<text x="{X0 - 6}" y="{y + 4}" text-anchor="end" class="small dim">{label}</text>'
                for y, label in ((Y0 + 14, "10"), (CY, "0"), (Y1 - 14, "-10")))

BODY = f"""{kit.window(P)}
{CURVES}
{kit.panel_frame()}
<rect x="{X0}" y="{Y0}" width="{X1 - X0}" height="{Y1 - Y0}" rx="3" fill="none" stroke="var(--line)"/>
<line x1="{X0}" y1="{Y0}" x2="{X0}" y2="{Y1}" stroke="var(--dim)"/>
{TICKS}<text x="{X0 - 30}" y="{Y0 + 8}" class="small dim">nT</text>
{kit.time_pill(474)}
{kit.strip()}
{kit.ring("click", *OVER)}
<g transform="translate({OVER[0]} {OVER[1]})">{kit.keycap("Wheel", cls="kwheel a")}</g>
<g transform="translate({OVER[0]} {OVER[1]})">{kit.keycap("Ctrl+wheel", cls="kctrl a")}</g>
<g transform="translate({AXIS[0]} {AXIS[1]})">{kit.keycap("Wheel", cls="kaxis a")}</g>
<g transform="translate({OVER[0]} {OVER[1]})">{kit.keycap("M", cls="km a")}</g>
{kit.CURSOR}
{kit.step(48, 1, "Wheel: move, Ctrl+wheel: zoom", "s1")}
{kit.step(300, 2, "Wheel on an axis: zoom it", "s2")}
{kit.step(510, 3, "Click, then M to fit", "s3")}"""

SVG = kit.svg(P, "Over a plot the wheel moves in time and Ctrl+wheel zooms in time; over an axis the wheel zooms that axis. "
              "Click the plot, then press M to fit it again. L toggles the log scale of the axis under the cursor.", STYLE, BODY)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "plot-keys-and-wheel.svg").write_text(SVG)
print(len(SVG))
