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
    """Symlink speasy's config/cache/data dirs, and the smart-search caches,
    from the real home into temp dirs.

    Without this, redirecting XDG vars empties speasy's cache, causing
    massive re-downloads. speasy uses appdirs which reads XDG_DATA_HOME,
    XDG_CACHE_HOME, and XDG_CONFIG_HOME. The smart-search caches are also
    symlinked through (both smart_search_index with products.pkl and
    smart_search_models with the model2vec snapshot), scoped to just those
    subdirectories (not all of ~/.cache/sciqlop), so tests/test_smart_search_benchmark.py
    can access the real product corpus and load real models instead of skipping
    unconditionally. Both are required for load_real_corpus() in the benchmark
    harness to succeed.
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

    sciqlop_cache_dir = cache_dir / "sciqlop"
    sciqlop_cache_dir.mkdir(exist_ok=True)
    # These symlinks deliberately punch through test isolation to read the user's real caches.
    # Reads are safe today, but a future test that drives a real reindex (instead of overriding
    # cache_dir explicitly like test_smart_search_registry.py does) would silently corrupt the user's
    # real 77157-entry product corpus — treat these as read-only facades.
    _symlink_if_exists(real_cache / "sciqlop" / "smart_search_index", sciqlop_cache_dir, "smart_search_index")
    _symlink_if_exists(real_cache / "sciqlop" / "smart_search_models", sciqlop_cache_dir, "smart_search_models")

    os.environ["XDG_CACHE_HOME"] = str(cache_dir)


# trylast so pytest-xvfb's own pytest_configure — which starts Xvfb and exports
# DISPLAY — has already run: conftest hooks are called before installed plugins',
# and the QApplication built at the end of this hook aborts the whole process
# ("could not connect to display", exit 134) when no display exists yet. Only CI
# hits it; a dev shell has a real DISPLAY, and the canonical local run passes
# --no-xvfb. Reproduce with: env -u DISPLAY -u WAYLAND_DISPLAY uv run pytest
@pytest.hookimpl(trylast=True)
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

    # Pre-initialize tscat's sqlite backend on the main thread so its alembic
    # migration runs exactly once. tscat.base.backend() is a lazy unsynchronized
    # singleton; the tscat_gui driver QThread races the test thread on first
    # access and re-runs the migration ("table alembic_version already exists"
    # / "not an error" on retry). Touching it here pins the init to one thread.
    from tscat.base import backend as _tscat_backend
    _tscat_backend()

    # Create the QApplication here (as SciQLopApp, not a plain QApplication)
    # so module-level imports of SciQLop user_api (which transitively import
    # core.models.ProductsModel) work during test collection. This ensures
    # ProductsModel.instance() doesn't fail with "application static was used
    # without a QCoreApplication instance". Using SciQLopApp specifically
    # matters: Qt only allows one QApplication per process, so if a plain
    # QApplication were created here, the qapp fixture (qapp_cls=SciQLopApp)
    # could never construct the real SciQLopApp later, and any fixture
    # calling sciqlop_app()/sciqlop_event_loop() would raise TypeError.
    from SciQLop.core.sciqlop_application import SciQLopApp
    SciQLopApp.instance() or SciQLopApp([])


@pytest.fixture(scope="session")
def qapp_cls():
    from SciQLop.core.sciqlop_application import SciQLopApp
    return SciQLopApp


@pytest.fixture(scope="session", autouse=True)
def sciqlop_test_env():
    """Expose the test temp root to fixtures that need it."""
    yield _test_tmp



def _cleanup_vp_state():
    import sys
    app_mod = sys.modules.get("PySide6.QtWidgets")
    app = app_mod.QApplication.instance() if app_mod else None
    reg_mod = sys.modules.get("SciQLop.user_api.virtual_products.registry")
    if reg_mod is not None:
        registry = getattr(reg_mod, "_registry", None)
        if registry is not None:
            for entry in registry._entries.values():
                if entry.panel is not None:
                    try:
                        panel = entry.panel
                        panel.clear()
                        dock = panel.parent()
                        if dock is not None:
                            dock.closeDockWidget()
                            dock.deleteLater()
                    except RuntimeError:
                        pass
                    entry.panel = None
            registry._entries.clear()
    backend_mod = sys.modules.get("SciQLop.user_api.plot._speasy_backend")
    if backend_mod is not None:
        backend_mod._current_panel = None
    if app is not None:
        app.processEvents()
        app.processEvents()


@pytest.fixture(autouse=True)
def _clean_vp_state():
    _cleanup_vp_state()
    yield
    _cleanup_vp_state()


@pytest.fixture(autouse=True)
def _isolate_catalog_registry():
    """Snapshot/restore the global CatalogRegistry around each test.

    Catalog providers self-register in their __init__. Tests that instantiate
    a provider ad-hoc (e.g. ``TscatCatalogProvider()`` in
    ``test_catalog_attribute_spec.py``) leave the instance in the singleton
    registry forever, and ``CatalogService._find_provider`` returns the FIRST
    provider matching the name — so later tests using a freshly-built provider
    end up routing through the leaked one and miss the expected signals.
    Snapshot before, restore after, so module-scoped fixture providers stay
    intact while function-local providers don't bleed across.
    """
    import sys
    reg_mod = sys.modules.get("SciQLop.components.catalogs.backend.registry")
    if reg_mod is None:
        yield
        return
    registry = reg_mod.CatalogRegistry.instance()
    snapshot = set(id(p) for p in registry._providers)
    yield
    registry._providers[:] = [p for p in registry._providers if id(p) in snapshot]


def pytest_unconfigure(config):
    import shutil
    shutil.rmtree(_test_tmp, ignore_errors=True)
