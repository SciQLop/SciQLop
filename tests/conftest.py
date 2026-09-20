import os
import platform
import tempfile
from pathlib import Path

import pytest

# Captured at collection time, before any fixture or test can run --
# Workspace.activate() (workspaces/backend/workspace.py) deliberately
# os.chdir()s into the workspace directory whenever a real
# SciQLopMainWindow is constructed (several test files do this directly,
# and the session-scoped `main_window` fixture in fixtures.py does too),
# so relative paths resolve inside the active workspace. Restored by
# _restore_cwd below after every test, so that behavior can't leak into a
# later test that resolves a path relative to the original cwd.
_ORIGINAL_CWD = os.getcwd()

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


def _is_xdist_master(config) -> bool:
    """Mirrors pytest_xvfb's own is_xdist_master(): true for the xdist
    controller process, which dispatches tests to workers and never runs one
    itself. pytest-xvfb already skips starting Xvfb for it; this module must
    skip building a real QApplication for the same reason, or -n crashes the
    whole run before a single test executes (see tests/test_xdist_master_boot.py).
    """
    import os as _os
    return config.getoption("dist", "no") != "no" and not _os.environ.get("PYTEST_XDIST_WORKER")


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
    # Browser-free test sessions: WebChannelPage (welcome/appstore) skips the
    # QWebEngineView, so plot/panel tests do not pay for Chromium renderer
    # processes. setdefault lets a dev force the real browser back with
    # SCIQLOP_TEST_NO_WEBENGINE=0 when working on the pages themselves.
    os.environ.setdefault("SCIQLOP_TEST_NO_WEBENGINE", "1")
    if platform.system() == "Windows":
        os.environ["APPDATA"] = str(_config_dir)

    if _is_xdist_master(config):
        # The controller dispatches work to workers and never collects or runs
        # a test itself, so it never needs a display or a real QApplication —
        # same reasoning pytest-xvfb applies to skip starting Xvfb for it. Each
        # worker is a separate process (PYTEST_XDIST_WORKER set) that re-enters
        # this hook and takes the normal path below.
        return

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
def _restore_cwd():
    """Undo Workspace.activate()'s os.chdir() (see _ORIGINAL_CWD above) after
    every test, regardless of which test -- or which session-scoped fixture
    -- triggered it. A per-test-file fixture only restores to whatever cwd
    happened to be current when that file's tests started, which can
    already be a leaked workspace directory from an earlier test; this
    restores the one true baseline captured at collection time instead.
    """
    yield
    os.chdir(_ORIGINAL_CWD)


@pytest.fixture(autouse=True)
def _clean_vp_state():
    _cleanup_vp_state()
    yield
    _cleanup_vp_state()


def _main_windows():
    import sys
    import shiboken6
    mod = sys.modules.get("SciQLop.core.ui.mainwindow")
    if mod is None:
        return []
    from PySide6.QtWidgets import QApplication
    return [w for w in QApplication.topLevelWidgets()
            if isinstance(w, mod.SciQLopMainWindow) and shiboken6.isValid(w)]


def _standalone_panels():
    """Top-level plot panels, i.e. built by a test directly (`TimeSyncPanel(...)`)
    rather than docked in a main window. Each one builds a ProductSearchOverlay
    whose ProductsFlatFilterModel re-scores the whole product tree on every
    ProductsModel change, so leaked ones make every later test cost more."""
    import shiboken6
    from PySide6.QtWidgets import QApplication
    from SciQLopPlots import SciQLopMultiPlotPanel
    return [w for w in QApplication.topLevelWidgets()
            if isinstance(w, SciQLopMultiPlotPanel) and shiboken6.isValid(w)]


@pytest.fixture(autouse=True)
def _current_event_loop_is_sciqlops():
    """`asyncio.run()` (used by several tests) leaves the main thread with no
    current loop, and Python 3.14's `asyncio.get_event_loop()` then raises for
    every later test that builds an AgentChatDock."""
    import asyncio
    import sys
    app_mod = sys.modules.get("SciQLop.core.sciqlop_application")
    loop = getattr(app_mod, "_event_loop", None)
    if loop is not None:
        asyncio.set_event_loop(loop)
    yield


