"""Guide: change a virtual product's adjustable inputs in the Properties pane.

    python -m SciQLop.components.guides.authoring.core.tune_a_virtual_product OUT_DIR      -> OUT_DIR/tune-a-virtual-product.svg

Verified in the code: each keyword argument with a default becomes an input (core/knobs/introspection.py),
listed under "Adjustable inputs" for the curve picked in the Properties pane's tree
(plotting/ui/knob_inspector/). A float input is a spin box, applied live after a short pause.
The Properties pane itself is SciQLopPlots' and changes with it: it is drawn loosely on purpose.
"""
import inspect
import math
import sys
from pathlib import Path

from SciQLop.components.guides.authoring import kit
from SciQLop.components.plotting.ui.knob_inspector.extension import KnobInspectorExtension

P, T = "sqt", 13.0
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
clock = kit.Clock(T)
SECTION = inspect.signature(KnobInspectorExtension).parameters["title"].default   # "Adjustable inputs"
HOME, ICON, ROW, UP = (600, 300), (35, 157), (132, 131), (226, 244)
OPEN, PICK, STEP, RESET = 1.8, 3.6, 5.4, 12.2


def sine(cycles):
    return " ".join(f"{76 + i / 120 * 592:.1f},{214 - 70 * math.sin(i / 120 * cycles * math.tau):.1f}" for i in range(121))


STYLE = kit.base_style(P, f"{T:g}s") + f"""
/* Resting state = the result: the curve picked, its frequency raised, the curve redrawn. */
.{P} .cursor {{ animation-name: {P}-cursor; opacity: 0; }}
.{P} .pane {{ animation-name: {P}-pane; }}
.{P} .tabhot {{ animation-name: {P}-tab; }}
.{P} .picked {{ animation-name: {P}-picked; }}
.{P} .inputs {{ animation-name: {P}-inputs; }}
.{P} .before {{ animation-name: {P}-before; opacity: 0; }}
.{P} .after {{ animation-name: {P}-after; }}
.{P} .old {{ animation-name: {P}-old; opacity: 0; }}
.{P} .new {{ animation-name: {P}-new; }}
""" + "".join(f".{P} .{n} {{ animation-name: {P}-{n}; }}\n" for n in ("open", "pick", "step", "s1", "s2", "s3")) \
    + kit.keyframes(f"{P}-cursor", clock.path([(0, HOME), (0.6, HOME), (1.5, ICON), (2.4, ICON), (3.3, ROW), (4.2, ROW), (5.1, UP),
                                               (11.4, UP), (T, HOME)], lambda t: "opacity: 1;")) \
    + kit.keyframes(f"{P}-pane", kit.pane_slide(clock, OPEN, RESET)) \
    + kit.keyframes(f"{P}-tab", clock.shown((OPEN - 0.1, RESET))) \
    + kit.keyframes(f"{P}-picked", clock.shown((PICK, RESET), fade=0.15)) \
    + kit.keyframes(f"{P}-inputs", clock.shown((PICK + 0.2, RESET))) \
    + kit.keyframes(f"{P}-before", clock.hidden((STEP, RESET), fade=0.1)) \
    + kit.keyframes(f"{P}-after", clock.shown((STEP, RESET), fade=0.1)) \
    + kit.keyframes(f"{P}-old", clock.hidden((STEP + 0.5, RESET + 0.3), fade=0.6)) \
    + kit.keyframes(f"{P}-new", clock.shown((STEP + 0.5, RESET), fade=0.6)) \
    + kit.keyframes(f"{P}-open", clock.pulse(OPEN)) + kit.keyframes(f"{P}-pick", clock.pulse(PICK)) + kit.keyframes(f"{P}-step", clock.pulse(STEP)) \
    + kit.keyframes(f"{P}-s1", clock.lit((0.5, 2.8))) + kit.keyframes(f"{P}-s2", clock.lit((3.0, 4.6))) \
    + kit.keyframes(f"{P}-s3", clock.lit((4.8, RESET - 0.3)))


def spin_box(y, values):
    texts = "".join(f'<text x="160" y="{y + 15}" class="small {cls}">{value}</text>' for cls, value in values)
    return (f'<rect x="152" y="{y}" width="82" height="22" rx="5" fill="var(--win)" stroke="var(--line)"/>{texts}'
            f'<path d="M222 {y + 9} l4 -4 l4 4 M222 {y + 13} l4 4 l4 -4" fill="none" stroke="var(--dim)" stroke-width="1.2"/>')


ROWS = (kit.tree_row(106, 0, "Plot", "open")
        + kit.tree_row(134, 1, "tunable_sine", "closed")
        + '<line x1="57" y1="180" x2="233" y2="180" stroke="var(--line)"/>'
        + f'<g class="inputs a"><text x="62" y="206" class="title">{kit.ui(SECTION)}</text>'
        + '<text x="62" y="249" class="small">frequency</text>' + spin_box(234, [("before a", "0.01"), ("after a", "0.02")])
        + '<text x="62" y="281" class="small">amplitude</text>' + spin_box(266, [("", "1.00")]) + "</g>")

BODY = f"""{kit.window(P, active="plot_properties", tab_class="tabhot a")}
{kit.panel_frame()}
<rect x="76" y="114" width="592" height="200" rx="3" fill="none" stroke="var(--line)"/>
<line x1="84" y1="214" x2="660" y2="214" stroke="var(--line)" stroke-dasharray="2 4"/>
<g class="old a">{kit.trace(sine(5), "c1", "solid")}</g>
<g class="new a">{kit.trace(sine(10), "c1", "solid")}</g>
{kit.time_pill(474)}
{kit.pane(kit.ui("Properties"), ROWS, hot_y=134, pane_class="pane a", hot_class="picked a")}
{kit.strip("plot_properties", "tabhot a")}
{kit.ring("open", ICON[0], ICON[1] - 3)}{kit.ring("pick", ROW[0], ROW[1] - 3)}{kit.ring("step", *UP)}
{kit.CURSOR}
{kit.step(58, 1, "Open the Properties pane", "s1")}
{kit.step(272, 2, "Pick the curve", "s2")}
{kit.step(430, 3, "Change an input: the curve follows", "s3")}"""

SVG = kit.svg(P, "Open the Properties pane from the left edge and pick a virtual product's curve: its keyword arguments "
              "are listed under Adjustable inputs. Change one and the curve is computed again.", STYLE, BODY)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "tune-a-virtual-product.svg").write_text(SVG)
print(len(SVG))
