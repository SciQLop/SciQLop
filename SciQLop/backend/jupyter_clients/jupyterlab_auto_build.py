import sys
import os
import subprocess
from pathlib import Path
from jupyterlab.commands import build, build_check


def main():
    if len(build_check()) != 0:
        build()
    subprocess.Popen([sys.executable] + sys.argv[1:], env=dict(os.environ), stdout=sys.stdout, stderr=sys.stderr,
                     cwd=Path.home()).wait()


if __name__ == "__main__":
    print(os.environ)
    main()
