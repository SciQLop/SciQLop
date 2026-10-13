import pytest


@pytest.fixture(autouse=True)
def _workers_skip_speasy_servers(monkeypatch):
    """A worker inits speasy's providers when its callback imports speasy (or
    SciQLop.user_api), pinging each server for up to 30 s. No remote test
    fetches speasy data, so an unreachable server must not time them out."""
    monkeypatch.setenv("SPEASY_CORE_DISABLED_PROVIDERS",
                       "amda,archive,cda,cdpp3dview,csa,ssc,uiowaephtool")
