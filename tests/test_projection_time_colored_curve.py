"""``plot_time_colored_curve`` actually colours by time.

It passed ``[x, y, t]`` to ``add_reference_curve``, which reads a list of that
length as one buffer per subplot -- three spatial dimensions on the three-subplot
plots a panel builds. So t was plotted as an axis and nothing was ever coloured
by it. Time now goes first, and the dimensions have to match the panels.

These use plain ``qtbot``/``qapp`` rather than the GUI fixtures, which segfault
in teardown on some machines.
"""
import numpy as np
import pytest

T0 = 1_500_000_000.0


@pytest.fixture
def projection():
    from SciQLopPlots import SciQLopNDProjectionPlot
    from SciQLop.user_api.plot._plots import ProjectionPlot

    def make(subplots):
        return ProjectionPlot(SciQLopNDProjectionPlot(subplots))

    return make


def _orbit(n=200):
    """(t, x, y, z) with t nine orders of magnitude away from the geometry.

    That gap is what makes a spatial axis carrying t unmistakable.
    """
    a = np.linspace(0, 2 * np.pi, n)
    return (np.linspace(T0, T0 + 100.0, n), np.cos(a), np.sin(a),
            np.linspace(-1.0, 1.0, n))


def test_three_dimensions_on_a_three_subplot_plot(qtbot, qapp, projection):
    t, x, y, z = _orbit()
    plot = projection(3)
    assert plot.plot_time_colored_curve(x, y, t, z=z) is not None
    assert plot._get_impl_or_raise().time_color_enabled() is True


def test_two_dimensions_on_a_two_subplot_plot(qtbot, qapp, projection):
    t, x, y, _z = _orbit()
    plot = projection(2)
    assert plot.plot_time_colored_curve(x, y, t) is not None


def test_time_is_never_plotted_as_a_dimension(qtbot, qapp, projection):
    """The original symptom: t on a spatial axis instead of in the colour."""
    t, x, y, z = _orbit()
    plot = projection(3)
    graph = plot.plot_time_colored_curve(x, y, t, z=z)
    impl = plot._get_impl_or_raise()
    qtbot.waitUntil(lambda: not graph._get_impl_or_raise().busy(), timeout=5000)
    qapp.processEvents()
    for i in range(impl.subplot_count()):
        impl.subplot(i).rescale_axes()
    qapp.processEvents()

    for i in range(impl.subplot_count()):
        for name, axis in (("x", impl.subplot(i).x_axis()),
                           ("y", impl.subplot(i).y_axis())):
            r = axis.range()
            assert abs(r.start()) < 100 and abs(r.stop()) < 100, (
                f"subplot {i} {name} axis {r.start()}..{r.stop()} is carrying t")


def test_a_dimension_short_says_so(qtbot, qapp, projection):
    t, x, y, _z = _orbit()
    with pytest.raises(ValueError, match="3 subplots.*3 dimensions.*got 2"):
        projection(3).plot_time_colored_curve(x, y, t)


def test_mismatched_lengths_are_rejected(qtbot, qapp, projection):
    t, x, y, z = _orbit()
    with pytest.raises(ValueError, match="same length"):
        projection(3).plot_time_colored_curve(x, y[:-1], t, z=z)
