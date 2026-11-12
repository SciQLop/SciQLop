"""The kit that draws gesture guides in SciQLop's style: colours, window chrome, side strip, tree pane,
cursor, click ring, step row, keyframe helper and the host page.

Every guide passes its own prefix `p` (e.g. "sqd"): class and keyframe names carry it, because
several guides are inlined in one page and an SVG's <style> is global there.
"""
import math

LIGHT = "--win:#ffffff;--bar:#ebebed;--side:#f4f4f6;--line:#d5d5da;--fg:#2f2f33;--dim:#77777f;--accent:#3584e4;--accent-soft:#3584e422;--on-accent:#ffffff;--c1:#1c71d8;--c2:#e66100;--c3:#26a269;--c4:#9141ac;--shadow:#00000022;"
DARK = "--win:#27272b;--bar:#34343a;--side:#2e2e33;--line:#4a4a52;--fg:#f1f1f3;--dim:#a3a3ad;--accent:#78aeed;--accent-soft:#78aeed2e;--on-accent:#14141a;--c1:#78aeed;--c2:#ffa348;--c3:#57e389;--c4:#dc8add;--shadow:#00000066;"

# SciQLop's own icons (Material icons, as shipped with SciQLopPlots): 24 x 24 path data.
ICON_PATHS = {
    "tree": ['M22 11V3h-7v3H9V3H2v8h7V8h2v10h4v3h7v-8h-7v3h-2V8h2v3z'],
    "catalogue": ['M21,5c-1.11-0.35-2.33-0.5-3.5-0.5c-1.95,0-4.05,0.4-5.5,1.5c-1.45-1.1-3.55-1.5-5.5-1.5S2.45,4.9,1,6v14.65 c0,0.25,0.25,0.5,0.5,0.5c0.1,0,0.15-0.05,0.25-0.05C3.1,20.45,5.05,20,6.5,20c1.95,0,4.05,0.4,5.5,1.5c1.35-0.85,3.8-1.5,5.5-1.5 c1.65,0,3.35,0.3,4.75,1.05c0.1,0.05,0.15,0.05,0.25,0.05c0.25,0,0.5-0.25,0.5-0.5V6C22.4,5.55,21.75,5.25,21,5z M21,18.5 c-1.1-0.35-2.3-0.5-3.5-0.5c-1.7,0-4.15,0.65-5.5,1.5V8c1.35-0.85,3.8-1.5,5.5-1.5c1.2,0,2.4,0.15,3.5,0.5V18.5z', 'M17.5,10.5c0.88,0,1.73,0.09,2.5,0.26V9.24C19.21,9.09,18.36,9,17.5,9c-1.7,0-3.24,0.29-4.5,0.83v1.66 C14.13,10.85,15.7,10.5,17.5,10.5z', 'M13,12.49v1.66c1.13-0.64,2.7-0.99,4.5-0.99c0.88,0,1.73,0.09,2.5,0.26V11.9c-0.79-0.15-1.64-0.24-2.5-0.24 C15.8,11.66,14.26,11.96,13,12.49z', 'M17.5,14.33c-1.7,0-3.24,0.29-4.5,0.83v1.66c1.13-0.64,2.7-0.99,4.5-0.99c0.88,0,1.73,0.09,2.5,0.26v-1.52 C19.21,14.41,18.36,14.33,17.5,14.33z'],
    "settings": ['M19.14,12.94c0.04-0.3,0.06-0.61,0.06-0.94c0-0.32-0.02-0.64-0.07-0.94l2.03-1.58c0.18-0.14,0.23-0.41,0.12-0.61 l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39,0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4,2.81c-0.04-0.24-0.24-0.41-0.48-0.41 h-3.84c-0.24,0-0.43,0.17-0.47,0.41L9.25,5.35C8.66,5.59,8.12,5.92,7.63,6.29L5.24,5.33c-0.22-0.08-0.47,0-0.59,0.22L2.74,8.87 C2.62,9.08,2.66,9.34,2.86,9.48l2.03,1.58C4.84,11.36,4.8,11.69,4.8,12s0.02,0.64,0.07,0.94l-2.03,1.58 c-0.18,0.14-0.23,0.41-0.12,0.61l1.92,3.32c0.12,0.22,0.37,0.29,0.59,0.22l2.39-0.96c0.5,0.38,1.03,0.7,1.62,0.94l0.36,2.54 c0.05,0.24,0.24,0.41,0.48,0.41h3.84c0.24,0,0.44-0.17,0.47-0.41l0.36-2.54c0.59-0.24,1.13-0.56,1.62-0.94l2.39,0.96 c0.22,0.08,0.47,0,0.59-0.22l1.92-3.32c0.12-0.22,0.07-0.47-0.12-0.61L19.14,12.94z M12,15.6c-1.98,0-3.6-1.62-3.6-3.6 s1.62-3.6,3.6-3.6s3.6,1.62,3.6,3.6S13.98,15.6,12,15.6z'],
    "plot_properties": ['M14.06,9.94L12,9l2.06-0.94L15,6l0.94,2.06L18,9l-2.06,0.94L15,12L14.06,9.94z M4,14l0.94-2.06L7,11l-2.06-0.94L4,8 l-0.94,2.06L1,11l2.06,0.94L4,14z M8.5,9l1.09-2.41L12,5.5L9.59,4.41L8.5,2L7.41,4.41L5,5.5l2.41,1.09L8.5,9z M4.5,20.5l6-6.01l4,4 L23,8.93l-1.41-1.41l-7.09,7.97l-4-4L3,19L4.5,20.5z'],
    "add_graph": ['M6 9.99h2v7H6zm8 3h2v4h-2zm-4-6h2v10h-2zM20 7V4h-2v3h-3v2h3v3h2V9h3V7zm-2 12H4V5h12V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-5h-2v5z'],
}
STRIP = ("tree", "catalogue", "settings", "plot_properties")


