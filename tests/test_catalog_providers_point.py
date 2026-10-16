"""Catalog providers are contributions to sciqlop.catalog_providers (Tier 3 spec §3.4)."""
import pytest

from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
from SciQLop.components.catalogs.backend.registry import CATALOG_PROVIDERS, CatalogRegistry, provider_key
from SciQLop.core.extensions import owned_by


@pytest.fixture
def registry(qapp):
    yield CatalogRegistry.instance()
    CATALOG_PROVIDERS.remove_owner("cp_demo")


def _provider(**kw):
    with owned_by("cp_demo"):
        return DummyProvider(num_catalogs=1, events_per_catalog=0, **kw)


def test_a_provider_built_by_a_plugin_is_owned_by_it(registry):
    p = _provider()
    assert CATALOG_PROVIDERS.owner_of(provider_key(p)) == "cp_demo"
    assert p in registry.providers()
    assert registry.provider_by_name("DummyProvider") is not None


def test_withdrawing_the_plugin_unregisters_its_providers(registry, qtbot):
    p = _provider()
    with qtbot.waitSignal(registry.provider_unregistered) as blocker:
        CATALOG_PROVIDERS.remove_owner("cp_demo")
    assert blocker.args == [p]
    assert p not in registry.providers()


def test_two_providers_may_share_a_name(registry):
    a, b = _provider(), _provider()
    assert a in registry.providers() and b in registry.providers()


def test_registering_twice_is_a_no_op(registry):
    p = _provider()
    registry.register(p)
    assert registry.providers().count(p) == 1


def test_a_destroyed_provider_leaves_without_a_signal(registry, qtbot):
    p = _provider()
    key, seen = provider_key(p), []
    registry.provider_unregistered.connect(seen.append)
    try:
        p.deleteLater()
        qtbot.waitUntil(lambda: key not in CATALOG_PROVIDERS)
    finally:
        registry.provider_unregistered.disconnect(seen.append)
    assert seen == []


def test_a_withdrawn_providers_catalogs_leave_the_catalog_tree(registry):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    p = _provider()
    model = CatalogTreeModel()
    assert model._provider_node(p) is not None
    CATALOG_PROVIDERS.remove_owner("cp_demo")
    assert model._provider_node(p) is None


def test_a_provider_built_on_a_worker_thread_registers_under_its_owner(registry, qtbot, monkeypatch):
    # A notebook cell, an agent tool or a live labelling pipeline may build a provider off the main thread.
    from .helpers import call_from_worker_thread
    p = call_from_worker_thread(qtbot, monkeypatch, _provider)
    assert CATALOG_PROVIDERS.owner_of(provider_key(p)) == "cp_demo"
    assert p in registry.providers()


def test_a_provider_built_like_sciqlop_msa_registers_and_lists_its_catalogs(registry):
    from SciQLop.components.catalogs.backend.provider import Catalog, CatalogProvider

    class FlybyProvider(CatalogProvider):
        def __init__(self):
            # sciqlop_msa sets its catalogs before super().__init__: registering asks for catalogs() right away.
            self._flybys = [Catalog(uuid="cp-demo-flyby", name="Flybys", provider=self)]
            super().__init__(name="CP demo flybys", description="Flybys.")

        def catalogs(self):
            return self._flybys

    with owned_by("cp_demo"):
        p = FlybyProvider()
    assert [c.name for c in registry.all_catalogs() if c.provider is p] == ["Flybys"]
