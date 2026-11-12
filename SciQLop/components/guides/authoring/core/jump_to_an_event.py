"""Guide: Jump mode - pick an event in the catalog's list and the panel goes to it.

    python -m SciQLop.components.guides.authoring.core.jump_to_an_event OUT_DIR      -> OUT_DIR/jump-to-an-event.svg

Verified in the code (panel_manager.py, catalog_browser.py): with the panel's Catalog mode on Jump,
selecting an event in the Catalogs pane's event table sets the panel's range to that event, widened
by the "Zoom out" factor shown next to the mode box (x2 = the event fills half the panel).
"""
import sys
from pathlib import Path

from SciQLop.components.guides.authoring import kit

P, T = "sqj", 14.0
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
clock = kit.Clock(T)
PX, W = 262, 412
EVENTS = [(40, 26, "12:17:29"), (190, 50, "13:23:01"), (330, 26, "14:24:13")]     # (local x, width, start time)
ROW_Y = [250, 274, 298]
HOME, COMBO, JUMP = (600, 300), (546, 345), (540, 300)
ROW2, ROW3 = (150, ROW_Y[1] - 2), (150, ROW_Y[2] - 2)
CLICK_COMBO, CLICK_JUMP, PICK2, PICK3, RESET = 1.7, 2.7, 4.4, 7.6, 12.8


def window_of(event=None) -> tuple[float, float]:
    """The local x-range of the plots that is visible: all of it, or `event` filling half the panel (zoom-out x2)."""
    if event is None:
        return 0.0, float(W)
    x, width, _ = event
    return x - width / 2, x + 1.5 * width


VIEWS = {"v0": None, "v2": EVENTS[1], "v3": EVENTS[2]}      # the panel before any pick, then on each picked event


STYLE = kit.base_style(P, f"{T:g}s") + f"""
/* Resting state = the result: Jump mode, the last picked event filling half the panel. */
.{P} .cursor {{ animation-name: {P}-cursor; opacity: 0; }}
.{P} .v0 {{ animation-name: {P}-v0; opacity: 0; }} .{P} .v2 {{ animation-name: {P}-v2; opacity: 0; }} .{P} .v3 {{ animation-name: {P}-v3; }}
.{P} .menu {{ animation-name: {P}-menu; opacity: 0; }}
.{P} .view {{ animation-name: {P}-view; opacity: 0; }}
.{P} .jump {{ animation-name: {P}-jump; }}
.{P} .row2 {{ animation-name: {P}-row2; opacity: 0; }}
.{P} .row3 {{ animation-name: {P}-row3; }}
.{P} .t0 {{ animation-name: {P}-t0; opacity: 0; }} .{P} .t2 {{ animation-name: {P}-t2; opacity: 0; }} .{P} .t3 {{ animation-name: {P}-t3; }}
.{P} .click {{ animation-name: {P}-click; }}
""" + "".join(f".{P} .s{i} {{ animation-name: {P}-s{i}; }}\n" for i in (1, 2, 3)) \
    + kit.keyframes(f"{P}-cursor", clock.path([(0, HOME), (0.6, HOME), (1.6, COMBO), (2.0, COMBO), (2.6, JUMP), (3.0, JUMP), (4.2, ROW2),
                                               (6.4, ROW2), (7.4, ROW3), (12.4, ROW3), (T, HOME)], lambda t: "opacity: 1;")) \
    + kit.keyframes(f"{P}-v0", clock.hidden((PICK2 + 0.1, RESET + 0.2))) + kit.keyframes(f"{P}-v2", clock.shown((PICK2 + 0.2, PICK3 + 0.1))) \
    + kit.keyframes(f"{P}-v3", clock.shown((PICK3 + 0.2, RESET))) \
    + kit.keyframes(f"{P}-menu", clock.shown((CLICK_COMBO + 0.05, CLICK_JUMP), fade=0.15)) \
    + kit.keyframes(f"{P}-view", clock.hidden((CLICK_JUMP, RESET), fade=0.15)) \
    + kit.keyframes(f"{P}-jump", clock.shown((CLICK_JUMP + 0.1, RESET))) \
    + kit.keyframes(f"{P}-row2", clock.shown((PICK2, PICK3), fade=0.15)) + kit.keyframes(f"{P}-row3", clock.shown((PICK3, RESET), fade=0.15)) \
    + kit.keyframes(f"{P}-t0", clock.hidden((PICK2 + 0.3, RESET + 0.3))) + kit.keyframes(f"{P}-t2", clock.shown((PICK2 + 0.5, PICK3 + 0.2))) \
    + kit.keyframes(f"{P}-t3", clock.shown((PICK3 + 0.5, RESET + 0.1))) \
    + kit.keyframes(f"{P}-click", [])   # replaced below: one ring element per click


