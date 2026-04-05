import os
import platform
import tempfile
from pathlib import Path

import pytest

# Temp root created early (before fixtures) for env var paths.
# Using tempfile directly because tmp_path_factory isn't available in hooks.
_test_tmp = Path(tempfile.mkdtemp(prefix="sciqlop_test_"))
_config_dir = _test_tmp / "config"
_data_dir = _test_tmp / "data"
_workspace_dir = _test_tmp / "workspace"
_config_dir.mkdir()
_data_dir.mkdir()
_workspace_dir.mkdir()


def _symlink_if_exists(real_dir: Path, target_parent: Path, name: str):
    """Create a symlink target_parent/name -> real_dir if real_dir exists."""
    if real_dir.exists():
        target = target_parent / name
        if not target.exists():
            target.symlink_to(real_dir)


def _preserve_speasy_dirs():
    """Symlink speasy's config/cache/data dirs from the real home into temp dirs.

    Without this, redirecting XDG vars empties speasy's cache, causing
    massive re-downloads. speasy uses appdirs which reads XDG_DATA_HOME,
    XDG_CACHE_HOME, and XDG_CONFIG_HOME.
    """
    home = Path.home()
    real_data = Path(os.environ.get("XDG_DATA_HOME", str(home / ".local" / "share")))
    real_cache = Path(os.environ.get("XDG_CACHE_HOME", str(home / ".cache")))
    real_config = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config")))

    _symlink_if_exists(real_data / "speasy", _data_dir, "speasy")
    _symlink_if_exists(real_config / "speasy", _config_dir, "speasy")

    cache_dir = _test_tmp / "cache"
    cache_dir.mkdir(exist_ok=True)
    _symlink_if_exists(real_cache / "speasy", cache_dir, "speasy")
    os.environ["XDG_CACHE_HOME"] = str(cache_dir)


def pytest_configure(config):
    # These env vars MUST be set before any SciQLop or speasy import.
    # pytest_configure runs before collection, so no test module is imported yet.
    _preserve_speasy_dirs()
    os.environ["XDG_CONFIG_HOME"] = str(_config_dir)
    os.environ["XDG_DATA_HOME"] = str(_data_dir)
    os.environ["SCIQLOP_WORKSPACE_DIR"] = str(_workspace_dir)
    os.environ["SPEASY_SKIP_INIT_PROVIDERS"] = "1"
    os.environ["SCIQLOP_DEBUG"] = "1"
    os.environ["INSIDE_SCIQLOP"] = "1"
    if platform.system() == "Windows":
        os.environ["APPDATA"] = str(_config_dir)

    # Qt OpenGL attributes — must be set before QApplication creation.
    from PySide6 import QtCore
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseDesktopOpenGL, True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts, True)

    if platform.system() == "Linux":
        os.environ["QT_QPA_PLATFORM"] = "xcb"


@pytest.fixture(scope="session", autouse=True)
def sciqlop_test_env():
    """Expose the test temp root to fixtures that need it."""
    yield _test_tmp


def pytest_unconfigure(config):
    import shutil
    shutil.rmtree(_test_tmp, ignore_errors=True)
