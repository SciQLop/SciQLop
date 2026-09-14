"""User-API misuse must fail loudly with actionable errors, not silently.

Reproducers from the 2026-06-12 fuzzing report (docs/api-fuzzing-report-2026-06-12.md).
"""
from .fixtures import *  # noqa: F401,F403 — qapp/main_window/plot_panel fixtures
import numpy as np
import pytest


class TestPlotProductErrors:
    """Report #10 — unknown/invalid products raised an internal
    `TypeError: cannot unpack non-iterable NoneType` instead of a ValueError."""

    def test_unknown_product_raises_value_error(self, plot_panel):
        with pytest.raises(ValueError, match="does//not//exist"):
            plot_panel.plot_product("does//not//exist")

    @pytest.mark.parametrize("bad", ["", None, 42, [], [1, 2], ["a", 3]])
    def test_invalid_product_spec_raises_value_error(self, plot_panel, bad):
        with pytest.raises(ValueError, match="invalid product"):
            plot_panel.plot_product(bad)

    def test_plot_with_unknown_product_on_existing_plot(self, plot_panel):
        from SciQLop.user_api.plot import PlotType

        x = np.linspace(0.0, 100.0, 50)
        plot, _ = plot_panel.plot_data(x, np.sin(x), plot_type=PlotType.TimeSeries)
        with pytest.raises(ValueError, match="does//not//exist"):
            plot.plot("does//not//exist")


def _flush_deferred_deletes(qapp):
    from PySide6.QtCore import QCoreApplication, QEvent

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


class TestStaleWrappersAndPlotType:
    """Report #8 — stale plot/graph wrappers must raise like stale panels do,
    and ``plot_type`` must return the real enum on healthy plots instead of
    the protocol stub's silent None."""

    @pytest.fixture
    def stale(self, qapp, plot_panel):
        from SciQLop.user_api.plot import PlotType

        x = np.linspace(0.0, 100.0, 50)
        plot, graph = plot_panel.plot_data(x, np.sin(x), plot_type=PlotType.TimeSeries)
        plot_panel.remove_plot(0)
        _flush_deferred_deletes(qapp)
        return plot, graph

    def test_plot_type_on_healthy_plots(self, plot_panel):
        from SciQLop.user_api.plot import PlotType

        x = np.linspace(0.0, 100.0, 50)
        ts, _ = plot_panel.plot_data(x, np.sin(x), plot_type=PlotType.TimeSeries)
        xy, _ = plot_panel.plot_data(x, np.sin(x), plot_type=PlotType.XY)
        assert ts.plot_type == PlotType.TimeSeries
        assert xy.plot_type == PlotType.XY

    def test_stale_plot_methods_raise(self, stale):
        plot, _graph = stale
        with pytest.raises(ValueError, match="does not exist anymore"):
            plot.replot()
        with pytest.raises(ValueError, match="does not exist anymore"):
            plot.set_y_range(0.0, 1.0)
        with pytest.raises(ValueError, match="does not exist anymore"):
            plot.plot_type

    def test_stale_graph_raises(self, stale):
        _plot, graph = stale
        with pytest.raises(ValueError, match="does not exist anymore"):
            graph.set_data(np.array([1.0, 2.0]), np.array([3.0, 4.0]))


class TestPanelImplDeathDoesNotCorruptSiblings:
    """Report #3 — destroying a panel's impl widget directly (abuse, but
    possible from the console) left a zombie dock entry that broke panel
    enumeration for *sibling* panels: ``plot_panels()`` raised on the dead
    Shiboken wrapper and reported nothing at all."""

    def test_killing_impl_keeps_siblings_enumerable(self, qapp, qtbot, main_window):
        from SciQLop.user_api.plot import create_plot_panel

        keeper = create_plot_panel()
        victim = create_plot_panel()
        keeper_name = keeper._impl.objectName()
        victim_name = victim._impl.objectName()
        assert {keeper_name, victim_name} <= set(main_window.plot_panels())

        victim._impl.close()
        victim._impl.deleteLater()
        _flush_deferred_deletes(qapp)

        qtbot.waitUntil(
            lambda: main_window.dock_manager.findDockWidget(victim_name) is None,
            timeout=5000)
        panels = main_window.plot_panels()
        assert keeper_name in panels
        assert victim_name not in panels


