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

    @patch("SciQLop.user_api.threading.invoke_on_main_thread",
           side_effect=lambda fn, *a: fn(*a))
    @patch("SciQLopPlots.ProductsModel")
    def test_double_slash_separator(self, mock_model, _mock_invoke):
        """Paths with // should split on // not /."""
        from SciQLop.user_api.magics.plot_magic import _resolve_product
        mock_model.node.return_value = True
        result = _resolve_product("speasy//cda//MMS")
        mock_model.node.assert_called_with(["speasy", "cda", "MMS"])
        assert result == "speasy//cda//MMS"

    @patch("SciQLop.user_api.threading.invoke_on_main_thread",
           side_effect=lambda fn, *a: fn(*a))
    @patch("SciQLopPlots.ProductsModel")
    def test_single_slash_separator(self, mock_model, _mock_invoke):
        """Paths with / should split on /."""
        from SciQLop.user_api.magics.plot_magic import _resolve_product
        mock_model.node.return_value = True
        result = _resolve_product("speasy/cda/MMS")
        mock_model.node.assert_called_with(["speasy", "cda", "MMS"])
        assert result == "speasy/cda/MMS"


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
