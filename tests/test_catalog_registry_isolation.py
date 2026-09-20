"""A test that dirties a provider must not leave it dirty for the next test
(closing a main window with a dirty provider pops a blocking dialog)."""
import pytest

from .fixtures import *


@pytest.fixture(scope="module")
def shared_provider(qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    return DummyProvider(num_catalogs=1, events_per_catalog=0, name="IsolationProv")


def test_a_dirties_the_provider(shared_provider):
    shared_provider.mark_provider_dirty()
    shared_provider.mark_dirty(shared_provider.catalogs()[0])
    assert shared_provider.is_dirty()


def test_b_finds_the_provider_clean(shared_provider):
    assert not shared_provider.is_dirty()
