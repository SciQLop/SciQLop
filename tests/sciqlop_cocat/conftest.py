"""Fixtures of the cocat-rs plugin's tests. The sandboxed settings and data folders, and the Qt
application, come from tests/conftest.py."""
from datetime import datetime, timedelta, timezone

import cocat_rs
import pytest

from ..fixtures import *  # noqa: F401,F403

PLUGIN_MODULE = "SciQLop.plugins.sciqlop_cocat"


def pytest_collection_modifyitems(config, items):
    """As in the plugin's own repository: a cocat-rs name the plugin still uses after a rename fails
    its tests, and the tests that run a local cocat-server are skipped unless asked for with `-m live`."""
    live_asked = "live" in (config.getoption("-m") or "")
    for item in items:
        if PLUGIN_MODULE.rsplit(".", 1)[-1] not in item.nodeid:
            continue
        item.add_marker(pytest.mark.filterwarnings(f"error::DeprecationWarning:{PLUGIN_MODULE}"))
        if item.get_closest_marker("live") and not live_asked:
            item.add_marker(pytest.mark.skip(reason="live test: run with -m live and COCAT_SERVER set"))


T0 = datetime(2020, 1, 1, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)


@pytest.fixture
def room(tmp_path):
    r = cocat_rs.Project.open(tmp_path / "cache", "r")
    yield r
    r.close()


@pytest.fixture
def provider(qapp):
    from SciQLop.components.catalogs import CatalogRegistry
    from SciQLop.plugins.sciqlop_cocat.provider import CocatRsProvider
    p = CocatRsProvider(author="me")
    yield p
    CatalogRegistry.instance()._forget_for_tests(p)


@pytest.fixture(autouse=True)
def gc_on_the_gui_thread_only():
    """As SciQLop does (core/main_thread_gc.py): the read worker runs Python, and a collection there
    finalised Qt objects of earlier tests that live on the GUI thread, crashing later in QObject::event."""
    import gc
    gc.disable()
    yield
    gc.enable()
    gc.collect()


@pytest.fixture
def attached(provider, room):
    """A provider with the offline test room attached as room id "r"."""
    provider.attach_room("r", room)
    return provider


@pytest.fixture
def tagged(attached):
    """A plain catalogue of three events: e0 and e1 tagged s, e2 tagged w."""
    from SciQLop.components.catalogs import CatalogEvent
    plain = attached.create_catalog("plain", ["r"])
    for i, tag in enumerate(["s", "s", "w"]):
        attached.add_event(plain, CatalogEvent(uuid=f"e{i}", start=T0 + i * HOUR, stop=T0 + (i + 1) * HOUR,
                                               meta={"tags": [tag]}))
    return plain


@pytest.fixture
def smart(attached, tagged):
    """A smart catalogue searching all events for tag:s."""
    return attached.create_smart_catalog("shocks", ["r"], "tag:s")


def loaded(provider, catalog, qtbot):
    """A smart catalogue's events, once its first read (started by asking) has been shown."""
    provider.events(catalog)
    qtbot.waitUntil(lambda: not provider.is_loading(catalog), timeout=5000)
    return provider.events(catalog)


def own_catalogs(provider):
    """The provider's catalogues, without each project's "All events" view."""
    return [c for c in provider.catalogs() if not c.uuid.startswith("all-events:")]


def only(provider):
    [catalog] = own_catalogs(provider)
    return catalog


def project_actions(provider, path):
    """A project's own menu entries, without the "New smart catalogue" presets."""
    return [a for a in provider.folder_actions(path) if a.group is None]


class WithPublicNames:
    """A project whose public calls answer as the server would, from the public names."""

    def __init__(self, room, public, broken_listing: str | None = None):
        self._room, self._public, self._broken = room, public, broken_listing
        self.gate = None  # a threading.Event the public vocabulary waits for

    def __getattr__(self, name):
        return getattr(self._room, name)

    def _server(self):
        if self._broken:
            raise RuntimeError(self._broken)
        return self._public

    def vocabulary(self, public=False):
        if not public:
            return self._room.vocabulary()
        if self.gate is not None:
            self.gate.wait(5)
        return self._server().vocabulary()

    def query_kind(self, text, public=False):
        return self._server().query_kind(text) if public else self._room.query_kind(text)

    def parse_query(self, text, source=None, public=False):
        return self._server().parse_query(text) if public else self._room.parse_query(text, source=source)


def answer_public_from(provider, public, monkeypatch) -> dict:
    """The provider's rooms answer their public calls from the catalogue names of ``public``, a cocat-rs
    project standing in for the server's public catalogues. The wrapped rooms, by id of the room."""
    rooms = {}
    real_room_of = provider._room_of

    def room_of(catalog):
        room = real_room_of(catalog)
        return rooms.setdefault(id(room), WithPublicNames(room, public))

    monkeypatch.setattr(provider, "_room_of", room_of)
    return rooms


@pytest.fixture
def public_names(tmp_path):
    """A cocat-rs project standing in for the server's list of public catalogues."""
    public = cocat_rs.Project.open(tmp_path / "public", "public")
    yield public
    public.close()
