"""Themes are contributions to sciqlop.themes; the palette loader resolves through it (Tier 3 spec §4.3)."""
from pathlib import Path

import pytest

from SciQLop.components.theming import palette as palette_module
from SciQLop.components.theming.themes import DEFAULT_THEME, THEMES, Theme
from SciQLop.core import sciqlop_application
from SciQLop.core.extensions import owned_by

_MIDNIGHT = {"Window": "#101020", "Base": "#000010", "Text": "#e0e0ff"}


@pytest.fixture
def restore_theme(qapp):
    original = qapp.current_theme()
    yield
    THEMES.remove_owner("th_demo")
    qapp.apply_theme(original)


def _contribute(theme_id="th_demo.midnight", palette=None):
    with owned_by("th_demo"):
        THEMES.contribute(Theme(theme_id, "Midnight", palette if palette is not None else dict(_MIDNIGHT)))


def test_the_core_themes_are_the_palette_files():
    files = {p.stem for p in Path(palette_module.palettes_path).glob("*.yaml")}
    assert set(THEMES.keys()) >= files
    assert THEMES.owner_of("space") == "sciqlop"


def test_a_theme_from_a_yaml_file_loads(tmp_path):
    path = tmp_path / "sand.yaml"
    path.write_text("Window: '#f0e0c0'\nText: '#202020'\n")
    assert Theme("th_demo.sand", "Sand", path).colors()["Window"] == "#f0e0c0"


@pytest.mark.parametrize("content", ["- a\n- b\n", "key: [unclosed\n"])
def test_a_yaml_that_is_not_a_mapping_is_refused_when_built(tmp_path, content):
    path = tmp_path / "bad.yaml"
    path.write_text(content)
    with pytest.raises(ValueError, match="th_demo.bad"):
        Theme("th_demo.bad", "Bad", path)


def test_a_missing_file_is_refused_when_built(tmp_path):
    with pytest.raises(ValueError, match="th_demo.gone"):
        Theme("th_demo.gone", "Gone", tmp_path / "gone.yaml")


def test_a_plugin_theme_applies(qapp, restore_theme):
    _contribute()
    qapp.apply_theme("th_demo.midnight")
    assert qapp.current_theme() == "th_demo.midnight"
    assert palette_module.current_palette()["window"] == "#101020"


def test_an_unknown_theme_starts_on_the_default(qapp, restore_theme):
    qapp.apply_theme("th_demo.never_installed")
    assert qapp.current_theme() == DEFAULT_THEME
    assert palette_module.active_theme_name() == DEFAULT_THEME


def test_the_saved_theme_applies_when_its_plugin_contributes_it(qapp, restore_theme, monkeypatch):
    monkeypatch.setattr(sciqlop_application, "_saved_theme", lambda: "th_demo.midnight")
    qapp.apply_theme("th_demo.midnight")
    assert qapp.current_theme() == DEFAULT_THEME
    _contribute()
    assert qapp.current_theme() == "th_demo.midnight"


def test_withdrawing_the_active_theme_falls_back_and_keeps_the_setting(qapp, restore_theme):
    from SciQLop.components.theming.settings import SciQLopStyle
    saved = SciQLopStyle().color_palette
    _contribute()
    qapp.apply_theme("th_demo.midnight")
    THEMES.remove_owner("th_demo")
    assert qapp.current_theme() == DEFAULT_THEME
    assert SciQLopStyle().color_palette == saved
