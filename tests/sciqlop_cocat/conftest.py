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


@pytest.fixture
def attached(provider, room):
    """A provider with the offline test room attached as room id "r"."""
    provider.attach_room("r", room)
    return provider


def only(provider):
    [catalog] = provider.catalogs()
    return catalog
