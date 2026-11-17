"""A project's state is a badge on its folder icon: each state its own shape, so it reads without
colour."""
from SciQLop.plugins.sciqlop_cocat.icons import BADGES, status_badge

STATES = ["synced", "connecting", "offline", "unauthorized", "no_access", "not joined",
          "read-only", "on this computer", "released", "elsewhere"]


def test_every_state_has_a_badge(qapp):
    assert set(STATES) <= set(BADGES)
    assert all(not status_badge(state).isNull() for state in STATES)


def test_every_state_has_a_shape_of_its_own(qapp):
    """Colour is only a second cue."""
    assert len({BADGES[s][0] for s in STATES}) == len(STATES)


def test_every_state_draws_a_different_icon(qapp):
    images = {bytes(status_badge(s).pixmap(16, 16).toImage().constBits()) for s in STATES}
    assert len(images) == len(STATES)


def test_an_unknown_state_still_draws(qapp):
    assert not status_badge("something new").isNull()
