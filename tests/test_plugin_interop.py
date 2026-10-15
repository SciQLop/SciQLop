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

_OWNERS = ("io_vdf", "io_study", "io_late", "io_export", "io_shell", "vp_maker", "vp_user")


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
    from pathlib import Path
    from PySide6.QtWidgets import QLabel
    from SciQLop.core.export_targets import ExportTarget
    from SciQLop.core.inspector_sections import InspectorSection

    def activate(ctx):
        ctx.contribute("sciqlop.export_targets", ExportTarget(
            "io_export.txt", "Text", (".txt",), write=lambda panel, path, w, h, scale: Path(path).write_text(panel.name)))
        ctx.contribute("sciqlop.inspector_sections", InspectorSection(
            "io_export.note", "Note", "panel", build=lambda panel, parent: QLabel(panel.name, parent)))
"""


def _contributed_ids(panel):
    from SciQLop.components.plotting.ui.contributed_sections import ContributedSection
    return [e.objectName() for e in panel._impl.inspector_extensions() if isinstance(e, ContributedSection)]


def test_plugin_adds_an_export_format_and_a_panel_inspector_section(tmp_path, plot_panel, fresh):
    loader.activate_all([_plugin(tmp_path, "io_export", _EXPORT)], main_window=object(), ep_plugins={})
    assert context.STATES["io_export"].status == "active", context.STATES["io_export"].reason

    plot_panel.save(str(tmp_path / "p.txt"))
    assert (tmp_path / "p.txt").read_text() == plot_panel.name
    assert "io_export.note" in _contributed_ids(plot_panel)

    loader._withdraw("io_export")
    assert "io_export.note" not in _contributed_ids(plot_panel)
    with pytest.raises(ValueError, match="Unsupported format"):
        plot_panel.save(str(tmp_path / "q.txt"))


_SHELL = """
    from SciQLop.core.kernel_namespace import NamespaceEntry
    from SciQLop.core.magics import Magic

    API = object()

    def activate(ctx):
        ctx.contribute("sciqlop.magics", Magic("io_shell.shout", "shout", "line", lambda line: line.upper()))
        ctx.contribute("sciqlop.kernel_namespace", NamespaceEntry("io_shell.api", "io_shell_api", API))
"""


def test_plugin_adds_a_magic_and_a_kernel_name_to_the_app_shell(tmp_path, main_window, fresh):
    from SciQLop.components.workspaces.backend.workspaces_manager import workspaces_manager_instance
    shell = workspaces_manager_instance()._kernel_manager.shell
    loader.activate_all([_plugin(tmp_path, "io_shell", _SHELL)], main_window=object(), ep_plugins={})
    assert context.STATES["io_shell"].status == "active", context.STATES["io_shell"].reason

    assert shell.run_line_magic("shout", "hi") == "HI"
    assert shell.user_ns["io_shell_api"] is sys.modules["io_shell"].API

    loader._withdraw("io_shell")
    assert "io_shell_api" not in shell.user_ns
    assert "shout" not in shell.magics_manager.magics["line"]


_VP_MAKER = """
    from SciQLop.user_api.layers import Marker, register_layer
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product

    def series(start: float, stop: float):
        return [start, stop], [0.0, 1.0]

    def peaks(start: float, stop: float):
        return [Marker(time=start, value=1.0)]

    def activate(ctx):
        create_virtual_product("vp_maker/b", series, VirtualProductType.Scalar, labels=["y"])
        register_layer("vp_maker/peaks")(peaks)
"""

_VP_USER = """
    from SciQLop.components.plotting.backend.easy_provider import VIRTUAL_PRODUCTS
    from SciQLop.user_api.layers._provider import LAYERS

    class Api:
        vp_owner = layer_owner = None

    def activate(ctx):
        ctx.plugin("vp_maker")
        api = Api()
        api.vp_owner = VIRTUAL_PRODUCTS.owner_of("vp_maker//b")
        api.layer_owner = LAYERS.owner_of("Layers/vp_maker/peaks")
        return api
"""


def test_plugin_contributes_a_virtual_product_and_a_layer_and_withdraws_them(tmp_path, main_window, fresh):
    from SciQLopPlots import ProductsModel
    from SciQLop.components.plotting.backend.data_provider import providers
    from SciQLop.components.plotting.backend.easy_provider import VIRTUAL_PRODUCTS
    loader.activate_all([_plugin(tmp_path, "vp_user", _VP_USER, dependencies=["vp_maker"]),
                         _plugin(tmp_path, "vp_maker", _VP_MAKER)], main_window=object(), ep_plugins={})
    assert context.STATES["vp_user"].status == "active", context.STATES["vp_user"].reason
    api = context.STATES["vp_user"].api
    assert (api.vp_owner, api.layer_owner) == ("vp_maker", "vp_maker")

    nodes = ProductsModel.instance()
    assert nodes.node(["vp_maker", "b"]) is not None
    assert nodes.node(["Layers", "vp_maker", "peaks"]) is not None

    provider_name = VIRTUAL_PRODUCTS.get("vp_maker//b").name
    assert provider_name in providers
    loader._withdraw("vp_maker")
    assert provider_name not in providers
    assert nodes.node(["vp_maker", "b"]) is None
    assert nodes.node(["Layers", "vp_maker", "peaks"]) is None
