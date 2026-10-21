"""Implementation of %restart line magic — restart SciQLop into the same workspace."""
from IPython.core.error import UsageError


def restart_magic(line: str):
    """%restart

    Restart SciQLop into the current workspace, e.g. after ``%install`` updated
    an already-imported package. Same as the Restart button in the settings.
    """
    if line.strip():
        raise UsageError("Usage: %restart  (takes no arguments)")
    from SciQLop.user_api.threading import invoke_on_main_thread
    from SciQLop import sciqlop_app
    print("Restarting SciQLop…")
    invoke_on_main_thread(sciqlop_app.restart_sciqlop)
