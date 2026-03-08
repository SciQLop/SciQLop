import os
import shutil
from typing import List, Optional


def find_uv() -> Optional[str]:
    """Resolve the uv binary path.

    Checks APPDIR env var first for bundled installs (AppImage ships uv
    at $APPDIR/opt/uv/uv), then falls back to shutil.which("uv").
    Returns None if uv cannot be found.
    """
    appdir = os.environ.get("APPDIR")
    if appdir:
        bundled = os.path.join(appdir, "opt", "uv", "uv")
        if os.path.exists(bundled):
            return bundled
    return shutil.which("uv")


def uv_command(*args: str) -> List[str]:
    """Build a command list for invoking uv with the given arguments.

    Raises RuntimeError if uv cannot be found.
    """
    uv_path = find_uv()
    if uv_path is None:
        raise RuntimeError("Could not find uv executable")
    return [uv_path, *args]
