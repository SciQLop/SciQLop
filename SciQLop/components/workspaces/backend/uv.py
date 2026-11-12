import os
import re
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
    # sys.executable = <root>/python/python.exe → two dirname calls
    if os.environ.get("SCIQLOP_BUNDLED"):
        package_root = os.path.dirname(os.path.dirname(sys.executable))
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


def error_detail(exc: Exception) -> str:
    """Human-readable cause for a failed uv run.

    ``str(CalledProcessError)`` is only "… returned non-zero exit status N";
    the actual reason (proxy/TLS/auth) is in ``.stderr``. Prefer it so the
    failure is diagnosable instead of a bare "Failed".
    """
    stderr = (getattr(exc, "stderr", None) or "").strip()
    return stderr or str(exc)


_COMMAND_LINE_PREAMBLE = re.compile(r"\Auv command failed \(exit -?\d+\):\n.*\n\n", re.MULTILINE)

# What uv says (lower-cased) -> what it means for the user. First match wins.
_PLAIN_REASONS = {
    "no solution found": "It does not work with the packages already in this workspace.",
    "not found in the package registry": "No such package was found for this platform and Python version.",
    "permission denied": "SciQLop is not allowed to write in this workspace's folder.",
    "no space left on device": "The disk is full.",
    "failed to fetch": "The package index could not be reached. Check your connection and the proxy in Settings.",
    "error sending request": "The package index could not be reached. Check your connection and the proxy in Settings.",
    "dns error": "The package index could not be reached. Check your connection and the proxy in Settings.",
    "timed out": "The package index could not be reached. Check your connection and the proxy in Settings.",
}


def error_summary(exc: Exception) -> str:
    """What to show for a failed install or update: a plain sentence when the cause is a known one, then
    uv's own reason. The command line stays out; error_detail() still has everything for the log."""
    reason = _COMMAND_LINE_PREAMBLE.sub("", error_detail(exc)).strip()
    lowered = reason.lower()
    headline = next((plain for said, plain in _PLAIN_REASONS.items() if said in lowered), None)
    return f"{headline}\n\n{reason}" if headline else reason