class TestTimeRangeValidation:
    """Report #6/#7 — non-finite ranges corrupted the panel to 1970, and the
    C++ TimeRange parses garbage strings to epoch 0 silently (zero-width)."""

    def test_nan_time_range_rejected(self, plot_panel):
        from SciQLop.user_api.plot import TimeRange

        with pytest.raises(ValueError, match="finite"):
            plot_panel.time_range = TimeRange(float("nan"), float("nan"))

    def test_garbage_string_time_range_rejected(self, plot_panel):
        from SciQLop.user_api.plot import TimeRange

        # round-2 #6 leftover: TimeRange now parses date strings on the Python
        # side, so garbage is rejected at construction (ParserError, a
        # ValueError) instead of silently becoming a NaN range.
        with pytest.raises(ValueError):
            plot_panel.time_range = TimeRange("garbage", "dates")

    def test_zero_width_time_range_rejected(self, plot_panel):
        from SciQLop.user_api.plot import TimeRange

        with pytest.raises(ValueError, match="zero-width"):
            plot_panel.time_range = TimeRange(1e9, 1e9)

    def test_valid_time_range_applies(self, plot_panel):
        from SciQLop.user_api.plot import TimeRange

        plot_panel.time_range = TimeRange(1e9, 1e9 + 3600.0)
        applied = plot_panel.time_range
        assert applied.start() == pytest.approx(1e9, abs=1.0)


class TestPanelSaveErrors:
    """Report #4/#5 — ``panel.save()`` returned None with no file and no error
    on unwritable destinations; the C++ exporters' boolean result was dropped."""

    def test_save_to_missing_directory_raises(self, plot_panel, tmp_path):
        with pytest.raises(OSError, match="failed to save"):
            plot_panel.save(str(tmp_path / "nonexistent" / "dir" / "x.png"))

    def test_save_to_unwritable_directory_raises(self, plot_panel, tmp_path):
        import os

        locked = tmp_path / "locked"
        locked.mkdir()
        locked.chmod(0o500)
        if os.access(locked, os.W_OK):  # running as root — permission not enforceable
            pytest.skip("cannot create an unwritable directory in this environment")
        try:
            with pytest.raises(OSError, match="failed to save"):
                plot_panel.save(str(locked / "x.png"))
        finally:
            locked.chmod(0o700)

    def test_save_success_writes_file(self, plot_panel, tmp_path):
        target = tmp_path / "panel.png"
        plot_panel.save(str(target))
        assert target.is_file() and target.stat().st_size > 0


class TestValidationSweep:
    """Report #11–#18 — lower-priority validation gaps."""

    def test_histogram2d_zero_or_negative_bins_rejected(self, plot_panel):
        x, y = np.random.rand(100), np.random.rand(100)
        for bad in (0, -5):
            with pytest.raises(ValueError, match="bins"):
                plot_panel.histogram2d(x, y, x_bins=bad, y_bins=10)

    def test_histogram2d_absurd_grid_rejected(self, plot_panel):
        x, y = np.random.rand(100), np.random.rand(100)
        with pytest.raises(ValueError, match="bins"):
            plot_panel.histogram2d(x, y, x_bins=10_000, y_bins=10_000)

    def test_plot_data_without_y_rejected(self, plot_panel):
        with pytest.raises(ValueError, match="y"):
            plot_panel.plot_data(np.linspace(0.0, 1.0, 10))

    def test_zero_dim_arrays_rejected(self, plot_panel):
        with pytest.raises(ValueError, match="scalar"):
            plot_panel.plot_data(np.array(1.0), np.array(2.0))

    def test_complex_data_rejected(self, plot_panel):
        x = np.linspace(0.0, 1.0, 10)
        with pytest.raises(ValueError, match="complex"):
            plot_panel.plot_data(x, x.astype(np.complex128))

    def test_negative_zoom_limit_rejected(self, plot_panel):
        with pytest.raises(ValueError, match="zoom_limit_seconds"):
            plot_panel.zoom_limit_seconds = -5

    def test_plot_panel_non_string_name_rejected(self, main_window):
        from SciQLop.user_api.plot import plot_panel as get_panel

        with pytest.raises(TypeError, match="str"):
            get_panel(42)


class TestPlotFunctionErrorOverlay:
    """Report #9 — a plot_function callback that raises produced a console
    traceback only: the plot was created 'successfully' and stayed empty
    forever. The error must land on the plot's in-canvas overlay."""

    def test_callback_error_shown_on_overlay(self, qtbot, plot_panel):
        from SciQLop.user_api.plot import TimeRange

        def bad(start, stop):
            raise RuntimeError("boom from callback")

        plot, _graph = plot_panel.plot_function(bad)
        plot_panel.time_range = TimeRange(1e9, 1e9 + 3600.0)
        qtbot.waitUntil(lambda: "boom from callback" in plot.overlay.text, timeout=5000)
        from SciQLop.user_api.plot.enums import OverlayLevel

        assert plot.overlay.level == OverlayLevel.Error

    def test_overlay_clears_after_successful_fetch(self, qtbot, plot_panel):
        from SciQLop.user_api.plot import TimeRange

        calls = {"n": 0}

        def flaky(start, stop):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient boom")
            x = np.linspace(start, stop, 10)
            return x, np.sin(x)

        plot, _graph = plot_panel.plot_function(flaky)
        plot_panel.time_range = TimeRange(1e9, 1e9 + 3600.0)
        qtbot.waitUntil(lambda: "transient boom" in plot.overlay.text, timeout=5000)
        plot_panel.time_range = TimeRange(2e9, 2e9 + 3600.0)
        qtbot.waitUntil(lambda: plot.overlay.text == "", timeout=5000)


