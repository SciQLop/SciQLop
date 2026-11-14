import asyncio
import threading

import cocat_rs
import pytest
from SciQLop.plugins.sciqlop_cocat.session import Session


class FakeClient:
    def __init__(self, session="token"):
        self.session = session
        self.logouts = 0
        self.apps = []

    def start_sign_in(self, app):
        self.apps.append((app, threading.current_thread()))
        return "sign-in"

    def logout(self):
        self.logouts += 1
        self.session = None


def test_the_session_uses_the_token_the_client_keeps():
    session = Session("https://h/cocat/", FakeClient("t"))
    assert session.url == "https://h/cocat"
    assert session.cookie == "t" and session.signed_in
    assert not Session("https://h", FakeClient(None)).signed_in


def test_sign_in_starts_off_the_qt_thread_as_sciqlop():
    client = FakeClient(None)
    assert asyncio.run(Session("https://h", client).start_sign_in()) == "sign-in"
    [(app, thread)] = client.apps
    assert app == "SciQLop" and thread is not threading.main_thread()


def test_call_runs_off_thread_with_url_and_token():
    seen = {}

    def server_call(url, cookie, project_id):
        seen.update(url=url, cookie=cookie, thread=threading.current_thread())
        return f"{project_id} ok"

    assert asyncio.run(Session("https://h", FakeClient("t")).call(server_call, "p1")) == "p1 ok"
    assert seen["url"] == "https://h" and seen["cookie"] == "t"
    assert seen["thread"] is not threading.main_thread()


def test_a_refused_token_is_forgotten_so_sign_in_is_offered_again():
    def server_call(url, cookie):
        raise cocat_rs.Unauthorized("revoked")

    client = FakeClient("t")
    session = Session("https://h", client)
    with pytest.raises(cocat_rs.Unauthorized):
        asyncio.run(session.call(server_call))
    assert client.logouts == 1 and not session.signed_in


def test_call_lets_other_refusals_through():
    def server_call(url, cookie):
        raise cocat_rs.Forbidden("no")

    client = FakeClient("t")
    with pytest.raises(cocat_rs.Forbidden):
        asyncio.run(Session("https://h", client).call(server_call))
    assert client.logouts == 0


def test_projects_failure_is_none(monkeypatch):
    def projects(*_):
        raise ValueError("connection refused")

    monkeypatch.setattr(cocat_rs.raw, "projects", projects)
    assert asyncio.run(Session("https://h", FakeClient()).projects()) is None


def test_email_is_the_signed_in_account(monkeypatch):
    monkeypatch.setattr(cocat_rs.raw, "account", lambda url, cookie: {
        "id": "u2", "email": "me@x.org", "is_curator": False})
    assert asyncio.run(Session("https://h", FakeClient()).email()) == "me@x.org"


def test_sign_out_forgets_the_token():
    client = FakeClient("t")
    asyncio.run(Session("https://h", client).sign_out())
    assert client.logouts == 1
