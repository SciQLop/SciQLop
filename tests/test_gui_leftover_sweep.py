"""Standalone panels tests build (`TimeSyncPanel(parent=None)`, ...) are Python-created
objects with no C++ parent, so Shiboken owns them. At interpreter finalization Shiboken
force-destroys every still-owned wrapped object outside Qt's own event-loop teardown --
fatal for a QRhiWidget plot (SIGSEGV in QRhi::removeCleanupCallback, seen on CI after
SciQLopPlots 0.37.0) and a use-after-free for a QtAds dock tree.

pytest-qt's own per-test cleanup calls `deleteLater()` then a plain `processEvents()`,
which does not reliably deliver DeferredDelete, so such a widget can still be alive (and
still Python-owned) at session end. conftest's `_release_leftover_widget_ownership` runs
at `pytest_sessionfinish` and detaches Python ownership from whatever is left, so
Shiboken's finalize sweep skips it instead of destroying it.
"""

import shiboken6
from PySide6.QtWidgets import QWidget

from tests.conftest import _release_leftover_widget_ownership, _shiboken_object_function
from tests.fixtures import *  # noqa: F401,F403


def _has_ownership(w):
    """`Shiboken::Object::hasOwnership` -- the exact predicate Shiboken's finalize sweep
    (`PySide::destructionVisitor`) tests. Not exposed in the Python module, so call the
    exported symbol the same way conftest does."""
    import ctypes

    return bool(_shiboken_object_function("hasOwnership", restype=ctypes.c_bool)(id(w)))


def test_release_detaches_python_ownership_from_a_leftover_widget(qtbot, qapp):
    w = QWidget()
    assert shiboken6.ownedByPython(w)

    _release_leftover_widget_ownership([w])

    assert shiboken6.isValid(w)
    assert not shiboken6.ownedByPython(w), (
        "still Python-owned -- Shiboken's interpreter-exit sweep would force-destroy it"
    )


def test_release_is_harmless_with_nothing_to_release(qtbot, qapp):
    with qtbot.captureExceptions() as exceptions:
        _release_leftover_widget_ownership([])
    assert exceptions == []


def test_release_skips_an_already_destroyed_widget(qtbot, qapp):
    w = QWidget()
    shiboken6.delete(w)

    with qtbot.captureExceptions() as exceptions:
        _release_leftover_widget_ownership([w])
    assert exceptions == []


def test_release_covers_a_parented_python_subclass_widget(qtbot, qapp):
    """A Python-subclass widget keeps Python ownership even with a C++ parent, so
    releasing only top-level widgets would leave it for the sweep to force-destroy.
    `TimeSyncPanel(parent=container)` is exactly the shape the CI crash recursed into."""
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel

    container = QWidget()
    panel = TimeSyncPanel(parent=container, name="parented_panel")
    assert panel.parent() is container
    assert _has_ownership(panel), "expected a parented Python-subclass widget to be owned"

    _release_leftover_widget_ownership([container, panel])

    assert shiboken6.isValid(panel)
    assert not _has_ownership(panel), (
        "still Python-owned -- Shiboken's interpreter-exit sweep would force-destroy it"
    )
