import os
from typing import List, Optional
from .python import get_python, run_python_module_cmd
from .process import Process


class _PipProcess(Process):
    def __init__(self, args: List[str], cwd: Optional[str] = None):
        cmd = run_python_module_cmd("pip", *args)
        super().__init__(cmd[0], cmd[1:], cwd=cwd)


def pip_install_packages(packages: List[str], install_dir: Optional[str] = None, cwd: Optional[str] = None,
                         upgrade: bool = False):
    args = ["install"] + packages
    if upgrade:
        args += ["--upgrade"]
    if install_dir is not None:
        args += ["--target", install_dir]
    return _PipProcess(args, cwd=cwd)


def pip_install_requirements(requirements_file: str, install_dir: Optional[str] = None, cwd: Optional[str] = None):
    assert os.path.exists(requirements_file)
    args = ["install", "-r", requirements_file]
    if install_dir is not None:
        args += ["--target", install_dir]
    return _PipProcess(args, cwd=cwd)
