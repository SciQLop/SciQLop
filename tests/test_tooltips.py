from SciQLop.core.ui.shortcuts import native_shortcut_text
from SciQLop.core.ui.tooltips import rich_tooltip


def test_title_only():
    assert rich_tooltip("New plot panel") == "<b>New plot panel</b>"


def test_title_and_body():
    assert rich_tooltip("New plot panel", "Create an empty panel.") == (
        "<b>New plot panel</b><br>Create an empty panel."
    )


_NATIVE_SHORTCUT = native_shortcut_text("Ctrl+Shift+H")


def test_title_with_shortcut():
    assert rich_tooltip("Crosshair", shortcut="Ctrl+Shift+H") == (
        f'<b>Crosshair</b> <span style="color:gray">({_NATIVE_SHORTCUT})</span>'
    )


def test_title_body_and_shortcut():
    assert rich_tooltip("Crosshair", "Toggle crosshair.", "Ctrl+Shift+H") == (
        f'<b>Crosshair</b> <span style="color:gray">({_NATIVE_SHORTCUT})</span>'
        "<br>Toggle crosshair."
    )


def test_escapes_html_metacharacters():
    assert rich_tooltip("A & B", "x < y > z") == (
        "<b>A &amp; B</b><br>x &lt; y &gt; z"
    )
