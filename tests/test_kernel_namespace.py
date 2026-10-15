import pytest
from IPython.core.interactiveshell import InteractiveShell

from SciQLop.core import kernel_namespace as kn
from SciQLop.core.kernel_namespace import (
    KERNEL_NAMESPACE, NamespaceEntry, contribute_name, follow_kernel_namespace, unfollow_kernel_namespace,
)

from .fixtures import *  # noqa: F401,F403 — qapp/main_window fixtures

OWNERS = ("kn_demo", "kn_demo2")
CORE_TEST_IDS = ("sciqlop.kn_core", "sciqlop.kn_core2")


def clean_up() -> None:
    for owner in (*OWNERS, "sciqlop"):
        for key in KERNEL_NAMESPACE.contributed_by(owner):
            if owner != "sciqlop" or key in CORE_TEST_IDS:
                KERNEL_NAMESPACE.remove(key)


@pytest.fixture
def shell(qapp):
    shell = InteractiveShell()
    follow_kernel_namespace(shell)
    yield shell
    unfollow_kernel_namespace(shell)
    clean_up()


@pytest.fixture
def errors(monkeypatch):
    logged = []
    monkeypatch.setattr(kn.log, "error", lambda message, *a, **kw: logged.append(message))
    return logged


def contribute(id: str, name: str, value, owner: str = "kn_demo", **kwargs) -> None:
    contribute_name(id, name, value, owner=owner, **kwargs)


def test_a_contributed_name_is_in_the_namespace(shell):
    contribute("kn_demo.x", "mydata", 7)
    assert shell.user_ns["mydata"] == 7


def test_an_invalid_name_is_refused():
    with pytest.raises(ValueError):
        NamespaceEntry("kn_demo.bad", "not a name", 1)


def test_a_name_contributed_before_the_shell_is_replayed(qapp):
    contribute("kn_demo.early", "early", 1)
    fresh = InteractiveShell()
    try:
        follow_kernel_namespace(fresh)
        assert fresh.user_ns["early"] == 1
    finally:
        unfollow_kernel_namespace(fresh)
        clean_up()


def test_withdrawal_removes_the_name(shell):
    contribute("kn_demo.x", "mydata", 7)
    KERNEL_NAMESPACE.remove_owner("kn_demo")
    assert "mydata" not in shell.user_ns


def test_withdrawal_keeps_a_user_rebinding(shell):
    contribute("kn_demo.x", "mydata", 7)
    shell.user_ns["mydata"] = 3
    KERNEL_NAMESPACE.remove_owner("kn_demo")
    assert shell.user_ns["mydata"] == 3


def test_a_plugin_cannot_shadow_a_core_name(shell, errors):
    contribute("sciqlop.kn_core", "kn_core_name", "core", owner="sciqlop")
    contribute("kn_demo.shadow", "kn_core_name", "plugin")
    assert shell.user_ns["kn_core_name"] == "core"
    assert any("kn_demo.shadow" in message and "sciqlop.kn_core" in message for message in errors)


def test_a_core_name_arriving_after_a_plugin_takes_over(shell, errors):
    contribute("kn_demo.app", "kn_core_name", "plugin")
    contribute("sciqlop.kn_core", "kn_core_name", "core", owner="sciqlop")
    assert shell.user_ns["kn_core_name"] == "core"
    assert any("kn_demo.app" in message for message in errors)


def test_the_first_plugin_holds_a_contested_name(shell, errors):
    contribute("kn_demo.a", "mydata", 1)
    contribute("kn_demo2.b", "mydata", 2, owner="kn_demo2")
    assert shell.user_ns["mydata"] == 1
    assert any("kn_demo2.b" in message and "kn_demo.a" in message for message in errors)


def test_withdrawing_the_holder_promotes_the_next(shell, errors):
    contribute("kn_demo.a", "mydata", 1)
    contribute("kn_demo2.b", "mydata", 2, owner="kn_demo2")
    KERNEL_NAMESPACE.remove_owner("kn_demo")
    assert shell.user_ns["mydata"] == 2


def test_replace_repushes_the_new_value(shell):
    contribute("kn_demo.x", "mydata", 1)
    contribute("kn_demo.x", "mydata", 2, replace=True)
    assert shell.user_ns["mydata"] == 2
    KERNEL_NAMESPACE.remove_owner("kn_demo")
    assert "mydata" not in shell.user_ns


def test_core_names_are_contributions(main_window):
    from SciQLop.components.workspaces.backend.workspaces_manager import workspaces_manager_instance
    user_ns = workspaces_manager_instance()._kernel_manager.shell.user_ns
    for name in ("main_window", "plugins"):
        id = f"sciqlop.{name}"
        assert KERNEL_NAMESPACE.owner_of(id) == "sciqlop"
        assert user_ns[name] is KERNEL_NAMESPACE.get(id).value