def base_style(p: str, duration: str) -> str:
    """Tokens and the rules every guide shares. Animated elements carry class "a"."""
    return f"""
.{p} {{ {LIGHT} font-family: "Adwaita Sans", Inter, Cantarell, system-ui, sans-serif; }}
@media (prefers-color-scheme: dark) {{ .{p} {{ {DARK} }} }}
.{p} text {{ fill: var(--fg); font-size: 12px; }}
.{p} .dim {{ fill: var(--dim); }}
.{p} .small {{ font-size: 10.5px; }}
.{p} .title {{ font-weight: 700; font-size: 12.5px; }}
.{p} .step text {{ font-size: 12.5px; font-weight: 600; }}
.{p} .a {{ animation-duration: {duration}; animation-iteration-count: infinite; animation-timing-function: ease-in-out; }}
.{p} .trace {{ fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; stroke-dasharray: 1; stroke-dashoffset: 0; vector-effect: non-scaling-stroke; }}
/* A plain curve, for groups the animation stretches or cross-fades: the dash trick misbehaves there. */
.{p} .curve {{ fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; vector-effect: non-scaling-stroke; }}
.{p} .ring {{ transform-box: fill-box; transform-origin: center; opacity: 0; }}
@media (prefers-reduced-motion: reduce) {{ .{p} .a {{ animation: none; }} }}
"""


def keyframes(name: str, stops: list[tuple[float, str]]) -> str:
    """`stops` are (percent of the loop, css declarations), in order."""
    body = " ".join(f"{max(0.0, min(100.0, pct)):.2f}% {{ {css} }}" for pct, css in stops)
    return f"@keyframes {name} {{ {body} }}\n"


