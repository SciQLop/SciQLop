"""Smart-search domains are contributions to sciqlop.search_domains (Tier 3 spec §3.3)."""
from unittest.mock import MagicMock

import pytest

import SciQLop.components.smart_search as facade
from SciQLop.components.smart_search.domain import SEARCH_DOMAINS
from SciQLop.components.smart_search.registry import SmartSearchRegistry
from SciQLop.core.extensions import owned_by


class _Domain:
    def __init__(self, name):
        self.name = name

    def snapshot(self):
        return []


@pytest.fixture
def fake_registry(qapp, monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(facade, "_get_registry", lambda: fake)
    yield fake
    SEARCH_DOMAINS.remove_owner("sd_demo")


def test_register_domain_contributes_under_the_current_owner(fake_registry):
    domain = _Domain("sd_demo.events")
    with owned_by("sd_demo"):
        facade.register_domain(domain)
    assert SEARCH_DOMAINS.owner_of("sd_demo.events") == "sd_demo"
    fake_registry.register_domain.assert_called_once_with(domain)


def test_a_withdrawn_domain_leaves_the_index(fake_registry):
    with owned_by("sd_demo"):
        facade.register_domain(_Domain("sd_demo.events"))
    SEARCH_DOMAINS.remove_owner("sd_demo")
    fake_registry.unregister_domain.assert_called_once_with("sd_demo.events")


def test_unregistering_an_unknown_domain_is_a_no_op(fake_registry):
    facade.unregister_domain("sd_demo.never_registered")
    fake_registry.unregister_domain.assert_not_called()


def test_a_registry_built_later_takes_the_domains_already_contributed(qapp, monkeypatch, fake_registry, tmp_path):
    with owned_by("sd_demo"):
        facade.register_domain(_Domain("sd_demo.early"))
    monkeypatch.undo()  # the real _get_registry again
    monkeypatch.setattr(facade, "_jobs_backend_instance", lambda: MagicMock())
    monkeypatch.setattr(facade, "_cache_dir", lambda: str(tmp_path / "models"))
    monkeypatch.setattr(facade, "_index_cache_dir", lambda: str(tmp_path / "index"))
    monkeypatch.setattr(facade, "_registry", None)
    assert "sd_demo.early" in facade._get_registry()._domains


def test_a_domain_registered_from_a_worker_thread_keeps_its_owner(fake_registry, qtbot, monkeypatch):
    from .helpers import call_from_worker_thread

    def register():
        with owned_by("sd_demo"):
            facade.register_domain(_Domain("sd_demo.threaded"))

    call_from_worker_thread(qtbot, monkeypatch, register)
    assert SEARCH_DOMAINS.owner_of("sd_demo.threaded") == "sd_demo"


def test_registering_a_domain_again_stops_its_old_reindex_timer(qapp, tmp_path):
    registry = SmartSearchRegistry(MagicMock(), model_name="m", cache_dir=str(tmp_path),
                                   index_cache_dir=str(tmp_path))
    registry.register_domain(_Domain("x"))
    old_timer = registry._domains["x"].reindex_timer
    old_timer.start(60_000)
    registry.register_domain(_Domain("x"))
    assert not old_timer.isActive()
