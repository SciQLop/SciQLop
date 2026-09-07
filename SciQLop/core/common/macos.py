"""macOS names a process — menu bar, Dock, Cmd+Tab — after the bundle that
owns the *executable it runs*, never after QCoreApplication.applicationName().
SciQLop's GUI is a bare interpreter spawned by the launcher, so it showed as
"Python". Two layers fix that:

* `session_interpreter()` runs the GUI through a SciQLop.app written into the
  workspace, whose executable is a symlink to the real interpreter binary.
  LaunchServices then reports "SciQLop" (and the SciQLop icon) everywhere.
  `__PYVENV_LAUNCHER__` is CPython's own macOS hook for launchers that run
  Python as a subprocess: sys.executable and the venv still resolve to
  <venv>/bin/python — see Modules/getpath.py "CALCULATE executable".
* `set_bundle_name()` patches CFBundleName in-process for direct
  `python -m SciQLop.sciqlop_app` runs; that covers the menu bar only.

Kept ctypes/stdlib-only so the thin launcher install can use it without pyobjc."""
import ctypes
import logging
import os
import subprocess
import sys
from pathlib import Path

_CORE_FOUNDATION = "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
_UTF8 = 0x08000100
_NAME_KEYS = (b"CFBundleName", b"CFBundleDisplayName")
_BUNDLE_ID = "com.LPP.SciQLop.session"
_ICON_NAME = "SciQLop.icns"
# Framework builds exec an inner Python.app binary; ask the interpreter which
# Mach-O it really runs so the symlink never lands on a stub.
_RUNNING_BINARY = ("import ctypes, os; b = ctypes.create_string_buffer(4096); "
                   "ctypes.CDLL(None).proc_pidpath(os.getpid(), b, 4096); print(b.value.decode())")
_INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleExecutable</key><string>{name}</string>
    <key>CFBundleName</key><string>{name}</string>
    <key>CFBundleDisplayName</key><string>{name}</string>
    <key>CFBundleIdentifier</key><string>{bundle_id}</string>{icon}
    <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
"""

log = logging.getLogger(__name__)


def _load_core_foundation():
    cf = ctypes.CDLL(_CORE_FOUNDATION)
    cf.CFBundleGetMainBundle.restype = ctypes.c_void_p
    cf.CFBundleGetInfoDictionary.restype = ctypes.c_void_p
    cf.CFBundleGetInfoDictionary.argtypes = [ctypes.c_void_p]
    cf.CFStringCreateWithCString.restype = ctypes.c_void_p
    cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
    cf.CFDictionarySetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    return cf


def _set_info_string(cf, info, key: bytes, value: bytes) -> None:
    cf_key = cf.CFStringCreateWithCString(None, key, _UTF8)
    cf_value = cf.CFStringCreateWithCString(None, value, _UTF8)
    cf.CFDictionarySetValue(info, cf_key, cf_value)
    cf.CFRelease(cf_key)
    cf.CFRelease(cf_value)


def set_bundle_name(name: str) -> None:
    """Rename this process in the macOS menu bar. Must run before the
    QApplication (hence NSApplication) is created. No-op elsewhere."""
    if sys.platform != "darwin":
        return
    cf = _load_core_foundation()
    info = cf.CFBundleGetInfoDictionary(cf.CFBundleGetMainBundle())
    if not info:
        return
    for key in _NAME_KEYS:
        _set_info_string(cf, info, key, name.encode())


def running_binary(python: Path) -> Path:
    out = subprocess.run([str(python), "-I", "-c", _RUNNING_BINARY],
                         capture_output=True, text=True, check=True).stdout
    return Path(out.strip())


def installed_icon(interpreter: Path) -> Path | None:
    """The installed SciQLop.app's icon when the interpreter is the bundled one."""
    candidates = (parent / "Contents" / "Resources" / _ICON_NAME for parent in interpreter.resolve().parents)
    return next((icon for icon in candidates if icon.exists()), None)


def _replace_symlink(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(target)


def write_session_bundle(bundle: Path, interpreter: Path, name: str, icon: Path | None) -> Path:
    """Write `bundle` as an .app whose executable `name` is `interpreter`; returns that executable."""
    stub = bundle / "Contents" / "MacOS" / name
    _replace_symlink(stub, interpreter)
    icon_key = ""
    if icon is not None:
        _replace_symlink(bundle / "Contents" / "Resources" / icon.name, icon)
        icon_key = f"\n    <key>CFBundleIconFile</key><string>{icon.name}</string>"
    (bundle / "Contents" / "Info.plist").write_text(
        _INFO_PLIST.format(name=name, bundle_id=_BUNDLE_ID, icon=icon_key), encoding="utf-8")
    return stub


def session_interpreter(python: Path, workspace_dir: Path) -> tuple[Path, dict[str, str]]:
    """(executable, extra env) to run the GUI with `python` so macOS names it
    SciQLop. Off macOS, or if the bundle cannot be written, `python` as-is."""
    if sys.platform != "darwin":
        return python, {}
    try:
        interpreter = running_binary(python)
        stub = write_session_bundle(workspace_dir / "SciQLop.app", interpreter, "SciQLop",
                                    installed_icon(interpreter))
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("Cannot set up the SciQLop.app session bundle, the process will show as Python: %s", e)
        return python, {}
    return stub, {"__PYVENV_LAUNCHER__": str(python)}
