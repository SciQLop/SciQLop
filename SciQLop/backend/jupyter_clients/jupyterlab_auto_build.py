import sys
import os
import subprocess
from pathlib import Path
from jupyterlab.commands import build, build_check
from uuid import uuid4
from SciQLop.backend.common.terminal_messages import spawn_message_dialog, close_message_dialog, spawn_error_dialog
from SciQLop.backend.common.python import get_python


def main():
    try:
        if 'win' not in sys.platform and len(build_check()) != 0:
            widget_id = str(uuid4())
            print(spawn_message_dialog(widget_id, "Building JupyterLab..."))
            try:
                build()
            except Exception as e:
                print(spawn_error_dialog(widget_id, str(e)))
            print(close_message_dialog(widget_id))
    except Exception as e:
        print(str(e))
    subprocess.Popen([get_python()] + sys.argv[1:], env=dict(os.environ), stdout=sys.stdout, stderr=sys.stderr,
                     cwd=Path.home()).wait()


if __name__ == "__main__":
    main()