class Clock:
    """Keyframe stops written in seconds of a loop that lasts `duration` seconds."""

    def __init__(self, duration: float):
        self.duration = duration

    def at(self, seconds: float) -> float:
        return seconds / self.duration * 100

    def path(self, waypoints, extra=lambda seconds: "") -> list:
        """(seconds, (x, y)) waypoints as translate stops; `extra(seconds)` adds declarations (e.g. opacity)."""
        return [(self.at(t), f"transform: translate({x}px, {y}px);" + extra(t)) for t, (x, y) in waypoints]

    def pulse(self, *moments: float) -> list:
        """A click ring that grows and fades at each moment."""
        stops = []
        for when in moments:
            stops += [(self.at(when - 0.02), "transform: scale(.3); opacity: 0;"), (self.at(when), "transform: scale(.3); opacity: .9;"),
                      (self.at(when + 0.6), "transform: scale(1.5); opacity: 0;")]
        return stops + [(100, "transform: scale(1.5); opacity: 0;")]

    def levels(self, intervals, on: str, off: str, fade: float = 0.3, rest: str | None = None) -> list:
        """`on` during each (start, end) interval, `off` elsewhere; `rest` is the value at both ends of the loop."""
        rest = off if rest is None else rest
        stops = [(0, rest)]
        for start, end in intervals:
            stops += [(self.at(start), off), (self.at(start + fade), on), (self.at(end), on), (self.at(end + fade), off)]
        return stops + [(100, rest)]

    def shown(self, *intervals, fade: float = 0.3) -> list:
        return self.levels(intervals, "opacity: 1;", "opacity: 0;", fade)

    def hidden(self, *intervals, fade: float = 0.3) -> list:
        return self.levels(intervals, "opacity: 0;", "opacity: 1;", fade)

    def lit(self, *intervals) -> list:
        """A step label: bright while its step happens."""
        return self.levels(intervals, "opacity: 1;", "opacity: .4;")


def icon(name: str, y: float, fill: str, x: float = 26) -> str:
    """One of ICON_PATHS at 16 px. A plugin's own icon: add its 24 x 24 path data to ICON_PATHS first."""
    body = "".join(f'<path d="{d}"/>' for d in ICON_PATHS[name])
    return f'<g transform="translate({x} {y}) scale(0.6667)" fill="{fill}">{body}</g>'


def strip(active: str | None = None, tab_class: str = "") -> str:
    """The left strip and its icons. `active` names the icon drawn as selected; `tab_class` lets a
    guide animate that selection. Draw it again after a pane that slides in, so the pane passes under it."""
    icons, y = "", 65
    for name in STRIP:
        icons += icon(name, y, "var(--fg)" if name == active else "var(--dim)")
        if name == active:
            icons = f'<rect class="{tab_class}" x="23" y="{y - 3}" width="22" height="22" rx="6" fill="var(--accent-soft)"/>' + icons
        y += 28
    return ('<path d="M21 55 H48 V359 H34 a13 13 0 0 1 -13 -13 Z" fill="var(--side)"/>'
            f'<line x1="48" y1="54" x2="48" y2="360" stroke="var(--line)"/>{icons}')


def pane_slide(clock, open_at: float, close_at: float) -> list:
    """Keyframe stops for a pane that opens at `open_at` and closes at `close_at` (seconds): a fade with
    a short slide. No clip-path: Qt's SVG renderer misdraws an animated group inside one."""
    shut, opened = "transform: translate(-28px, 0px); opacity: 0;", "transform: translate(0px, 0px); opacity: 1;"
    return [(0, shut), (clock.at(open_at), shut), (clock.at(open_at + 0.7), opened), (clock.at(close_at), opened),
            (clock.at(close_at + 0.5), shut), (100, shut)]


def window(p: str, active: str | None = None, tab_class: str = "") -> str:
    """Frame, header bar and the left strip (see `strip`)."""
    icons = strip(active, tab_class)
    return f"""<defs>
  <clipPath id="{p}-win"><rect x="20" y="16" width="680" height="344" rx="14"/></clipPath>
  <clipPath id="{p}-body"><path d="M49 55 H700 V346 a14 14 0 0 1 -14 14 H49 Z"/></clipPath>
</defs>
<rect x="20" y="19" width="680" height="344" rx="14" fill="var(--shadow)"/>
<g clip-path="url(#{p}-win)">
  <rect x="20" y="16" width="680" height="344" fill="var(--win)"/>
  <rect x="20" y="16" width="680" height="38" fill="var(--bar)"/>
  <line x1="20" y1="54" x2="700" y2="54" stroke="var(--line)"/>
</g>
<rect x="20" y="16" width="680" height="344" rx="14" fill="none" stroke="var(--line)"/>
<text x="360" y="40" text-anchor="middle" class="title">SciQLop</text>
<circle cx="678" cy="35" r="8" fill="var(--line)"/>
<path d="M674.5 31.5 l7 7 M681.5 31.5 l-7 7" stroke="var(--fg)" stroke-width="1.4" stroke-linecap="round"/>
{icons}"""


