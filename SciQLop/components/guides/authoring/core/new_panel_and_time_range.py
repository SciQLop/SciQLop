"""Guide: add a plot panel and set its time range.

    python -m SciQLop.components.guides.authoring.core.new_panel_and_time_range OUT_DIR      -> OUT_DIR/new-panel-and-time-range.svg

Verified in the code: the tab strip of a panel area has a "New plot panel" button with the add_graph
icon (mainwindow.py _ensure_add_panel_button); File > New plot panel (Ctrl+N) does the same. A new
panel is empty and says "Add a product to this panel". The bar under a panel holds, in this order:
step buttons, the start box (UTC), the duration box, step buttons, "Zoom limit", then "Catalog mode"
(panel_container.py, time_range_bar.py). A typed start applies on Enter; the duration box takes a
preset or typed text such as 3h, 90m, 2d.
"""
import sys
from pathlib import Path

from SciQLop.components.guides.authoring import kit

P, T = "sqn", 13.0
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
clock = kit.Clock(T)
HOME, PLUS, START, DURATION = (575, 250), (136, 77), (214, 346), (338, 346)
ADD, EDIT_START, TYPED_START, ENTER_START, EDIT_DUR, TYPED_DUR, ENTER_DUR, RESET = 1.8, 4.0, 4.6, 5.9, 7.4, 8.0, 9.1, 12.0

beside = lambda xy: (xy[0], xy[1] - 62)             # where the "Enter" badge sits: above the box being edited

STYLE = kit.base_style(P, f"{T:g}s") + f"""
/* Resting state = the result: the new empty panel, with the typed start and duration. */
.{P} .cursor {{ animation-name: {P}-cursor; opacity: 0; }}
.{P} .old {{ animation-name: {P}-old; opacity: 0; }}
.{P} .new {{ animation-name: {P}-new; }}
.{P} .plus {{ animation-name: {P}-plus; transform: translate(58px, 0px); }}
.{P} .start0 {{ animation-name: {P}-start0; opacity: 0; }} .{P} .start1 {{ animation-name: {P}-start1; }}
.{P} .dur0 {{ animation-name: {P}-dur0; opacity: 0; }} .{P} .dur1 {{ animation-name: {P}-dur1; }}
.{P} .focus1 {{ animation-name: {P}-focus1; opacity: 0; }} .{P} .focus2 {{ animation-name: {P}-focus2; opacity: 0; }}
.{P} .enter {{ animation-name: {P}-enter; opacity: 0; }}
""" + "".join(f".{P} .{name} {{ animation-name: {P}-{name}; }}\n" for name in ("k0", "k1", "k2", "s1", "s2", "s3")) \
    + kit.keyframes(f"{P}-cursor", clock.path([(0, HOME), (0.6, HOME), (1.6, PLUS), (2.6, PLUS), (3.8, START), (6.4, START), (7.2, DURATION),
                                               (11.6, DURATION), (T, HOME)], lambda t: "opacity: 1;")) \
    + kit.keyframes(f"{P}-old", clock.hidden((ADD + 0.1, RESET))) + kit.keyframes(f"{P}-new", clock.shown((ADD + 0.1, RESET))) \
    + kit.keyframes(f"{P}-plus", [(0, "transform: translate(0px, 0px);"), (clock.at(ADD + 0.1), "transform: translate(0px, 0px);"),
                                  (clock.at(ADD + 0.4), "transform: translate(58px, 0px);"), (clock.at(RESET), "transform: translate(58px, 0px);"),
                                  (clock.at(RESET + 0.3), "transform: translate(0px, 0px);"), (100, "transform: translate(0px, 0px);")]) \
    + kit.keyframes(f"{P}-start0", clock.hidden((TYPED_START, RESET))) + kit.keyframes(f"{P}-start1", clock.shown((TYPED_START + 0.3, RESET))) \
    + kit.keyframes(f"{P}-dur0", clock.hidden((TYPED_DUR, RESET))) + kit.keyframes(f"{P}-dur1", clock.shown((TYPED_DUR + 0.3, RESET))) \
    + kit.keyframes(f"{P}-focus1", clock.shown((EDIT_START, ENTER_START + 0.3), fade=0.15)) \
    + kit.keyframes(f"{P}-focus2", clock.shown((EDIT_DUR, ENTER_DUR + 0.3), fade=0.15)) \
    + kit.keyframes(f"{P}-enter", clock.path([(0, beside(START)), (ENTER_START - 0.4, beside(START)), (ENTER_START - 0.2, beside(START)),
                                              (ENTER_START + 0.5, beside(START)), (ENTER_START + 0.7, beside(START)), (ENTER_START + 0.8, beside(DURATION)),
                                              (ENTER_DUR - 0.4, beside(DURATION)), (ENTER_DUR - 0.2, beside(DURATION)), (ENTER_DUR + 0.5, beside(DURATION)),
                                              (ENTER_DUR + 0.7, beside(DURATION)), (T, beside(DURATION))],
                                             lambda t: f"opacity: {1 if t in (ENTER_START - 0.2, ENTER_START + 0.5, ENTER_DUR - 0.2, ENTER_DUR + 0.5) else 0};")) \
    + kit.keyframes(f"{P}-k0", clock.pulse(ADD)) + kit.keyframes(f"{P}-k1", clock.pulse(EDIT_START)) + kit.keyframes(f"{P}-k2", clock.pulse(EDIT_DUR)) \
    + kit.keyframes(f"{P}-s1", clock.lit((0.5, 2.8))) + kit.keyframes(f"{P}-s2", clock.lit((3.2, ENTER_START + 0.5))) \
    + kit.keyframes(f"{P}-s3", clock.lit((6.8, ENTER_DUR + 0.6)))


