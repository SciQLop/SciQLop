import os
import sys
from typing import List


def get_python() -> str:
    if "APPIMAGE" in os.environ:
        return os.path.join(os.environ["APPDIR"], f"opt/python{sys.version_info.major}.{sys.version_info.minor}/bin/python{sys.version_info.major}.{sys.version_info.minor}")
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


def run_python_module_cmd(module: str, *args: str) -> List[str]:
    if 'SCIQLOP_BUNDLED' in os.environ:
        return [get_python(), '-I', '-m', module, *args]
    else:
        return [get_python(), '-m', module, *args]
