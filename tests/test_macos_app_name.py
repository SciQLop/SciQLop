"""macOS names a process (menu bar, Dock, Cmd+Tab) after the bundle that owns
the *executable it runs*, never after QCoreApplication.applicationName(). A
bare `python -m SciQLop.sciqlop_app` therefore shows as "Python". The GUI is
run through a SciQLop.app written into the workspace instead, whose executable
is a symlink to the real interpreter; __PYVENV_LAUNCHER__ keeps the venv."""
import ctypes
import os
import subprocess
import sys
from pathlib import Path

import pytest

from SciQLop.core.common import macos


def test_set_bundle_name_is_a_no_op_off_macos(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(macos, "_load_core_foundation",
                        lambda: pytest.fail("CoreFoundation must not be touched off macOS"))
    macos.set_bundle_name("SciQLop")


def test_session_bundle_layout(tmp_path):
    interpreter = tmp_path / "python3.14"
    interpreter.write_text("")
    icon = tmp_path / "SciQLop.icns"
    icon.write_text("")

    stub = macos.write_session_bundle(tmp_path / "SciQLop.app", interpreter, "SciQLop", icon)

    assert stub == tmp_path / "SciQLop.app" / "Contents" / "MacOS" / "SciQLop"
    assert stub.is_symlink() and stub.resolve() == interpreter
    assert (tmp_path / "SciQLop.app/Contents/Resources/SciQLop.icns").resolve() == icon
    plist = (tmp_path / "SciQLop.app/Contents/Info.plist").read_text()
    for key, value in (("CFBundleExecutable", "SciQLop"), ("CFBundleName", "SciQLop"),
                       ("CFBundleDisplayName", "SciQLop"), ("CFBundleIconFile", "SciQLop.icns"),
                       ("CFBundleIdentifier", macos._BUNDLE_ID)):
        assert f"<key>{key}</key>" in plist and f"<string>{value}</string>" in plist


def test_session_bundle_without_icon_omits_the_key(tmp_path):
    macos.write_session_bundle(tmp_path / "S.app", tmp_path / "py", "SciQLop", None)
    assert "CFBundleIconFile" not in (tmp_path / "S.app/Contents/Info.plist").read_text()


def test_session_bundle_rewrite_follows_a_new_interpreter(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    stub = macos.write_session_bundle(tmp_path / "S.app", old, "SciQLop", None)
    macos.write_session_bundle(tmp_path / "S.app", new, "SciQLop", None)
    assert os.readlink(stub) == str(new)


def test_installed_icon_is_found_above_a_bundled_interpreter(tmp_path):
    app = tmp_path / "SciQLop.app" / "Contents" / "Resources"
    interpreter = app / "usr" / "local" / "bin" / "python3.14"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("")
    assert macos.installed_icon(interpreter) is None
    (app / "SciQLop.icns").write_text("")
    assert macos.installed_icon(interpreter) == app / "SciQLop.icns"


def test_session_interpreter_is_identity_off_macos(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert macos.session_interpreter(Path("/venv/bin/python"), tmp_path) == (Path("/venv/bin/python"), {})
    assert not (tmp_path / "SciQLop.app").exists()


def test_session_interpreter_falls_back_when_the_bundle_cannot_be_written(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(macos, "running_binary", lambda python: (_ for _ in ()).throw(OSError("no")))
    assert macos.session_interpreter(Path("/venv/bin/python"), tmp_path) == (Path("/venv/bin/python"), {})


def _live_bundle_name(cf) -> str:
    cf.CFBundleGetValueForInfoDictionaryKey.restype = ctypes.c_void_p
    cf.CFBundleGetValueForInfoDictionaryKey.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
    key = cf.CFStringCreateWithCString(None, b"CFBundleName", macos._UTF8)
    value = cf.CFBundleGetValueForInfoDictionaryKey(cf.CFBundleGetMainBundle(), key)
    buffer = ctypes.create_string_buffer(256)
    assert cf.CFStringGetCString(value, buffer, len(buffer), macos._UTF8)
    return buffer.value.decode()


darwin_only = pytest.mark.skipif(sys.platform != "darwin", reason="needs a real macOS process")


@darwin_only
def test_bundle_name_is_rewritten_on_macos():
    macos.set_bundle_name("SciQLop")
    assert _live_bundle_name(macos._load_core_foundation()) == "SciQLop"


@darwin_only
def test_session_interpreter_keeps_this_venv(tmp_path):
    stub, extra_env = macos.session_interpreter(Path(sys.executable), tmp_path)
    probe = "import sys; print(sys.executable); print(sys.prefix); print(sys.base_prefix)"
    out = subprocess.run([str(stub), "-c", probe], env={**os.environ, **extra_env},
                         capture_output=True, text=True, check=True).stdout.splitlines()
    assert out == [sys.executable, sys.prefix, sys.base_prefix]
    assert stub.parent.parent.parent.name == "SciQLop.app"
    assert extra_env["CFProcessPath"] == str(stub)


def test_gui_command_uses_the_session_interpreter_for_a_workspace(monkeypatch, tmp_path):
    from SciQLop import sciqlop_launcher
    monkeypatch.setattr(macos, "session_interpreter",
                        lambda python, ws: (ws / "SciQLop.app/Contents/MacOS/SciQLop", {"__PYVENV_LAUNCHER__": str(python)}))
    argv, env = sciqlop_launcher._gui_command(Path("/venv/bin/python"), {"SCIQLOP_WORKSPACE_DIR": str(tmp_path), "A": "1"})
    assert argv == [str(tmp_path / "SciQLop.app/Contents/MacOS/SciQLop"), "-m", "SciQLop.sciqlop_app"]
    assert env == {"SCIQLOP_WORKSPACE_DIR": str(tmp_path), "A": "1", "__PYVENV_LAUNCHER__": "/venv/bin/python"}


def test_gui_command_without_a_workspace_runs_python_directly():
    from SciQLop import sciqlop_launcher
    assert sciqlop_launcher._gui_command(Path("/venv/bin/python"), {}) == (["/venv/bin/python", "-m", "SciQLop.sciqlop_app"], {})
