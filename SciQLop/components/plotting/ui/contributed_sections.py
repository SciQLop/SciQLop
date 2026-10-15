"""Shows sciqlop.inspector_sections contributions in the inspector of every panel, plot and graph."""
from __future__ import annotations

import shiboken6
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from SciQLopPlots import InspectorExtension, SciQLopPlotInterface

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.inspector_sections import (INSPECTOR_SECTIONS, InspectorSection,
                                             PANEL_TARGET, PLOT_TARGET, GRAPH_TARGET)

log = getLogger(__name__)

# Shiboken drops a Python-subclass extension whose wrapper nobody references, even with a Qt parent
# (see graph_context_inspector/extension.py). simplify: holds the wrapper of every live section,
# O(sections x hosts) memory; fine until thousands of graphs.
_alive: set = set()


def _plot_of(graph):
    parent = graph.parent()
    while parent is not None and not isinstance(parent, SciQLopPlotInterface):
        parent = parent.parent()
    return parent


def _wrap_panel(impl):
    from SciQLop.user_api.plot import PlotPanel
    return PlotPanel(impl)


def _wrap_plot(impl):
    from SciQLop.user_api.plot import _panel
    return _panel._wrap_plot(impl)


def _wrap_graph(impl):
    from SciQLop.user_api.plot._graphs import to_plottable
    plot = _plot_of(impl)
    return to_plottable(impl, _wrap_plot(plot) if plot is not None else None)


_WRAPPERS = {PANEL_TARGET: _wrap_panel, PLOT_TARGET: _wrap_plot, GRAPH_TARGET: _wrap_graph}


def _wrap(host, target: str):
    return _WRAPPERS[target](host)


class ContributedSection(InspectorExtension):
    """One contributed section on one host. State lives in Qt storage (objectName = section id,
    parent = host) because Shiboken may hand back a fresh wrapper with an empty __dict__."""

    def __init__(self, section_id: str, host):
        super().__init__(host)
        self.setObjectName(section_id)

    def _section(self) -> InspectorSection | None:
        """None once withdrawn: remove_owner empties the registry before the inspector drops each section."""
        section_id = self.objectName()
        return INSPECTOR_SECTIONS.get(section_id) if section_id in INSPECTOR_SECTIONS else None

    def section_title(self) -> str:
        section = self._section()
        return section.title if section is not None else self.objectName()

    def priority(self) -> int:
        section = self._section()
        return section.priority if section is not None else 0

    def build_widget(self, parent: QWidget) -> QWidget | None:
        section = self._section()
        if section is None:
            return None  # SciQLopPlots skips a null section widget
        try:
            return section.build(_wrap(self.parent(), section.target), parent)
        except Exception:
            log.error(f"inspector section {section.id} failed to build", exc_info=True)
            return QLabel(f"{section.title}: failed to build, see the log", parent)


def _section_ids_on(host) -> set[str]:
    return {e.objectName() for e in host.inspector_extensions() if isinstance(e, ContributedSection)}


def _applies(section: InspectorSection, obj) -> bool:
    try:
        return obj is not None and bool(section.applies(obj))
    except Exception:
        log.error(f"inspector section {section.id}: applies() raised, section skipped", exc_info=True)
        return False


def _add_section(host, section_id: str) -> None:
    ext = ContributedSection(section_id, host)
    _alive.add(ext)
    ext.destroyed.connect(lambda *_, e=ext: _alive.discard(e))
    host.add_inspector_extension(ext)


def attach_sections(host, target: str) -> None:
    """Add every section of ``target`` that applies to ``host`` and is not on it yet. Idempotent."""
    missing = [s for s in INSPECTOR_SECTIONS.list(target=target) if s.id not in _section_ids_on(host)]
    obj = _wrap(host, target) if missing else None
    # simplify: a rejected section is re-checked on every graph_list_changed of its plot, so each change costs
    # O(graphs) applies() calls and one wrapper (one destroyed connection) per graph. Rejections are not cached
    # because graph context attaches after graph_list_changed fires. Upgrade: re-check on a context-attached signal.
    for section in missing:
        if _applies(section, obj):
            _add_section(host, section.id)


def attach_graph_sections(plot) -> None:
    if shiboken6.isValid(plot):
        for graph in _valid(plot.plottables()):
            attach_sections(graph, GRAPH_TARGET)


def _valid(objects) -> list:
    return [o for o in objects if o is not None and shiboken6.isValid(o)]


def _panels() -> list:
    window = getattr(QApplication.instance(), "main_window", None)
    if window is None or not shiboken6.isValid(window):
        return []
    return _valid(window.plot_panel(name) for name in window.plot_panels())


def _plots() -> list:
    return [plot for panel in _panels() for plot in _valid(panel.plots())]


def _graphs() -> list:
    return [graph for plot in _plots() for graph in _valid(plot.plottables())]


_HOSTS = {PANEL_TARGET: _panels, PLOT_TARGET: _plots, GRAPH_TARGET: _graphs}


def _on_section_added(section: InspectorSection) -> None:
    for host in _HOSTS[section.target]():
        attach_sections(host, section.target)


def _on_section_removed(section: InspectorSection) -> None:
    for ext in [e for e in _alive if shiboken6.isValid(e) and e.objectName() == section.id]:
        _alive.discard(ext)
        ext.deleteLater()
        ext.parent().remove_inspector_extension(ext)


def follow_inspector_sections() -> None:
    """Attach sections contributed later to the hosts that already exist; withdraw removed ones.

    Main thread only. Marks the signals object it connected, so it is idempotent and reconnects when a test
    swaps in fresh signals."""
    signals = INSPECTOR_SECTIONS.signals
    if not getattr(signals, "_hosts_follow", False):
        signals.added.connect(_on_section_added)
        signals.removed.connect(_on_section_removed)
        signals._hosts_follow = True
