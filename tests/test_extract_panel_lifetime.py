"""_extract_panel must tolerate a dead dock widget, not just a dead
PanelContainer.panel (opencode review of c7d5e682's new
CatalogBrowser._focused_panel, which calls this on a dock widget that came
from the dock manager and may have died in the same teardown window this
helper's own docstring already worries about for w.panel).
"""
import shiboken6
import PySide6QtAds as QtAds

from .fixtures import *


def test_extract_panel_tolerates_destroyed_dock_widget(qapp):
    from SciQLop.core.ui.mainwindow import _extract_panel

    dock = QtAds.CDockWidget("standalone-test-dock")
    shiboken6.delete(dock)
    assert not shiboken6.isValid(dock)

    assert _extract_panel(dock) is None  # must not raise


def test_extract_panel_none_dock_widget_is_a_noop(qapp):
    from SciQLop.core.ui.mainwindow import _extract_panel
    assert _extract_panel(None) is None
