from .fixtures import *
from SciQLop.components.catalogs.backend.event_table_view_state import (
    EventTableViewState,
    CatalogViewState,
    get_view_state,
    save_view_state,
)


def test_view_state_default_empty(qapp):
    state = get_view_state("nonexistent-uuid-1")
    assert state.hidden_columns == []
    assert state.column_order == []


def test_view_state_save_and_reload(qapp):
    cat_uid = "test-cat-uuid-2"
    state = CatalogViewState(
        hidden_columns=["author", "rating"],
        column_order=["start", "stop", "class"],
    )
    save_view_state(cat_uid, state)
    reloaded = get_view_state(cat_uid)
    assert reloaded.hidden_columns == ["author", "rating"]
    assert reloaded.column_order == ["start", "stop", "class"]


def test_view_state_overwrite(qapp):
    cat_uid = "test-cat-uuid-3"
    save_view_state(cat_uid, CatalogViewState(hidden_columns=["a"], column_order=["start"]))
    save_view_state(cat_uid, CatalogViewState(hidden_columns=[], column_order=["start", "stop"]))
    reloaded = get_view_state(cat_uid)
    assert reloaded.hidden_columns == []
    assert reloaded.column_order == ["start", "stop"]


def test_browser_applies_hidden_columns_on_catalog_select(qtbot, qapp, tmp_path, monkeypatch):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.event_table_view_state import (
        CatalogViewState, save_view_state,
    )

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    save_view_state(cat.uuid, CatalogViewState(hidden_columns=["score"], column_order=[]))

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    browser._current_provider = provider
    browser._current_catalog = cat
    browser._event_model.set_context(provider, cat)
    browser._event_model.set_events(provider.events(cat))
    browser._apply_view_state(cat)

    score_col = len(browser._event_model._FIXED_COLUMNS) + browser._event_model._meta_keys.index("score")
    assert browser._event_table.isColumnHidden(score_col)


def test_browser_save_view_state_records_hidden_columns(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.event_table_view_state import get_view_state

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    browser._current_provider = provider
    browser._current_catalog = cat
    browser._event_model.set_context(provider, cat)
    browser._event_model.set_events(provider.events(cat))

    score_col = len(browser._event_model._FIXED_COLUMNS) + browser._event_model._meta_keys.index("score")
    browser._event_table.setColumnHidden(score_col, True)
    browser._save_view_state()

    state = get_view_state(cat.uuid)
    assert "score" in state.hidden_columns


def test_browser_save_view_state_records_column_order(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.event_table_view_state import get_view_state

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    browser._current_provider = provider
    browser._current_catalog = cat
    browser._event_model.set_context(provider, cat)
    browser._event_model.set_events(provider.events(cat))

    header = browser._event_table.horizontalHeader()
    # Move "stop" (logical 1) to visual position 0
    header.moveSection(1, 0)
    browser._save_view_state()

    state = get_view_state(cat.uuid)
    assert state.column_order[0] == "stop"
