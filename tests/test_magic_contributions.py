import pytest
from IPython.core.interactiveshell import InteractiveShell

from SciQLop.core import magics as magics_module
from SciQLop.core.extensions import owned_by
from SciQLop.core.magics import CORE_MAGICS, MAGICS, Magic, contribute_core_magics, unfollow_magics
from SciQLop.user_api.magics import register_all_magics

CORE_NAMES = ("vp", "layer", "plot", "timerange", "install", "workspace", "job")
OWNERS = ("mg_demo", "mg_demo2")


@pytest.fixture
def shell(qapp):
    shell = InteractiveShell()
    register_all_magics(shell)
    yield shell
    unfollow_magics(shell)
    for owner in OWNERS:
        MAGICS.remove_owner(owner)


@pytest.fixture
def errors(monkeypatch):
    logged = []
    monkeypatch.setattr(magics_module.log, "error", lambda message, *a, **kw: logged.append(message))
    return logged


def contribute(magic: Magic, owner: str = "mg_demo") -> None:
    with owned_by(owner):
        MAGICS.contribute(magic)


def registered(shell, kind: str, name: str):
    return shell.magics_manager.magics[kind].get(name)


def test_core_magics_are_contributions(shell):
    for name in CORE_NAMES:
        magic = MAGICS.get(f"sciqlop.{name}")
        assert MAGICS.owner_of(magic.id) == "sciqlop"
        assert registered(shell, magic.kind, name) is magic.function


def test_core_magics_carry_their_completers(shell):
    completers = {m.name: m.completer for m in CORE_MAGICS}
    assert all(completers[n] is not None for n in ("vp", "plot", "timerange", "workspace", "job"))
    assert all(completers[n] is None for n in ("layer", "install"))
    assert all(c in shell.Completer.custom_matchers for c in completers.values() if c is not None)


def test_a_plugin_line_magic_runs(shell):
    contribute(Magic("mg_demo.hello", "hello", "line", lambda line: f"hi {line}"))
    assert shell.run_line_magic("hello", "you") == "hi you"


def test_a_magic_contributed_before_the_shell_is_replayed(qapp):
    contribute(Magic("mg_demo.early", "early", "line", lambda line: "early"))
    try:
        fresh = InteractiveShell()
        register_all_magics(fresh)
        assert fresh.run_line_magic("early", "") == "early"
    finally:
        unfollow_magics(fresh)
        MAGICS.remove_owner("mg_demo")


def test_withdrawal_removes_the_magic_and_its_completer(shell):
    def matcher(context):
        return {"completions": [], "suppress": False}
    matcher.matcher_identifier = "mg_demo.matcher"
    contribute(Magic("mg_demo.hello", "hello", "line", lambda line: "hi", matcher))
    assert matcher in shell.Completer.custom_matchers

    MAGICS.remove_owner("mg_demo")

    assert registered(shell, "line", "hello") is None
    assert matcher not in shell.Completer.custom_matchers


def test_withdrawal_leaves_a_function_the_user_registered_since(shell):
    contribute(Magic("mg_demo.hello", "hello", "line", lambda line: "hi"))
    user_function = lambda line: "mine"  # noqa: E731
    shell.register_magic_function(user_function, magic_kind="line", magic_name="hello")

    MAGICS.remove_owner("mg_demo")

    assert registered(shell, "line", "hello") is user_function


def test_a_plugin_cannot_shadow_a_core_magic(shell, errors):
    contribute(Magic("mg_demo.plot", "plot", "line", lambda line: "shadow"))
    assert registered(shell, "line", "plot") is MAGICS.get("sciqlop.plot").function
    assert len(set(errors)) == 1 and "mg_demo.plot" in errors[0]


def test_a_core_magic_arriving_after_a_plugin_takes_the_name(shell, errors):
    contribute(Magic("mg_demo.qq", "qq", "line", lambda line: "plugin"))
    core = Magic("sciqlop.qq", "qq", "line", lambda line: "core")
    try:
        with owned_by("sciqlop"):
            MAGICS.contribute(core)
        assert registered(shell, "line", "qq") is core.function
        assert len(set(errors)) == 1 and "mg_demo.qq" in errors[0]
    finally:
        MAGICS.remove_owner("sciqlop")
        contribute_core_magics()


def test_a_line_cell_magic_clashes_with_both_kinds(shell, errors):
    contribute(Magic("mg_demo.both", "both", "line_cell", lambda line, cell=None: "both"))
    contribute(Magic("mg_demo2.both", "both", "cell", lambda line, cell: "cell"), owner="mg_demo2")
    assert len(set(errors)) == 1 and "mg_demo2.both" in errors[0]
    assert registered(shell, "cell", "both") is registered(shell, "line", "both")


def test_withdrawing_the_holder_promotes_the_next(shell, errors):
    first = Magic("mg_demo.zz", "zz", "line", lambda line: "first")
    second = Magic("mg_demo2.zz", "zz", "line", lambda line: "second")
    contribute(first)
    contribute(second, owner="mg_demo2")
    assert registered(shell, "line", "zz") is first.function

    MAGICS.remove_owner("mg_demo")

    assert registered(shell, "line", "zz") is second.function


def test_register_all_magics_twice_adds_no_duplicate_completers(shell):
    before = list(shell.Completer.custom_matchers)
    register_all_magics(shell)
    assert shell.Completer.custom_matchers == before


def test_a_raising_magic_reports_and_the_shell_lives(shell):
    def boom(line):
        raise RuntimeError("boom")
    contribute(Magic("mg_demo.boom", "boom", "line", boom))

    assert shell.run_cell("%boom").error_in_exec is not None
    assert shell.run_cell("1+1").success


def test_kind_and_name_are_validated():
    with pytest.raises(ValueError):
        Magic("mg_demo.x", "x", "block", lambda line: None)
    for bad in ("%x", "two words", ""):
        with pytest.raises(ValueError):
            Magic("mg_demo.x", bad, "line", lambda line: None)
