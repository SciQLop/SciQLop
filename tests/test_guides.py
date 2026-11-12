"""Gesture guides: every guide plays in Qt's SVG renderer with the theme's colours, is reachable from
Help, the palette and a "?" button, and a plugin can add its own."""
from .fixtures import *
import pytest
from PySide6.QtCore import QByteArray
from PySide6.QtSvg import QSvgRenderer

from SciQLop.components.guides.qt_svg import for_qt, palette_tokens
from SciQLop.components.guides.registry import CORE_GUIDES, GUIDES, Guide, get_guide, guide_for, register_guide


@pytest.fixture
def guides(qapp):
    from SciQLop.components.extension_points import prepare_extension_points
    prepare_extension_points()
    return GUIDES


@pytest.mark.parametrize("guide", CORE_GUIDES, ids=lambda g: g.id)
def test_a_core_guide_animates_in_qt(qapp, guide):
    """Qt drops an animation silently for a CSS variable or an @media block: this is the only alarm."""
    svg = for_qt(guide.path.read_text(encoding="utf-8"), palette_tokens(qapp.palette()))
    assert "var(" not in svg and "@media" not in svg
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    assert renderer.isValid() and renderer.animated()
    assert 8000 <= renderer.animationDuration() <= 20000


def test_the_guide_takes_the_theme_colours(qapp):
    tokens = palette_tokens(qapp.palette())
    svg = for_qt(CORE_GUIDES[0].path.read_text(encoding="utf-8"), tokens)
    assert f'fill="{tokens["--win"]}"' in svg and f'fill="{tokens["--accent"]}"' in svg


def test_translucent_colours_are_split_for_qt():
    svg = for_qt('<rect fill="var(--soft)" stroke="var(--line)"/>', {"--soft": "#3584e42e", "--line": "#d5d5da"})
    assert svg == '<rect fill="#3584e4" fill-opacity="0.180" stroke="#d5d5da"/>'


def test_core_guides_are_registered_with_their_context(guides):
    assert [g.id for g in guides.list()][:len(CORE_GUIDES)] == [g.id for g in CORE_GUIDES]
    assert guide_for("catalog.mode.edit").id == "sciqlop.create-an-event"
    assert guide_for("no.such.context") is None


def test_every_guide_is_a_palette_command(guides):
    from SciQLop.components.command_palette.backend.registry import COMMANDS
    command = COMMANDS.get("guides.sciqlop.create-an-event")
    assert command.name == "Guide: Create an event" and "event" in command.keywords


def test_a_plugin_guide_comes_and_goes_with_its_palette_command(guides, tmp_path):
    from SciQLop.components.command_palette.backend.registry import COMMANDS
    from SciQLop.core.extensions import owned_by
    path = tmp_path / "fit.svg"
    path.write_text(CORE_GUIDES[0].path.read_text(encoding="utf-8"), encoding="utf-8")
    with owned_by("guide_demo"):
        register_guide(Guide("guide_demo.fit", "Fit a distribution", "Drag a box, press F.", path, ("fit",), ("guide_demo.fit_tool",)))
    try:
        assert guide_for("guide_demo.fit_tool").title == "Fit a distribution"
        assert "guides.guide_demo.fit" in COMMANDS
    finally:
        GUIDES.remove_owner("guide_demo")
    assert get_guide("guide_demo.fit") is None and "guides.guide_demo.fit" not in COMMANDS


def test_the_guides_window_plays_the_picked_guide(guides, qtbot):
    from SciQLop.components.guides.ui import GuidesWindow
    window = GuidesWindow()
    qtbot.addWidget(window)
    assert window.list.count() == len(guides.list())
    window.show_guide("sciqlop.jump-to-an-event")
    assert window.title.text() == "Go from event to event"
    assert window.player.renderer().animated()


def test_help_guides_opens_the_window(main_window, guides):
    action = next(a for a in main_window.helpMenu.actions() if a.text() == "Guides")
    action.trigger()
    assert main_window._guides_window.isVisible()
    main_window._guides_window.close()


def test_a_guide_button_follows_its_context(guides, qtbot):
    from SciQLop.components.guides.ui import GuideButton
    button = GuideButton("catalog.mode.jump")
    qtbot.addWidget(button)
    assert not button.isHidden() and "Go from event to event" in button.toolTip()
    button.set_context("no.such.context")
    assert button.isHidden()


def test_the_catalog_mode_box_offers_the_guide_of_its_mode(guides, qtbot):
    from SciQLop.components.plotting.ui.catalog_chrome import CatalogChrome
    chrome = CatalogChrome()
    qtbot.addWidget(chrome)
    assert chrome._guide_button.context == "catalog.mode.view"
    chrome.mode = "edit"
    assert chrome._guide_button.context == "catalog.mode.edit"


def test_the_first_start_question_offers_the_guides(main_window, guides):
    from PySide6.QtWidgets import QPushButton
    main_window._onboarding_controller = None
    offer = main_window._offer_getting_started_tour()
    buttons = {b.text(): b for b in offer.findChildren(QPushButton)}
    assert set(buttons) == {"Take the tour", "Watch the guides", "Not now"}
    buttons["Watch the guides"].click()
    assert main_window._guides_window.isVisible()
    assert main_window._onboarding_controller is None
    main_window._guides_window.close()


def test_the_welcome_page_has_a_guides_card(main_window, qapp, guides):
    qapp.quickstart_shortcut("Watch the guides")["callback"]()
    assert main_window._guides_window.isVisible()
    main_window._guides_window.close()
