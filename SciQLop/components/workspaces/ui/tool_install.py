"""Ask before installing or updating a plugin's command-line tool in the workspace, then show its progress;
and remove the tools no active plugin uses anymore."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QProcess, QProcessEnvironment
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QMessageBox, QPlainTextEdit, QVBoxLayout

from SciQLop.components.workspaces.backend import tools


def offer_tool_install(parent, tool, installed: Optional[str] = None) -> bool:
    """True once *tool* is installed (or updated from *installed*); False when declined or failed."""
    return _InstallDialog(parent, tool, installed).exec() == QDialog.DialogCode.Accepted


class _InstallDialog(QDialog):
    def __init__(self, parent, tool, installed: Optional[str] = None):
        super().__init__(parent)
        self._tool, self._process = tool, None
        self._verb = "Update" if installed else "Install"
        self.setWindowTitle(f"{self._verb} {tool.package}?")
        need = f"{tool.package}{_shown_range(tool)}"
        why = (f"{tool.package} {installed} is installed, but its plugin needs {tool.version}."
               if installed else f"{need} is needed and is not installed in this workspace.")
        self._label = QLabel(
            f"{why}\n{self._verb} it now with {tool.kind}? It goes into its own environment in the workspace's "
            ".tools folder, so SciQLop's own packages don't change. This may download a few hundred MB.")
        self._label.setWordWrap(True)
        self._log = QPlainTextEdit(readOnly=True)
        self._log.setVisible(False)
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self._go = self._buttons.addButton(self._verb, QDialogButtonBox.ButtonRole.AcceptRole)
        self._buttons.accepted.connect(self._start)
        self._buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for w in (self._label, self._log, self._buttons):
            layout.addWidget(w)

    def _start(self) -> None:
        self._go.setEnabled(False)
        try:
            argv, env = tools.install_command(self._tool)
        except RuntimeError as e:   # no npm, no uv
            self._fail(str(e))
            return
        self._log.setVisible(True)
        self._label.setText(f"{self._verb.removesuffix('e')}ing {self._tool.package}…")
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.setProcessEnvironment(_qt_environment(env))
        self._process.readyReadStandardOutput.connect(self._append_output)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(lambda _e: self._fail(self._process.errorString()))
        self._process.start(argv[0], argv[1:])

    def _append_output(self) -> None:
        text = bytes(self._process.readAllStandardOutput()).decode(errors="replace").rstrip()
        if text:
            self._log.appendPlainText(text)

    def _on_finished(self, code: int, status) -> None:
        self._append_output()
        if code == 0 and status == QProcess.ExitStatus.NormalExit:
            self.accept()
        else:
            self._fail(f"{self._tool.kind} exited with code {code}; its output is below")

    def _fail(self, why: str) -> None:
        self._label.setText(f"{self._verb} of {self._tool.package} failed: {why}.")
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Close")

    def reject(self) -> None:
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(2000)
        super().reject()


def _shown_range(tool) -> str:
    return f" ({tool.version})" if tool.kind == "npm" and tool.version else tool.version


def _qt_environment(env: dict) -> QProcessEnvironment:
    qenv = QProcessEnvironment()
    for key, value in env.items():
        qenv.insert(key, value)
    return qenv


def remove_unused_tools(parent) -> None:
    """Ask, then remove the tools installed in this workspace that no active plugin declares."""
    unused = tools.unused_tools()
    if not unused:
        QMessageBox.information(parent, "Workspace tools", "Every tool installed in this workspace is in use.")
        return
    names = "\n".join(f"  {t.package} ({t.kind})" for t in unused)
    answer = QMessageBox.question(
        parent, "Remove unused tools?",
        f"No active plugin uses these tools anymore:\n{names}\n\nRemove them from this workspace? "
        "A plugin that needs one again offers to reinstall it.")
    if answer != QMessageBox.StandardButton.Yes:
        return
    failed = []
    for tool in unused:
        try:
            tools.remove_tool(tool)
        except Exception as e:
            failed.append(f"  {tool.package}: {e}")
    if failed:
        QMessageBox.warning(parent, "Workspace tools", "Some tools could not be removed:\n" + "\n".join(failed))
