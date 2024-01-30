from typing import Optional
from .jupyter_client import SciQLopJupyterClient, ClientType
from ..common.python import get_python


class QtConsoleClient(SciQLopJupyterClient):
    def __init__(self, connection_file: str, cwd: Optional[str] = None):
        super().__init__(ClientType.QTCONSOLE)
        args = ["-S", "-c", "from qtconsole import qtconsoleapp;qtconsoleapp.main()", "--existing", connection_file]
        self._start_process(cmd=get_python(), args=args, connection_file=connection_file, cwd=cwd)
