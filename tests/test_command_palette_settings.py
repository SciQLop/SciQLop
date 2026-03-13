from tests.fixtures import *

def test_command_palette_settings_defaults(tmp_path, monkeypatch):
    import SciQLop.components.settings.backend.entry as entry_mod
    monkeypatch.setattr(entry_mod, "SCIQLOP_CONFIG_DIR", str(tmp_path))
    from SciQLop.components.command_palette.settings import CommandPaletteSettings
    s = CommandPaletteSettings()
    assert s.keybinding == "Ctrl+K"
    assert s.max_history_size == 50
