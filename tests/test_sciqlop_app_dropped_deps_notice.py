"""Tests for sciqlop_app's dropped-dependencies startup notice.

See workspace_setup._sync_workspace_venv's culprit-isolation retry ladder
(task-1-brief item 6): when a workspace sync had to leave a plugin/appstore
dependency out, the running app must warn about it once at startup, reading
the drop-notice `read_dropped_dependencies` persisted."""

import json

import pytest

from SciQLop.components.workspaces.backend.workspace_setup import DROPPED_DEPS_FILENAME
from SciQLop.sciqlop_app import _notify_dropped_dependencies


@pytest.fixture
def parent_widget(qtbot):
    """A real (but otherwise unused) top-level widget to parent the notice
    to -- mirrors passing the real main window in start_sciqlop(). A message
    box parented to None has nothing keeping its Python wrapper alive past
    this function call, so it would be garbage-collected (and its native
    window destroyed) before a test could observe it; production code never
    hits that since it always passes the real main window."""
    from PySide6.QtWidgets import QWidget
    widget = QWidget()
    qtbot.addWidget(widget)
    return widget


def _message_boxes(parent):
    from PySide6.QtWidgets import QMessageBox
    return parent.findChildren(QMessageBox)


class TestNotifyDroppedDependencies:
    def test_no_workspace_dir_env_var_shows_nothing(self, monkeypatch, parent_widget):
        monkeypatch.delenv("SCIQLOP_WORKSPACE_DIR", raising=False)

        _notify_dropped_dependencies(parent_widget)

        assert _message_boxes(parent_widget) == []

    def test_no_notice_file_shows_nothing(self, monkeypatch, tmp_path, parent_widget):
        monkeypatch.setenv("SCIQLOP_WORKSPACE_DIR", str(tmp_path))

        _notify_dropped_dependencies(parent_widget)

        assert _message_boxes(parent_widget) == []

    def test_shows_a_non_modal_warning_naming_the_dropped_packages(
        self, monkeypatch, tmp_path, parent_widget
    ):
        """The persisted notice keeps the raw dep string (here a wheel URL);
        the message shown to the user must be the package name instead."""
        monkeypatch.setenv("SCIQLOP_WORKSPACE_DIR", str(tmp_path))
        (tmp_path / DROPPED_DEPS_FILENAME).write_text(
            json.dumps({
                "dropped": ["https://example.com/wheels/radio_plugin-1.2.0-py3-none-any.whl"],
                "error": "boom",
            })
        )

        _notify_dropped_dependencies(parent_widget)

        from PySide6.QtCore import Qt
        boxes = _message_boxes(parent_widget)
        assert len(boxes) == 1
        assert "radio-plugin" in boxes[0].text()
        assert "radio_plugin-1.2.0-py3-none-any.whl" not in boxes[0].text()
        assert boxes[0].windowModality() == Qt.WindowModality.NonModal
