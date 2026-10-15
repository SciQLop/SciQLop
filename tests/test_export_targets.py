"""sciqlop.export_targets (spec §4.3): file formats for PlotPanel.save and the Export menu."""
from .fixtures import *  # noqa: F401,F403
import pytest

from SciQLop.core.export_targets import EXPORT_TARGETS, ExportTarget, target_for
from SciQLop.core.extensions import owned_by


@pytest.fixture(autouse=True)
def core_extension_points(qapp):
    from SciQLop.components.extension_points import prepare_extension_points
    prepare_extension_points()


@pytest.fixture
def csv_target(qapp):
    written = []
    with owned_by("et_demo"):
        EXPORT_TARGETS.contribute(ExportTarget(
            "et_demo.csv", "CSV", (".csv",),
            write=lambda panel, path, w, h, s: written.append((panel, path, w, h, s)),
            scalable=False))
    yield written
    EXPORT_TARGETS.remove_owner("et_demo")


def test_core_targets_cover_the_formats_save_always_had(qapp):
    for suffix in (".png", ".pdf", ".jpg", ".jpeg", ".bmp"):
        assert EXPORT_TARGETS.owner_of(target_for(f"x{suffix}").id) == "sciqlop"


def test_suffix_lookup_ignores_case(csv_target):
    assert target_for("A.CSV").id == "et_demo.csv"


def test_save_writes_through_a_plugin_target(plot_panel, csv_target, tmp_path):
    plot_panel.save(str(tmp_path / "a.csv"), width=10, height=20)
    (panel, path, w, h, s), = csv_target
    assert panel is plot_panel and path.endswith("a.csv") and (w, h, s) == (10, 20, None)


def test_a_core_suffix_claimed_by_a_plugin_stays_core(qapp):
    with owned_by("et_demo"):
        EXPORT_TARGETS.contribute(ExportTarget("et_demo.png", "Fancy PNG", (".png",), write=lambda *a: None))
    try:
        assert target_for("x.png").id == "sciqlop.png"
    finally:
        EXPORT_TARGETS.remove_owner("et_demo")


def test_unknown_suffix_error_lists_plugin_suffixes(plot_panel, csv_target, tmp_path):
    with pytest.raises(ValueError, match=r"Unsupported.*\.csv"):
        plot_panel.save(str(tmp_path / "a.svg"))


def test_scale_is_refused_by_a_non_scalable_plugin_target(plot_panel, csv_target, tmp_path):
    with pytest.raises(ValueError, match="raster"):
        plot_panel.save(str(tmp_path / "a.csv"), scale=2.0)


def test_suffixes_are_validated(qapp):
    with pytest.raises(ValueError):
        ExportTarget("et_demo.bad", "Bad", ("csv",), write=lambda *a: None)


@pytest.fixture
def menu(qtbot):
    from PySide6.QtWidgets import QMenu
    return QMenu()


def _export_submenu(plot_panel, menu):
    plot_panel._get_impl_or_raise()._build_export_share_menu(menu)
    return next(a.menu() for a in menu.actions() if a.menu() and a.text() == "Export")


def _action(submenu, text):
    return next(a for a in submenu.actions() if a.text() == text)


def test_the_export_submenu_lists_every_target(plot_panel, menu, csv_target):
    texts = [a.text() for a in _export_submenu(plot_panel, menu).actions() if not a.isSeparator()]
    assert texts[:5] == ["Export as PNG\u2026", "Export as PDF\u2026", "Export as JPEG\u2026",
                         "Export as BMP\u2026", "Export as CSV\u2026"]


def _answer_dialog(monkeypatch, path):
    from SciQLop.components.plotting.ui import time_sync_panel as tsp
    monkeypatch.setattr(tsp.QFileDialog, "getSaveFileName", lambda *a, **k: (path, ""))
    return tsp


def test_export_appends_the_suffix_the_user_left_out(plot_panel, menu, csv_target, tmp_path, monkeypatch):
    _answer_dialog(monkeypatch, str(tmp_path / "quicklook"))
    _action(_export_submenu(plot_panel, menu), "Export as CSV\u2026").trigger()
    (_, path, *_), = csv_target
    assert path.endswith("quicklook.csv")


def test_a_failing_export_is_shown_not_raised(plot_panel, menu, tmp_path, monkeypatch):
    def full_disk(*args):
        raise OSError("disk full")
    with owned_by("et_demo"):
        EXPORT_TARGETS.contribute(ExportTarget("et_demo.bad", "Bad", (".bad",), write=full_disk))
    try:
        tsp = _answer_dialog(monkeypatch, str(tmp_path / "x.bad"))
        shown = []
        monkeypatch.setattr(tsp.QMessageBox, "warning", lambda parent, title, text: shown.append(text))
        monkeypatch.setattr(tsp.log, "error", lambda *a, **k: None)
        _action(_export_submenu(plot_panel, menu), "Export as Bad\u2026").trigger()
    finally:
        EXPORT_TARGETS.remove_owner("et_demo")
    assert shown == ["disk full"]
