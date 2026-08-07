import pytest
from SciQLop.user_api import themes


def test_list_themes():
    assert set(themes.list_themes()) == {"light", "dark", "neutral", "space"}


def test_apply_and_read_theme():
    themes.apply_theme("dark")
    assert themes.current_theme() == "dark"
    themes.apply_theme("light")
    assert themes.current_theme() == "light"
