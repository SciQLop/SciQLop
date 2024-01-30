import os
from typing import List, Optional
from .python import get_python
from .process import Process


class _PipProcess(Process):
    def __init__(self, args: List[str], cwd: Optional[str] = None):
        super().__init__(get_python(), ["-m", "pip"] + args, cwd=cwd)


def pip_install_packages(packages: List[str], install_dir: Optional[str] = None, cwd: Optional[str] = None):
    args = ["install"] + packages
    if install_dir is not None:
        args += ["--target", install_dir]
    return _PipProcess(args, cwd=cwd)


def install_pip_package(package: str, install_dir: Optional[str] = None, cwd: Optional[str] = None):
    return pip_install_packages([package], install_dir, cwd=cwd)


def pip_install_requirements(requirements_file: str, install_dir: Optional[str] = None, cwd: Optional[str] = None):
    assert os.path.exists(requirements_file)
    args = ["install", "-r", requirements_file]
    if install_dir is not None:
        args += ["--target", install_dir]
    return _PipProcess(args, cwd=cwd)
