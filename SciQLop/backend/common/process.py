from typing import Optional

from PySide6.QtCore import QObject, Signal, QProcess, QProcessEnvironment
from SciQLop.backend import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)


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

    def start(self):
        log.debug(f"Starting process {self.cmd} {' '.join(self.args)} in {self.cwd}")
        env = QProcessEnvironment.systemEnvironment()
        for key, value in self.extra_env.items():
            env.insert(key, value)
        self.process.setProcessEnvironment(env)
        if self.cwd:
            self.process.setWorkingDirectory(self.cwd)
        self.process.finished.connect(lambda code, status: self.finished.emit(code))
        self.process.readyReadStandardOutput.connect(self._capture_stdout)
        self.process.readyReadStandardError.connect(self._capture_stderr)
        self.process.start(self.cmd, self.args)
        self._started = True

    def _capture_stdout(self):
        self._stdout = str(self.process.readAllStandardOutput(), encoding="utf-8")

    def _capture_stderr(self):
        self._stderr = str(self.process.readAllStandardError(), encoding="utf-8")

    def complete(self):
        return self.process.state() == QProcess.ProcessState.NotRunning and self._started

    @property
    def stdout(self):
        return self.process.readAllStandardOutput().data().decode()

    @property
    def stderr(self):
        return self.process.readAllStandardError().data().decode()
