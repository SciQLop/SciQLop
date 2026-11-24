"""Links in the agent transcript: workspace files open in the JupyterLab pane,
web links in the system browser, anything else gets a short message."""
import pytest

from .fixtures import qapp_cls, sciqlop_resources  # noqa: F401 — fixtures


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "Ephemeris.ipynb").write_text("{}")
    (tmp_path / "ephemeris availability.png").write_bytes(b"png")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "data.csv").write_text("a,b")
    return tmp_path


def _classify(href, workspace):
    from SciQLop.components.agents.chat.links import classify_link
    return classify_link(href, workspace)


@pytest.mark.parametrize("href", ["https://example.com/x", "http://example.com"])
def test_http_links_go_to_the_browser(href, workspace):
    action = _classify(href, workspace)
    assert (action.kind, action.target) == ("web", href)


@pytest.mark.parametrize("href,rel", [
    ("Ephemeris.ipynb", "Ephemeris.ipynb"),
    ("./sub/data.csv", "sub/data.csv"),
    ("ephemeris%20availability.png", "ephemeris availability.png"),
    ("ephemeris availability.png", "ephemeris availability.png"),
])
def test_relative_paths_resolve_against_the_workspace(href, rel, workspace):
    action = _classify(href, workspace)
    assert (action.kind, action.target) == ("workspace", rel)


def test_absolute_paths_inside_the_workspace_open(workspace):
    action = _classify(str(workspace / "sub" / "data.csv"), workspace)
    assert (action.kind, action.target) == ("workspace", "sub/data.csv")
    action = _classify((workspace / "Ephemeris.ipynb").as_uri(), workspace)
    assert (action.kind, action.target) == ("workspace", "Ephemeris.ipynb")


@pytest.mark.parametrize("href", [
    "../outside.txt", "/etc/passwd", "file:///etc/passwd", "missing.ipynb",
    "javascript:alert(1)", "mailto:a@b.c", "",
])
def test_everything_else_is_refused_with_a_message(href, workspace):
    (workspace.parent / "outside.txt").write_text("x")
    action = _classify(href, workspace)
    assert action.kind == "refused"
    assert action.target


class _FakeLabWidget:
    def __init__(self):
        self.loaded = []

    def load(self, url):
        self.loaded.append(url)


class _FakeJupyter:
    _launcher = None

    def __init__(self):
        self.lab = _FakeLabWidget()
        self.opened = []

    def widget(self):
        return self.lab

    def open_file(self, path):
        self.opened.append(path)
        return self.lab


def test_open_in_lab_opens_the_file_in_the_running_lab_without_reloading():
    from SciQLop.components.jupyter.kernel.manager import KernelManager
    km = KernelManager.__new__(KernelManager)
    km._jupyter = _FakeJupyter()
    assert km.open_in_lab("sub dir/a b.png") is km._jupyter.lab
    assert km._jupyter.opened == ["sub dir/a b.png"]
    assert km._jupyter.lab.loaded == []


@pytest.fixture
def opened(monkeypatch, workspace):
    """Record what a click opens instead of opening it."""
    from SciQLop.components.agents.chat import links
    calls = []
    monkeypatch.setattr(links, "workspace_dir", lambda: workspace)
    monkeypatch.setattr(links, "_open_in_browser", lambda url: calls.append(("web", url)))
    monkeypatch.setattr(links, "_open_in_lab", lambda rel: calls.append(("workspace", rel)))
    return calls


def _native_view(qtbot):
    from SciQLop.components.agents.chat import TranscriptView
    view = TranscriptView()
    qtbot.addWidget(view)
    return view


def _web_view(qtbot):
    from SciQLop.components.agents.chat.web_view import WebTranscriptView
    view = WebTranscriptView()
    qtbot.addWidget(view)
    return view


def _click(view, href):
    from PySide6.QtCore import QUrl
    backend = getattr(view, "backend", None)
    if backend is not None:
        backend.open_link(href)
    else:
        view.anchorClicked.emit(QUrl(href))


@pytest.mark.parametrize("make_view", [_native_view, _web_view])
def test_clicking_links_opens_them(make_view, qtbot, opened):
    view = make_view(qtbot)
    _click(view, "Ephemeris.ipynb")
    _click(view, "https://example.com")
    assert opened == [("workspace", "Ephemeris.ipynb"), ("web", "https://example.com")]


@pytest.mark.parametrize("make_view", [_native_view, _web_view])
def test_clicking_a_bad_link_reports_instead_of_opening(make_view, qtbot, opened):
    view = make_view(qtbot)
    with qtbot.waitSignal(view.link_refused, timeout=1000) as blocker:
        _click(view, "missing.ipynb")
    assert "missing.ipynb" in blocker.args[0]
    assert opened == []


@pytest.mark.parametrize("href", [
    "//attacker/share/x.ipynb", "\\\\attacker\\share\\x.ipynb",
    "file://attacker/share/x.ipynb", "file:////attacker/share/x.ipynb",
])
def test_remote_and_foreign_paths_are_refused_without_touching_the_filesystem(href, workspace, monkeypatch):
    """A UNC path that reaches the filesystem makes Windows contact that SMB
    server (and send NTLM credentials) before any containment check."""
    import pathlib

    def guarded(real):
        def method(self, *args, **kwargs):
            assert "attacker" not in str(self), f"filesystem touched for {self}"
            return real(self, *args, **kwargs)
        return method

    for name in ("resolve", "exists", "stat"):
        monkeypatch.setattr(pathlib.Path, name, guarded(getattr(pathlib.Path, name)))
    assert _classify(href, workspace).kind == "refused"