# ---------------------------------------------------------------------------
# Round-2 fuzzing (docs/api-fuzzing-report-round2-2026-06-12.md)
# ---------------------------------------------------------------------------

class TestRemoveGraphOwnership:
    """R2-2 — ``plot_a.remove_graph(graph_b)`` destroyed another plot's graph;
    R2-12 — non-graph arguments raised a raw AttributeError."""

    @pytest.fixture
    def two_plots(self, plot_panel):
        from SciQLop.user_api.plot import PlotType

        x = np.linspace(0.0, 100.0, 50)
        plot_a, graph_a = plot_panel.plot_data(x, np.sin(x), plot_type=PlotType.TimeSeries)
        plot_b, graph_b = plot_panel.plot_data(x, np.cos(x), plot_type=PlotType.TimeSeries)
        return plot_a, graph_a, plot_b, graph_b

    def test_foreign_graph_is_rejected(self, qapp, two_plots):
        plot_a, _graph_a, _plot_b, graph_b = two_plots
        with pytest.raises(ValueError, match="does not belong to this plot"):
            plot_a.remove_graph(graph_b)

    def test_foreign_graph_survives(self, qapp, two_plots):
        plot_a, _graph_a, _plot_b, graph_b = two_plots
        with pytest.raises(ValueError):
            plot_a.remove_graph(graph_b)
        _flush_deferred_deletes(qapp)
        assert graph_b.data is not None  # still alive

    def test_own_graph_removal_still_works(self, qapp, two_plots):
        plot_a, graph_a, _plot_b, _graph_b = two_plots
        plot_a.remove_graph(graph_a)
        _flush_deferred_deletes(qapp)
        with pytest.raises(ValueError, match="does not exist anymore"):
            graph_a.data

    @pytest.mark.parametrize("bad", [42, "graph", None, object()])
    def test_non_graph_argument_raises_type_error(self, two_plots, bad):
        plot_a, *_ = two_plots
        with pytest.raises(TypeError, match="expects a Graph"):
            plot_a.remove_graph(bad)


class TestTimeRangeStringParsing:
    """Round-1 #6 leftover — ``TimeRange('garbage', 'dates')`` silently became
    a NaN range (rendered as 1970); the C++ (str, str) overload swallows
    parse failures."""

    def test_garbage_strings_raise(self):
        from SciQLop.user_api import TimeRange

        with pytest.raises(ValueError):
            TimeRange("garbage", "dates")

    def test_valid_strings_parse_to_utc_epochs(self):
        from SciQLop.user_api import TimeRange

        r = TimeRange("2020-01-01", "2020-01-02")
        assert r.start() == 1577836800.0
        assert r.stop() == 1577836800.0 + 86400.0

    def test_floats_and_datetimes_still_work(self):
        from datetime import datetime, timezone
        from SciQLop.user_api import TimeRange

        assert TimeRange(1.0, 2.0).start() == 1.0
        r = TimeRange(datetime(2020, 1, 1, tzinfo=timezone.utc),
                      datetime(2020, 1, 2, tzinfo=timezone.utc))
        assert r.start() == 1577836800.0

    def test_is_still_a_sciqlopplotrange(self):
        from SciQLopPlots import SciQLopPlotRange
        from SciQLop.user_api import TimeRange

        assert isinstance(TimeRange(1.0, 2.0), SciQLopPlotRange)


class TestAddLayerScopeValidation:
    """R2-10 — a bogus ``scope`` was accepted silently."""

    def test_bogus_scope_raises(self, plot_panel):
        from SciQLop.user_api.plot import PlotType

        x = np.linspace(0.0, 100.0, 50)
        plot_panel.plot_data(x, np.sin(x), plot_type=PlotType.TimeSeries)
        with pytest.raises(ValueError, match="scope"):
            plot_panel.add_layer(lambda start, stop: [], scope="bogus_scope")