def content(signals: dict, cls: str, event) -> str:
    """One plot's curves and event bands as seen in one view. Each view is drawn in place and the views
    are cross-faded: panning one drawing behind a clip-path is misdrawn by Qt's SVG renderer."""
    left, right = window_of(event)
    scale = W / (right - left)
    def trace(name, color):
        f, pts = kit.SIGNALS[name], []
        for i in range(121):
            u = (left + i / 120 * (right - left) - 8) / (W - 16)
            if 0 <= u <= 1:
                pts.append(f"{i / 120 * W:.1f},{50 - f(u) * 50 * 0.8:.1f}")
        return kit.trace(" ".join(pts), color, "solid")
    def band(x, width):
        x0, x1 = max(0.0, (x - left) * scale), min(float(W), (x + width - left) * scale)
        if x1 <= 0 or x0 >= W:
            return ""
        edges = "".join(f"M{e:.1f} 0 v100 " for e in (x0, x1) if 0 < e < W)
        return (f'<rect x="{x0:.1f}" width="{x1 - x0:.1f}" height="100" fill="var(--c4)" opacity=".22"/>'
                f'<path d="{edges}" stroke="var(--c4)" stroke-width="1.5" fill="none"/>')
    return f'<g class="{cls} a">{"".join(trace(n, c) for n, c in signals.items())}{"".join(band(x, w) for x, w, _ in EVENTS)}</g>'


def plot(y: float, signals: dict) -> str:
    views = "".join(content(signals, cls, event) for cls, event in VIEWS.items())
    return f'<g transform="translate({PX} {y})">{views}<rect width="{W}" height="100" rx="3" fill="none" stroke="var(--line)"/></g>'


RINGS = [("k0", CLICK_COMBO, (542, 341)), ("k1", CLICK_JUMP, (540, 297)), ("k2", PICK2, (146, ROW_Y[1] - 4)), ("k3", PICK3, (146, ROW_Y[2] - 4))]
STYLE = STYLE.replace(kit.keyframes(f"{P}-click", []), "") \
    + "".join(f".{P} .{name} {{ animation-name: {P}-{name}; }}\n" + kit.keyframes(f"{P}-{name}", clock.pulse(when)) for name, when, _ in RINGS) \
    + kit.keyframes(f"{P}-s1", clock.lit((0.5, 3.2))) \
    + kit.keyframes(f"{P}-s2", clock.lit((3.5, PICK2), (6.6, PICK3))) \
    + kit.keyframes(f"{P}-s3", clock.lit((PICK2 + 0.3, 6.3), (PICK3 + 0.3, RESET - 0.2)))

DOT = '<circle cx="{x}" cy="{y}" r="4" fill="var(--c4)"/>'
EVENT_ROWS = "".join(DOT.format(x=70, y=y - 4) + f'<text x="82" y="{y}" class="small">2019-03-01 {start}</text>' for y, (_, _, start) in zip(ROW_Y, EVENTS))
ROWS = (kit.tree_row(106, 0, "My Catalogs", "open") + '<rect x="55" y="118" width="180" height="24" rx="6" fill="var(--accent-soft)"/>'
        + DOT.format(x=84, y=130) + kit.tree_row(134, 1, "MMS crossings") + kit.tree_row(162, 1, "Flux ropes", cls="dim")
        + '<line x1="57" y1="196" x2="233" y2="196" stroke="var(--line)"/>'
        + '<text x="62" y="222" class="small dim">Start (UTC)</text>'
        + f'<rect class="row2 a" x="55" y="{ROW_Y[1] - 16}" width="180" height="24" rx="6" fill="var(--accent-soft)"/>'
        + EVENT_ROWS)

PILL = ('<rect x="262" y="330" width="164" height="22" rx="11" fill="var(--side)" stroke="var(--line)"/>'
        + "".join(f'<text x="274" y="345" class="small dim {cls} a">{start} UTC</text><text x="418" y="345" text-anchor="end" class="small {cls} a">{length}</text>'
                  for cls, start, length in (("t0", "2019-03-01 12:00", "3h"), ("t2", "2019-03-01 13:12", "44m"), ("t3", "2019-03-01 14:18", "23m"))))

BODY = f"""{kit.window(P, active="catalogue")}
{kit.panel_frame(x=252, title_x=258)}
{plot(104, {"bx": "c1", "by": "c2", "bz": "c3"})}
{plot(214, {"density": "c3"})}
{PILL}
<text x="436" y="345" class="small dim">Catalog mode:</text>
{kit.combo(510, 66, "View", "view a")}
<text x="519" y="345" class="small jump a">Jump</text>
<g class="jump a"><text x="584" y="345" class="small dim">Zoom out:</text>
  <rect x="636" y="330" width="46" height="22" rx="6" fill="var(--win)" stroke="var(--line)"/><text x="645" y="345" class="small">×2.0</text></g>
{kit.pane("Catalogs", ROWS, hot_y=ROW_Y[2], hot_class="row3 a")}
{kit.popup(510, 252, 72, ["View", "Jump", "Edit"], hot=1, cls="menu a")}
{"".join(kit.ring(name, *xy) for name, _, xy in RINGS)}
{kit.CURSOR}
{kit.step(58, 1, "Set Catalog mode to Jump", "s1")}
{kit.step(270, 2, "Pick an event in the list", "s2")}
{kit.step(480, 3, "The panel goes to that event", "s3")}"""

SVG = kit.svg(P, "With the panel's Catalog mode on Jump, picking an event in the Catalogs pane's list moves the panel to that event, "
              "which fills half of it with the zoom-out factor at 2.", STYLE, BODY)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "jump-to-an-event.svg").write_text(SVG)
print(len(SVG))
