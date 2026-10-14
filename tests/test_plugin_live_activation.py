"""Plugins loaded after startup go through the same resolver (spec §3.2, live install)."""
import json
import textwrap
from types import SimpleNamespace

import pytest

from SciQLop.components.plugins.backend.loader import context, loader
from tests.test_appstore_install import tmp_config_dir  # noqa: F401  (fixture)
from tests.test_plugin_activation import fresh  # noqa: F401  (fixture)


def _plugin(folder, name, code, deps=()):
    pkg = folder / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(textwrap.dedent(code))
    (pkg / "plugin.json").write_text(json.dumps({"name": name, "version": "1.0.0", "dependencies": list(deps)}))
    return (str(folder), name)


def test_live_plugin_reaches_an_already_active_dependency(tmp_path, fresh):  # noqa: F811
    base = _plugin(tmp_path, "live_base", "def activate(ctx):\n    return 7\n")
    loader.activate_all([base], main_window=object(), ep_plugins={})
    late = _plugin(tmp_path, "live_late", """
        GOT = []
        def activate(ctx):
            GOT.append(ctx.plugin("live_base"))
    """, deps=["live_base"])
    from SciQLop.components.plugins.backend.live_loader import PluginsLiveLoader
    PluginsLiveLoader._load(SimpleNamespace(_main_window=object()), [late])
    import sys
    assert sys.modules["live_late"].GOT == [7] and context.STATES["live_late"].status == "active"


def test_refused_plugin_loads_once_its_dependency_is_enabled(tmp_path, fresh):  # noqa: F811
    late = _plugin(tmp_path, "retry_late", """
        GOT = []
        def activate(ctx):
            GOT.append(ctx.plugin("retry_base"))
    """, deps=["retry_base"])
    loader.activate_all([late], main_window=object(), ep_plugins={})
    assert context.STATES["retry_late"].status == "refused"
    assert "retry_late" not in loader._attempted
    base = _plugin(tmp_path, "retry_base", "def activate(ctx):\n    return 5\n")
    loader.activate_all([base], main_window=object(), ep_plugins={})
    from SciQLop.components.plugins.backend.live_loader import PluginsLiveLoader
    PluginsLiveLoader._load(SimpleNamespace(_main_window=object()), [late])
    import sys
    assert sys.modules["retry_late"].GOT == [5] and context.STATES["retry_late"].status == "active"


def test_an_active_plugin_is_never_activated_twice(tmp_path, fresh):  # noqa: F811
    once = _plugin(tmp_path, "once_p", """
        from dataclasses import dataclass
        CALLS = []
        @dataclass(frozen=True)
        class Thing:
            id: str
        def activate(ctx):
            CALLS.append(1)
            ctx.extension_point("once_p.things", Thing)
            return "api"
    """)
    loader.activate_all([once], main_window=object(), ep_plugins={})
    assert loader.activate_all([once], main_window=object(), ep_plugins={}) == {"once_p": "api"}
    import sys
    assert sys.modules["once_p"].CALLS == [1] and context.STATES["once_p"].status == "active"


def _broken_activate(ctx):
    raise RuntimeError("no luck")


def test_hot_loaded_entry_point_failure_is_reported(monkeypatch, fresh, tmp_config_dir):  # noqa: F811
    mod = SimpleNamespace(activate=_broken_activate)
    ep = SimpleNamespace(name="ep_broken", module="ep_broken", load=lambda: mod,
                         dist=SimpleNamespace(name="ep-broken", requires=None, files=None))
    import importlib.metadata
    monkeypatch.setattr(importlib.metadata, "entry_points", lambda group: [ep])
    from SciQLop.core import sciqlop_application
    monkeypatch.setattr(sciqlop_application, "sciqlop_app", lambda: SimpleNamespace(main_window=object()))
    from SciQLop.components.appstore.backend import _try_load_plugin
    assert _try_load_plugin("ep-broken") == "ep_broken: RuntimeError: no luck"
