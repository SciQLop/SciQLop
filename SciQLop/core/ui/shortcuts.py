"""Display text for keyboard shortcuts using each platform's real key names.

Qt swaps the Ctrl and Cmd modifiers on macOS: a QKeySequence written as
"Ctrl+K" fires on Cmd+K there, not on the physical Control key macOS
keyboards also have. Showing the literal word "Ctrl" in that case names a
key the user isn't meant to press.
"""
import sys

from PySide6.QtGui import QKeySequence

__all__ = ["native_shortcut_text", "modifier_key_name"]


def native_shortcut_text(shortcut: str) -> str:
    """Render a portable QKeySequence string with the platform's real key names."""
    return QKeySequence(shortcut).toString(QKeySequence.SequenceFormat.NativeText)


def modifier_key_name() -> str:
    """Name of Qt's primary shortcut modifier for use in prose (e.g. "Ctrl+scroll"):
    Cmd on macOS, Ctrl elsewhere."""
    return "Cmd" if sys.platform == "darwin" else "Ctrl"
