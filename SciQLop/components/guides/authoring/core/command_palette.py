"""Guide: run any command from the command palette (Ctrl+K).

    python -m SciQLop.components.guides.authoring.core.command_palette OUT_DIR      -> OUT_DIR/command-palette.svg

Verified in the code: Ctrl+K opens the palette (shortcuts/registry.py), drawn over the top of the window
(palette_widget.py). Typing filters the commands; a row shows the name, the description and "Command" or
"Recent" on the right; Enter runs the first row. "New plot panel" opens an empty panel (commands.py).
Which other rows show depends on the history and on other commands' keywords: they are drawn as plain bars.
"""
import sys
from pathlib import Path

from SciQLop.components.guides.authoring import kit

P, T = "sqp", 12.0
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
clock = kit.Clock(T)
OPEN, TYPED, ENTER, RESET = 1.4, (2.5, 2.9, 3.4), 5.0, 11.2
X, Y, W = 196, 70, 360
TYPING = ("n", "new", "new pa")

STYLE = kit.base_style(P, f"{T:g}s") + f"""
/* Resting state = the result: a second, empty panel. */
.{P} .palette {{ animation-name: {P}-palette; opacity: 0; }}
.{P} .hint {{ animation-name: {P}-hint; }}
.{P} .bars {{ animation-name: {P}-bars; }}
.{P} .hit {{ animation-name: {P}-hit; }}
.{P} .ctrlk {{ animation-name: {P}-ctrlk; opacity: 0; }}
.{P} .enter {{ animation-name: {P}-enter; opacity: 0; }}
.{P} .old {{ animation-name: {P}-old; opacity: 0; }}
.{P} .new {{ animation-name: {P}-new; }}
""" + "".join(f".{P} .t{i} {{ animation-name: {P}-t{i}; opacity: 0; }}\n" for i in range(len(TYPING))) \
    + "".join(f".{P} .{n} {{ animation-name: {P}-{n}; }}\n" for n in ("s1", "s2", "s3")) \
    + kit.keyframes(f"{P}-palette", clock.shown((OPEN, ENTER + 0.2), fade=0.2)) \
    + kit.keyframes(f"{P}-hint", clock.hidden((TYPED[0], RESET), fade=0.05)) \
    + kit.keyframes(f"{P}-bars", clock.hidden((TYPED[0], RESET), fade=0.15)) \
    + kit.keyframes(f"{P}-hit", clock.shown((TYPED[0] + 0.1, RESET), fade=0.15)) \
    + "".join(kit.keyframes(f"{P}-t{i}", clock.shown((start, (TYPED + (ENTER + 0.2,))[i + 1] - 0.05), fade=0.05))
              for i, start in enumerate(TYPED)) \
    + kit.keyframes(f"{P}-ctrlk", clock.shown((OPEN - 0.5, OPEN + 0.5), fade=0.2)) \
    + kit.keyframes(f"{P}-enter", clock.shown((ENTER - 0.4, ENTER + 0.5), fade=0.2)) \
    + kit.keyframes(f"{P}-old", clock.hidden((ENTER + 0.3, RESET), fade=0.3)) \
    + kit.keyframes(f"{P}-new", clock.shown((ENTER + 0.3, RESET), fade=0.3)) \
    + kit.keyframes(f"{P}-s1", clock.lit((0.6, 2.2))) + kit.keyframes(f"{P}-s2", clock.lit((2.3, 4.4))) \
    + kit.keyframes(f"{P}-s3", clock.lit((4.6, RESET - 0.3)))

BARS = "".join(f'<rect x="{X + 12}" y="{Y + 48 + 28 * i}" width="{w}" height="8" rx="4" fill="var(--line)"/>'
               for i, w in enumerate((150, 210, 120, 180)))
HIT = (f'<rect x="{X + 4}" y="{Y + 38}" width="{W - 8}" height="26" rx="5" fill="var(--accent-soft)"/>'
       f'<text x="{X + 12}" y="{Y + 55}" class="small" style="font-weight:600">{kit.ui("New plot panel")}</text>'
       f'<text x="{X + 104}" y="{Y + 55}" class="small dim">{kit.ui("Create a new plot panel")}</text>'
       f'<text x="{X + W - 12}" y="{Y + 55}" text-anchor="end" class="small dim">{kit.ui("Command")}</text>'
       + "".join(f'<rect x="{X + 12}" y="{Y + 76 + 28 * i}" width="{w}" height="8" rx="4" fill="var(--line)"/>' for i, w in enumerate((190, 140))))
PALETTE = (f'<g class="palette a"><rect x="{X}" y="{Y + 3}" width="{W}" height="150" rx="10" fill="var(--shadow)"/>'
           f'<rect x="{X}" y="{Y}" width="{W}" height="150" rx="10" fill="var(--win)" stroke="var(--line)"/>'
           f'<rect x="{X + 8}" y="{Y + 7}" width="{W - 16}" height="26" rx="6" fill="var(--side)" stroke="var(--accent)" stroke-width="1.5"/>'
           f'<text x="{X + 18}" y="{Y + 24}" class="small dim hint a">{kit.ui("Search commands...")}</text>'
           + "".join(f'<text x="{X + 18}" y="{Y + 24}" class="small t{i} a">{text}</text>' for i, text in enumerate(TYPING))
           + f'<g class="bars a">{BARS}</g><g class="hit a">{HIT}</g></g>')

BODY = f"""{kit.window(P)}
<text x="66" y="78" class="title">Panel 1</text>
<line class="old a" x1="66" y1="84" x2="112" y2="84" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/>
<g class="new a"><text x="124" y="78" class="title">Panel 2</text>
  <line x1="124" y1="84" x2="170" y2="84" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/></g>
<rect x="60" y="96" width="624" height="226" rx="10" fill="none" stroke="var(--line)"/>
<g class="old a">{kit.static_plot(76, 104, 592, {"bx": "c1", "by": "c2", "bz": "c3"})}{kit.static_plot(76, 214, 592, {"density": "c3"})}</g>
<g class="new a"><rect x="76" y="112" width="592" height="194" rx="8" fill="none" stroke="var(--dim)" stroke-width="1.2" stroke-dasharray="5 5"/>
  <text x="372" y="214" text-anchor="middle" class="dim" style="font-size:13px">{kit.ui("Add a product to this panel")}</text></g>
{kit.time_pill(474)}
{PALETTE}
<g transform="translate({X + W - 8} {Y - 14})">{kit.keycap("Ctrl+K", cls="ctrlk a")}</g>
<g transform="translate({X + W - 8} {Y + 18})">{kit.keycap("Enter", cls="enter a")}</g>
{kit.step(58, 1, "Press Ctrl+K", "s1")}
{kit.step(230, 2, "Type a few letters", "s2")}
{kit.step(430, 3, "Press Enter to run the command", "s3")}"""

SVG = kit.svg(P, "Press Ctrl+K (Cmd+K on macOS) to open the command palette, type a few letters of what you want, "
              "such as new pa, and press Enter: New plot panel opens an empty panel.", STYLE, BODY)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "command-palette.svg").write_text(SVG)
print(len(SVG))
