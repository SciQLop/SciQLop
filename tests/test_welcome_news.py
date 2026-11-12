"""The welcome page's news: a few plain lines about this release, gone for
good once dismissed, back when the news changes."""
import json
from unittest.mock import patch

import pytest
from PySide6.QtCore import QObject

from SciQLop.components.settings.backend import entry
from SciQLop.components.welcome import backend as welcome_backend
from SciQLop.components.welcome.backend import WelcomeBackend


@pytest.fixture
def backend(qapp, tmp_path):
    instance = WelcomeBackend.__new__(WelcomeBackend)
    QObject.__init__(instance)
    with patch.object(entry, "SCIQLOP_CONFIG_DIR", str(tmp_path)):
        yield instance


def _news(backend):
    return json.loads(backend.list_news())


def test_the_news_is_short_and_plain(backend):
    news = _news(backend)
    assert 3 <= len(news) <= 5
    for item in news:
        assert set(item) == {"icon", "title"}
        assert "@" not in item["title"] and "`" not in item["title"] and len(item["title"]) < 140


def test_dismissed_news_stays_dismissed(backend):
    backend.dismiss_news()
    assert _news(backend) == []


def test_news_that_changed_is_shown_again(backend, monkeypatch):
    backend.dismiss_news()
    monkeypatch.setattr(welcome_backend, "NEWS", [{"icon": "🆕", "title": "Something new"}])
    assert _news(backend) == [{"icon": "🆕", "title": "Something new"}]
