"""The startup sequence (built-in commands, plugins, one palette harvest) leaves a clean palette."""
from SciQLop.components.command_palette.backend.registry import COMMANDS

from .fixtures import *  # noqa: F401,F403


def test_replaced_menu_actions_are_not_harvested(main_window):
    replaced = {c.replaces_qaction for c in COMMANDS.list() if c.replaces_qaction}
    harvested = {c.name for c in COMMANDS.list() if c.id.startswith("qaction.")}
    assert replaced
    assert not replaced & harvested


def test_a_builtin_command_shows_once_in_the_palette(main_window):
    assert [c.name for c in COMMANDS.list()].count("New plot panel") == 1


def test_builtin_commands_are_owned_by_sciqlop(main_window):
    assert COMMANDS.owner_of("plot.new_panel") == "sciqlop"
    assert COMMANDS.owner_of("view.fullscreen") == "sciqlop"
