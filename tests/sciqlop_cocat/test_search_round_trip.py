"""A catalogue's saved search reads back as it was typed, after the project is opened again, wherever it
looks (cocat-rs 0.12.4 keeps the typed text beside the rule). Before, a search on the public catalogues
came back with no text form: "start:>2018" could only be edited as JSON."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import cocat_rs
import pytest

from SciQLop.components.catalogs import CatalogRegistry
from SciQLop.plugins.sciqlop_cocat import provider as provider_module
from SciQLop.plugins.sciqlop_cocat.provider import CocatRsProvider
from .test_provider_rooms import FakeSession, RecordingRoom, run
from .test_search_filter import _browser_on

TYPED = "start:>2018"
ROOMS = [cocat_rs.ProjectInfo("t", "Storm study", "editor")]


class _NoPublicCatalogues(BaseHTTPRequestHandler):
    """The one call saving a public search makes: the server's public catalogues, none here."""

    def do_GET(self):
        body = b"[]" if self.path == "/api/public" else b""
        self.send_response(200 if body else 404)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _NoPublicCatalogues)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def signed_in(qapp, tmp_path, monkeypatch, server):
    """Opens the signed-in provider on the same folders as often as asked: a reload is a second one."""
    monkeypatch.setattr(provider_module, "open_room",
                        lambda folder, room_id: RecordingRoom(cocat_rs.Project.open(folder, room_id)))
    opened = []

    def close_all():
        while opened:
            p = opened.pop()
            run(p.close())
            CatalogRegistry.instance()._forget_for_tests(p)

    def open_provider():
        close_all()
        session = FakeSession(rooms=ROOMS)
        session.url = server
        p = CocatRsProvider(author="me", session=session, cache_dir=tmp_path / "cache",
                            local_dir=tmp_path / "local")
        run(p.connect())
        opened.append(p)
        return p

    yield open_provider
    close_all()


def _named(provider, name):
    [catalog] = [c for c in provider.catalogs() if c.name == name]
    return catalog


@pytest.mark.parametrize("scope, saved_as", [
    ("public", dict(public=True)),
    ("all", dict()),
    ("source", dict(source="plain")),
], ids=["Public catalogues", "All events", "In a catalogue"])
def test_a_saved_search_reads_back_as_typed_after_a_reload(signed_in, qtbot, scope, saved_as):
    p = signed_in()
    p.create_catalog("plain", ["t"])
    found = p.create_catalog("found", ["t"])
    source = _named(p, saved_as.pop("source")) if "source" in saved_as else None
    p.set_catalog_search(found, TYPED, source, **saved_as)  # what the box's Save does

    p = signed_in()
    box = _browser_on(p, _named(p, "found"), qtbot)._event_filter
    assert (box.scope(), box.mode()) == (scope, "search")
    assert box.line.toPlainText() == TYPED
    assert box.line.isVisibleTo(box.widget()) and not box.no_text.isVisibleTo(box.widget())