def nav(x: float, glyph: str) -> str:
    return (f'<rect x="{x}" y="330" width="20" height="22" rx="6" fill="var(--win)" stroke="var(--line)"/>'
            f'<path d="{glyph}" transform="translate({x + 10} 341)" fill="var(--dim)"/>')


BACK, FORWARD = "M3 -4 v8 l-6 -4 z", "M-3 -4 v8 l6 -4 z"
FAST_BACK, FAST_FORWARD = "M4 -4 v8 l-6 -4 z M-5 -4 h1.6 v8 h-1.6 z", "M-4 -4 v8 l6 -4 z M5 -4 h-1.6 v8 h1.6 z"
box = lambda x, w: f'<rect x="{x}" y="330" width="{w}" height="22" rx="6" fill="var(--win)" stroke="var(--line)"/>'
focus = lambda cls, x, w: f'<rect class="{cls} a" x="{x}" y="330" width="{w}" height="22" rx="6" fill="none" stroke="var(--accent)" stroke-width="2"/>'

TIME_BAR = f"""{nav(76, FAST_BACK)}{nav(100, BACK)}
{box(126, 172)}{focus("focus1", 126, 172)}
<text x="136" y="345" class="small start0 a">2025-11-16 15:59:00 UTC</text><text x="136" y="345" class="small start1 a">2019-03-01 12:00:00 UTC</text>
{box(304, 58)}{focus("focus2", 304, 58)}
<text x="314" y="345" class="small dur0 a">1d</text><text x="314" y="345" class="small dur1 a">3h</text>
<path d="M343 339 l4 4 l4 -4" fill="none" stroke="var(--dim)" stroke-width="1.3"/>
{nav(368, FORWARD)}{nav(392, FAST_FORWARD)}
<text x="426" y="345" class="small dim">Zoom limit:</text>{kit.combo(482, 52, "1d")}
<text x="548" y="345" class="small dim">Catalog mode:</text>{kit.combo(620, 64, "View")}"""

PLUS_ICON = kit.icon("add_graph", 66, "var(--fg)", x=126)

BODY = f"""{kit.window(P)}
<text x="66" y="78" class="title">Panel 1</text>
<line class="old a" x1="66" y1="84" x2="112" y2="84" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/>
<g class="new a"><text x="124" y="78" class="title">Panel 2</text>
  <line x1="124" y1="84" x2="170" y2="84" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/></g>
<g class="plus a">{PLUS_ICON}</g>
<rect x="60" y="96" width="624" height="226" rx="10" fill="none" stroke="var(--line)"/>
<g class="old a">{kit.static_plot(76, 104, 592, {"bx": "c1", "by": "c2", "bz": "c3"})}{kit.static_plot(76, 214, 592, {"density": "c3"})}</g>
<g class="new a"><rect x="76" y="112" width="592" height="194" rx="8" fill="none" stroke="var(--dim)" stroke-width="1.2" stroke-dasharray="5 5"/>
  <text x="372" y="214" text-anchor="middle" class="dim" style="font-size:13px">Add a product to this panel</text></g>
{TIME_BAR}
{kit.ring("k0", 134, 74)}{kit.ring("k1", 212, 341)}{kit.ring("k2", 333, 341)}
<g class="enter a">{kit.keycap("Enter")}</g>
{kit.CURSOR}
{kit.step(58, 1, "Click + for a new panel", "s1")}
{kit.step(252, 2, "Type the start, press Enter", "s2")}
{kit.step(468, 3, "Type a duration: 3h, 90m, 2d", "s3")}"""

SVG = kit.svg(P, "Click the plus button next to the panel tabs for a new, empty panel. Under it, type a start date and press Enter, "
              "then type a duration such as 3h in the box beside it.", STYLE, BODY)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "new-panel-and-time-range.svg").write_text(SVG)
print(len(SVG))
