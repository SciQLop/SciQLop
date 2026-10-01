"""One place for every keyboard shortcut: its default key, the user's change,
and live rebinding of the QShortcut/QAction that use it."""
from dataclasses import dataclass
from typing import Callable, ClassVar

import shiboken6
from pydantic import Field
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut

from SciQLop.components.settings.backend.entry import ConfigEntry, SettingsCategory
from SciQLop.core.ui.shortcuts import native_shortcut_text
from SciQLop.core.ui.tooltips import rich_tooltip


@dataclass(frozen=True)
class Shortcut:
    id: str
    group: str
    label: str
    default: str
    # Listed in the help panel, but not rebindable (text-editing keys, the
    # platform's standard Delete key).
    fixed: bool = False


_BUILTIN = [
    Shortcut("app.command_palette", "General", "Open the command palette", "Ctrl+K"),
    Shortcut("app.full_screen", "General", "Toggle full screen", "F11"),
    Shortcut("app.shortcuts_help", "General", "Show keyboard shortcuts", "F1"),
    Shortcut("panel.toggle_crosshair", "Plot panel", "Toggle crosshair & hover read-out", "Ctrl+Shift+H"),
    Shortcut("panel.cycle_catalog_mode", "Plot panel", "Cycle catalog mode (View, Jump, Edit)", "Ctrl+Shift+M"),
    Shortcut("panel.autoscale_all", "Plot panel", "Autoscale all plots", "Ctrl+Shift+A"),
    Shortcut("panel.equalize_heights", "Plot panel", "Equalize plot heights", "Ctrl+Shift+E"),
    Shortcut("panel.organize", "Plot panel", "Organize plots", "O"),
    Shortcut("panel.deselect_all", "Plot panel", "Deselect everything", "Escape"),
    Shortcut("plot.autoscale", "Plot", "Autoscale the hovered or selected axis", "M"),
    Shortcut("plot.toggle_log", "Plot", "Toggle log scale of the hovered or selected axis", "L"),
    Shortcut("plot.toggle_selection_visibility", "Plot", "Hide or show the selected graph", "H"),
    Shortcut("catalogs.delete", "Catalogs", "Delete the selected catalog or events", "Del", fixed=True),
    Shortcut("agent.send", "Agent chat", "Send the message", "Ctrl+Return", fixed=True),
    Shortcut("profiling.start", "Profiling", "Start recording a trace", "Ctrl+Alt+P"),
    Shortcut("profiling.stop", "Profiling", "Stop recording and save the trace", "Ctrl+Alt+S"),
    Shortcut("profiling.open_last", "Profiling", "Open the last trace in Perfetto", "Ctrl+Alt+O"),
]

_registry: dict[str, Shortcut] = {s.id: s for s in _BUILTIN}


def register_shortcut(shortcut: Shortcut) -> Shortcut:
    """For plugins: make a shortcut configurable and listed in the help panel."""
    _registry[shortcut.id] = shortcut
    return shortcut


def registered_shortcuts() -> list[Shortcut]:
    return list(_registry.values())


class KeyboardShortcutsSettings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.SHORTCUTS
    subcategory: ClassVar[str] = "general"
    shortcuts: dict[str, str] = Field(
        default_factory=dict,
        description="Click a shortcut and press the new key combination. "
                    "Clear it to disable the shortcut.",
        json_schema_extra={"widget": "shortcuts"})


class _Changes(QObject):
    changed = Signal()


_changes = _Changes()
shortcuts_changed = _changes.changed
_overrides: dict[str, str] | None = None


def _on_settings_changed(name: str, value) -> None:
    global _overrides
    if name == "shortcuts":
        _overrides = dict(value)
        shortcuts_changed.emit()


KeyboardShortcutsSettings._notifier.changed.connect(_on_settings_changed)


def _current_overrides() -> dict[str, str]:
    # Loaded once: per-plot binding would otherwise re-read the YAML per plot.
    global _overrides
    if _overrides is None:
        _overrides = dict(KeyboardShortcutsSettings().shortcuts)
    return _overrides


def key_for(shortcut_id: str, overrides: dict[str, str] | None = None) -> str:
    """The key bound to *shortcut_id*: the user's choice, else the default.
    An empty string means the user disabled it."""
    shortcut = _registry[shortcut_id]
    if shortcut.fixed:
        return shortcut.default
    chosen = _current_overrides() if overrides is None else overrides
    return chosen.get(shortcut_id, shortcut.default)


def shortcut_text(shortcut_id: str) -> str:
    """Key of *shortcut_id* for display in labels, with the platform's key names."""
    return native_shortcut_text(key_for(shortcut_id))


def _normalized(key: str) -> str:
    return QKeySequence(key).toString(QKeySequence.SequenceFormat.PortableText)


def conflicts(overrides: dict[str, str]) -> dict[str, list[str]]:
    """Shortcut ids that share a key with others, given *overrides*."""
    by_key: dict[str, list[str]] = {}
    for shortcut in _registry.values():
        key = _normalized(key_for(shortcut.id, overrides))
        if key and not shortcut.fixed:
            by_key.setdefault(key, []).append(shortcut.id)
    return {sid: [other for other in ids if other != sid]
            for ids in by_key.values() if len(ids) > 1 for sid in ids}


# Why not a per-owner connection to shortcuts_changed: PySide kept those alive
# after a main window's deleteLater() teardown, and they then called into the
# deleted QActions. Owners are checked with shiboken6.isValid instead.
_bindings: list[tuple[QObject, Callable[[QObject], None]]] = []


def _live_bindings() -> list[tuple[QObject, Callable[[QObject], None]]]:
    _bindings[:] = [b for b in _bindings if shiboken6.isValid(b[0])]
    return _bindings


def _refresh_bindings() -> None:
    for owner, refresh in _live_bindings():
        refresh(owner)


shortcuts_changed.connect(_refresh_bindings)


def on_shortcuts_changed(owner: QObject, refresh: Callable[[QObject], None]) -> None:
    """Call ``refresh(owner)`` now and after every shortcut change, for as
    long as *owner*'s C++ object lives."""
    refresh(owner)
    _live_bindings().append((owner, refresh))


def on_shortcut_changed(owner: QObject, shortcut_id: str, apply: Callable[[QObject, str], None]) -> None:
    on_shortcuts_changed(owner, lambda o: apply(o, key_for(shortcut_id)))


def _set_key(target: QShortcut | QAction, key: str) -> None:
    if isinstance(target, QAction):
        target.setShortcut(QKeySequence(key))
    else:
        target.setKey(QKeySequence(key))


def bind_shortcut(target: QShortcut | QAction, shortcut_id: str) -> None:
    on_shortcut_changed(target, shortcut_id, _set_key)


def add_shortcut(parent, shortcut_id: str, slot: Callable,
                 context=Qt.ShortcutContext.WidgetWithChildrenShortcut) -> QShortcut:
    shortcut = QShortcut(parent)
    shortcut.setContext(context)
    shortcut.activated.connect(slot)
    bind_shortcut(shortcut, shortcut_id)
    return shortcut


def bind_tooltip(widget, shortcut_id: str, title: str, body: str = "") -> None:
    on_shortcut_changed(widget, shortcut_id,
                        lambda owner, key: owner.setToolTip(rich_tooltip(title, body, key)))
