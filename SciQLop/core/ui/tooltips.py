from html import escape

from SciQLop.core.ui.shortcuts import native_shortcut_text

__all__ = ["rich_tooltip"]


def rich_tooltip(title: str, body: str = "", shortcut: str = "") -> str:
    """Format a Qt rich-text tooltip: bold title, optional shortcut and body.

    Qt auto-detects HTML in tooltips, so returning tags is sufficient. Inputs
    are HTML-escaped defensively (static literals today, but cheap insurance
    against accidental markup breakage). `shortcut` is a portable QKeySequence
    string (e.g. "Ctrl+K") and is rendered with the platform's real key names.
    """
    html = f"<b>{escape(title)}</b>"
    if shortcut:
        html += f' <span style="color:gray">({escape(native_shortcut_text(shortcut))})</span>'
    if body:
        html += f"<br>{escape(body)}"
    return html
