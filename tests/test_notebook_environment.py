"""The notebook stamp wired to a real workspace: stamping on save, prompting on
open, and creating a workspace that matches a stamped notebook."""
import json
import threading
from unittest.mock import patch

from SciQLop.components.workspaces.backend.notebook_stamp import (
    EnvironmentGap, NotebookStamp, current_stamp, read_stamp,
)
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.components.workspaces.backend.workspaces_manager import WorkspaceManager
from SciQLop.components.workspaces.ui.notebook_environment import (
    NotebookEnvironmentPrompt, describe_gap, stamp_on_save,
)


def _workspace(tmp_path, requires=()):
    ws_dir = tmp_path / "ws"
    ws_dir.mkdir()
    WorkspaceManifest(name="ws", requires=list(requires)).save(ws_dir / "workspace.sciqlop")
    return str(ws_dir)


def _stamped(dependencies, version="0.0.1"):
    return {"cells": [], "metadata": {"sciqlop": {"version": version, "dependencies": dependencies}}}


def test_current_stamp_reads_the_workspace_manifest(tmp_path):
    ws_dir = _workspace(tmp_path, requires=["packaging", "/home/me/local_plugin"])

    stamp = current_stamp(ws_dir)

    assert stamp.dependencies == [f"packaging=={__import__('packaging').__version__}"]


def test_save_hook_stamps_the_notebook(tmp_path):
    ws_dir = _workspace(tmp_path, requires=["packaging"])

    saved = stamp_on_save(ws_dir)("nb.ipynb", {"cells": [], "metadata": {}})

    assert read_stamp(saved) == current_stamp(ws_dir)


def test_prepare_workspace_for_notebook_pins_version_and_copies_notebook(tmp_path):
    notebook = tmp_path / "analysis.ipynb"
    notebook.write_text(json.dumps(_stamped(["scipy==1.15.0"])))
    workspaces = tmp_path / "workspaces"
    workspaces.mkdir()
    stamp = NotebookStamp(version="0.14.0", dependencies=["scipy==1.15.0"])

    with patch("SciQLop.components.workspaces.backend.workspaces_manager.SciQLopWorkspacesSettings") as settings:
        settings.return_value.workspaces_dir = str(workspaces)
        directory = WorkspaceManager.prepare_workspace_for_notebook(str(notebook), stamp)

    manifest = WorkspaceManifest.load(f"{directory}/workspace.sciqlop")
    assert manifest.name == "analysis"
    assert manifest.sciqlop_version == "0.14.0"
    assert manifest.requires == ["scipy==1.15.0"]
    assert (tmp_path / "workspaces").joinpath(directory, "analysis.ipynb").read_text() == notebook.read_text()


def test_describe_gap_names_version_and_missing_packages():
    gap = EnvironmentGap(stamp=NotebookStamp(version="0.14.0", dependencies=["x==1"]),
                         running="0.13.0", missing=["x==1"], needs_newer_sciqlop=True)

    text = describe_gap("analysis.ipynb", gap)

    assert "analysis.ipynb" in text
    assert "SciQLop 0.14.0" in text and "SciQLop 0.13.0" in text
    assert "x==1" in text


def _open_from_server_thread(prompt, path, notebook):
    thread = threading.Thread(target=prompt.on_open, args=(path, notebook))
    thread.start()
    thread.join()


def test_prompt_reports_a_gap_once_per_notebook(qtbot, tmp_path):
    prompt = NotebookEnvironmentPrompt(_workspace(tmp_path))
    received = []
    prompt.gap_found.connect(lambda path, gap: received.append((path, gap.missing)))
    notebook = _stamped(["surely-not-installed-package==1.0"])

    _open_from_server_thread(prompt, "/ws/a.ipynb", notebook)
    _open_from_server_thread(prompt, "/ws/a.ipynb", notebook)

    qtbot.waitUntil(lambda: len(received) == 1)
    qtbot.wait(50)
    assert received == [("/ws/a.ipynb", ["surely-not-installed-package==1.0"])]


def test_prompt_stays_quiet_for_reproducible_and_unstamped_notebooks(qtbot, tmp_path):
    prompt = NotebookEnvironmentPrompt(_workspace(tmp_path))
    received = []
    prompt.gap_found.connect(lambda path, gap: received.append(path))

    _open_from_server_thread(prompt, "/ws/ok.ipynb", _stamped(["packaging"]))
    _open_from_server_thread(prompt, "/ws/plain.ipynb", {"cells": [], "metadata": {}})

    qtbot.wait(50)
    assert received == []


def _visible_message_boxes():
    from PySide6.QtWidgets import QApplication, QMessageBox
    return [w for w in QApplication.topLevelWidgets() if isinstance(w, QMessageBox) and w.isVisible()]


def test_dialog_survives_after_show_returns(qtbot, tmp_path):
    import gc
    prompt = NotebookEnvironmentPrompt(_workspace(tmp_path))
    gap = EnvironmentGap(stamp=NotebookStamp(version="0.0.1", dependencies=["x==1"]),
                         running="0.0.1", missing=["x==1"], needs_newer_sciqlop=False)

    prompt.show_dialog("/ws/a.ipynb", gap)
    gc.collect()
    qtbot.wait(20)

    boxes = _visible_message_boxes()
    assert len(boxes) == 1
    assert "x==1" in boxes[0].text()
    boxes[0].reject()
