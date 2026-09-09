"""Tests for sciqlop_app's incompatible-plugins startup notice.

See workspace_setup._sync_appstore_plugin_pins: when a SciQLop version
change leaves an installed plugin with no compatible version to update to,
the running app must warn about it once at startup, reading the notice
`read_incompatible_plugins_notice` persisted -- otherwise the plugin just
silently stops loading (loader.py only logs a warning)."""

import json

import pytest

from SciQLop.components.workspaces.backend.workspace_setup import INCOMPATIBLE_PLUGINS_FILENAME
from SciQLop.sciqlop_app import _notify_incompatible_plugins


@pytest.fixture
def parent_widget(qtbot):
    """See test_sciqlop_app_dropped_deps_notice.py's identical fixture for
    why a real top-level widget (not a bare None parent) is needed here."""
    from PySide6.QtWidgets import QWidget
    widget = QWidget()
    qtbot.addWidget(widget)
    return widget


def _message_boxes(parent):
    from PySide6.QtWidgets import QMessageBox
    return parent.findChildren(QMessageBox)


class TestNotifyIncompatiblePlugins:
    def test_no_workspace_dir_env_var_shows_nothing(self, monkeypatch, parent_widget):
        monkeypatch.delenv("SCIQLOP_WORKSPACE_DIR", raising=False)

        _notify_incompatible_plugins(parent_widget)

        assert _message_boxes(parent_widget) == []

    def test_no_notice_file_shows_nothing(self, monkeypatch, tmp_path, parent_widget):
        monkeypatch.setenv("SCIQLOP_WORKSPACE_DIR", str(tmp_path))

        _notify_incompatible_plugins(parent_widget)

        assert _message_boxes(parent_widget) == []

    def test_empty_plugin_list_shows_nothing(self, monkeypatch, tmp_path, parent_widget):
        monkeypatch.setenv("SCIQLOP_WORKSPACE_DIR", str(tmp_path))
        (tmp_path / INCOMPATIBLE_PLUGINS_FILENAME).write_text(
            json.dumps({"plugins": [], "sciqlop_version": "0.14.0"})
        )

        _notify_incompatible_plugins(parent_widget)

        assert _message_boxes(parent_widget) == []

    def test_shows_a_non_modal_warning_naming_the_plugins_and_version(
        self, monkeypatch, tmp_path, parent_widget
    ):
        monkeypatch.setenv("SCIQLOP_WORKSPACE_DIR", str(tmp_path))
        (tmp_path / INCOMPATIBLE_PLUGINS_FILENAME).write_text(
            json.dumps({"plugins": ["Radio Plugin"], "sciqlop_version": "0.14.0"})
        )

        _notify_incompatible_plugins(parent_widget)

        from PySide6.QtCore import Qt
        boxes = _message_boxes(parent_widget)
        assert len(boxes) == 1
        assert "Radio Plugin" in boxes[0].text()
        assert "0.14.0" in boxes[0].text()
        assert boxes[0].windowModality() == Qt.WindowModality.NonModal

    def test_non_dict_notice_payload_shows_nothing_instead_of_crashing(
        self, monkeypatch, tmp_path, parent_widget
    ):
        monkeypatch.setenv("SCIQLOP_WORKSPACE_DIR", str(tmp_path))
        (tmp_path / INCOMPATIBLE_PLUGINS_FILENAME).write_text('["not", "a", "dict"]')

        _notify_incompatible_plugins(parent_widget)

        assert _message_boxes(parent_widget) == []
