"""Edit mode on a panel with no catalog that accepts events used to be a dead
end: the "Add to:" box vanished and Shift+click did nothing, with no word why."""
from datetime import datetime, timedelta, timezone

import pytest

from .fixtures import *


@pytest.fixture
def chrome(qtbot):
    from SciQLop.components.plotting.ui.catalog_chrome import CatalogChrome
    w = CatalogChrome()
    qtbot.addWidget(w)
    return w


def test_no_target_says_so_instead_of_hiding(chrome):
    chrome.set_targets([])
    assert chrome._target_combo.isHidden() is False
    assert chrome._target_combo.isEnabled() is False
    assert chrome._target_combo.currentText() == "No editable catalog on this panel"
    assert chrome.selected_target() is None


def test_targets_arriving_replace_the_notice(chrome):
    chrome.set_targets([])
    chrome.set_targets([("Bow shocks", "uuid-1")])
    assert chrome._target_combo.isEnabled() is True
    assert chrome._target_combo.count() == 1
    assert chrome.selected_target() == "uuid-1"


def test_new_catalog_button_shows_with_the_target_box_only(chrome):
    assert chrome._new_catalog_btn.isHidden() is True
    chrome.set_targets([])
    assert chrome._new_catalog_btn.isHidden() is False
    chrome.clear_targets()
    assert chrome._new_catalog_btn.isHidden() is True


def test_new_catalog_button_asks_for_a_catalog(chrome, qtbot):
    chrome.set_targets([])
    with qtbot.waitSignal(chrome.new_catalog_requested, timeout=1000):
        chrome._new_catalog_btn.click()


@pytest.fixture
def edited_panel(qtbot, qapp):
    """A panel in Edit mode with its catalog bar and no catalog."""
    from SciQLop.components.catalogs.backend.panel_manager import InteractionMode, PanelCatalogManager
    from SciQLop.components.plotting.ui.catalog_chrome import CatalogChrome
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange
    panel = TimeSyncPanel("edit-without-target")
    qtbot.addWidget(panel)
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=2)).timestamp())
    panel._catalog_chrome = CatalogChrome(panel)
    manager = PanelCatalogManager(panel)
    manager.attach_chrome(panel._catalog_chrome)
    manager.mode = InteractionMode.EDIT
    return manager, panel._catalog_chrome


def test_edit_mode_without_a_catalog_explains_itself(edited_panel):
    _manager, chrome = edited_panel
    assert chrome._target_combo.currentText() == "No editable catalog on this panel"
    assert chrome._new_catalog_btn.isHidden() is False


def test_new_catalog_is_created_shown_on_the_panel_and_selected(edited_panel, monkeypatch):
    from SciQLop.components.catalogs.backend import panel_manager
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    manager, chrome = edited_panel
    provider = DummyProvider(num_catalogs=0)
    monkeypatch.setattr(panel_manager, "_ask_new_catalog", lambda parent: (provider, "Bow shocks"))
    chrome._new_catalog_btn.click()
    created = [c for c in provider.catalogs() if c.name == "Bow shocks"]
    assert len(created) == 1
    assert created[0].uuid in manager.catalog_uuids
    assert chrome.selected_target() == created[0].uuid
    assert chrome._target_combo.isEnabled() is True


def test_cancelling_the_question_creates_nothing(edited_panel, monkeypatch):
    from SciQLop.components.catalogs.backend import panel_manager
    manager, chrome = edited_panel
    monkeypatch.setattr(panel_manager, "_ask_new_catalog", lambda parent: None)
    chrome._new_catalog_btn.click()
    assert manager.catalog_uuids == set()
