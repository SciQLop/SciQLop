"""macOS names the application menu after the *running executable's* bundle
(`CFBundleName`), never after QCoreApplication.applicationName(). SciQLop's GUI
is a bare interpreter spawned by the launcher, so its menu bar reads "python".
CFBundleGetInfoDictionary() returns the bundle's own mutable dictionary; writing
the name there before AppKit starts fixes the menu bar, and Qt's "About/Quit
<name>" items with it (qt_mac_applicationName() reads the same key).
Kept ctypes-only so the thin launcher install can use it without pyobjc."""
import ctypes
import sys

_CORE_FOUNDATION = "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
_UTF8 = 0x08000100
_NAME_KEYS = (b"CFBundleName", b"CFBundleDisplayName")


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
