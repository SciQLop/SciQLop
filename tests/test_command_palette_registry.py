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


def test_registry_duplicate_id_raises():
    from SciQLop.components.command_palette.backend.registry import (
        CommandRegistry, PaletteCommand,
    )
    registry = CommandRegistry()
    cmd = PaletteCommand(
        id="test.dup", name="Dup", description="dup",
        callback=lambda: None,
    )
    registry.register(cmd)
    import pytest
    with pytest.raises(ValueError):
        registry.register(cmd)
