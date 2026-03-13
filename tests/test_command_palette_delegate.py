from tests.fixtures import *


def test_delegate_instantiates(qtbot, qapp):
    from SciQLop.components.command_palette.ui.delegate import PaletteItemDelegate
    delegate = PaletteItemDelegate()
    assert delegate is not None
