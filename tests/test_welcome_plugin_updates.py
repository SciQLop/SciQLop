"""The welcome page tells the user when installed store plugins have updates,
and its button opens the store's Updates page."""
import json

from .fixtures import *  # noqa: F401, F403


def _pkg(name, *versions):
    return {"name": name, "versions": [{"version": v, "pip": f"{name.lower()}=={v}"} for v in versions]}


def _installed(monkeypatch, versions: dict):
    monkeypatch.setattr("SciQLop.components.appstore.backend._installed_version", versions.get)


def test_only_installed_packages_with_a_newer_version_are_listed(monkeypatch):
    from SciQLop.components.appstore.backend import available_updates
    _installed(monkeypatch, {"alpha": "1.0", "beta": "2.0", "gamma": "1.10"})
    packages = [_pkg("Alpha", "1.0", "1.2"), _pkg("Beta", "2.0"), _pkg("Gamma", "1.9"), _pkg("Delta", "3.0")]

    assert available_updates(packages) == [{"name": "Alpha", "installed": "1.0", "latest": "1.2"}]


def test_an_unparsable_version_is_skipped_rather_than_breaking_the_list(monkeypatch):
    from SciQLop.components.appstore.backend import available_updates
    _installed(monkeypatch, {"alpha": "not-a-version", "beta": "1.0"})
    packages = [_pkg("Alpha", "2.0"), _pkg("Beta", "1.1")]

    assert [u["name"] for u in available_updates(packages)] == ["Beta"]


def test_the_welcome_backend_reports_updates_from_the_store_index(qtbot, monkeypatch):
    from SciQLop.components.welcome.backend import WelcomeBackend
    monkeypatch.setattr("SciQLop.components.welcome.backend.fetch_index",
                        lambda url: [_pkg("Alpha", "1.0", "1.2")])
    monkeypatch.setattr("SciQLop.components.welcome.backend.filter_packages", lambda p: p)
    _installed(monkeypatch, {"alpha": "1.0"})
    backend = WelcomeBackend()

    with qtbot.waitSignal(backend.plugin_updates_ready, timeout=3000) as blocker:
        backend.fetch_plugin_updates()

    assert json.loads(blocker.args[0]) == [{"name": "Alpha", "installed": "1.0", "latest": "1.2"}]


def test_the_welcome_backend_reports_nothing_when_offline(qtbot, monkeypatch):
    from SciQLop.components.welcome.backend import WelcomeBackend

    def offline(url):
        raise OSError("network unreachable")

    monkeypatch.setattr("SciQLop.components.welcome.backend.fetch_index", offline)
    backend = WelcomeBackend()

    with qtbot.waitSignal(backend.plugin_updates_ready, timeout=3000) as blocker:
        backend.fetch_plugin_updates()

    assert json.loads(blocker.args[0]) == []


def test_review_updates_opens_the_store_on_its_updates_page(main_window, monkeypatch):
    shown = []
    main_window.welcome.backend.open_appstore_updates()
    store = main_window._appstore
    assert store is not None
    monkeypatch.setattr(store, "show_page", shown.append)
    main_window.welcome.backend.open_appstore_updates()
    assert shown == ["updates"]

