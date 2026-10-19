"""sciqlop.inspector_sections (spec §4.3): plugin sections in the inspector of panels, plots and graphs."""
from .fixtures import *  # noqa: F401,F403
import numpy as np
import pytest
from PySide6.QtWidgets import QLabel, QWidget

from SciQLop.core.extensions import owned_by
from SciQLop.core.inspector_sections import (INSPECTOR_SECTIONS, InspectorSection,
                                             PANEL_TARGET, PLOT_TARGET, GRAPH_TARGET)
from SciQLop.components.plotting.ui import contributed_sections
from SciQLop.components.plotting.ui.contributed_sections import ContributedSection


@pytest.fixture(autouse=True)
def demo_sections(qapp):
    from SciQLop.components.extension_points import prepare_extension_points
    prepare_extension_points()
    yield
    INSPECTOR_SECTIONS.remove_owner("is_demo")


def _sections(host):
    return [contributed_sections.section_id(e) for e in host.inspector_extensions() if isinstance(e, ContributedSection)]


def _contribute(id, target, build=lambda obj, parent: QLabel("x", parent), **kwargs):
    with owned_by("is_demo"):
        return INSPECTOR_SECTIONS.contribute(InspectorSection(id, id.title(), target, build, **kwargs))


def _plot_line(plot_panel):
    from SciQLop.user_api.plot import PlotType
    x = np.linspace(0, 100, 50)
    return plot_panel.plot_data(x, np.sin(x), plot_type=PlotType.TimeSeries)


def _section_on(host, id):
    return next(e for e in host.inspector_extensions() if isinstance(e, ContributedSection) and contributed_sections.section_id(e) == id)


def test_a_graph_section_appears_on_new_graphs(plot_panel):
    from SciQLop.user_api.plot._graphs import Graph
    received = []
    _contribute("is_demo.g", GRAPH_TARGET, build=lambda obj, parent: received.append(obj) or QLabel("g", parent))
    _plot, graph = _plot_line(plot_panel)
    assert "is_demo.g" in _sections(graph._impl)
    parent = QWidget()
    widget = _section_on(graph._impl, "is_demo.g").build_widget(parent)
    assert isinstance(widget, QLabel)
    assert isinstance(received[0], Graph)
    assert received[0]._plot._impl is _plot._impl


def test_applies_filters_and_a_raising_applies_is_skipped(plot_panel, monkeypatch):
    errors = []
    monkeypatch.setattr(contributed_sections.log, "error", lambda *a, **k: errors.append(a))

    def _raise(obj):
        raise RuntimeError("boom")

    _contribute("is_demo.never", GRAPH_TARGET, applies=lambda g: False)
    _contribute("is_demo.raising", GRAPH_TARGET, applies=_raise)
    _plot, graph = _plot_line(plot_panel)
    assert not {"is_demo.never", "is_demo.raising"} & set(_sections(graph._impl))
    assert errors


def test_a_raising_build_shows_a_failed_label(plot_panel, monkeypatch):
    monkeypatch.setattr(contributed_sections.log, "error", lambda *a, **k: None)

    def _raise(obj, parent):
        raise RuntimeError("boom")

    _contribute("is_demo.broken", GRAPH_TARGET, build=_raise)
    _plot, graph = _plot_line(plot_panel)
    parent = QWidget()
    widget = _section_on(graph._impl, "is_demo.broken").build_widget(parent)
    assert isinstance(widget, QLabel)
    assert "failed" in widget.text()


def test_a_section_contributed_later_reaches_existing_graphs(plot_panel):
    _plot, graph = _plot_line(plot_panel)
    _contribute("is_demo.late", GRAPH_TARGET)
    assert "is_demo.late" in _sections(graph._impl)


def test_withdrawing_removes_the_section(plot_panel):
    _contribute("is_demo.gone", GRAPH_TARGET)
    _plot, graph = _plot_line(plot_panel)
    INSPECTOR_SECTIONS.remove_owner("is_demo")
    assert "is_demo.gone" not in _sections(graph._impl)


