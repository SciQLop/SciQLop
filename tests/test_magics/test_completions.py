"""Tests for shared magic completion and parsing helpers."""
import sys
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional
from functools import cached_property


@dataclass
class FakeContext:
    """Minimal CompletionContext stand-in for testing matchers."""
    token: str
    full_text: str
    cursor_position: int
    cursor_line: int = 0
    limit: Optional[int] = None

    @cached_property
    def text_until_cursor(self):
        return self.line_with_cursor[:self.cursor_position]

    @cached_property
    def line_with_cursor(self):
        return self.full_text.split("\n")[self.cursor_line]


def _ctx(line: str, token: str) -> FakeContext:
    """Build a FakeContext from a line and the token being completed."""
    return FakeContext(token=token, full_text=line, cursor_position=len(line))


def _texts(result: dict) -> list[str]:
    """Extract completion text strings from a matcher result dict."""
    return [c.text for c in result["completions"]]


class TestParseTime:
    def test_parse_iso_date(self):
        from SciQLop.user_api.magics.completions import _parse_time
        result = _parse_time("2024-01-01")
        expected = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
        assert result == expected

    def test_parse_iso_datetime(self):
        from SciQLop.user_api.magics.completions import _parse_time
        result = _parse_time("2024-01-01T12:00:00")
        expected = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        assert result == expected

    def test_parse_float_timestamp(self):
        from SciQLop.user_api.magics.completions import _parse_time
        assert _parse_time("1704067200.0") == 1704067200.0

    def test_parse_tz_aware_iso(self):
        from SciQLop.user_api.magics.completions import _parse_time
        result = _parse_time("2024-01-01T02:00:00+02:00")
        expected = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()
        assert result == expected

    def test_raises_on_invalid(self):
        from SciQLop.user_api.magics.completions import _parse_time
        with pytest.raises(ValueError):
            _parse_time("not-a-time")


class TestCompleteProducts:
    @patch("SciQLopPlots.ProductsFlatFilterModel")
    @patch("SciQLopPlots.ProductsModel")
    @patch("PySide6.QtWidgets.QApplication")
    def test_returns_product_paths(self, mock_qapp, mock_pm, mock_flat_cls):
        from SciQLop.user_api.magics.completions import _complete_products

        mock_flat = MagicMock()
        mock_flat_cls.return_value = mock_flat
        mock_flat.rowCount.return_value = 2

        mime = MagicMock()
        mime.text.return_value = "provider/product_a\nprovider/product_b\n"
        mock_flat.mimeData.return_value = mime

        mock_qapp.instance.return_value = MagicMock()

        result = _complete_products("prod")
        assert result == ["provider/product_a", "provider/product_b"]

    @patch("SciQLopPlots.ProductsFlatFilterModel")
    @patch("SciQLopPlots.ProductsModel")
    @patch("PySide6.QtWidgets.QApplication")
    def test_returns_empty_on_no_match(self, mock_qapp, mock_pm, mock_flat_cls):
        from SciQLop.user_api.magics.completions import _complete_products

        mock_flat = MagicMock()
        mock_flat_cls.return_value = mock_flat
        mock_flat.rowCount.return_value = 0

        mock_qapp.instance.return_value = MagicMock()

        result = _complete_products("zzz_no_match")
        assert result == []


class TestCompletePanels:
    def _mock_gui_module(self):
        """Insert a mock for SciQLop.user_api.gui to avoid heavy Qt imports."""
        mock_mod = MagicMock()
        self._original = sys.modules.get("SciQLop.user_api.gui")
        sys.modules["SciQLop.user_api.gui"] = mock_mod
        return mock_mod

    def _restore_gui_module(self):
        if self._original is not None:
            sys.modules["SciQLop.user_api.gui"] = self._original
        else:
            sys.modules.pop("SciQLop.user_api.gui", None)

    def test_returns_panel_names_reversed(self):
        mock_mod = self._mock_gui_module()
        try:
            mock_mw = MagicMock()
            mock_mw.plot_panels.return_value = ["Panel-0", "Panel-1", "Panel-2"]
            mock_mod.get_main_window.return_value = mock_mw

            from SciQLop.user_api.magics.completions import _complete_panels
            result = _complete_panels()
            assert result == ["Panel-2", "Panel-1", "Panel-0"]
        finally:
            self._restore_gui_module()

    def test_returns_empty_when_no_main_window(self):
        mock_mod = self._mock_gui_module()
        try:
            mock_mod.get_main_window.return_value = None

            from SciQLop.user_api.magics.completions import _complete_panels
            assert _complete_panels() == []
        finally:
            self._restore_gui_module()


