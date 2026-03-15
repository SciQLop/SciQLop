"""Tests for %plot line magic."""
import pytest
from unittest.mock import MagicMock, patch


class TestResolveProduct:
    @patch("SciQLop.user_api.magics.plot_magic._complete_products")
    def test_returns_top_match(self, mock_cp):
        from SciQLop.user_api.magics.plot_magic import _resolve_product
        mock_cp.return_value = ["speasy/amda/imf_mag"]
        assert _resolve_product("imf") == "speasy/amda/imf_mag"

    @patch("SciQLop.user_api.magics.plot_magic._complete_products")
    def test_raises_on_no_match(self, mock_cp):
        from SciQLop.user_api.magics.plot_magic import _resolve_product
        mock_cp.return_value = []
        with pytest.raises(Exception, match="No product matching"):
            _resolve_product("zzz_nothing")


class TestPlotMagic:
    @patch("SciQLop.user_api.magics.plot_magic.plot_panel")
    @patch("SciQLop.user_api.magics.plot_magic._resolve_product")
    def test_plot_in_existing_panel(self, mock_resolve, mock_pp):
        from SciQLop.user_api.magics.plot_magic import plot_magic
        from SciQLopPlots import PlotType
        mock_resolve.return_value = "speasy/amda/imf"
        mock_panel = MagicMock()
        mock_pp.return_value = mock_panel

        plot_magic('imf "Panel-0"')

        mock_pp.assert_called_once_with("Panel-0")
        mock_panel.plot_product.assert_called_once_with("speasy/amda/imf", plot_type=PlotType.TimeSeries)

    @patch("SciQLop.user_api.magics.plot_magic.create_plot_panel")
    @patch("SciQLop.user_api.magics.plot_magic._resolve_product")
    def test_plot_in_new_panel(self, mock_resolve, mock_create):
        from SciQLop.user_api.magics.plot_magic import plot_magic
        mock_resolve.return_value = "speasy/amda/imf"
        mock_panel = MagicMock()
        mock_create.return_value = mock_panel

        plot_magic("imf")

        mock_create.assert_called_once()
        mock_panel.plot_product.assert_called_once()

    def test_empty_input_raises(self):
        from SciQLop.user_api.magics.plot_magic import plot_magic
        with pytest.raises(Exception, match="Usage"):
            plot_magic("")


class TestCompletePlot:
    @patch("SciQLop.user_api.magics.plot_magic._complete_products")
    def test_completes_product_on_first_arg(self, mock_cp):
        from SciQLop.user_api.magics.plot_magic import complete_plot
        mock_cp.return_value = ["speasy/amda/imf"]
        event = MagicMock()
        event.line = "%plot im"
        event.symbol = "im"

        result = complete_plot(None, event)
        assert result == ["speasy/amda/imf"]

    @patch("SciQLop.user_api.magics.plot_magic._complete_panels")
    def test_completes_panel_on_second_arg(self, mock_panels):
        from SciQLop.user_api.magics.plot_magic import complete_plot
        mock_panels.return_value = ["Panel-1", "Panel-0"]
        event = MagicMock()
        event.line = "%plot imf Pan"
        event.symbol = "Pan"

        result = complete_plot(None, event)
        assert result == ["Panel-1", "Panel-0"]