@pytest.fixture(autouse=True)
def _release_gui_leftovers():
    """Every SciQLopMainWindow is a ~1GB widget tree, and close() only hides it.
    Tests build throwaway windows (and the shared one outlives every test), so
    whatever a test leaves behind accumulates until the machine runs out of
    memory. Destroy the extra windows this test created, restore
    `app.main_window`, and remove panels it added to the shared window."""
    import shiboken6
    from PySide6.QtWidgets import QApplication
    from tests.fixtures import destroy_main_window
    before_windows = {id(w) for w in _main_windows()}
    before_panels = {id(w) for w in _standalone_panels()}
    app = QApplication.instance()
    main = getattr(app, "main_window", None)
    panels_before = set(main.plot_panels()) if main is not None and shiboken6.isValid(main) else None
    shortcuts_before = dict(app._quickstart_shortcuts)
    yield
    app._quickstart_shortcuts.clear()
    app._quickstart_shortcuts.update(shortcuts_before)
    destroyed = False
    for w in _main_windows():
        if id(w) not in before_windows:
            destroy_main_window(w)
            destroyed = True
    for w in _standalone_panels():
        if id(w) not in before_panels:
            w.hide()
            w.deleteLater()
            destroyed = True
    if main is not None and shiboken6.isValid(main):
        app.main_window = main
        if panels_before is not None:
            for name in set(main.plot_panels()) - panels_before:
                main.remove_panel(name)
                destroyed = True
    if destroyed:
        from PySide6 import QtCore
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


@pytest.fixture(autouse=True)
def _no_blocking_modal_dialogs(monkeypatch):
    """Nobody can answer a modal dialog in a headless run, so it would block
    until the timeout kills the whole process. Fail at the call site instead,
    naming the dialog. A test that expects one patches it itself, which wins
    over this since it runs later."""
    from PySide6.QtWidgets import QMessageBox

    def _fail(kind):
        def blocked(parent, title, text, *args, **kwargs):
            raise AssertionError(f"unexpected blocking QMessageBox.{kind}: {title!r}: {text}")
        return staticmethod(blocked)

    for kind in ("question", "warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, kind, _fail(kind))


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
    clean_before = [p for p in registry._providers if not p.is_dirty()]
    yield
    registry._providers[:] = [p for p in registry._providers if id(p) in snapshot]
    _forget_dirty_state(clean_before)


def _forget_dirty_state(providers):
    """A test that edits a shared provider (e.g. the main window's "My Catalogs")
    and never saves leaves it dirty; every later ``mw.close()`` then pops the
    "Unsaved catalog changes" dialog."""
    for p in providers:
        p._dirty_catalogs.clear()
        p._provider_dirty = False


_MAX_RSS_MB = int(os.environ.get("SCIQLOP_TEST_MAX_RSS_MB", "6144"))
_RSS_LOG = os.environ.get("SCIQLOP_TEST_RSS_LOG")


def _rss_mb() -> float:
    import psutil
    return psutil.Process().memory_info().rss / 2**20


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item):
    """The GUI suite accumulates Qt state in one process; without a ceiling a
    full run takes the whole machine down. Abort cleanly (fixtures torn down,
    Xvfb stopped) instead. SCIQLOP_TEST_RSS_LOG=<file> logs RSS per test."""
    rss = _rss_mb()
    if _RSS_LOG:
        from PySide6.QtWidgets import QApplication
        with open(_RSS_LOG, "a") as f:
            f.write(f"{rss:.0f} {item.nodeid} widgets={len(QApplication.allWidgets())}\n")
    if rss > _MAX_RSS_MB:
        pytest.exit(f"RSS {rss:.0f}MB > SCIQLOP_TEST_MAX_RSS_MB={_MAX_RSS_MB} "
                    f"after {item.nodeid}", returncode=3)


def pytest_sessionfinish(session):
    if not _RSS_LOG:
        return
    import collections
    from PySide6.QtWidgets import QApplication
    counts = collections.Counter(type(w).__name__ for w in QApplication.allWidgets())
    with open(_RSS_LOG + ".widgets", "w") as f:
        f.writelines(f"{n} {name}\n" for name, n in counts.most_common(30))


def pytest_unconfigure(config):
    import shutil
    shutil.rmtree(_test_tmp, ignore_errors=True)
