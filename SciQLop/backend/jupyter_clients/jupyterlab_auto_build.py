import sys
from jupyterlab.commands import build, build_check
from uuid import uuid4
from SciQLop.backend.common.terminal_messages import spawn_message_dialog, close_message_dialog, spawn_error_dialog
from jupyterlab.labapp import main as jupyterlab_main


def build_if_needed():
    if 'win' not in sys.platform and len(build_check()) != 0:
        widget_id = str(uuid4())
        print(spawn_message_dialog(widget_id, "Building JupyterLab..."))
        try:
            build()
        except Exception as e:
            print(spawn_error_dialog(widget_id, str(e)))
        print(close_message_dialog(widget_id))


def main():
    build_if_needed()
    jupyterlab_main(sys.argv[1:])


if __name__ == "__main__":
    main()
