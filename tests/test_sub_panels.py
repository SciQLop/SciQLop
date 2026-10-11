"""A panel whose content is a sub-panel is not empty.

Before: its "add a product" overlay stayed on top of the sub-panel's plots.
"""
from .fixtures import *  # noqa: F401,F403 — qapp/main_window/plot_panel fixtures


def test_adding_a_sub_panel_dismisses_the_empty_panel_overlay(plot_panel):
    impl = plot_panel._get_impl_or_raise()
    assert impl._search_overlay is not None
    plot_panel.add_sub_panel()
    assert impl._search_overlay is None
