"""Palette commands are contributions to sciqlop.commands; CommandRegistry stays as the published adapter."""
import pytest

from SciQLop.components.command_palette.backend.registry import COMMANDS, CommandRegistry, PaletteCommand
from SciQLop.core.extensions import owned_by


@pytest.fixture
def withdraw(qapp):
    yield
    COMMANDS.remove_owner("cmd_demo")


def _cmd(cid, name="Demo"):
    return PaletteCommand(id=cid, name=name, description="", callback=lambda: None)


def test_registering_contributes_with_the_current_owner(withdraw):
    with owned_by("cmd_demo"):
        CommandRegistry().register(_cmd("cmd_demo.hello"))
    assert COMMANDS.owner_of("cmd_demo.hello") == "cmd_demo"
    assert CommandRegistry().get("cmd_demo.hello").name == "Demo"


def test_registering_again_replaces(withdraw):
    with owned_by("cmd_demo"):
        CommandRegistry().register(_cmd("cmd_demo.hello", "First"))
        CommandRegistry().register(_cmd("cmd_demo.hello", "Second"))
    assert CommandRegistry().get("cmd_demo.hello").name == "Second"


def test_unregister_and_unknown_ids(withdraw):
    with owned_by("cmd_demo"):
        CommandRegistry().register(_cmd("cmd_demo.bye"))
    CommandRegistry().unregister("cmd_demo.bye")
    CommandRegistry().unregister("cmd_demo.never")
    assert CommandRegistry().get("cmd_demo.bye") is None
    assert "cmd_demo.bye" not in [c.id for c in CommandRegistry().commands()]


def test_the_app_registry_is_a_view_onto_the_extension_point(withdraw):
    from SciQLop.core.sciqlop_application import sciqlop_app
    with owned_by("cmd_demo"):
        COMMANDS.contribute(_cmd("cmd_demo.direct"))
    assert sciqlop_app().command_registry.get("cmd_demo.direct") is not None
