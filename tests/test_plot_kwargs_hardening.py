"""Backward-compatible promotion of plot **kwargs to explicit keyword params."""
import numpy as np
import pytest
from .fixtures import *

from SciQLop.user_api.plot._graphs import _UNSET, _with_explicit
from SciQLop.user_api.plot import PlotPanel


def test_with_explicit_forwards_set_values():
    kwargs = {"existing": 1}
    out = _with_explicit(kwargs, labels=["a", "b"], name="g")
    assert out is kwargs                      # mutates and returns the same dict
    assert out == {"existing": 1, "labels": ["a", "b"], "name": "g"}


def test_with_explicit_skips_unset_values():
    out = _with_explicit({}, labels=_UNSET, name="g", colors=_UNSET)
    assert out == {"name": "g"}               # _UNSET params are not forwarded


def test_with_explicit_unset_is_falsy_safe():
    # A real value that is falsy (False / [] / 0) must still be forwarded.
    out = _with_explicit({}, y_log_scale=False, labels=[], graph_type=0)
    assert out == {"y_log_scale": False, "labels": [], "graph_type": 0}


def _capture_panel_fn(monkeypatch, attr):
    """Spy that records the kwargs reaching a component-layer plot function
    and still delegates to the real one (so the graph is really created)."""
    import SciQLop.user_api.plot._panel as pm
    captured = {}
    original = getattr(pm, attr)

    def spy(impl, *args, **kwargs):
        captured.clear()
        captured.update(kwargs)
        return original(impl, *args, **kwargs)

    monkeypatch.setattr(pm, attr, spy)
    return captured


def test_plot_function_forwards_set_params_only(plot_panel, monkeypatch):
    captured = _capture_panel_fn(monkeypatch, "_plot_function")

    def f(start, stop):
        x = np.linspace(start, stop, 10)
        return x, np.sin(x)

    # Note: y_log_scale is only accepted by the SciQLopPlots colormap()
    # binding, not line() (the default graph_type here) — verified directly
    # against SciQLopPlots 0.29.2, and true of the *unmodified* plot_function
    # too, so this is a pre-existing library constraint, not something
    # introduced by this promotion. colors is used instead to exercise a
    # second "present" param; y_log_scale exercises the "absent" case.
    plot_panel.plot_function(f, labels=["s"], colors=["#ff0000"])
    assert captured["labels"] == ["s"]
    assert captured["colors"] == ["#ff0000"]
    assert "y_log_scale" not in captured       # omitted → not forwarded


def test_plot_function_name_hint_from_function_name(plot_panel):
    # `name` is applied via `set_name()` on the created graph rather than
    # forwarded through kwargs to `_plot_function` (SciQLopPlots' line()
    # binding rejects an upfront `name=` keyword — see the implementation
    # comment in _panel.py), so this is asserted on the real graph object
    # instead of via the `_capture_panel_fn` kwargs spy used above.
    def my_signal(start, stop):
        x = np.linspace(start, stop, 10)
        return x, np.sin(x)

    _, graph = plot_panel.plot_function(my_signal)
    assert graph._get_impl_or_raise().name == "my_signal"  # base name hint applied

    _, graph2 = plot_panel.plot_function(
        lambda s, e: (np.array([s, e]), np.array([0.0, 1.0])))
    assert graph2._get_impl_or_raise().name != "my_signal"  # <lambda> is skipped


def test_plot_data_forwards_set_params_only(plot_panel, monkeypatch):
    captured = _capture_panel_fn(monkeypatch, "_plot_static_data")
    x = np.linspace(0, 1, 20)
    y = np.column_stack([np.sin(x), np.cos(x)])
    plot_panel.plot_data(x, y, labels=["a", "b"], colors=["#ff0000", "#00ff00"])
    assert captured["labels"] == ["a", "b"]
    assert captured["colors"] == ["#ff0000", "#00ff00"]
    assert "y_log_scale" not in captured


def test_plot_data_promoted_params_are_keyword_only():
    # The brief's originally proposed regression test tried to prove
    # keyword-only-ness via `plot_data(x, y, -1, ["a"])` raising TypeError.
    # Verified against both the pre- and post-promotion code: that call
    # binds positionally to `z=-1, plot_index=["a"]` in *both* versions
    # (plot_data's own `z`/`plot_index` occupy positions 3-4, not `labels`)
    # and raises the same ValueError from `ensure_arrays_of_double` either
    # way — it does not exercise the keyword-only promotion at all. The
    # actual, verifiable contract is checked directly on the signature.
    import inspect
    from SciQLop.user_api.plot._panel import PlotPanel

    sig = inspect.signature(PlotPanel.plot_data)
    for name in ("labels", "name", "plot_type", "graph_type", "colors",
                "y_log_scale", "z_log_scale"):
        assert sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY


