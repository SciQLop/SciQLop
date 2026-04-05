import os
import shutil
import sys
from typing import List, Optional


def _find_bundled_uv() -> Optional[str]:
    """Check known bundled locations for uv (AppImage, MSIX)."""
    # AppImage: $APPDIR/opt/uv/uv
    appdir = os.environ.get("APPDIR")
    if appdir:
        candidate = os.path.join(appdir, "opt", "uv", "uv")
        if os.path.exists(candidate):
            return candidate
    # MSIX / Windows bundle: <package_root>/uv/uv.exe (sibling of python/)
    if os.environ.get("SCIQLOP_BUNDLED"):
        package_root = os.path.dirname(os.path.dirname(os.path.dirname(sys.executable)))
        candidate = os.path.join(package_root, "uv", "uv.exe" if sys.platform == "win32" else "uv")
        if os.path.exists(candidate):
            return candidate
    return None


def find_uv() -> Optional[str]:
    """Resolve the uv binary path.

    Checks bundled locations first (AppImage, MSIX), then falls back to
    shutil.which("uv").  Returns None if uv cannot be found.
    """
    return _find_bundled_uv() or shutil.which("uv")


def uv_command(*args: str) -> List[str]:
    """Build a command list for invoking uv with the given arguments.

    Raises RuntimeError if uv cannot be found.
    """
    uv_path = find_uv()
    if uv_path is None:
        raise RuntimeError("Could not find uv executable")
    return [uv_path, *args]
