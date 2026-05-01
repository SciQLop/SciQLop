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