def test_plot_data_name_applied_without_forwarding(plot_panel, monkeypatch):
    # `name` is applied via `set_name()` on the created graph rather than
    # forwarded through kwargs to `_plot_static_data`: SciQLopPlots' line()
    # binding (used here since `y` is 1-D/2-D, i.e. no `z`) rejects an
    # upfront `name=` keyword — only colormap() accepts it — verified
    # directly against SciQLopPlots 0.29.2, same constraint already hit by
    # `plot_function` in Task 2.
    captured = _capture_panel_fn(monkeypatch, "_plot_static_data")
    x = np.linspace(0, 1, 20)
    y = np.sin(x)
    _, graph = plot_panel.plot_data(x, y, name="my_line")
    assert "name" not in captured
    assert graph._get_impl_or_raise().name == "my_line"


def test_plot_product_keyword_only_and_backward_compatible(plot_panel):
    # Verified against the pre-promotion signature too: `plot_product(self,
    # product, plot_index=-1, **kwargs)` only has two positional-or-keyword
    # parameters, so a 3rd positional argument already raised TypeError
    # before this change (no *args to absorb it) — this call doesn't
    # exercise the keyword-only promotion itself. The real contract is
    # checked below via inspect.signature. This test still guards the
    # user-facing behavior: passing an extra positional must keep raising,
    # not silently succeed.
    from SciQLop.user_api.plot import PlotType
    with pytest.raises(TypeError):
        plot_panel.plot_product(["a", "b"], -1, PlotType.XY)


def test_plot_product_plot_type_and_graph_type_are_keyword_only():
    import inspect
    from SciQLop.user_api.plot._panel import PlotPanel

    sig = inspect.signature(PlotPanel.plot_product)
    for name in ("plot_type", "graph_type"):
        assert sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY


def test_plot_product_forwards_plot_type_and_graph_type(plot_panel, simple_vp_callback, monkeypatch):
    # Verifies plot_type/graph_type reach the real component-layer
    # plot_product call cleanly when passed by keyword (the promoted path).
    #
    # graph_type=GraphType.Scatter was tried first and found to crash: the
    # SciQLopPlots 0.29.2 scatter() binding reuses the name `plot_type` for
    # an unrelated GraphMarkerShape parameter (and calls the actual PlotType
    # parameter `marker`), so forwarding our PlotType under the `plot_type`
    # keyword raises a ValueError from the Shiboken overload resolver.
    # Verified this is pre-existing (reproduces identically against the
    # unmodified plot_product) and independent of this promotion, so it is
    # a SciQLopPlots binding concern, not something to fix here. graph_type
    # =GraphType.Line (the default, going through the line() binding used
    # by every other test in this file) is used instead to exercise the
    # forwarding path cleanly.
    from SciQLop.user_api.plot import PlotType
    from SciQLop.user_api.plot.enums import GraphType
    from SciQLopPlots import GraphType as _GraphType
    from SciQLop.user_api.virtual_products import (
        create_virtual_product, VirtualProductType,
    )
    # plot_product routes through _plots.plot_product_or_raise, which calls
    # its own module-level `_plot_product` reference (not _panel's) — spy on
    # that one instead of reusing `_capture_panel_fn` (which patches _panel).
    import SciQLop.user_api.plot._plots as plots_mod
    captured = {}
    original = plots_mod._plot_product

    def spy(impl, *args, **kwargs):
        captured.clear()
        captured.update(kwargs)
        return original(impl, *args, **kwargs)

    monkeypatch.setattr(plots_mod, "_plot_product", spy)
    vp = create_virtual_product(
        "test_plot_product_kwargs/vp1", simple_vp_callback,
        VirtualProductType.Scalar, labels=["y"])
    plot, graph = plot_panel.plot_product(
        vp, plot_type=PlotType.TimeSeries, graph_type=GraphType.Line)
    assert plot is not None
    assert graph is not None
    assert captured["graph_type"] == _GraphType.Line


def test_plot_omnibus_still_dispatches_and_forwards(plot_panel, monkeypatch):
    captured = _capture_panel_fn(monkeypatch, "_plot_function")

    def f(start, stop):
        x = np.linspace(start, stop, 10)
        return x, np.sin(x)

    plot_panel.plot(f, labels=["s"])           # routes to plot_function
    assert captured["labels"] == ["s"]


