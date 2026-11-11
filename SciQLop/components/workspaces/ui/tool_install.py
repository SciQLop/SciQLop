"""Ask before installing a plugin's command-line tool into the workspace, then show uv's progress."""
from __future__ import annotations

from PySide6.QtCore import QProcess, QProcessEnvironment
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, QVBoxLayout

from SciQLop.components.workspaces.backend.tools import install_command


def offer_tool_install(parent, tool) -> bool:
    """True once *tool* is installed; False when the user declines or the install fails."""
    return _InstallDialog(parent, tool).exec() == QDialog.DialogCode.Accepted


class _InstallDialog(QDialog):
    def __init__(self, parent, tool):
        super().__init__(parent)
        self.setWindowTitle(f"Install {tool.package}?")
        self._tool = tool
        self._process = None
        self._label = QLabel(
            f"{tool.package}{tool.version} is needed and is not installed in this workspace.\n"
            "Install it now with uv? It goes into its own environment in the workspace's .tools folder, "
            "so SciQLop's own packages don't change. This may download a few hundred MB.")
        self._label.setWordWrap(True)
        self._log = QPlainTextEdit(readOnly=True)
        self._log.setVisible(False)
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self._install = self._buttons.addButton("Install", QDialogButtonBox.ButtonRole.AcceptRole)
        self._buttons.accepted.connect(self._start)
        self._buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        for w in (self._label, self._log, self._buttons):
            layout.addWidget(w)

    def _start(self) -> None:
        argv, env = install_command(self._tool)
        self._install.setEnabled(False)
        self._log.setVisible(True)
        self._label.setText(f"Installing {self._tool.package}…")
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
            self._fail(f"uv exited with code {code}")

    def _fail(self, why: str) -> None:
        self._label.setText(f"Installing {self._tool.package} failed: {why}. The output is below.")
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Close")

    def reject(self) -> None:
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(2000)
        super().reject()


def _qt_environment(env: dict) -> QProcessEnvironment:
    qenv = QProcessEnvironment()
    for key, value in env.items():
        qenv.insert(key, value)
    return qenv
