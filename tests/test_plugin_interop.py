"""Spec §10 interop proof for data contracts: one plugin declares a product kind, a source kind, a provider and
an extension point; a second uses its API and fills that extension point; a third, activated later, is seen
through `added`."""
import json
import sys
import textwrap

import pytest

from .fixtures import *  # noqa: F401,F403
from .helpers import restore_extension_points
from SciQLop.components.plugins.backend.loader import context, loader
from SciQLop.core import extensions

_OWNERS = ("io_vdf", "io_study", "io_late", "io_export", "io_shell", "vp_maker", "vp_user", "ui_maker",
           "agent_maker", "viewer_maker", "viewer_user", "broken_viewer")


@pytest.fixture
def fresh(qapp):
    saved = (dict(context.STATES), set(loader._attempted), dict(vars(loader.loaded_plugins)))
    saved_points = dict(extensions._EXTENSION_POINTS)
    yield
    for ep in extensions.all_extension_points():
        for owner in _OWNERS:
            ep.remove_owner(owner)
    for live, old in zip((context.STATES, loader._attempted, vars(loader.loaded_plugins)), saved):
        live.clear()
        live.update(old)
    restore_extension_points(saved_points)


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


_UI_MAKER = """
    from typing import ClassVar
    from pydantic import BaseModel
    from PySide6.QtWidgets import QLabel
    from SciQLop.components.settings.backend.entry import ConfigEntry
    from SciQLop.components.workspaces.backend.workspace_sections import WorkspaceSection
    from SciQLop.core.docks import Dock

    class UiMakerSettings(ConfigEntry):
        category: ClassVar[str] = "ui_maker"
        subcategory: ClassVar[str] = "general"
        knob: int = 1

    class UiMakerModel(BaseModel):
        value: int = 0

    def activate(ctx):
        ctx.contribute("sciqlop.docks", Dock("ui_maker.panel", "UiMakerPanel", build=lambda: QLabel("ui")))
        ctx.contribute("sciqlop.workspace_sections", WorkspaceSection("ui_maker", UiMakerModel))
"""


def test_plugin_contributes_settings_a_dock_and_a_workspace_section(tmp_path, main_window, qtbot, fresh):
    from SciQLop.components.settings.backend.entry import ConfigEntry, SETTINGS
    from SciQLop.components.workspaces.backend.workspace_sections import WORKSPACE_SECTIONS
    dock_manager = main_window.dock_manager
    loader.activate_all([_plugin(tmp_path, "ui_maker", _UI_MAKER)], main_window=main_window, ep_plugins={})
    assert context.STATES["ui_maker"].status == "active", context.STATES["ui_maker"].reason

    assert SETTINGS.owner_of("UiMakerSettings") == "ui_maker"
    dock = dock_manager.findDockWidget("UiMakerPanel")
    assert dock is not None
    assert dock.dockAreaWidget() is dock_manager.findDockWidget("Welcome").dockAreaWidget()
    assert WORKSPACE_SECTIONS.owner_of("ui_maker") == "ui_maker"

    loader._withdraw("ui_maker")
    qtbot.wait(50)
    assert "UiMakerSettings" not in ConfigEntry.list_entries()
    assert dock_manager.findDockWidget("UiMakerPanel") is None
    assert "ui_maker" not in WORKSPACE_SECTIONS.keys()


_AGENT_MAKER = """
    from pathlib import Path
    from SciQLop.components.agents import AgentSkill, AgentTool, register_agent_backend

    class Fake:
        display_name = "AgentMakerFake"

    def activate(ctx):
        register_agent_backend(Fake)
        ctx.contribute("sciqlop.agent_tools", AgentTool(
            "agent_maker_ping", "Ping.", {{"type": "object", "properties": {{}}}}, lambda p: "pong"))
        ctx.contribute("sciqlop.agent_skills", AgentSkill("agent-maker", Path({skill_dir!r})))
"""


def test_plugin_contributes_an_agent_backend_a_tool_and_a_skill(tmp_path, main_window, fresh):
    from SciQLop.components.agents import (
        AGENT_BACKENDS, AGENT_SKILLS, AGENT_TOOLS, available_backends)
    from SciQLop.components.agents.skills import sync_skills
    from SciQLop.components.agents.tools import build_sciqlop_tools
    skill_dir = tmp_path / "skill_src"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: agent-maker\ndescription: Demo.\n---\nBody.\n")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    published = workspace / ".claude" / "skills" / "agent-maker" / "SKILL.md"
    code = _AGENT_MAKER.format(skill_dir=str(skill_dir))
    loader.activate_all([_plugin(tmp_path, "agent_maker", code)], main_window=main_window, ep_plugins={})
    assert context.STATES["agent_maker"].status == "active", context.STATES["agent_maker"].reason

    assert AGENT_BACKENDS.owner_of("AgentMakerFake") == "agent_maker"
    assert AGENT_TOOLS.owner_of("agent_maker_ping") == "agent_maker"
    assert AGENT_SKILLS.owner_of("agent-maker") == "agent_maker"
    assert "AgentMakerFake" in available_backends()
    assert "agent_maker_ping" in [t["name"] for t in build_sciqlop_tools(main_window)]
    sync_skills(workspace)
    assert published.is_file()

    loader._withdraw("agent_maker")
    assert "AgentMakerFake" not in available_backends()
    assert "agent_maker_ping" not in [t["name"] for t in build_sciqlop_tools(main_window)]
    sync_skills(workspace)
    assert not published.parent.exists()


