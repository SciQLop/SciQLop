"""Listing and naming panels from the public user API."""
from .fixtures import *  # noqa: F401,F403


def test_create_plot_panel_takes_a_name(main_window):
    from SciQLop.user_api.plot import create_plot_panel, plot_panel

    panel = create_plot_panel(name="listing-test")
    assert panel.name == "listing-test"
    assert plot_panel("listing-test").name == "listing-test"


def test_list_plot_panels_names_every_open_panel(main_window):
    from SciQLop.user_api.plot import create_plot_panel, list_plot_panels

    a = create_plot_panel()
    b = create_plot_panel()
    names = list_plot_panels()
    assert a.name in names and b.name in names


def test_plot_enums_are_reexported():
    import SciQLop.user_api.plot as plot
    from SciQLop.user_api.plot import enums

    for name in ("GraphType", "GraphLineStyle", "BinStrategy", "AxisType",
                 "CoordinateSystem", "Orientation"):
        assert getattr(plot, name) is getattr(enums, name)
        assert name in plot.__all__
