"""Two-phase plugin activation (spec §3.2-3.3): order, states, ctx, legacy plugins unchanged."""
import json
import textwrap

import pytest

from SciQLop.components.plugins.backend.loader import context, loader
from SciQLop.core import extensions


@pytest.fixture
def fresh(qapp):
    saved = (dict(context.STATES), set(loader._attempted), dict(vars(loader.loaded_plugins)),
             dict(extensions._EXTENSION_POINTS))
    yield
    for live, old in zip((context.STATES, loader._attempted, vars(loader.loaded_plugins),
                          extensions._EXTENSION_POINTS), saved):
        live.clear()
        live.update(old)


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
