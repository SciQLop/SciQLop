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


def test_registry_register_and_list():
    from SciQLop.components.command_palette.backend.registry import (
        CommandRegistry, PaletteCommand,
    )
    registry = CommandRegistry()
    cmd = PaletteCommand(
        id="test.hello", name="Hello", description="Say hello",
        callback=lambda: None, args=[],
    )
    registry.register(cmd)
    assert "test.hello" in [c.id for c in registry.commands()]


def test_registry_unregister():
    from SciQLop.components.command_palette.backend.registry import (
        CommandRegistry, PaletteCommand,
    )
    registry = CommandRegistry()
    cmd = PaletteCommand(
        id="test.bye", name="Bye", description="Say bye",
        callback=lambda: None, args=[],
    )
    registry.register(cmd)
    registry.unregister("test.bye")
    assert "test.bye" not in [c.id for c in registry.commands()]


def test_registry_reregister_overwrites():
    from SciQLop.components.command_palette.backend.registry import (
        CommandRegistry, PaletteCommand,
    )
    registry = CommandRegistry()
    cmd1 = PaletteCommand(
        id="test.dup", name="Dup", description="original",
        callback=lambda: None,
    )
    cmd2 = PaletteCommand(
        id="test.dup", name="Dup", description="updated",
        callback=lambda: None,
    )
    registry.register(cmd1)
    registry.register(cmd2)
    assert registry.get("test.dup").description == "updated"
    assert len([c for c in registry.commands() if c.id == "test.dup"]) == 1