def test_plot_has_docstring():
    assert (PlotPanel.plot.__doc__ or "").strip(), "plot() must document its options"


def test_plot_level_methods_are_keyword_only():
    # The brief's originally proposed regression test tried to prove
    # keyword-only-ness via `plot.plot(x, y, ["a"])` raising TypeError.
    # Verified against both TimeSeriesPlot and XYPlot (pre- and
    # post-promotion): 3 positional args always land in `*args` — that's the
    # z=colormap path for either plot type — regardless of whether `labels`
    # is keyword-only, since `*args` absorbs any number of positional
    # arguments and never binds them to a named parameter. The actual
    # failure is a ValueError from `ensure_arrays_of_double` trying to
    # convert `["a"]` to float64, never a TypeError; this call does not
    # exercise the keyword-only promotion at all. The real, verifiable
    # contract is checked directly on the signatures instead (same fix
    # already applied to `test_plot_data_promoted_params_are_keyword_only`).
    import inspect
    from SciQLop.user_api.plot._plots import XYPlot, TimeSeriesPlot

    for cls in (XYPlot, TimeSeriesPlot):
        sig = inspect.signature(cls.plot)
        for name in ("labels", "name", "colors", "graph_type",
                    "y_log_scale", "z_log_scale", "y_axis"):
            assert sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY, \
                f"{cls.__name__}.plot's {name!r} must be keyword-only"


def test_plot_level_name_is_observable(plot_panel):
    x = np.linspace(0, 1, 20)
    y = np.sin(x)
    plot, _g = plot_panel.plot_data(x, y)      # a TimeSeriesPlot
    graph = plot.plot(x, np.cos(x), name="second")
    assert graph._impl.name == "second"


def test_plot_level_name_is_observable_on_xy_plot(plot_panel):
    # XYPlot.plot's default graph_type is ParametricCurve; the installed
    # SciQLopPlots 0.29.2 `parametric_curve()` binding rejects an upfront
    # `name=` keyword the same way `line()`/`scatter()` do (verified
    # directly) — so this exercises the same `_apply_name`-after-creation
    # fix as the TimeSeriesPlot/line case above, on a different graph
    # creation path.
    from SciQLop.user_api.plot import PlotType
    x = np.linspace(0, 1, 20)
    y = np.sin(x)
    plot, _g = plot_panel.plot_data(x, y, plot_type=PlotType.XY)
    graph = plot.plot(x, np.cos(x), name="xy_second")
    assert graph._impl.name == "xy_second"


def test_plot_level_name_is_observable_on_colormap(plot_panel):
    # The 3-arg (x, y, z) path routes through SciQLopPlots' `colormap()`
    # binding, which — unlike line/curve/scatter — accepts an upfront
    # `name=` keyword directly (verified directly against SciQLopPlots
    # 0.29.2). `_apply_name` still applies it after creation uniformly, so
    # this guards that the colormap path keeps working under that scheme.
    from SciQLop.user_api.plot import PlotType
    x = np.linspace(0, 1, 5)
    y = np.linspace(0, 1, 6)
    z = np.random.rand(5, 6)
    # Create a bare XY plot first (2-arg curve, not a colormap) so the
    # 3-arg colormap call below is the plot's first and only colormap —
    # a plot can host only one (see _reject_if_colormap_already_present).
    plot, _g = plot_panel.plot_data(x, x, plot_type=PlotType.XY)
    colormap = plot.plot(x, y, z, name="my_colormap")
    assert colormap._impl.name == "my_colormap"


def test_plot_level_colors_and_labels_still_forward(plot_panel):
    # Regression guard: colors/labels forward cleanly on the line path (no
    # provider to conflict with, unlike the product path) — promoting them
    # to explicit keyword-only params must not break this.
    x = np.linspace(0, 1, 20)
    y = np.column_stack([np.sin(x), np.cos(x)])
    plot, _g = plot_panel.plot_data(x, y)
    graph = plot.plot(x, y, colors=["#ff0000", "#00ff00"], labels=["a", "b"])
    assert graph is not None


