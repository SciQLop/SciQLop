"""Turn a guide's SVG into what Qt's SVG renderer animates, in the colours of the current theme.

Qt plays CSS keyframes since 6.10, but drops the whole animation, silently, when the style sheet
has a CSS variable or an @media block, and paints #rrggbbaa colours as opaque black (seen with
6.11). The guides are written for browsers, which need exactly those: this is the bridge.
"""
import re

from PySide6.QtGui import QColor, QPalette

_MEDIA_BLOCK = re.compile(r"@media [^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}\n?")
_VARIABLE_DECLARATION = re.compile(r"--[\w-]+:[^;}]+;")
_VARIABLE_USE = re.compile(r"var\((--[\w-]+)\)")
_TRANSLUCENT_PAINT = re.compile(r'(fill|stroke)="#([0-9a-fA-F]{6})([0-9a-fA-F]{2})"')

# Curve colours: the palette has no roles for them.
_CURVES_ON_LIGHT = {"--c1": "#1c71d8", "--c2": "#e66100", "--c3": "#26a269", "--c4": "#9141ac"}
_CURVES_ON_DARK = {"--c1": "#78aeed", "--c2": "#ffa348", "--c3": "#57e389", "--c4": "#dc8add"}


def _with_alpha(color: QColor, alpha: float) -> str:
    return f"{color.name()}{round(alpha * 255):02x}"


def palette_tokens(palette: QPalette) -> dict[str, str]:
    """The guides' colour tokens, taken from `palette`."""
    role = lambda r: palette.color(QPalette.ColorGroup.Active, r)
    base, accent = role(QPalette.ColorRole.Base), role(QPalette.ColorRole.Highlight)
    dark = base.lightnessF() < 0.5
    return {
        "--win": base.name(), "--bar": role(QPalette.ColorRole.Window).name(),
        "--side": role(QPalette.ColorRole.AlternateBase).name(), "--line": role(QPalette.ColorRole.Mid).name(),
        "--fg": role(QPalette.ColorRole.Text).name(), "--dim": role(QPalette.ColorRole.PlaceholderText).name(),
        "--accent": accent.name(), "--on-accent": role(QPalette.ColorRole.HighlightedText).name(),
        "--accent-soft": _with_alpha(accent, 0.18), "--shadow": _with_alpha(QColor("black"), 0.4 if dark else 0.13),
        **(_CURVES_ON_DARK if dark else _CURVES_ON_LIGHT),
    }


def _split_alpha(match: re.Match) -> str:
    attribute, rgb, alpha = match.groups()
    return f'{attribute}="#{rgb}" {attribute}-opacity="{int(alpha, 16) / 255:.3f}"'


def for_qt(svg: str, tokens: dict[str, str]) -> str:
    svg = _MEDIA_BLOCK.sub("", svg)
    svg = _VARIABLE_DECLARATION.sub("", svg)
    svg = _VARIABLE_USE.sub(lambda m: tokens[m.group(1)], svg)
    return _TRANSLUCENT_PAINT.sub(_split_alpha, svg)
