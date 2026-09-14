"""Guards for the 2026-06-09 review API-consistency fixes (A1-A7, V1-V3)."""
from .fixtures import *
import pytest
import numpy as np
from datetime import datetime
from PySide6.QtGui import QColor


@pytest.fixture
def ts_plot(plot_panel):
    from SciQLop.user_api.plot import PlotType
    x = np.linspace(0, 100, 50)
    plot, _ = plot_panel.plot_data(x, np.sin(x), plot_type=PlotType.TimeSeries)
    return plot


class TestGraphicPrimitives:
    def test_color_getters_return_qcolor(self, ts_plot):
        from SciQLop.user_api.plot._graphic_primitives import Ellipse, Text, CurvedLine
        e = Ellipse(ts_plot, 1.0, 1.0, 2.0, 2.0, line_color="#ff0000")
        assert isinstance(e.line_color, QColor)
        assert e.line_color.name() == "#ff0000"
        assert isinstance(e.fill_color, QColor)
        t = Text(ts_plot, "hello", 1.0, 1.0, color="#00ff00")
        assert isinstance(t.color, QColor)
        c = CurvedLine(ts_plot, (0.0, 0.0), (10.0, 10.0), color="#0000ff")
        assert isinstance(c.color, QColor)

    def test_all_items_have_remove(self, ts_plot):
        from SciQLop.user_api.plot._graphic_primitives import Ellipse, Text, CurvedLine
        probes = [
            (Ellipse(ts_plot, 1.0, 1.0, 2.0, 2.0), "position"),
            (Text(ts_plot, "hello", 1.0, 1.0), "text"),
            (CurvedLine(ts_plot, (0.0, 0.0), (10.0, 10.0)), "start"),
        ]
        for item, attr in probes:
            item.remove()
            with pytest.raises(ValueError, match="does not exist anymore"):
                getattr(item, attr)

    def test_item_visible_round_trips(self, ts_plot):
        """SciQLopPlots >= 0.29 implements item visibility upstream, so the
        wrapper delegates instead of raising NotImplementedError."""
        from SciQLop.user_api.plot._graphic_primitives import Ellipse, Text, CurvedLine
        for item in (Ellipse(ts_plot, 1.0, 1.0, 2.0, 2.0),
                     Text(ts_plot, "hello", 1.0, 1.0),
                     CurvedLine(ts_plot, (0.0, 0.0), (10.0, 10.0))):
            assert item.visible is True
            item.visible = False
            assert item.visible is False
            item.visible = True
            assert item.visible is True

    def test_remove_is_idempotent(self, ts_plot):
        from SciQLop.user_api.plot._graphic_primitives import Text
        t = Text(ts_plot, "hello", 1.0, 1.0)
        t.remove()
        t.remove()  # must not raise


class TestNegativePlotIndex:
    def test_remove_plot_accepts_negative_index(self, plot_panel):
        x = np.linspace(0, 100, 50)
        plot_panel.plot(x, np.sin(x))
        plot_panel.plot(x, np.cos(x))
        assert len(plot_panel.plots) == 2
        plot_panel.remove_plot(-1)
        assert len(plot_panel.plots) == 1

    def test_remove_plot_out_of_range_raises(self, plot_panel):
        x = np.linspace(0, 100, 50)
        plot_panel.plot(x, np.sin(x))
        with pytest.raises(IndexError):
            plot_panel.remove_plot(5)
        with pytest.raises(IndexError):
            plot_panel.remove_plot(-5)


class TestVirtualProductValidation:
    def test_create_virtual_product_raises_value_error(self):
        from SciQLop.user_api.virtual_products import (
            create_virtual_product, VirtualProductType,
        )
        with pytest.raises(ValueError, match="exactly one label"):
            create_virtual_product("x/y", lambda a, b: None,
                                   VirtualProductType.Scalar, labels=None)
        with pytest.raises(ValueError, match="exactly three labels"):
            create_virtual_product("x/y", lambda a, b: None,
                                   VirtualProductType.Vector, labels=["a"])


class TestVPRobustness:
    def test_unresolvable_hints_warn_instead_of_silent_drop(self, caplog):
        import logging
        from SciQLop.components.plotting.backend.dependencies import (
            extract_dependencies_from_callback,
        )

        def cb(start: float, stop: float, dep: "NoSuchType") -> None:  # noqa: F821
            pass

        with caplog.at_level(logging.WARNING,
                             logger="SciQLop.components.plotting.backend.dependencies"):
            specs = extract_dependencies_from_callback(cb)
        assert specs == []
        assert any("cannot resolve type hints" in r.message for r in caplog.records)

    def test_easy_provider_does_not_mutate_caller_metadata(self, qapp):
        from SciQLop.components.plotting.backend.easy_provider import EasyScalar

        meta = {"mine": 1}
        def cb(start: float, stop: float):
            return None

        EasyScalar("test_meta_mutation/vp", cb, component_name="y", metadata=meta)
        assert meta == {"mine": 1}

    def test_ensure_dt64_accepts_other_datetime64_units(self):
        from SciQLop.components.plotting.backend.easy_provider import ensure_dt64
        us = np.array([0, 1_000_000], dtype="datetime64[us]")
        out = ensure_dt64(us)
        assert out.dtype == np.dtype("datetime64[ns]")
        ns = np.array([0, 10], dtype="datetime64[ns]")
        assert ensure_dt64(ns) is ns or np.shares_memory(ensure_dt64(ns), ns)

    def test_ensure_dt64_error_names_dtype(self):
        from SciQLop.components.plotting.backend.easy_provider import ensure_dt64
        with pytest.raises(ValueError, match="int32|int64"):
            ensure_dt64(np.array([1, 2], dtype=np.int32))
