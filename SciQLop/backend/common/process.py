from typing import Optional, Dict
import os
from PySide6.QtCore import QObject, Signal, QProcess, QProcessEnvironment, Slot
from shiboken6 import isValid
from SciQLop.backend import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)


def fix_environment(env: Dict) -> Dict:
    return env


def to_qt_environment(env: Dict) -> QProcessEnvironment:
    qt_env = QProcessEnvironment()
    for k, v in env.items():
        qt_env.insert(k, v)
    return qt_env


class Process(QObject):
    finished = Signal(int)

    def __init__(self, cmd: str, args: Optional[list] = None, extra_env: Optional[dict] = None,
                 cwd: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.process = QProcess()
        self.cmd = cmd
        self.args = args or []
        self.extra_env = extra_env or {}
        self.cwd = cwd
        self._started = False
        self._stdout = ""
        self._stderr = ""

    @property
    def full_cmd(self):
        return f"{self.cmd} {' '.join(self.args)}"

    def start(self):
        log.debug(f"Starting process {self.full_cmd} in {self.cwd}")
        self.process.setProcessEnvironment(to_qt_environment(fix_environment(os.environ | self.extra_env)))
        log.debug(f"Process environment: {'\n'.join(self.process.processEnvironment().toStringList())}")
        if self.cwd:
            self.process.setWorkingDirectory(self.cwd)
        self.process.finished.connect(self._notify_finished)
        self.process.readyReadStandardOutput.connect(self._capture_stdout)
        self.process.readyReadStandardError.connect(self._capture_stderr)
        self.process.start(self.cmd, self.args)
        self._started = True

    def _notify_finished(self, code: int, status: QProcess.ExitStatus):
        if status == QProcess.ExitStatus.NormalExit:
            log.debug(f"Process {self.full_cmd} finished with code {code}")
            if code != 0:
                log.error(f"Process {self.full_cmd} finished with error code {code}")
                log.error(f"Process {self.full_cmd} stderr: {self.stderr}")
        else:
            log.error(f"Process {self.full_cmd} crashed with code {code}")
        self.finished.emit(code)

    @Slot()
    def _capture_stdout(self):
        if isValid(self.process):
            self._stdout += str(self.process.readAllStandardOutput(), encoding="utf-8")

    @Slot()
    def _capture_stderr(self):
        if isValid(self.process):
            self._stderr += str(self.process.readAllStandardError(), encoding="utf-8")

    def complete(self):
        return self.process.state() == QProcess.ProcessState.NotRunning and self._started

    @property
    def stdout(self):
        if isValid(self.process):
            return self.process.readAllStandardOutput().data().decode()
        return self._stdout

    @property
    def stderr(self):
        if isValid(self.process):
            return self.process.readAllStandardError().data().decode()
        return self._stderr
