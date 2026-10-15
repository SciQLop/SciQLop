"""Icon wiring for the Agent Chat UI and the catalog provider actions.

The Agent Chat toolbar button, Tools-menu entry and dock-tab icon are owned by
SciQLop core (not by backend plugins), using the core-shipped ``assistant``
icon. Two regressions are pinned here:

- ``theme_icon(name)`` resolves a *baked* PNG from the per-palette icon cache,
  which only exists for icons SciQLopPlots ships under ``:/icons/theme/``.
  Pointing it at a non-shipped name (``chat``, ``trash``) yields a blank icon.
- App-provided assets must go through ``register_icon`` + ``get_icon`` instead.
"""
import re
from pathlib import Path

import pytest
import shiboken6
from PySide6.QtCore import QSize

import SciQLop
from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures

_PKG_ROOT = Path(SciQLop.__file__).parent
_THEME_ICON_CALL = re.compile(r'theme_icon\(\s*["\']([A-Za-z0-9_]+)["\']\s*\)')


def _renders(icon) -> bool:
    return not icon.pixmap(QSize(24, 24)).isNull()


def _bakeable_theme_icon_names() -> set[str]:
    from SciQLopPlots import Icons

    return {
        Path(i).stem
        for i in Icons.icons()
        if ":/icons/theme/" in i
    }


@pytest.fixture
def bare_main_window(qapp, sciqlop_resources):
    """A main window with no plugins loaded — avoids the network call that
    backend plugins make in their ``load()`` during the shared fixture."""
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow

    mw = SciQLopMainWindow()
    yield mw
    mw.close()


def test_agent_assistant_icon_renders(qapp):
    import SciQLop.components.agents.chat_dock  # noqa: F401 — registers "assistant"
    from SciQLop.components.theming import get_icon

    assert _renders(get_icon("assistant"))


def test_agent_ui_registered_once_centrally(bare_main_window):
    """Core owns the whole agent chat UI. Calling ``ensure_agent_dock`` from
    several backend plugins must yield exactly one shared dock, registered as a
    left auto-hide side panel (like the product tree / catalogs / settings
    panels) with a single View-menu toggle — no top-toolbar button and no
    Tools-menu entry."""
    from SciQLop.components.agents import ensure_agent_dock

    mw = bare_main_window
    dock1 = ensure_agent_dock(mw)  # first backend plugin
    dock2 = ensure_agent_dock(mw)  # second backend plugin
    assert dock1 is dock2  # single shared dock instance

    cdw = mw.dock_manager.findDockWidget("Agents")
    assert cdw is not None
    assert not cdw.icon().isNull()  # tab icon present, core assistant icon
    assert cdw.isAutoHide()         # docked as a left auto-hide side panel

    # Wired exactly like the other side panels: one View-menu toggle, and no
    # dedicated top-toolbar button or Tools-menu entry.
    assert [a for a in mw.toolBar.actions() if a.text() == "Agent Chat"] == []
    assert [a for a in mw.toolsMenu.actions() if a.text() == "Agent Chat"] == []
    view_toggles = [a for a in mw.viewMenu.actions() if a.text() == "Agents"]
    assert len(view_toggles) == 1


def test_agent_dock_survives_the_withdrawal_of_the_backend_that_created_it(bare_main_window, qtbot):
    """The chat UI is owned by core: a failing backend plugin's withdrawal must not close it for the others."""
    from SciQLop.components.agents import ensure_agent_dock
    from SciQLop.core.docks import DOCKS
    from SciQLop.core.extensions import owned_by

    with owned_by("legacy:first_backend"):
        dock = ensure_agent_dock(bare_main_window)
    try:
        DOCKS.remove_owner("legacy:first_backend")
        qtbot.wait(50)
        assert shiboken6.isValid(dock)
        assert bare_main_window.dock_manager.findDockWidget("Agents") is not None
        assert DOCKS.owner_of("sciqlop.Agents") == "sciqlop"
    finally:
        DOCKS.remove("sciqlop.Agents")


def test_added_dock_gets_widget_window_icon(bare_main_window):
    """A widget docked via ``addWidgetIntoDock`` must surface its windowIcon on
    the dock tab. Before, only ``add_side_pan`` propagated it, so docks created
    via ``addWidgetIntoDock`` (the Agent Chat path) had no tab icon."""
    import PySide6QtAds as QtAds
    from PySide6.QtWidgets import QWidget
    from PySide6.QtGui import QIcon
    from SciQLop.components.theming import get_icon

    w = QWidget(bare_main_window)  # parent it: avoid shiboken GC of the wrapper
    w.setWindowTitle("IconProbe")
    w.setWindowIcon(get_icon("assistant"))
    bare_main_window.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, w)

    dock = bare_main_window.dock_manager.findDockWidget("IconProbe")
    try:
        assert dock is not None
        assert isinstance(dock.icon(), QIcon) and not dock.icon().isNull()
    finally:
        dock.takeWidget()
        dock.closeDockWidget()


def test_orphan_cleanup_action_icon_renders(qapp):
    from SciQLop.components.theming import theme_icon

    assert _renders(theme_icon("delete"))


def test_every_theme_icon_literal_is_bakeable(qapp):
    """``theme_icon(name)`` is blank unless ``name`` is a baked theme resource.

    Guards against re-introducing the chat/trash class of bug: pointing
    ``theme_icon`` at a name SciQLopPlots does not ship under ``:/icons/theme/``.
    """
    bakeable = _bakeable_theme_icon_names()
    offenders: dict[str, list[str]] = {}
    for path in _PKG_ROOT.rglob("*.py"):
        for name in _THEME_ICON_CALL.findall(path.read_text(encoding="utf-8")):
            if name not in bakeable:
                offenders.setdefault(name, []).append(
                    str(path.relative_to(_PKG_ROOT))
                )
    assert not offenders, f"theme_icon() used with non-bakeable names: {offenders}"
