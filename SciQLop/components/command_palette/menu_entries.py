"""Append the sciqlop.menus entries of one location to a QMenu."""
from SciQLop.components.command_palette.backend.registry import COMMANDS
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.menus import MENUS

log = getLogger(__name__)

# Marks actions made here, so the menu-bar harvest does not turn them into duplicate palette commands.
MENU_ENTRY_PROPERTY = "sciqlop_menu_entry"


def _shown(entry, context) -> bool:
    # simplify: problems are logged on every menu build, not once; menus are built on demand so it stays quiet enough.
    if entry.command not in COMMANDS:
        log.warning(f"menu entry {entry.id}: command {entry.command!r} is not registered")
        return False
    try:
        return bool(entry.when(context))
    except Exception as e:
        log.error(f"menu entry {entry.id}: when() failed: {e}")
        return False


def _run(command, context: dict) -> None:
    args = {a.name: context[a.name] for a in command.args if a.name in context}
    try:
        command.callback(**args)
    except Exception as e:
        log.error(f"command {command.id} failed: {e}", exc_info=True)


def add_menu_entries(menu, location: str, context: dict) -> list:
    """Append the entries. A separator goes first, but only if something was added and the menu already has items."""
    entries = sorted((e for e in MENUS.list(location=location) if _shown(e, context)), key=lambda e: (e.order, e.id))
    if entries and menu.actions():
        menu.addSeparator()
    actions = []
    for entry in entries:
        command = COMMANDS.get(entry.command)
        action = menu.addAction(entry.label or command.name)
        action.setProperty(MENU_ENTRY_PROPERTY, True)
        action.triggered.connect(lambda _checked=False, c=command: _run(c, context))
        actions.append(action)
    return actions
