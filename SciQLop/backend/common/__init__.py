import os, sys
from typing import Optional
from contextlib import closing
import socket


def get_python() -> str:
    if "APPIMAGE" in os.environ:
        return os.path.join(os.environ["APPDIR"], "usr/bin/python3")
    python_exe = 'python.exe' if os.name == 'nt' else 'python'
    if python_exe not in os.path.basename(sys.executable):
        def _find_python() -> str:
            return next(filter(lambda p: os.path.exists(p),
                               map(lambda p: os.path.join(p, python_exe),
                                   [sys.prefix, os.path.join(sys.prefix, 'bin'), sys.base_prefix, sys.base_exec_prefix,
                                    os.path.join(sys.base_prefix, 'bin')])))

        if (python_path := _find_python()) in (None, "") or not os.path.exists(python_path):
            raise RuntimeError("Could not find python executable")
        else:
            return python_path
    return sys.executable


def find_available_port(start_port: int = 8000, end_port: int = 9000) -> Optional[int]:
    for port in range(start_port, end_port):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            res = sock.connect_ex(('localhost', port))
            if res != 0:
                return port
    return None
