"""The recency cut drops untouched sessions only — never customised ones."""
from .test_sessions_view_groups import _Entry, _Meta


def _view():
    import SciQLop.components.agents.chat.sessions_view as v
    return v


def _entries(count):
    return [_Entry(f"s{i}", f"Auto {i}", float(i)) for i in range(count)]


def _ids(groups):
    return {s.id for g in groups for s in g.sessions}


def test_keeps_only_the_most_recent_untouched_sessions():
    v = _view()
    groups = v.grouped_sessions(_entries(10), _Meta({}), "K", recent_limit=3)
    assert _ids(groups) == {"s9", "s8", "s7"}


def test_renamed_session_survives_the_cut():
    v = _view()
    meta = _Meta({("K", "s0"): ("Magnetopause crossings", False, "", [])})
    groups = v.grouped_sessions(_entries(10), meta, "K", recent_limit=3)
    assert "s0" in _ids(groups)


def test_grouped_pinned_and_tagged_sessions_survive_the_cut():
    v = _view()
    meta = _Meta({
        ("K", "s0"): ("", False, "MMS", []),
        ("K", "s1"): ("", True, "", []),
        ("K", "s2"): ("", False, "", ["reconnection"]),
    })
    groups = v.grouped_sessions(_entries(10), meta, "K", recent_limit=1)
    assert {"s0", "s1", "s2", "s9"} == _ids(groups)


def test_customised_sessions_do_not_consume_the_recent_budget():
    v = _view()
    meta = _Meta({("K", "s9"): ("Kept", False, "", [])})
    groups = v.grouped_sessions(_entries(10), meta, "K", recent_limit=2)
    assert _ids(groups) == {"s9", "s8", "s7"}


def test_no_limit_lists_everything():
    v = _view()
    groups = v.grouped_sessions(_entries(10), _Meta({}), "K", recent_limit=None)
    assert len(_ids(groups)) == 10