class TestMatchPlot:
    @patch("SciQLop.user_api.magics.completions._complete_products")
    def test_completes_product_on_first_arg(self, mock_cp):
        from SciQLop.user_api.magics.completions import _match_plot
        mock_cp.return_value = ["speasy/amda/imf"]

        result = _match_plot(_ctx("%plot im", "im"))
        assert _texts(result) == ["speasy/amda/imf"]

    @patch("SciQLop.user_api.magics.completions._complete_panels")
    def test_completes_panel_on_second_arg(self, mock_panels):
        from SciQLop.user_api.magics.completions import _match_plot
        mock_panels.return_value = ["Panel-1", "Panel-0"]

        result = _match_plot(_ctx("%plot imf Pan", "Pan"))
        assert _texts(result) == ["Panel-1", "Panel-0"]

    def test_ignores_non_plot_lines(self):
        from SciQLop.user_api.magics.completions import _match_plot
        result = _match_plot(_ctx("print('hello')", "hello"))
        assert _texts(result) == []


class TestMatchTimerange:
    @patch("SciQLop.user_api.magics.completions._complete_panels")
    def test_completes_panel_on_first_arg(self, mock_panels):
        from SciQLop.user_api.magics.completions import _match_timerange
        mock_panels.return_value = ["Panel-1", "Panel-0"]

        result = _match_timerange(_ctx("%timerange Pan", "Pan"))
        assert _texts(result) == ["Panel-1", "Panel-0"]

    @patch("SciQLop.user_api.magics.completions._complete_panels")
    def test_completes_panel_on_fourth_token(self, mock_panels):
        from SciQLop.user_api.magics.completions import _match_timerange
        mock_panels.return_value = ["Panel-0"]

        result = _match_timerange(_ctx("%timerange 2024-01-01 2024-01-02 Pan", "Pan"))
        assert _texts(result) == ["Panel-0"]

    def test_no_completion_for_time_args(self):
        from SciQLop.user_api.magics.completions import _match_timerange
        result = _match_timerange(_ctx("%timerange 2024-01-01 20", "20"))
        assert _texts(result) == []

    def test_ignores_non_timerange_lines(self):
        from SciQLop.user_api.magics.completions import _match_timerange
        result = _match_timerange(_ctx("x = 1", "1"))
        assert _texts(result) == []


class TestMatchVp:
    @patch("SciQLop.user_api.magics.completions._complete_products")
    def test_completes_product_after_path_flag(self, mock_cp):
        from SciQLop.user_api.magics.completions import _match_vp
        mock_cp.return_value = ["speasy/amda/imf"]

        result = _match_vp(_ctx("%%vp --path im", "im"))
        assert _texts(result) == ["speasy/amda/imf"]

    def test_completes_flags(self):
        from SciQLop.user_api.magics.completions import _match_vp
        result = _match_vp(_ctx("%%vp --", "--"))
        texts = _texts(result)
        assert "--path" in texts
        assert "--debug" in texts
        assert "--start" in texts
        assert "--stop" in texts

    def test_no_completion_for_bare_text(self):
        from SciQLop.user_api.magics.completions import _match_vp
        result = _match_vp(_ctx("%%vp foo", "foo"))
        assert _texts(result) == []

    def test_ignores_non_vp_lines(self):
        from SciQLop.user_api.magics.completions import _match_vp
        result = _match_vp(_ctx("print('hello')", "hello"))
        assert _texts(result) == []
