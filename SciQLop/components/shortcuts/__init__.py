from .registry import (
    KeyboardShortcutsSettings, Shortcut, add_shortcut, bind_shortcut, bind_tooltip, conflicts,
    key_for, on_shortcut_changed, on_shortcuts_changed, register_shortcut, registered_shortcuts,
    shortcut_text,
)
# Registers the "shortcuts" settings widget used by KeyboardShortcutsSettings.
from . import ui  # noqa: E402,F401
