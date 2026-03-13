from __future__ import annotations
from PySide6.QtWidgets import QMainWindow, QMenu
from SciQLop.components.command_palette.backend.registry import (CommandRegistry, PaletteCommand)


def _collect_menu_actions(menu: QMenu, path: str) -> list[tuple[str, str, callable]]:
    results = []
    for action in menu.actions():
        if action.isSeparator():
            continue
        submenu = action.menu()
        if submenu:
            results.extend(_collect_menu_actions(submenu, f"{path}.{submenu.title()}"))
        elif action.text():
            action_id = f"qaction.{path}.{action.text()}"
            results.append((action_id, action.text(), action.trigger))
    return results


def _suppressed_texts(registry: CommandRegistry) -> set[str]:
    return {cmd.replaces_qaction for cmd in registry.commands() if cmd.replaces_qaction}


def harvest_qactions(registry: CommandRegistry, main_window: QMainWindow) -> None:
    suppressed = _suppressed_texts(registry)
    existing_ids = {cmd.id for cmd in registry.commands()}
    for action in main_window.menuBar().actions():
        menu = action.menu()
        if not menu:
            continue
        for action_id, text, trigger in _collect_menu_actions(menu, menu.title()):
            if action_id in existing_ids:
                continue
            if text in suppressed:
                continue
            registry.register(PaletteCommand(
                id=action_id, name=text, description=f"Menu: {menu.title()}", callback=trigger,
            ))
