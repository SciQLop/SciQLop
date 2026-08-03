"""Claimed sessions are handed to the backend for archiving, and forgotten on delete."""
from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures
from .test_sessions_view_groups import _Entry, _Meta


def test_claimed_ids_lists_only_customised_sessions():
    import SciQLop.components.agents.chat.sessions_view as v

    entries = [_Entry("a", "Auto A", 1.0), _Entry("b", "Auto B", 2.0),
               _Entry("c", "Auto C", 3.0), _Entry("d", "Auto D", 4.0)]
    meta = _Meta({
        ("K", "a"): ("Renamed", False, "", []),
        ("K", "b"): ("", True, "", []),
        ("K", "c"): ("", False, "MMS", []),
    })
    assert v.claimed_ids(entries, meta, "K") == ["a", "b", "c"]


def test_meta_forget_drops_every_field():
    from SciQLop.components.agents.settings import AgentSessionMeta

    meta = AgentSessionMeta()
    meta.set_name("K", "s1", "Kept")
    meta.set_group("K", "s1", "MMS")
    meta.set_name("K", "s2", "Other")
    meta.forget("K", "s1")

    assert meta.get("K", "s1") == meta.get("K", "unknown-session")
    assert meta.get("K", "s2").name == "Other"
    meta.forget("K", "s2")


def test_forgetting_an_unknown_session_is_a_no_op():
    from SciQLop.components.agents.settings import AgentSessionMeta

    AgentSessionMeta().forget("K", "never-seen")