def tree_row(y: float, depth: int, text: str, arrow: str | None = None, cls: str = "") -> str:
    x = 62 + depth * 16
    tri = {"open": f'<path d="M{x} {y-7} l8 0 l-4 6 z" fill="var(--dim)"/>',
           "closed": f'<path d="M{x+1} {y-9} l6 4 l-6 4 z" fill="var(--dim)"/>'}.get(arrow, "")
    return f'{tri}<text x="{x+14}" y="{y}" class="{cls}">{text}</text>'


def products_pane(rows: str, hot_y: float, pane_class: str = "", hot_class: str = "rowhot a") -> str:
    return pane("Products", rows, hot_y, pane_class, hot_class)


def pane(title: str, rows: str, hot_y: float, pane_class: str = "", hot_class: str = "rowhot a") -> str:
    """A side pane, open over the panel area (x 49..241). Rows come from tree_row().
    When `pane_class` slides it in (see `pane_slide`), draw `strip()` again after it."""
    return f"""<g class="{pane_class}">
  <rect x="49" y="55" width="196" height="306" fill="var(--shadow)"/>
  <rect x="49" y="55" width="192" height="306" fill="var(--side)"/>
  <line x1="241" y1="55" x2="241" y2="361" stroke="var(--line)"/>
  <text x="62" y="78" class="title">{title}</text>
  <rect class="{hot_class}" x="55" y="{hot_y - 16}" width="180" height="24" rx="6" fill="var(--accent-soft)"/>
  {rows}
</g>"""


def curve(f, width: float, height: float = 100, amplitude: float = 0.8, n: int = 60) -> str:
    """Points of y = f(u), u in 0..1, f in -1..1, inside a local width x height plot box.
    Raise `n` when the plot is zoomed in by the animation."""
    return " ".join(f"{i / n * (width - 16) + 8:.1f},{height / 2 - f(i / n) * height / 2 * amplitude:.1f}" for i in range(n + 1))


_wob = lambda u, k, ph: 0.05 * math.sin(k * u * math.tau + ph)
# A magnetopause-like crossing: Bx reverses, By bumps, Bz reverses the other way; density steps up; |B| dips.
SIGNALS = {
    "bx": lambda u: 0.75 * math.tanh((u - 0.5) * 9) + _wob(u, 7, 0.3),
    "by": lambda u: 0.55 * math.exp(-((u - 0.5) / 0.13) ** 2) - 0.2 + _wob(u, 9, 1.1),
    "bz": lambda u: -0.6 * math.tanh((u - 0.52) * 7) + 0.1 + _wob(u, 6, 2.0),
    "density": lambda u: 0.5 / (1 + math.exp(-(u - 0.5) * 14)) - 0.35 + _wob(u, 11, 0.7) + 0.5 * _wob(u, 23, 2),
    "bmag": lambda u: 0.55 - 0.5 * math.exp(-((u - 0.5) / 0.1) ** 2) + _wob(u, 8, 1.6),
}


def trace(points: str, color: str, cls: str = "") -> str:
    """A curve. With "solid" in `cls` it is a plain line; otherwise it can draw itself (the dash trick)."""
    if "solid" in cls.split():
        return f'<polyline class="curve {cls}" stroke="var(--{color})" points="{points}"/>'
    return f'<polyline class="trace {cls}" pathLength="1" stroke="var(--{color})" points="{points}"/>'


def static_plot(x: float, y: float, width: float, signals: dict[str, str], height: float = 100) -> str:
    """A plot that does not move: frame, zero line and one curve per (signal name -> colour token)."""
    traces = "".join(trace(curve(SIGNALS[name], width, height), color) for name, color in signals.items())
    return (f'<g transform="translate({x} {y})"><rect width="{width}" height="{height}" rx="3" fill="none" stroke="var(--line)"/>'
            f'<line x1="8" y1="{height / 2}" x2="{width - 8}" y2="{height / 2}" stroke="var(--line)" stroke-dasharray="2 4"/>{traces}</g>')


def panel_frame(x: float = 60, title_x: float = 66) -> str:
    """Tab title and outline of "Panel 1"; x=60 when no pane is docked beside it."""
    return (f'<text x="{title_x}" y="78" class="title">Panel 1</text>'
            f'<line x1="{title_x}" y1="84" x2="{title_x + 46}" y2="84" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/>'
            f'<rect x="{x}" y="96" width="{684 - x}" height="226" rx="10" fill="none" stroke="var(--line)"/>')


