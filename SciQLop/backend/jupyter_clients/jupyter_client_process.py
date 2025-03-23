import os.path
import sys
from typing import List, Mapping, Optional, Callable

from PySide6.QtCore import QProcess, QProcessEnvironment, QObject

from enum import Enum
from SciQLop.backend import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)


def is_pyinstaller_exe() -> bool:
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def pyinstaller_exe_path() -> str:
    assert is_pyinstaller_exe()
    return sys._MEIPASS


class ClientType(Enum):
    QTCONSOLE = "qtconsole"
    JUPYTERLAB = "jupyterlab"


class SciQLopJupyterClient(QObject):
    def __init__(self, client_type: ClientType, parent=None, stdout_parser: Optional[Callable] = None,
                 stderr_parser: Optional[Callable] = None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.client_type = client_type
        self._stdout_parser = stdout_parser or (lambda x: x)
        self._stderr_parser = stderr_parser or (lambda x: x)

    def _start_process(self, cmd: str, args: List[str], connection_file: str,
                       extra_env: Optional[Mapping[str, str]] = None, cwd: Optional[str] = None):
        env = QProcessEnvironment.systemEnvironment()
        env.insert("SCIQLOP_IPYTHON_CONNECTION_FILE", connection_file)
        if extra_env:
            for key, value in extra_env.items():
                env.insert(key, value)

        if os.name == 'nt':
            sep = ';'
        else:
            sep = ':'
        PYTHONPATH = sep.join(sys.path)
        if is_pyinstaller_exe():
            PYTHONPATH += sep.join([f"{pyinstaller_exe_path()}", f"{pyinstaller_exe_path()}/base_library.zip"])
        env.insert("PYTHONPATH", PYTHONPATH)
        self.process.setProcessEnvironment(env)
        self.process.readyReadStandardOutput.connect(self._forward_stdout)
        self.process.readyReadStandardError.connect(self._forward_stderr)
        self.process.stateChanged.connect(self._process_state_changed)
        if cwd:
            self.process.setWorkingDirectory(cwd)
        self.process.start(cmd, args)
        log.info(f"\n{self.process.program()}  {' '.join(self.process.arguments())}\n")

    def state(self) -> QProcess.ProcessState:
        return self.process.state()

    def _process_state_changed(self, state: QProcess.ProcessState):
        log.info(f"Process state changed to {state}")

    def _forward_stdout(self):
        log.info(self._stdout_parser(str(self.process.readAllStandardOutput(), encoding="utf-8")))

    def _forward_stderr(self):
        log.error(self._stderr_parser(str(self.process.readAllStandardError(), encoding="utf-8")))

    def kill(self):
        self.process.kill()

    def waitForFinished(self):
        self.process.waitForFinished()
