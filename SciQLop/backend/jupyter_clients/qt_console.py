from typing import Optional
from .jupyter_client_process import SciQLopJupyterClient, ClientType
from ..common.python import get_python
import os


class QtConsoleClient(SciQLopJupyterClient):
    def __init__(self, connection_file: str, cwd: Optional[str] = None):
        super().__init__(ClientType.QTCONSOLE)
        args = ["-c", "from qtconsole import qtconsoleapp;qtconsoleapp.main()", "--existing", connection_file]
        if 'SCIQLOP_BUNDLED' in os.environ:
            args.insert(0, '-I')
        self._start_process(cmd=get_python(), args=args, connection_file=connection_file, cwd=cwd)