def test_plot_level_name_not_forwarded_via_kwargs(plot_panel, monkeypatch):
    # `name` must never reach SciQLopPlots' raw `impl.plot()` call: forwarding
    # it crashes for line/curve/scatter graph types (verified directly
    # against SciQLopPlots 0.29.2 — only colormap() accepts an upfront
    # `name=`). Spy on the impl's `plot` method to confirm it is applied via
    # `set_name()` afterwards instead.
    x = np.linspace(0, 1, 20)
    y = np.sin(x)
    plot, _g = plot_panel.plot_data(x, y)
    impl = plot._get_impl_or_raise()
    original_plot = type(impl).plot
    captured = {}

    def spy(self, *args, **kwargs):
        captured.update(kwargs)
        return original_plot(self, *args, **kwargs)

    monkeypatch.setattr(type(impl), "plot", spy)
    graph = plot.plot(x, np.cos(x), name="not_forwarded")
    assert "name" not in captured
    assert graph._impl.name == "not_forwarded"


def test_plot_level_name_is_observable_on_product(plot_panel, simple_vp_callback):
    # TimeSeriesPlot.plot's product branch (a single non-callable arg) also
    # routes through _apply_name after creation. Unlike labels (which
    # collides with the provider's own labels= and raises TypeError, see
    # PlotPanel.plot_product's docstring), name has no provider-side
    # equivalent to collide with, so it applies cleanly here too. Pins the
    # non-obvious fact this relies on: plot_product returns a single
    # set_name-able graph (not a (plot, graph) tuple) when the target is a
    # plot rather than a panel.
    from SciQLop.user_api.virtual_products import (
        create_virtual_product, VirtualProductType,
    )
    x = np.linspace(0, 1, 20)
    y = np.sin(x)
    plot, _g = plot_panel.plot_data(x, y)          # a TimeSeriesPlot
    vp = create_virtual_product(
        "test_plot_level_name_kwargs/vp1", simple_vp_callback,
        VirtualProductType.Scalar, labels=["y"])
    graph = plot.plot(vp, name="product_name")
    assert graph._impl.name == "product_name"


def test_scatter_labels_observable(plot_panel):
    from SciQLop.user_api.plot import PlotType
    x = np.linspace(0, 1, 20)
    y = np.sin(x)
    plot, _g = plot_panel.plot_data(x, y, plot_type=PlotType.XY)
    g = plot.scatter(x, np.cos(x), labels=["pts"])
    assert g._impl.labels() == ["pts"]


def test_scatter_label_is_keyword_only(plot_panel):
    from SciQLop.user_api.plot import PlotType
    x = np.linspace(0, 1, 20)
    y = np.sin(x)
    plot, _g = plot_panel.plot_data(x, y, plot_type=PlotType.XY)
    with pytest.raises(TypeError):
        plot.scatter(x, np.cos(x), ["pts"])    # labels keyword-only


def test_scatter_name_applied_without_forwarding(plot_panel, monkeypatch):
    # `name` must never reach SciQLopPlots' raw `impl.scatter()` call: the
    # installed SciQLopPlots 0.29.2 `scatter()` binding rejects an upfront
    # `name=` keyword the same way `line()`/`parametric_curve()` do (verified
    # directly, see `_apply_name`'s docstring in `_plots.py`). Spy on the
    # impl's `scatter` method to confirm it is applied via `set_name()`
    # afterwards instead.
    from SciQLop.user_api.plot import PlotType
    x = np.linspace(0, 1, 20)
    y = np.sin(x)
    plot, _g = plot_panel.plot_data(x, y, plot_type=PlotType.XY)
    impl = plot._get_impl_or_raise()
    original_scatter = type(impl).scatter
    captured = {}

    def spy(self, *args, **kwargs):
        captured.update(kwargs)
        return original_scatter(self, *args, **kwargs)

    monkeypatch.setattr(type(impl), "scatter", spy)
    graph = plot.scatter(x, np.cos(x), name="my_scatter")
    assert "name" not in captured
    assert graph._impl.name == "my_scatter"


def test_plot_data_xy_honours_an_explicit_graph_type(plot_panel):
    from SciQLop.user_api.plot import PlotType
    from SciQLop.user_api.plot.enums import GraphType
    x = np.linspace(0, 1, 20)
    plot, curve = plot_panel.plot_data(x, np.sin(x), plot_type=PlotType.XY)
    _plot, scatter = plot_panel.plot_data(x, np.cos(x), plot_type=PlotType.XY,
                                          graph_type=GraphType.Scatter)
    reference = plot.scatter(x, np.cos(x))
    assert type(scatter._impl) is type(reference._impl)
    assert type(scatter._impl) is not type(curve._impl)
