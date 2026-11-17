"""A project's state is a badge on its folder icon: each state its own shape, so it reads without
colour."""
from SciQLop.plugins.sciqlop_cocat.icons import BADGES, status_badge

STATES = ["synced", "connecting", "offline", "unauthorized", "no_access", "not joined",
          "read-only", "on this computer", "released", "elsewhere"]


def test_every_state_has_a_badge(qapp):
    assert set(STATES) <= set(BADGES)
    assert all(not status_badge(state).isNull() for state in STATES)


def test_the_states_people_must_tell_apart_have_different_shapes(qapp):
    shapes = {BADGES[s][0] for s in ("synced", "connecting", "offline", "unauthorized", "on this computer",
                                     "read-only", "elsewhere")}
    assert len(shapes) == 7


def test_an_unknown_state_still_draws(qapp):
    assert not status_badge("something new").isNull()
