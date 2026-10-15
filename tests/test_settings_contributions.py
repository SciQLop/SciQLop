"""ConfigEntry subclasses are contributions to sciqlop.settings, and the settings panel follows them."""
import threading
from typing import ClassVar
from unittest.mock import patch

import pytest
import shiboken6
from PySide6.QtCore import QObject, Qt, Signal

from .fixtures import *  # noqa: F401, F403
from SciQLop.components.settings.backend.entry import ConfigEntry, SETTINGS
from SciQLop.core.extensions import owned_by

CREATED = ("SetContribA", "SetContribB", "SetContribDup", "SetContribWorker", "SetContribLive")


@pytest.fixture(autouse=True)
def tmp_config_dir(tmp_path):
    with patch("SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR", str(tmp_path)):
        yield tmp_path
    for name in CREATED:
        if name in SETTINGS:
            SETTINGS.remove(name)


def _define(name: str, category: str = "set_contrib_category"):
    return type(name, (ConfigEntry,), {
        "__annotations__": {"category": ClassVar[str], "subcategory": ClassVar[str], "knob": int},
        "knob": 1, "category": category, "subcategory": "general"})


class _BlockingInvoker(QObject):
    """The primitive jupyqt's invoker is built on: a worker blocks while the main thread runs its call."""
    run_requested = Signal()

    def __init__(self):
        super().__init__()
        self._call = None
        self._result = None
        self.run_requested.connect(self._run, Qt.BlockingQueuedConnection)

    def _run(self):
        self._result = self._call()

    def __call__(self, func, *args, **kwargs):
        self._call = lambda: func(*args, **kwargs)
        self.run_requested.emit()
        return self._result


def test_a_config_entry_is_a_contribution(qapp):
    cls = _define("SetContribA")

    assert SETTINGS.get("SetContribA") is cls
    assert SETTINGS.owner_of("SetContribA") == "user"
    assert ConfigEntry.list_entries()["SetContribA"] is cls


def test_a_plugin_config_entry_is_owned_by_the_plugin(qapp):
    with owned_by("set_demo"):
        _define("SetContribB")

    assert SETTINGS.owner_of("SetContribB") == "set_demo"
    SETTINGS.remove_owner("set_demo")
    assert "SetContribB" not in ConfigEntry.list_entries()
    with pytest.raises(ValueError):
        ConfigEntry.get_entry("SetContribB")


def test_duplicate_name_still_raises(qapp):
    _define("SetContribDup")

    with pytest.raises(ValueError, match="Duplicate entry name"):
        _define("SetContribDup")


def test_defined_on_a_worker_thread(qapp, qtbot):
    from SciQLop.user_api import threading as sqp_threading
    outcome = {"done": False, "error": None}

    def define():
        try:
            _define("SetContribWorker")
        except Exception as e:
            outcome["error"] = e
        outcome["done"] = True

    invoker = _BlockingInvoker()
    invoker.moveToThread(qapp.thread())
    previous = sqp_threading._invoker
    sqp_threading.init_invoker(invoker)
    try:
        thread = threading.Thread(target=define)
        thread.start()
        qtbot.waitUntil(lambda: outcome["done"], timeout=5000)
        thread.join(timeout=1)
    finally:
        sqp_threading.init_invoker(previous)

    assert outcome["error"] is None
    assert SETTINGS.owner_of("SetContribWorker") == "user"


def _categories(panel) -> set:
    proxy = panel._left_panel.categories_list.model()
    return {proxy.index(r, 0).data() for r in range(proxy.rowCount())}


def test_the_panel_follows_live_settings(qapp, qtbot):
    from SciQLop.components.settings.ui.setting_panel import SettingsPanel
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    panel.show()
    assert "set_live_category" not in _categories(panel)

    _define("SetContribLive", category="set_live_category")
    assert "set_live_category" in _categories(panel)

    categories = panel._left_panel.categories_list
    categories.setCurrentIndex(categories.model().index(0, 0))
    SETTINGS.remove("SetContribLive")

    assert "set_live_category" not in _categories(panel)
    view = panel._category_view
    assert view._current in _categories(panel)
    assert shiboken6.isValid(view._stack.currentWidget())
