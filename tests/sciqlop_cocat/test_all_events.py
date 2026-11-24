"""Each open project shows "All events": every event of the project not in the trash, read when first
opened, in the background, and kept up to date. It is a view: nothing to rename, delete or edit."""
import pytest

from SciQLop.components.catalogs import CatalogEvent

from .conftest import HOUR, T0, loaded


def _all_events(provider, room_id="r"):
    return next(c for c in provider.catalogs() if c.name == "All events" and c.path == [room_id])


@pytest.fixture
def filled(provider, room):
    listed = room.create_event(start=T0, stop=T0 + HOUR, author="me", tags=["s"])
    room.create_event(start=T0 + 2 * HOUR, stop=T0 + 3 * HOUR, author="me")  # in no catalogue
    room.create_event(start=T0 + 4 * HOUR, stop=T0 + 5 * HOUR, author="me").delete()
    room.create_catalogue(name="plain", author="me").add_events([listed.uuid])
    provider.attach_room("r", room)
    return provider


def test_an_open_project_shows_all_its_events_but_the_trash(filled, qtbot):
    view = _all_events(filled)
    assert len(loaded(filled, view, qtbot)) == 2


def test_it_is_read_once_opened_and_follows_edits(filled, qtbot):
    view = _all_events(filled)
    assert view.uuid in filled._unread
    loaded(filled, view, qtbot)
    plain = next(c for c in filled.catalogs() if c.name == "plain")
    filled.add_event(plain, CatalogEvent(uuid="new", start=T0 + 9 * HOUR, stop=T0 + 10 * HOUR))
    qtbot.waitUntil(lambda: len(filled.events(view)) == 3, timeout=5000)


def test_it_is_a_view_nothing_to_rename_delete_or_edit(filled):
    view = _all_events(filled)
    assert filled.capabilities(view) == set()
    assert filled.actions(view) == [] or all(a.name not in {"Edit as JSON…", "Freeze…", "Remove the search…"}
                                             for a in filled.actions(view))
    assert filled.catalog_search(view) is None
    with pytest.raises(PermissionError):
        filled.set_catalog_search(view, "tag:s")


def test_leaving_the_project_takes_it_away(filled):
    view = _all_events(filled)
    filled.detach_room("r")
    assert view not in filled.catalogs()