def time_pill(x: float = 76) -> str:
    """The time range under a panel, simplified to start + duration. In SciQLop this bar comes first
    in the row under the panel; "Catalog mode" and its boxes come after it, to the right."""
    return (f'<rect x="{x}" y="330" width="210" height="22" rx="11" fill="var(--side)" stroke="var(--line)"/>'
            f'<text x="{x + 14}" y="345" class="small dim">2019-03-01 12:00 UTC</text><text x="{x + 168}" y="345" class="small">3h</text>')


TIME_PILL = time_pill(474)   # right-aligned, for guides whose row has nothing else


def span(x: float, width: float, cls: str = "", color: str = "c4", plots=((104, 100), (214, 100))) -> str:
    """A catalog event: a translucent band with two edges on each plot (`plots` = (top, height) pairs)."""
    bands = "".join(f'<rect x="{x}" y="{y}" width="{width}" height="{h}" fill="var(--{color})" opacity=".22"/>'
                    f'<path d="M{x} {y} v{h} M{x + width} {y} v{h}" stroke="var(--{color})" stroke-width="1.5"/>' for y, h in plots)
    return f'<g class="{cls}">{bands}</g>'


def combo(x: float, width: float, label: str, label_class: str = "", y: float = 330) -> str:
    """A combo box of the row under the panel (Catalog mode, Add to)."""
    return (f'<rect x="{x}" y="{y}" width="{width}" height="22" rx="6" fill="var(--win)" stroke="var(--line)"/>'
            f'<text x="{x + 9}" y="{y + 15}" class="small {label_class}">{label}</text>'
            f'<path d="M{x + width - 15} {y + 9} l4 4 l4 -4" fill="none" stroke="var(--dim)" stroke-width="1.3"/>')


