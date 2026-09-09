"""Structure of the panel right-click menu: actions are grouped by intention
into 'Export' and 'Panel templates' submenus rather than flat at the top
level (2026-06-14 readability refactor)."""


def _submenu(menu, title):
    for a in menu.actions():
        sub = a.menu()
        if sub is not None and a.text().replace("&&", "&") == title:
            return sub
    return None


def _submenu_titles(menu):
    return [a.text().replace("&&", "&") for a in menu.actions() if a.menu() is not None]


def _leaf_labels(menu):
    return [a.text() for a in menu.actions() if a.menu() is None and not a.isSeparator()]


def _panel(qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    panel = TimeSyncPanel("test-panel")
    qtbot.addWidget(panel)
    return panel


def test_top_level_is_grouped(qtbot, qapp):
    panel = _panel(qtbot)
    menu = panel._build_context_menu()
    assert _submenu_titles(menu) == ["Catalogs", "Export", "Panel templates"]
    # nothing loose at the top level except separators
    assert _leaf_labels(menu) == []


def test_export_share_group_contents(qtbot, qapp):
    panel = _panel(qtbot)
    menu = panel._build_context_menu()
    export = _submenu(menu, "Export")
    assert export is not None
    labels = _leaf_labels(export)
    assert "Export as PNG…" in labels
    assert "Export as PDF…" in labels


def test_templates_group_contents(qtbot, qapp):
    panel = _panel(qtbot)
    menu = panel._build_context_menu()
    templates = _submenu(menu, "Panel templates")
    assert templates is not None
    labels = _leaf_labels(templates)
    assert "Save as template…" in labels
    assert "Export template…" in labels
    # no template source bound -> no 'Update template'
    assert "Update template" not in labels
