"""Spec §10 interop proof for data contracts: one plugin declares a product kind, a source kind, a provider and
an extension point; a second uses its API and fills that extension point; a third, activated later, is seen
through `added`."""
import json
import sys
import textwrap

import pytest

from .fixtures import *  # noqa: F401,F403
from SciQLop.components.plugins.backend.loader import context, loader
from SciQLop.core import extensions

_OWNERS = ("io_vdf", "io_study", "io_late", "io_export")


@pytest.fixture
def fresh(qapp):
    saved = (dict(context.STATES), set(loader._attempted), dict(vars(loader.loaded_plugins)),
             dict(extensions._EXTENSION_POINTS))
    yield
    for ep in extensions.all_extension_points():
        for owner in _OWNERS:
            ep.remove_owner(owner)
    for live, old in zip((context.STATES, loader._attempted, vars(loader.loaded_plugins),
                          extensions._EXTENSION_POINTS), saved):
        live.clear()
        live.update(old)


def _plugin(folder, name, code, **desc):
    pkg = folder / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(textwrap.dedent(code))
    (pkg / "plugin.json").write_text(json.dumps({"name": name, "version": "1.0.0", **desc}))
    return (str(folder), name)


_VDF = """
    from dataclasses import dataclass
    from SciQLop.components.plotting.backend.data_provider import DataProvider
    from SciQLop.core.product_kinds import PRODUCT_KINDS, ProductKind
    from SciQLop.core.source_kinds import SOURCE_KINDS, SourceKind

    @dataclass(frozen=True)
    class Method:
        id: str

    class VdfProvider(DataProvider):
        source_kind = "io_vdf.instrument"

    class Api:
        Method = Method
        def __init__(self, ep):
            self.seen = []
            ep.signals.added.connect(lambda m: self.seen.append(m.id))

    def activate(ctx):
        ep = ctx.extension_point("io_vdf.methods", Method)
        ctx.contribute("sciqlop.product_kinds", ProductKind("io_vdf.distribution", "VDF", 3, "io_vdf.slice_plot"))
        ctx.contribute("sciqlop.source_kinds", SourceKind("io_vdf.instrument", lambda c: "VDF", lambda c: "VDF"))
        VdfProvider("io_vdf")
        return Api(ep)
"""

_STUDY = """
    def activate(ctx):
        vdf = ctx.plugin("io_vdf")
        ctx.contribute("io_vdf.methods", vdf.Method("io_study.moments"))
"""

_LATE = """
    def activate(ctx):
        ctx.contribute("io_vdf.methods", ctx.plugin("io_vdf").Method("io_late.fit"))
"""


def test_plugins_share_kinds_providers_and_extension_points(tmp_path, fresh):
    from SciQLop.components.plotting.backend.data_provider import DATA_PROVIDERS, providers
    from SciQLop.core.product_kinds import PRODUCT_KINDS
    from SciQLop.core.source_kinds import source_kind
    loader.activate_all([_plugin(tmp_path, "io_study", _STUDY, dependencies=["io-vdf>=1"]),
                         _plugin(tmp_path, "io_vdf", _VDF)], main_window=object(), ep_plugins={})
    assert {n: context.STATES[n].status for n in ("io_vdf", "io_study")} == {"io_vdf": "active",
                                                                             "io_study": "active"}
    api = context.STATES["io_vdf"].api
    assert api.seen == ["io_study.moments"]
    assert PRODUCT_KINDS.owner_of("io_vdf.distribution") == "io_vdf"
    assert DATA_PROVIDERS.owner_of("io_vdf") == "io_vdf"
    assert source_kind(providers["io_vdf"].source_kind).inspector_line(None) == "VDF"

    loader.activate_all([_plugin(tmp_path, "io_late", _LATE, dependencies=["io_vdf"])],
                        main_window=object(), ep_plugins={})
    assert api.seen == ["io_study.moments", "io_late.fit"]
    assert sys.modules["io_late"] is not None


_EXPORT = """
    from PySide6.QtWidgets import QLabel
    from SciQLop.core.export_targets import ExportTarget
    from SciQLop.core.inspector_sections import InspectorSection

    def activate(ctx):
        ctx.contribute("sciqlop.export_targets", ExportTarget(
            "io_export.txt", "Text", (".txt",), write=lambda panel, path, w, h, scale: open(path, "w").write(panel.name)))
        ctx.contribute("sciqlop.inspector_sections", InspectorSection(
            "io_export.note", "Note", "panel", build=lambda panel, parent: QLabel(panel.name, parent)))
"""


def _contributed_ids(panel):
    from SciQLop.components.plotting.ui.contributed_sections import ContributedSection
    return [e.objectName() for e in panel._impl.inspector_extensions() if isinstance(e, ContributedSection)]


def test_plugin_adds_an_export_format_and_a_panel_inspector_section(tmp_path, plot_panel, fresh):
    from SciQLop.core.export_targets import EXPORT_TARGETS
    from SciQLop.core.inspector_sections import INSPECTOR_SECTIONS
    loader.activate_all([_plugin(tmp_path, "io_export", _EXPORT)], main_window=object(), ep_plugins={})
    assert context.STATES["io_export"].status == "active", context.STATES["io_export"].reason

    plot_panel.save(str(tmp_path / "p.txt"))
    assert (tmp_path / "p.txt").read_text() == plot_panel.name
    assert "io_export.note" in _contributed_ids(plot_panel)

    EXPORT_TARGETS.remove_owner("io_export")
    INSPECTOR_SECTIONS.remove_owner("io_export")
    assert "io_export.note" not in _contributed_ids(plot_panel)
    with pytest.raises(Exception):
        plot_panel.save(str(tmp_path / "q.txt"))