def popup(x: float, y: float, width: float, rows: list[str], hot: int | None = None, cls: str = "", dim: tuple = ()) -> str:
    """A pop-up list or context menu; `hot` is the highlighted row, `dim` the greyed-out rows.
    Row i's text baseline is at y + 18 + 22 * i."""
    height = 8 + 22 * len(rows)
    hot_rect = "" if hot is None else f'<rect x="{x + 4}" y="{y + 5 + 22 * hot}" width="{width - 8}" height="20" rx="5" fill="var(--accent-soft)"/>'
    texts = "".join(f'<text x="{x + 12}" y="{y + 18 + 22 * i}" class="small{" dim" if i in dim else ""}">{row}</text>' for i, row in enumerate(rows))
    return (f'<g class="{cls}"><rect x="{x}" y="{y + 2}" width="{width}" height="{height}" rx="8" fill="var(--shadow)"/>'
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="8" fill="var(--win)" stroke="var(--line)"/>{hot_rect}{texts}</g>')


def keycap(label: str, cls: str = "") -> str:
    """A held key, shown beside the cursor (give it the cursor's transform keyframes). To place one that
    does not move, wrap it in <g transform="translate(x y)">: Qt ignores a CSS `transform` that is not
    inside keyframes."""
    width = 14 + 7 * len(label)
    return (f'<g class="{cls}"><rect x="16" y="20" width="{width}" height="20" rx="5" fill="var(--win)" stroke="var(--fg)" stroke-width="1.2"/>'
            f'<text x="{16 + width / 2}" y="34" text-anchor="middle" style="font-size:11px;font-weight:600">{label}</text></g>')


def ring(cls: str, cx: float, cy: float) -> str:
    return f'<circle class="ring a {cls}" cx="{cx}" cy="{cy}" r="14" fill="none" stroke="var(--accent)" stroke-width="2"/>'


def ghost(text: str, width: int = 62) -> str:
    """The dragged product, a pill that follows the cursor."""
    return (f'<g class="ghost a"><rect x="10" y="10" width="{width}" height="24" rx="12" fill="var(--accent)"/>'
            f'<text x="{10 + width / 2}" y="26.5" text-anchor="middle" style="fill:var(--on-accent);font-weight:600">{text}</text></g>')


CURSOR = ('<g class="cursor a"><path d="M0 0 L0 17 L4.6 12.8 L7.6 19.6 L10.4 18.4 L7.4 11.6 L13.4 11.6 Z" '
          'fill="var(--fg)" stroke="var(--win)" stroke-width="1.3" stroke-linejoin="round"/></g>')


def step(x: float, n: int, label: str, cls: str) -> str:
    return (f'<g class="step a {cls}"><circle cx="{x}" cy="398" r="10" fill="var(--accent)"/>'
            f'<text x="{x}" y="402.3" text-anchor="middle" style="fill:var(--on-accent);font-size:11.5px;font-weight:700">{n}</text>'
            f'<text x="{x+18}" y="402.3">{label}</text></g>')


def svg(p: str, label: str, style: str, body: str) -> str:
    return (f'<svg class="{p}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 430" role="img" aria-label="{label}">\n'
            f'<style>{style}</style>\n{body}\n</svg>')


def host_page(guides: list[tuple[str, str, str, str]]) -> str:
    """One artifact page for all guides. Each guide: (root class, title, caption, svg text).
    No doctype: the Artifact tool wraps the file."""
    roots = ", ".join(f".{p}" for p, *_ in guides)
    figures = "".join(f"""
  <figure>
    <h2>{title}</h2>
    {text.replace(' xmlns="http://www.w3.org/2000/svg"', "")}
    <div class="bar"><figcaption>{caption}</figcaption><button type="button" aria-pressed="false">Pause</button></div>
  </figure>""" for _, title, caption, text in guides)
    themed = lambda scope, values: "".join(f'{scope} .{p} {{ {values} }}\n' for p, *_ in guides)
    return f"""<title>SciQLop gesture guides</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">
<style>
/* Layout: one centred column; each guide is a figure, the animation is the page. */
:root {{ --bg:#f6f6f8; --fg:#2f2f33; --dim:#6b6b74; --line:#d9d9de; --surface:#ffffff; --accent:#1c71d8; --accent-bg:#3584e41f;
  --font: Inter, "Adwaita Sans", system-ui, sans-serif; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#1c1c1f; --fg:#f1f1f3; --dim:#a3a3ad; --line:#43434a; --surface:#27272b; --accent:#78aeed; --accent-bg:#78aeed2e; color-scheme: dark; }} }}
:root[data-theme="dark"] {{ --bg:#1c1c1f; --fg:#f1f1f3; --dim:#a3a3ad; --line:#43434a; --surface:#27272b; --accent:#78aeed; --accent-bg:#78aeed2e; color-scheme: dark; }}
/* The drawings follow the system theme by themselves; these make them follow the page's theme switch too. */
{themed(':root[data-theme="light"]', LIGHT)}{themed(':root[data-theme="dark"]', DARK)}
body {{ background: var(--bg); color: var(--fg); font-family: var(--font); font-size: 15px; line-height: 1.55; }}
main {{ max-width: 780px; margin: 0 auto; padding-block: 36px 56px; padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); display: flex; flex-direction: column; gap: 40px; }}
h1 {{ font-size: 1.7rem; font-weight: 700; letter-spacing: -0.01em; margin: 0; text-wrap: balance; }}
h2 {{ font-size: 1.15rem; font-weight: 600; margin: 0; }}
p {{ margin: 0; max-width: 65ch; }}
.lede {{ color: var(--dim); }}
figure {{ margin: 0; display: flex; flex-direction: column; gap: 10px; }}
figure svg {{ display: block; width: 100%; height: auto; }}
.bar {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; }}
figcaption {{ color: var(--dim); font-size: .9rem; max-width: 60ch; }}
button {{ font: inherit; font-weight: 500; color: var(--fg); background: var(--surface); border: 1px solid var(--line); border-radius: 999px; padding: 5px 16px; cursor: pointer; }}
button:hover {{ border-color: var(--accent); }}
button:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
figure.paused .a {{ animation-play-state: paused; }}
</style>
<main>
  <header><h1>SciQLop gesture guides</h1><p class="lede">Short loops that each teach one manipulation, with a simplified window. Each guide is one SVG file with no script.</p></header>{figures}
</main>
<script>
document.querySelectorAll("figure button").forEach(function (button) {{
  button.addEventListener("click", function () {{
    var paused = button.closest("figure").classList.toggle("paused");
    button.textContent = paused ? "Play" : "Pause";
    button.setAttribute("aria-pressed", String(paused));
  }});
}});
</script>
"""
