"""macOS names the application menu after the running executable's bundle, so a
bare `python -m SciQLop.sciqlop_app` process shows "python" in the menu bar
whatever QCoreApplication.applicationName() says."""
import ctypes
import sys

import pytest

from SciQLop.core.common import macos


def test_no_op_off_macos(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(macos, "_load_core_foundation",
                        lambda: pytest.fail("CoreFoundation must not be touched off macOS"))
    macos.set_bundle_name("SciQLop")


def _live_bundle_name(cf) -> str:
    cf.CFBundleGetValueForInfoDictionaryKey.restype = ctypes.c_void_p
    cf.CFBundleGetValueForInfoDictionaryKey.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
    key = cf.CFStringCreateWithCString(None, b"CFBundleName", macos._UTF8)
    value = cf.CFBundleGetValueForInfoDictionaryKey(cf.CFBundleGetMainBundle(), key)
    buffer = ctypes.create_string_buffer(256)
    assert cf.CFStringGetCString(value, buffer, len(buffer), macos._UTF8)
    return buffer.value.decode()


@pytest.mark.skipif(sys.platform != "darwin", reason="reads the live CFBundle info dictionary")
def test_bundle_name_is_rewritten_on_macos():
    macos.set_bundle_name("SciQLop")
    assert _live_bundle_name(macos._load_core_foundation()) == "SciQLop"
