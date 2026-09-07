"""macOS names the application menu after the *running executable's* bundle
(`CFBundleName`), never after QCoreApplication.applicationName(). SciQLop's GUI
is a bare interpreter spawned by the launcher, so its menu bar reads "python".
CFBundleGetInfoDictionary() returns the bundle's own mutable dictionary; writing
the name there before AppKit starts fixes the menu bar, and Qt's "About/Quit
<name>" items with it (qt_mac_applicationName() reads the same key).

The Dock (Cmd+Tab) and Activity Monitor read a separate LaunchServices record
instead, only reachable through the private `_LSSetApplicationInformationItem`
— the same SPI Java's -Xdock:name, WebKit and Chromium use, see
https://github.com/tiancaiamao/devdraw/blob/master/cocoa-screen.m (setprocname).
Kept ctypes-only so the thin launcher install can use it without pyobjc."""
import ctypes
import logging
import sys

_CORE_FOUNDATION = "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
_LAUNCH_SERVICES = ("/System/Library/Frameworks/CoreServices.framework/Frameworks/"
                    "LaunchServices.framework/LaunchServices")
_UTF8 = 0x08000100
_LS_DEFAULT_SESSION = -2
_NAME_KEYS = (b"CFBundleName", b"CFBundleDisplayName")

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


def _load_launch_services():
    ls = ctypes.CDLL(_LAUNCH_SERVICES)
    ls._LSGetCurrentApplicationASN.restype = ctypes.c_void_p
    ls._LSSetApplicationInformationItem.restype = ctypes.c_int32
    ls._LSSetApplicationInformationItem.argtypes = [
        ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    return ls


def _set_info_string(cf, info, key: bytes, value: bytes) -> None:
    cf_key = cf.CFStringCreateWithCString(None, key, _UTF8)
    cf_value = cf.CFStringCreateWithCString(None, value, _UTF8)
    cf.CFDictionarySetValue(info, cf_key, cf_value)
    cf.CFRelease(cf_key)
    cf.CFRelease(cf_value)


def _set_bundle_info_names(cf, name: bytes) -> None:
    info = cf.CFBundleGetInfoDictionary(cf.CFBundleGetMainBundle())
    if not info:
        return
    for key in _NAME_KEYS:
        _set_info_string(cf, info, key, name)


def _set_launch_services_display_name(cf, name: bytes) -> None:
    try:
        ls = _load_launch_services()
        key = ctypes.c_void_p.in_dll(ls, "_kLSDisplayNameKey").value
    except (OSError, AttributeError, ValueError) as e:
        log.debug("LaunchServices display-name SPI unavailable: %s", e)
        return
    cf_value = cf.CFStringCreateWithCString(None, name, _UTF8)
    status = ls._LSSetApplicationInformationItem(
        _LS_DEFAULT_SESSION, ls._LSGetCurrentApplicationASN(), key, cf_value, None)
    cf.CFRelease(cf_value)
    if status != 0:
        log.debug("_LSSetApplicationInformationItem failed: %d", status)


def set_bundle_name(name: str) -> None:
    """Rename this process in the macOS menu bar, Dock and Cmd+Tab switcher.
    Must run before the QApplication (hence NSApplication) is created.
    No-op elsewhere."""
    if sys.platform != "darwin":
        return
    cf = _load_core_foundation()
    _set_bundle_info_names(cf, name.encode())
    _set_launch_services_display_name(cf, name.encode())