_VIEWER_MAKER = """
    from PySide6.QtWidgets import QLabel
    from SciQLop.core.panel_extensions import PanelExtension
    from SciQLop.core.panel_kinds import PanelKind

    class Api:
        def __init__(self):
            self.log = []

        def attach(self, panel):
            self.log.append(("attach", panel.text()))
            return lambda: self.log.append(("cleanup", panel.text()))

    def activate(ctx):
        api = Api()
        ctx.contribute("sciqlop.panel_kinds", PanelKind(
            "viewer_maker.viewer", "Viewer", create=lambda n, c: QLabel(c.get("text", "")),
            to_config=lambda w: {"text": w.text()}))
        ctx.contribute("sciqlop.panel_extensions", PanelExtension(
            "viewer_maker.badge", attach=api.attach, kinds=("viewer_maker.viewer",)))
        return api
"""

_VIEWER_USER = """
    from SciQLop.core.panel_extensions import PanelExtension

    class Api:
        def __init__(self):
            self.attached = []

    def activate(ctx):
        api = Api()
        ctx.main_window.open_panel("viewer_maker.viewer", text="from user")
        ctx.contribute("sciqlop.panel_extensions", PanelExtension(
            "viewer_user.time", attach=lambda p: api.attached.append(p.objectName()),
            kinds=("sciqlop.time_panel",)))
        return api
"""


def _viewers(main_window):
    return [p for p in main_window.panels() if getattr(p, "text", None) and p.text() == "from user"]


def test_plugin_contributes_a_panel_kind_and_another_extends_it(tmp_path, main_window, fresh):
    from SciQLop.core.panel_extensions import PANEL_EXTENSIONS
    from SciQLop.core.panel_kinds import PANEL_KINDS
    opened = []
    try:
        loader.activate_all([_plugin(tmp_path, "viewer_user", _VIEWER_USER, dependencies=["viewer_maker"]),
                             _plugin(tmp_path, "viewer_maker", _VIEWER_MAKER)],
                            main_window=main_window, ep_plugins={})
        assert context.STATES["viewer_user"].status == "active", context.STATES["viewer_user"].reason
        maker, user = context.STATES["viewer_maker"].api, context.STATES["viewer_user"].api
        assert PANEL_KINDS.owner_of("viewer_maker.viewer") == "viewer_maker"
        assert PANEL_EXTENSIONS.owner_of("viewer_maker.badge") == "viewer_maker"
        assert PANEL_EXTENSIONS.owner_of("viewer_user.time") == "viewer_user"
        assert maker.log == [("attach", "from user")]

        time_panel = main_window.new_plot_panel()
        opened.append(time_panel)
        assert user.attached == [time_panel.objectName()]

        loader._withdraw("viewer_maker")
        assert maker.log == [("attach", "from user"), ("cleanup", "from user")]
        assert len(_viewers(main_window)) == 1
        with pytest.raises(LookupError):
            main_window.open_panel("viewer_maker.viewer")
    finally:
        for panel in [*opened, *_viewers(main_window)]:
            main_window.remove_panel(panel)


_BROKEN_VIEWER = """
    from PySide6.QtWidgets import QLabel
    from SciQLop.core.panel_kinds import PanelKind

    def activate(ctx):
        ctx.contribute("sciqlop.panel_kinds", PanelKind("broken_viewer.viewer", "Viewer",
                                                        create=lambda n, c: QLabel("real")))
        raise RuntimeError("fails after contributing its kind")
"""


def _one_event_loop_turn(qtbot):
    from PySide6.QtCore import QTimer
    turned = []
    QTimer.singleShot(0, lambda: turned.append(True))
    qtbot.waitUntil(lambda: bool(turned))


def test_a_plugin_failing_after_contributing_a_kind_leaves_the_placeholder(tmp_path, main_window, fresh, qtbot,
                                                                         monkeypatch):
    from SciQLop.components.plotting.ui.placeholder_panel import open_placeholder
    from SciQLop.components.plugins import install_offer
    from SciQLop.core.panel_kinds import PANEL_KINDS
    monkeypatch.setattr(install_offer, "fetch_index", lambda *a, **k: [])
    placeholder = open_placeholder(main_window, {"kind": "broken_viewer.viewer", "config": {}, "slots": {}},
                                   name="io_broken")
    try:
        loader.activate_all([_plugin(tmp_path, "broken_viewer", _BROKEN_VIEWER)],
                            main_window=main_window, ep_plugins={})
        assert context.STATES["broken_viewer"].status == "failed"
        _one_event_loop_turn(qtbot)
        assert "broken_viewer.viewer" not in PANEL_KINDS
        assert placeholder in main_window.panels() and placeholder.objectName() == "io_broken"
    finally:
        for panel in [p for p in main_window.panels() if p.objectName() == "io_broken"]:
            main_window.remove_panel(panel)
