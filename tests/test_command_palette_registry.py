from tests.fixtures import *


def test_palette_command_creation():
    from SciQLop.components.command_palette.backend.registry import (
        PaletteCommand, Completion, CommandArg,
    )
    called_with = {}
    def callback(**kwargs):
        called_with.update(kwargs)
    cmd = PaletteCommand(
        id="test.cmd", name="Test Command", description="A test",
        callback=callback, args=[],
    )
    assert cmd.id == "test.cmd"
    assert cmd.name == "Test Command"
    assert cmd.args == []
    assert cmd.icon is None
    assert cmd.keywords == []
    assert cmd.replaces_qaction is None


def test_completion_creation():
    from SciQLop.components.command_palette.backend.registry import Completion
    c = Completion(value="v1", display="Value 1", description="desc")
    assert c.value == "v1"
    assert c.display == "Value 1"
    assert c.description == "desc"
    assert c.icon is None