def test_panel_and_plot_targets(plot_panel):
    from SciQLop.user_api.plot import PlotPanel
    received = []
    _contribute("is_demo.panel", PANEL_TARGET, build=lambda obj, parent: received.append(obj) or QLabel("p", parent))
    _contribute("is_demo.plot", PLOT_TARGET)
    _plot_line(plot_panel)
    _plot_line(plot_panel)
    panel_impl = plot_panel._impl
    assert "is_demo.panel" in _sections(panel_impl)
    parent = QWidget()
    _section_on(panel_impl, "is_demo.panel").build_widget(parent)
    assert isinstance(received[0], PlotPanel)
    assert all("is_demo.plot" in _sections(p) for p in panel_impl.plots())


def test_removing_a_graph_with_a_section_is_safe(plot_panel, qtbot):
    _contribute("is_demo.first", GRAPH_TARGET)
    _plot_line(plot_panel)
    plot_panel.remove_plot(0)
    qtbot.wait(0)
    _contribute("is_demo.second", GRAPH_TARGET)
    assert not [e for e in contributed_sections._alive if contributed_sections.section_id(e) == "is_demo.second"]
    INSPECTOR_SECTIONS.remove_owner("is_demo")
    qtbot.wait(0)
    assert not [e for e in contributed_sections._alive if contributed_sections.section_id(e).startswith("is_demo.")]


def _show_in_inspector(name, qtbot):
    from PySide6.QtCore import QModelIndex
    from SciQLopPlots import PlotsTreeView, PropertiesPanel
    inspector = PropertiesPanel()
    qtbot.addWidget(inspector)
    inspector.show()
    tree = inspector.findChild(PlotsTreeView)
    model = tree.model()

    def find(parent=QModelIndex()):
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            if index.data() == name:
                return index
            found = find(index)
            if found is not None:
                return found
        return None

    tree.setCurrentIndex(find())
    qtbot.wait(0)


def test_withdrawing_two_sections_while_the_inspector_shows_their_host(plot_panel, qtbot, monkeypatch):
    errors = []
    monkeypatch.setattr(contributed_sections.log, "error", lambda *a, **k: errors.append(a))
    _contribute("is_demo.one", PLOT_TARGET)
    _contribute("is_demo.two", PLOT_TARGET)
    plot, _graph = _plot_line(plot_panel)
    _show_in_inspector(plot._impl.objectName(), qtbot)
    INSPECTOR_SECTIONS.remove_owner("is_demo")
    qtbot.wait(0)
    assert _sections(plot._impl) == []
    assert not [e for e in contributed_sections._alive if contributed_sections.section_id(e).startswith("is_demo.")]
    assert errors == []


def _inspector_names(qtbot) -> list:
    from PySide6.QtCore import QModelIndex
    from SciQLopPlots import PlotsTreeView, PropertiesPanel
    inspector = PropertiesPanel()
    qtbot.addWidget(inspector)
    model = inspector.findChild(PlotsTreeView).model()

    def names(parent=QModelIndex()):
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            yield index.data()
            yield from names(index)
    return list(names())


def test_the_inspector_tree_names_a_section_by_its_title(plot_panel, qtbot):
    with owned_by("is_demo"):
        INSPECTOR_SECTIONS.contribute(InspectorSection("is_demo.titled", "Readable title", PLOT_TARGET,
                                                       lambda obj, parent: QLabel("x", parent)))
    _plot_line(plot_panel)
    names = _inspector_names(qtbot)
    assert "Readable title" in names and "is_demo.titled" not in names


def test_target_and_priority_are_validated():
    build = lambda obj, parent: None  # noqa: E731
    with pytest.raises(ValueError):
        InspectorSection("x", "X", "axis", build)
    with pytest.raises(TypeError):
        InspectorSection("x", "X", GRAPH_TARGET, build, priority="high")
