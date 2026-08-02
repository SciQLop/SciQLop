"""The session-info strip renders per field and hides when there is nothing."""
from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures


def test_hidden_when_snapshot_is_none(qtbot):
    from SciQLop.components.agents.chat.info_bar import SessionInfoBar

    bar = SessionInfoBar()
    qtbot.addWidget(bar)
    bar.set_snapshot(None)
    assert bar.isHidden()


def test_hidden_when_snapshot_carries_nothing(qtbot):
    from SciQLop.components.agents.backend import UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import SessionInfoBar

    bar = SessionInfoBar()
    qtbot.addWidget(bar)
    bar.set_snapshot(UsageSnapshot())
    assert bar.isHidden()


def test_tokens_only_backend_still_shows_a_segment(qtbot):
    from SciQLop.components.agents.backend import TokenCounts, UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import SessionInfoBar

    bar = SessionInfoBar()
    qtbot.addWidget(bar)
    bar.set_snapshot(UsageSnapshot(tokens=TokenCounts(input=1000, output=200)))
    assert not bar.isHidden()
    assert bar.text() == "1.2k"


def test_context_meter_appears_only_with_a_known_limit(qtbot):
    from SciQLop.components.agents.backend import TokenCounts, UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import SessionInfoBar

    bar = SessionInfoBar()
    qtbot.addWidget(bar)

    bar.set_snapshot(UsageSnapshot(tokens=TokenCounts(input=10)))
    assert bar.meter.isHidden()

    bar.set_snapshot(UsageSnapshot(context_tokens=50_000, context_max=200_000))
    assert not bar.meter.isHidden()
    assert bar.meter.value() == 25


def test_strip_rehides_when_the_snapshot_is_cleared(qtbot):
    from SciQLop.components.agents.backend import TokenCounts, UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import SessionInfoBar

    bar = SessionInfoBar()
    qtbot.addWidget(bar)

    bar.set_snapshot(UsageSnapshot(tokens=TokenCounts(input=1000, output=200)))
    assert not bar.isHidden()      # setVisible(True) ran

    bar.set_snapshot(None)
    assert bar.isHidden()          # setVisible(False) ran


def test_effort_is_shown_and_updated_independently_of_the_snapshot(qtbot):
    from SciQLop.components.agents.backend import UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import SessionInfoBar

    bar = SessionInfoBar()
    qtbot.addWidget(bar)
    bar.set_snapshot(UsageSnapshot(model="Opus 4.5"))
    assert bar.text() == "Opus 4.5"

    bar.set_effort("high")
    assert bar.text() == "Opus 4.5 · high"


def test_details_button_emits_details_requested(qtbot):
    from SciQLop.components.agents.backend import ContextCategory, UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import SessionInfoBar

    bar = SessionInfoBar()
    qtbot.addWidget(bar)
    bar.set_snapshot(UsageSnapshot(
        context_tokens=100, context_max=200,
        context_categories=(ContextCategory(name="System prompt", tokens=100),),
    ))
    with qtbot.waitSignal(bar.details_requested, timeout=1000):
        bar.details_button.click()


def test_details_button_hidden_without_a_breakdown(qtbot):
    from SciQLop.components.agents.backend import TokenCounts, UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import SessionInfoBar

    bar = SessionInfoBar()
    qtbot.addWidget(bar)
    bar.set_snapshot(UsageSnapshot(tokens=TokenCounts(input=10)))
    assert bar.details_button.isHidden()


def test_breakdown_popup_lists_categories_largest_first(qtbot):
    from SciQLop.components.agents.backend import ContextCategory, UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import ContextBreakdownPopup

    popup = ContextBreakdownPopup()
    qtbot.addWidget(popup)
    popup.set_snapshot(UsageSnapshot(
        context_tokens=168_000, context_max=500_000,
        context_categories=(
            ContextCategory(name="System prompt", tokens=3_100),
            ContextCategory(name="Messages", tokens=127_000),
            ContextCategory(name="MCP tools", tokens=28_400),
        ),
    ))
    assert popup.category_rows == [
        ("Messages", "127.0k"),
        ("MCP tools", "28.4k"),
        ("System prompt", "3.1k"),
    ]


def test_breakdown_popup_footer_joins_available_metrics(qtbot):
    from SciQLop.components.agents.backend import (
        CarbonFootprint, ContextCategory, Cost, UsageSnapshot)
    from SciQLop.components.agents.chat.info_bar import ContextBreakdownPopup

    popup = ContextBreakdownPopup()
    qtbot.addWidget(popup)
    popup.set_snapshot(UsageSnapshot(
        context_categories=(ContextCategory(name="Messages", tokens=10),),
        num_turns=12, duration_api_ms=108_000, cost=Cost(amount=0.42),
        carbon=CarbonFootprint(kg_co2eq=0.0043),
    ))
    assert popup.footer_text() == "12 turns · 1m 48s api · $0.42 · 4.3 gCO₂eq"


def test_breakdown_popup_footer_omits_missing_metrics(qtbot):
    from SciQLop.components.agents.backend import ContextCategory, UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import ContextBreakdownPopup

    popup = ContextBreakdownPopup()
    qtbot.addWidget(popup)
    popup.set_snapshot(UsageSnapshot(
        context_categories=(ContextCategory(name="Messages", tokens=10),), num_turns=1))
    assert popup.footer_text() == "1 turn"


def test_breakdown_popup_rebuilds_rows_on_second_snapshot(qtbot):
    from SciQLop.components.agents.backend import ContextCategory, UsageSnapshot
    from SciQLop.components.agents.chat.info_bar import ContextBreakdownPopup

    popup = ContextBreakdownPopup()
    qtbot.addWidget(popup)
    popup.set_snapshot(UsageSnapshot(
        context_categories=(ContextCategory(name="Messages", tokens=10),)))
    popup.set_snapshot(UsageSnapshot(
        context_categories=(ContextCategory(name="MCP tools", tokens=20),)))
    assert popup.category_rows == [("MCP tools", "20")]
    # category_rows is a plain list rebuilt unconditionally on every call, so it
    # can't detect stale grid rows on its own — assert directly on the grid's
    # widget count (name label + tokens label + meter = 3 items per row) so this
    # test still fails if the teardown loop in _render_categories is removed.
    assert popup._grid.count() == 3