class TestCreateVirtualProductValidation:
    """R2-3/4/6/7/8 — ``create_virtual_product`` silently returned None on a
    string product_type, accepted empty paths, and masked every argument
    error behind the Scalar label message."""

    @staticmethod
    def _cb(start: float, stop: float):
        return None

    def test_string_product_type_raises_type_error(self, qapp):
        from SciQLop.user_api.virtual_products import create_virtual_product

        with pytest.raises(TypeError, match="product_type"):
            create_virtual_product("fuzz//p1", self._cb, "Scalar", labels=["x"])

    def test_empty_path_raises_value_error(self, qapp):
        from SciQLop.user_api.virtual_products import (
            create_virtual_product, VirtualProductType)

        with pytest.raises(ValueError, match="path"):
            create_virtual_product("", self._cb, VirtualProductType.Scalar,
                                   labels=["x"])

    def test_none_path_raises_type_error(self, qapp):
        from SciQLop.user_api.virtual_products import (
            create_virtual_product, VirtualProductType)

        with pytest.raises(TypeError, match="path"):
            create_virtual_product(None, self._cb, VirtualProductType.Scalar,
                                   labels=["x"])

    def test_bad_callback_reported_before_labels(self, qapp):
        """R2-6 — with cb=42 AND missing labels, the error must blame the
        callback, not the labels."""
        from SciQLop.user_api.virtual_products import (
            create_virtual_product, VirtualProductType)

        with pytest.raises(TypeError, match="callable"):
            create_virtual_product("fuzz//p2", 42, VirtualProductType.Scalar)

    def test_bad_path_reported_before_labels(self, qapp):
        from SciQLop.user_api.virtual_products import (
            create_virtual_product, VirtualProductType)

        with pytest.raises(ValueError, match="path"):
            create_virtual_product("", self._cb, VirtualProductType.Scalar)

    def test_scalar_label_rule_unchanged(self, qapp):
        from SciQLop.user_api.virtual_products import (
            create_virtual_product, VirtualProductType)

        with pytest.raises(ValueError, match="exactly one label"):
            create_virtual_product("fuzz//p3", self._cb, VirtualProductType.Scalar,
                                   labels=["a", "b", "c"])

    def test_direct_scalar_ctor_rejects_none_label(self, qapp):
        """R2-7 — the direct class constructors accepted what
        create_virtual_product rejects."""
        from SciQLop.user_api.virtual_products import VirtualScalar

        with pytest.raises((TypeError, ValueError)):
            VirtualScalar("fuzz//p4", self._cb, label=None)

    def test_direct_vector_ctor_rejects_empty_labels(self, qapp):
        from SciQLop.user_api.virtual_products import VirtualVector

        with pytest.raises(ValueError, match="exactly three labels"):
            VirtualVector("fuzz//p5", self._cb, labels=[])

    @pytest.mark.parametrize("path, expected", [
        ("leadslash//p1", ["leadslash", "p1"]),
        ("//leadslash//p2", ["leadslash", "p2"]),
        ("/leadslash//p3", ["leadslash", "p3"]),
        ("leadslash/p4", ["leadslash", "p4"]),
        ("/leadslash/p5", ["leadslash", "p5"]),
    ])
    def test_leading_separators_normalize(self, qapp, path, expected):
        """Leading '/' / '//' strip to the same product-tree path."""
        from SciQLop.user_api.virtual_products import (
            create_virtual_product, VirtualProductType)
        from SciQLop.user_api.plot._plots import to_product_path
        vp = create_virtual_product(path, self._cb, VirtualProductType.Scalar,
                                    labels=["x"])
        assert to_product_path(vp) == expected

    def test_split_spellings_are_equivalent(self, qapp):
        from SciQLop.core.snippets import split_product_path
        assert (split_product_path("//a//b")
                == split_product_path("/a//b")
                == split_product_path("a//b") == ["a", "b"])
        assert (split_product_path("/a/b")
                == split_product_path("a/b") == ["a", "b"])

    @pytest.mark.parametrize("bad", ["", " ", "/", "//", "///", "a////b"])
    def test_blank_or_hollow_paths_rejected(self, qapp, bad):
        from SciQLop.user_api.virtual_products import (
            create_virtual_product, VirtualProductType)
        with pytest.raises(ValueError, match="path"):
            create_virtual_product(bad, self._cb, VirtualProductType.Scalar,
                                   labels=["x"])

    def test_leading_slash_product_resolves_in_tree(self, qapp):
        from SciQLop.user_api.virtual_products import (
            create_virtual_product, VirtualProductType)
        from SciQLop.core.models import products
        create_virtual_product("//leadslash//plotme", self._cb,
                               VirtualProductType.Scalar, labels=["x"])
        assert products.node(["leadslash", "plotme"]) is not None
