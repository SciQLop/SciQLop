"""Two-phase plugin activation (spec §3.2-3.3): order, states, ctx, legacy plugins unchanged."""
import json
import textwrap

import pytest

from SciQLop.components.plugins.backend.loader import context, loader
from SciQLop.core import extensions

from .helpers import restore_extension_points


@pytest.fixture
def fresh(qapp):
    saved = (dict(context.STATES), set(loader._attempted), dict(vars(loader.loaded_plugins)))
    saved_points = dict(extensions._EXTENSION_POINTS)
    yield
    for live, old in zip((context.STATES, loader._attempted, vars(loader.loaded_plugins)), saved):
        live.clear()
        live.update(old)
    restore_extension_points(saved_points)


def _plugin(folder, name, code, desc=None):
    pkg = folder / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(textwrap.dedent(code))
    if desc is not None:
        (pkg / "plugin.json").write_text(desc if isinstance(desc, str) else json.dumps(desc))
    return (str(folder), name)


def _desc(**kw):
    return {"name": kw.pop("display", "x"), "version": kw.pop("version", "1.0.0"), **kw}


def test_dependencies_activate_first_and_reach_each_other(tmp_path, fresh):
    plugins = [
        _plugin(tmp_path, "act_study", """
            GOT = []
            def activate(ctx):
                GOT.append(ctx.plugin("act_vdf").answer)
        """, _desc(dependencies=["act_vdf>=1"])),
        _plugin(tmp_path, "act_vdf", """
            class Api:
                answer = 42
            def activate(ctx):
                return Api()
        """, _desc()),
    ]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    import sys
    assert sys.modules["act_study"].GOT == [42]
    assert [n for n in context.STATES if n.startswith("act_")] == ["act_vdf", "act_study"]


def test_undeclared_dependency_raises(tmp_path, fresh):
    plugins = [
        _plugin(tmp_path, "und_a", "def activate(ctx):\n    return 1\n", _desc()),
        _plugin(tmp_path, "und_b", "def activate(ctx):\n    ctx.plugin('und_a')\n", _desc()),
    ]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert context.STATES["und_b"].status == "failed"
    assert "und_b uses plugin 'und_a' without declaring it" in context.STATES["und_b"].reason


def test_runtime_failure_refuses_dependents(tmp_path, fresh):
    plugins = [
        _plugin(tmp_path, "rf_base", "def activate(ctx):\n    raise RuntimeError('boom')\n", _desc()),
        _plugin(tmp_path, "rf_user", "def activate(ctx):\n    return 1\n", _desc(dependencies=["rf_base"])),
    ]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert context.STATES["rf_base"].status == "failed" and "boom" in context.STATES["rf_base"].reason
    assert context.STATES["rf_user"].status == "refused"
    assert "needs plugin 'rf_base', which failed: RuntimeError: boom" == context.STATES["rf_user"].reason


def test_missing_dependency_is_refused_and_named(tmp_path, fresh):
    plugins = [_plugin(tmp_path, "md_user", "def activate(ctx):\n    return 1\n", _desc(dependencies=["md_gone"]))]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert context.STATES["md_user"].reason == "needs plugin 'md_gone', which is not installed or not enabled"


def test_legacy_plugin_loads_as_before(tmp_path, fresh):
    old_desc = {"name": "Old", "version": "1.0", "description": "x", "authors": [], "license": "MIT"}
    plugins = [_plugin(tmp_path, "legacy_p", """
        from SciQLop.core.extensions import current_owner
        def load(main_window):
            return ("LOADED", main_window, current_owner())
    """, old_desc)]
    mw = object()
    result = loader.activate_all(plugins, main_window=mw, ep_plugins={})
    assert result["legacy_p"] == ("LOADED", mw, "legacy:legacy_p")
    assert loader.loaded_plugins.legacy_p == ("LOADED", mw, "legacy:legacy_p")


def test_plugin_without_plugin_json_loads(tmp_path, fresh):
    plugins = [_plugin(tmp_path, "nojson_p", "def load(main_window):\n    return 'ok'\n")]
    assert loader.activate_all(plugins, main_window=object(), ep_plugins={})["nojson_p"] == "ok"


def test_malformed_plugin_json_still_loads(tmp_path, fresh):
    plugins = [_plugin(tmp_path, "bad_json_p", "def load(main_window):\n    return 'ok'\n", "{ not json")]
    assert loader.activate_all(plugins, main_window=object(), ep_plugins={})["bad_json_p"] == "ok"


def test_none_api_is_active_but_not_stored(tmp_path, fresh):
    plugins = [_plugin(tmp_path, "none_api", "def activate(ctx):\n    return None\n", _desc())]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert context.STATES["none_api"].status == "active" and not hasattr(loader.loaded_plugins, "none_api")


def test_plugin_declares_an_extension_point_others_fill_in_ready(tmp_path, fresh):
    plugins = [
        _plugin(tmp_path, "ep_owner", """
            from dataclasses import dataclass
            @dataclass(frozen=True)
            class Method:
                id: str
            SEEN = []
            def activate(ctx):
                ctx.extension_point("ep_owner.methods", Method)
                return Method
            def ready(ctx):
                from SciQLop.core import extensions
                SEEN.extend(m.id for m in extensions.get("ep_owner.methods").list())
        """, _desc()),
        _plugin(tmp_path, "ep_filler", """
            def activate(ctx):
                Method = ctx.plugin("ep_owner")
                ctx.contribute("ep_owner.methods", Method("ep_filler.fast"))
        """, _desc(dependencies=["ep_owner"])),
    ]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    import sys
    assert sys.modules["ep_owner"].SEEN == ["ep_filler.fast"]
    assert extensions.get("ep_owner.methods").owner_of("ep_filler.fast") == "ep_filler"


