import os
import sys
import re
from itertools import filterfalse
from typing import Optional, List
from packaging.version import Version
from SciQLop import sciqlop_dependencies
from SciQLop.backend.common.python import run_python_module_cmd
from subprocess import run, PIPE

_requirements_rx = re.compile(r"^(?P<package>[\w\d_\-]+)(?P<operator>[=<>]+)?(?P<version>[\d\.\*]+)?")


def installed_version(package: str) -> Optional[str]:
    from importlib.metadata import version
    try:
        return version(package)
    except ModuleNotFoundError:
        return None


def check_dependency(dependency: str) -> bool:
    operators = {
        "==": lambda a, b: a == b,
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b
    }
    if matched := _requirements_rx.match(dependency):
        package, operator, version = matched.groups()
        if _installed_version := installed_version(package):
            if version is None:
                return True
            if operator is None:
                return _installed_version is not None
            if operator not in operators:
                raise ValueError(f"Invalid operator: {operator}")
            if '*' in version:
                if matched := re.compile(re.escape(version).replace(r'\*', '.*')).match(_installed_version):
                    version = matched.string
                else:
                    return False
            return operators[operator](Version(_installed_version), Version(version.replace('.*', '')))
    return False


def missing_dependencies() -> List[str]:
    dependencies = sciqlop_dependencies()
    return list(filterfalse(check_dependency, dependencies))


def install_missing_dependencies():
    return run(
        run_python_module_cmd("pip", "install", "--upgrade", *missing_dependencies()),
        stdout=PIPE, stderr=PIPE).returncode == 0


def ask_for_installation(missing_dependencies: List[str]):
    from tkinter import messagebox
    return messagebox.askyesno("SciQLop", "Would you like to install the following missing dependencies?\n\n"
                                          f"{', '.join(missing_dependencies)}")


def run_sciqlop():
    if not os.environ.get('SCIQLOP_BUNDLED', False):
        if missing := missing_dependencies():
            if ask_for_installation(missing):
                if not install_missing_dependencies():
                    from tkinter import messagebox
                    if not messagebox.askyesno("SciQLop", "Failed to install missing dependencies. Continue anyway?"):
                        return 1
    os.environ['SPEASY_SKIP_INIT_PROVIDERS'] = '1'
    return run(run_python_module_cmd("SciQLop.sciqlop_app")).returncode


def main():
    # return code 64 means restart
    while (return_code := run_sciqlop()) == 64:
        pass
    return return_code


if __name__ == '__main__':
    sys.exit(main())
