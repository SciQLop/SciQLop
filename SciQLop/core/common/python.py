import os
import sys


def get_python() -> str:
    appdir = os.environ.get("APPDIR")
    if appdir:
        return os.path.join(appdir, "opt", "python", "bin", "python3")
    python_exe = 'python.exe' if os.name == 'nt' else 'python'
    if python_exe not in os.path.basename(sys.executable):
        candidates = [
            os.path.join(sys.prefix, "bin", python_exe),
            os.path.join(sys.prefix, python_exe),
            os.path.join(sys.base_prefix, "bin", python_exe),
            os.path.join(sys.base_exec_prefix, "bin", python_exe),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        raise RuntimeError("Could not find python executable")
    return sys.executable
