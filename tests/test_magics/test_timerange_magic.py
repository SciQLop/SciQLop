"""Tests for %timerange line magic."""
import pytest
from unittest.mock import MagicMock, patch, call


class TestTimerangeMagic:
    @patch("SciQLop.user_api.magics.timerange_magic._print_all_time_ranges")
    def test_no_args_prints_all(self, mock_print_all):
        from SciQLop.user_api.magics.timerange_magic import timerange_magic
        timerange_magic("")
        mock_print_all.assert_called_once()

    @patch("SciQLop.user_api.magics.timerange_magic._print_time_range")
    def test_one_arg_prints_panel(self, mock_print):
        from SciQLop.user_api.magics.timerange_magic import timerange_magic
        timerange_magic("Panel-0")
        mock_print.assert_called_once_with("Panel-0")

    @patch("SciQLop.user_api.magics.timerange_magic._set_time_range")
    def test_three_args_sets_range(self, mock_set):
        from SciQLop.user_api.magics.timerange_magic import timerange_magic
        timerange_magic("2024-01-01 2024-01-02 Panel-0")
        mock_set.assert_called_once()
        assert mock_set.call_args.kwargs["panel_name"] == "Panel-0"

    def test_two_args_raises(self):
        from SciQLop.user_api.magics.timerange_magic import timerange_magic
        with pytest.raises(Exception, match="Usage"):
            timerange_magic("2024-01-01 2024-01-02")
