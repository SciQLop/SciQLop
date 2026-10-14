"""Extension points: typed, owner-tagged registries (spec §4.1)."""
import threading
from dataclasses import dataclass

import pytest

from SciQLop.core import extensions
from SciQLop.core.extensions import (DuplicateContribution, ExtensionPoint, NotRegistered, WrongThread,
                                     current_owner, owned_by)


@dataclass(frozen=True)
class Kind:
    id: str
    colour: str = "red"


@pytest.fixture
def ep():
    return ExtensionPoint("test.kinds", Kind, what="kind")


@pytest.fixture
def clean_registry():
    saved = dict(extensions._EXTENSION_POINTS)
    yield
    extensions._EXTENSION_POINTS.clear()
    extensions._EXTENSION_POINTS.update(saved)


def test_contribute_then_get_and_list(ep):
    ep.contribute(Kind("a.x", "blue"), owner="a")
    ep.contribute(Kind("b.y"), owner="b")
    assert ep.get("a.x").colour == "blue"
    assert [k.id for k in ep.list(colour="red")] == ["b.y"]


def test_wrong_type_is_refused(ep):
    with pytest.raises(TypeError, match="test.kinds takes Kind, got str"):
        ep.contribute("nope", owner="a")


def test_same_owner_replaces_other_owner_raises(ep):
    ep.contribute(Kind("a.x"), owner="a")
    ep.contribute(Kind("a.x", "green"), owner="a")
    assert ep.get("a.x").colour == "green"
    with pytest.raises(DuplicateContribution, match="kind 'a.x' is already registered by a"):
        ep.contribute(Kind("a.x"), owner="b")


def test_explicit_replace_lets_another_owner_take_over(ep):
    ep.contribute(Kind("a.x"), owner="a")
    ep.contribute(Kind("a.x", "pink"), owner="b", replace=True)
    assert ep.owner_of("a.x") == "b"


def test_missing_key_names_what_exists(ep):
    ep.contribute(Kind("a.x"), owner="a")
    with pytest.raises(NotRegistered, match="no kind named 'zz'; available: a.x"):
        ep.get("zz")


def test_owner_defaults_to_the_current_owner(ep):
    assert current_owner() == "user"
    with owned_by("legacy:old"):
        ep.contribute(Kind("o.k"))
    assert ep.owner_of("o.k") == "legacy:old" and current_owner() == "user"


def test_remove_owner_removes_only_theirs_and_signals(ep, qtbot):
    ep.contribute(Kind("a.x"), owner="a")
    ep.contribute(Kind("b.y"), owner="b")
    removed = []
    ep.signals.removed.connect(removed.append)
    assert [k.id for k in ep.remove_owner("a")] == ["a.x"]
    assert [k.id for k in removed] == ["a.x"] and ep.contributed_by("b") == ["b.y"]


def test_added_signal_fires(ep, qtbot):
    added = []
    ep.signals.added.connect(added.append)
    ep.contribute(Kind("a.x"), owner="a")
    assert [k.id for k in added] == ["a.x"]


def test_contributing_off_the_main_thread_raises(ep, qapp):
    errors = []

    def worker():
        try:
            ep.contribute(Kind("a.x"), owner="a")
        except WrongThread as e:
            errors.append(e)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert errors and "main thread" in str(errors[0])


def test_declare_and_lookup(clean_registry):
    ep = extensions.declare(ExtensionPoint("test.declared", Kind, owner="tester"))
    assert extensions.get("test.declared") is ep and ep.owner == "tester"
    with pytest.raises(DuplicateContribution, match="extension point 'test.declared' is already declared by tester"):
        extensions.declare(ExtensionPoint("test.declared", Kind))
    with pytest.raises(NotRegistered, match="no extension point named 'test.nope'"):
        extensions.get("test.nope")