def test_extension_point_id_must_start_with_the_plugin_id(tmp_path, fresh):
    plugins = [_plugin(tmp_path, "badid_p", "def activate(ctx):\n    ctx.extension_point('other.x', object)\n",
                       _desc())]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert "must start with 'badid_p.'" in context.STATES["badid_p"].reason


class _UnreadableDist:
    version = "1.0.0"

    @property
    def files(self):
        raise OSError("RECORD unreadable")


def _ep(name, dist, code="def activate(ctx):\n    return 'ep'\n"):
    from types import ModuleType, SimpleNamespace
    mod = ModuleType(name)
    exec(code, mod.__dict__)
    return SimpleNamespace(name=name, module=name, load=lambda: mod, dist=dist)


def test_unreadable_entry_point_metadata_does_not_stop_other_plugins(tmp_path, fresh):
    plugins = [(None, "unreadable_ep"), _plugin(tmp_path, "readable_p", "def activate(ctx):\n    return 1\n", _desc())]
    loader.activate_all(plugins, main_window=object(), ep_plugins={"unreadable_ep": _ep("unreadable_ep",
                                                                                        _UnreadableDist())})
    assert context.STATES["readable_p"].status == "active"
    assert context.STATES["unreadable_ep"].status == "active"


def test_entry_point_without_plugin_json_takes_its_distribution_version(fresh):
    from types import SimpleNamespace
    ep = _ep("versioned_ep", SimpleNamespace(files=None, version="2.3.0"))
    loader.activate_all([(None, "versioned_ep")], main_window=object(), ep_plugins={"versioned_ep": ep})
    assert context.STATES["versioned_ep"].version == "2.3.0"


def test_entry_point_shadowing_a_folder_plugin_is_warned(tmp_path, fresh, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    spy = MagicMock()
    monkeypatch.setattr(loader, "log", spy)
    folder = _plugin(tmp_path, "twin_p", "def activate(ctx):\n    return 'folder'\n", _desc())
    ep = _ep("twin_p", SimpleNamespace(files=None, version="1.0.0"))
    result = loader.activate_all([folder, (None, "twin_p")], main_window=object(), ep_plugins={"twin_p": ep})
    assert result["twin_p"] == "ep"
    warned = [c.args[0] for c in spy.warning.call_args_list if "twin_p" in c.args[0]]
    assert len(warned) == 1 and str(tmp_path) in warned[0] and "entry point" in warned[0]


def test_has_reports_present_optional_dependency(tmp_path, fresh):
    plugins = [
        _plugin(tmp_path, "opt_mars", "def activate(ctx):\n    return 1\n", _desc()),
        _plugin(tmp_path, "opt_earth", """
            FOUND = []
            def activate(ctx):
                FOUND.extend([ctx.has("opt_mars"), ctx.has("opt_pluto")])
        """, _desc(optional_dependencies=["opt_mars", "opt_pluto"])),
    ]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    import sys
    assert sys.modules["opt_earth"].FOUND == [True, False]


def test_failed_activate_withdraws_its_contributions(tmp_path, fresh):
    ep = extensions.declare(extensions.ExtensionPoint("wd_test.things", str, key=lambda s: s))
    plugins = [_plugin(tmp_path, "wd_half", """
        def activate(ctx):
            ctx.contribute("wd_test.things", "wd_half.one")
            raise RuntimeError("half way")
    """, _desc())]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert context.STATES["wd_half"].status == "failed"
    assert ep.list() == []


def test_failed_legacy_load_withdraws_its_contributions(tmp_path, fresh):
    ep = extensions.declare(extensions.ExtensionPoint("wd_test.legacy", str, key=lambda s: s))
    plugins = [_plugin(tmp_path, "wd_legacy", """
        from SciQLop.core import extensions
        def load(main_window):
            extensions.get("wd_test.legacy").contribute("wd_legacy.one")
            raise RuntimeError("half way")
    """, _desc())]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert ep.list() == []


def test_failed_import_withdraws_module_level_contributions(tmp_path, fresh):
    ep = extensions.declare(extensions.ExtensionPoint("imp_test.things", str, key=lambda s: s))
    plugins = [_plugin(tmp_path, "imp_mod", """
        from SciQLop.core import extensions
        extensions.get("imp_test.things").contribute("imp_mod.one")
        def activate(ctx):
            raise RuntimeError("after import")
    """, _desc())]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert context.STATES["imp_mod"].status == "failed"
    assert ep.list() == []


def test_plugin_and_has_accept_any_spelling_of_a_declared_dependency(tmp_path, fresh):
    plugins = [
        _plugin(tmp_path, "hy_user", """
            GOT = []
            def activate(ctx):
                GOT.extend([ctx.plugin("hy-dep").answer, ctx.plugin("hy_dep").answer,
                            ctx.has("hy-opt"), ctx.has("HY_OPT")])
        """, _desc(dependencies=["hy-dep>=1"], optional_dependencies=["Hy_Opt"])),
        _plugin(tmp_path, "hy_dep", """
            class Api:
                answer = 1
            def activate(ctx):
                return Api()
        """, _desc()),
        _plugin(tmp_path, "hy_opt", "def activate(ctx):\n    pass\n", _desc()),
    ]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    import sys
    assert sys.modules["hy_user"].GOT == [1, 1, True, True]
