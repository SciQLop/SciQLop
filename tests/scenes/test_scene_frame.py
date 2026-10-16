"""A scene plot can be redrawn in another frame centred on its body."""
import pytest

from SciQLop.components.scenes import summary
from SciQLop.components.scenes.frames import FrameError

from ..fixtures import *  # noqa: F401, F403
from .helpers import proj_of


def pane_labels(sp):
    proj = proj_of(sp)
    return [(proj.subplot(i).x_axis().label(), proj.subplot(i).y_axis().label()) for i in range(proj.subplot_count())]


def expected_labels(frame):
    return [(f"{'XYZ'[i]} {frame} [R_E]", f"{'XYZ'[j]} {frame} [R_E]") for i, j in summary.PANES]


def plottable_counts(sp):
    proj = proj_of(sp)
    return [len(proj.plottables())] + [len(proj.subplot(i).plottables()) for i in range(proj.subplot_count())]


def test_changing_the_frame_relabels_and_redraws_everything_in_it(plot_panel, earth, fake_speasy, qtbot):
    sp = plot_panel.plot_scene("Earth environment")
    sp.add_trajectory("MMS1")
    before = plottable_counts(sp)
    sp.set_frame("GSE")
    assert sp.scene.frame == "GSE"
    assert pane_labels(sp) == expected_labels("GSE")
    assert plottable_counts(sp) == before
    assert sp._trajectories == ["MMS1"]
    qtbot.waitUntil(lambda: ("cdpp3dview/MMS1", {"coordinate_frame": "GSE", "sampling": "600"}) in fake_speasy,
                    timeout=5000)


def test_a_frame_centred_on_another_body_is_refused_and_nothing_changes(plot_panel, earth):
    sp = plot_panel.plot_scene("Earth environment")
    before = plottable_counts(sp)
    with pytest.raises(FrameError, match="Mars"):
        sp.set_frame("MSO")
    assert sp.scene.frame == "GSM" and pane_labels(sp) == expected_labels("GSM")
    assert plottable_counts(sp) == before


def test_the_frame_round_trips_through_a_template(plot_panel, registered, earth):
    from SciQLop.components.plotting.panel_template import PanelTemplate
    from SciQLop.components.scenes.scene_plot import scene_plot_for
    from SciQLop.user_api.plot import create_plot_panel
    plot_panel.plot_scene("Earth environment").set_frame("SM")
    saved = PanelTemplate.from_panel(plot_panel._get_impl_or_raise())
    assert saved.plots[0].config["frame"] == "SM"
    other = create_plot_panel()._get_impl_or_raise()
    saved.apply(other)
    restored = next(s for s in map(scene_plot_for, other.plots()) if s is not None)
    assert restored.scene.frame == "SM"


def _frame_combo(sp, parent):
    from PySide6.QtWidgets import QComboBox
    ext = next(e for e in proj_of(sp).inspector_extensions() if e.objectName() == "sciqlop.scenes.frame")
    return ext.build_widget(parent).findChild(QComboBox)


def test_the_inspector_picks_among_the_frames_centred_on_the_body(plot_panel, earth, qtbot):
    from PySide6.QtWidgets import QWidget
    sp = plot_panel.plot_scene("Earth environment")
    parent = QWidget()
    qtbot.addWidget(parent)
    combo = _frame_combo(sp, parent)
    frames = [combo.itemText(i) for i in range(combo.count())]
    assert "GSE" in frames and "SM" in frames and "MSO" not in frames
    assert combo.currentText() == "GSM"
    combo.setCurrentText("GSE")
    assert sp.scene.frame == "GSE"
