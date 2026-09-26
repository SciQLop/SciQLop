"""Stamp notebooks on save; on open, offer to fix what this workspace lacks.

Both hooks run in the Jupyter server thread. Only the dialog runs on the GUI
thread, reached through the queued ``gap_found`` signal.
"""
import os
import threading

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication, QMessageBox

from SciQLop.components.workspaces.backend.notebook_stamp import (
    EnvironmentGap, current_stamp, environment_gap, installed_version, read_stamp,
    stamp_notebook, workspace_requirements,
)
from SciQLop.components.workspaces.backend.workspace_project import running_sciqlop_version


def stamp_on_save(workspace_dir: str):
    def hook(_path: str, notebook: dict) -> dict:
        return stamp_notebook(notebook, current_stamp(workspace_dir))
    return hook


def describe_gap(notebook_name: str, gap: EnvironmentGap) -> str:
    lines = []
    if gap.needs_newer_sciqlop:
        lines += [f"{notebook_name} was written with SciQLop {gap.stamp.version}. "
                  f"This is SciQLop {gap.running}.", ""]
    if gap.missing:
        subject = "It" if gap.needs_newer_sciqlop else notebook_name
        lines.append(f"{subject} uses packages this workspace does not have:")
        lines += [f"    {spec}" for spec in gap.missing]
    return "\n".join(lines).strip()


class NotebookEnvironmentPrompt(QObject):
    gap_found = Signal(str, object)
    _install_done = Signal(object)

    def __init__(self, workspace_dir: str, parent=None):
        super().__init__(parent)
        self._workspace_dir = workspace_dir
        self._prompted: set[str] = set()
        self._open_boxes: set[QMessageBox] = set()
        self._install_done.connect(self._report_install)

    def on_open(self, path: str, notebook: dict) -> None:
        """Open hook: runs in the server thread."""
        stamp = read_stamp(notebook)
        if stamp is None or path in self._prompted:
            return
        gap = environment_gap(stamp, running_sciqlop_version(), installed_version,
                              workspace_requirements(self._workspace_dir))
        if gap is not None:
            self._prompted.add(path)
            self.gap_found.emit(path, gap)

    @Slot(str, object)
    def show_dialog(self, path: str, gap: EnvironmentGap) -> None:
        install = [("Install here", QMessageBox.ButtonRole.AcceptRole,
                    lambda: self._install(gap.missing))] if gap.missing else []
        self._show_box(
            QMessageBox.Icon.Information, "Notebook environment differs",
            describe_gap(os.path.basename(path), gap),
            "Install what is missing here, or create a new workspace that matches the notebook.",
            install + [("New matching workspace", QMessageBox.ButtonRole.ActionRole,
                        lambda: self._switch_to_matching_workspace(path, gap)),
                       ("Ignore", QMessageBox.ButtonRole.RejectRole, None)])

    def _install(self, specs: list[str]) -> None:
        from SciQLop.components.workspaces import workspaces_manager_instance
        workspace = workspaces_manager_instance().workspace
        threading.Thread(target=lambda: self._install_done.emit(workspace.add_packages(specs)),
                         daemon=True).start()

    @Slot(object)
    def _report_install(self, result: dict) -> None:
        if not result["ok"]:
            self._show_box(QMessageBox.Icon.Warning, "Install failed", result["error"][-2000:], "",
                           [("Close", QMessageBox.ButtonRole.RejectRole, None)])
            return
        installed = ", ".join(result["installed"] or result["already_present"])
        self._show_box(QMessageBox.Icon.Information, "Packages installed", f"Installed: {installed}",
                       "Plugins among them load after a restart.",
                       [("Restart now", QMessageBox.ButtonRole.AcceptRole, _restart),
                        ("Later", QMessageBox.ButtonRole.RejectRole, None)])

    def _show_box(self, icon, title: str, text: str, informative: str, actions) -> None:
        """Show a non-modal box. It is kept referenced until it closes: without a
        reference Python collects it, and the box vanishes as soon as it appears."""
        box = QMessageBox(icon, title, text, parent=QApplication.activeWindow())
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setInformativeText(informative)
        for label, role, callback in actions:
            button = box.addButton(label, role)
            if callback is not None:
                button.clicked.connect(callback)
        box.setModal(False)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._open_boxes.add(box)
        box.finished.connect(lambda _result: self._open_boxes.discard(box))
        box.show()

    @staticmethod
    def _switch_to_matching_workspace(path: str, gap: EnvironmentGap) -> None:
        from SciQLop.components.workspaces.backend.workspaces_manager import WorkspaceManager
        from SciQLop.sciqlop_app import switch_workspace
        switch_workspace(WorkspaceManager.prepare_workspace_for_notebook(path, gap.stamp))


def _restart() -> None:
    from SciQLop.sciqlop_app import restart_sciqlop
    restart_sciqlop()


def install_notebook_hooks(hooks, workspace_dir: str, parent: QObject) -> NotebookEnvironmentPrompt:
    prompt = NotebookEnvironmentPrompt(workspace_dir, parent)
    prompt.gap_found.connect(prompt.show_dialog)
    hooks.add_save_hook(stamp_on_save(workspace_dir))
    hooks.add_open_hook(prompt.on_open)
    return prompt
