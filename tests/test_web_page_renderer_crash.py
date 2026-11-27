"""A SciQLop web page (welcome, app store, agent transcript) reloads itself
when its Chromium renderer dies, but stops after a few crashes in a row so a
page that crashes on load does not spin for ever."""
from PySide6.QtWebEngineCore import QWebEnginePage

from SciQLop.components.appstore.web_appstore_page import AppStorePage
from SciQLop.core.web_channel_page import should_reload

Status = QWebEnginePage.RenderProcessTerminationStatus


def test_a_normal_exit_does_not_reload():
    assert not should_reload(Status.NormalTerminationStatus, [], now=100.0)


def test_a_crash_reloads():
    for status in (Status.AbnormalTerminationStatus, Status.CrashedTerminationStatus,
                   Status.KilledTerminationStatus):
        assert should_reload(status, [], now=100.0)


def test_too_many_recent_crashes_stop_the_reloads():
    assert not should_reload(Status.CrashedTerminationStatus, [90.0, 95.0, 99.0], now=100.0)


def test_old_crashes_do_not_count():
    assert should_reload(Status.CrashedTerminationStatus, [1.0, 2.0, 3.0], now=100.0)


def test_the_page_reloads_after_a_crash_then_gives_up(qapp, monkeypatch):
    page = AppStorePage()
    loads = []
    monkeypatch.setattr(page, "_load_html", lambda: loads.append(1))
    for _ in range(5):
        page._on_render_process_terminated(Status.CrashedTerminationStatus, 1)
    assert len(loads) == 3
    page.deleteLater()
    qapp.processEvents()
