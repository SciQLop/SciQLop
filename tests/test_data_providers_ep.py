"""Data providers are contributions to sciqlop.data_providers; `providers` stays a dict-like view (spec §4.3)."""
import pytest

from SciQLop.components.plotting.backend import data_provider
from SciQLop.components.plotting.backend.data_provider import DATA_PROVIDERS, DataProvider, providers
from SciQLop.core.extensions import owned_by


@pytest.fixture
def withdraw(qapp):
    owners = []
    yield owners.append
    for owner in owners:
        DATA_PROVIDERS.remove_owner(owner)


def test_a_provider_is_owned_by_the_plugin_that_created_it(withdraw):
    withdraw("dp_demo")
    with owned_by("dp_demo"):
        p = DataProvider("dp_demo.provider")
    assert providers["dp_demo.provider"] is p
    assert DATA_PROVIDERS.owner_of("dp_demo.provider") == "dp_demo"
    assert "dp_demo.provider" in providers and "dp_demo.provider" in list(providers)


def test_recreating_a_provider_replaces_it(withdraw):
    withdraw("dp_test")
    with owned_by("dp_test"):
        first, second = DataProvider("dp_again"), DataProvider("dp_again")
    assert providers["dp_again"] is second and first is not second


def test_dict_writes_and_pops_go_through_the_extension_point(withdraw):
    withdraw("dp_test")

    class Fake:
        name = "dp_fake"

    seen = []
    DATA_PROVIDERS.signals.removed.connect(seen.append)
    with owned_by("dp_test"):
        providers["dp_fake"] = fake = Fake()
    assert DATA_PROVIDERS.get("dp_fake") is fake
    assert providers.pop("dp_fake") is fake and seen == [fake]
    assert providers.pop("dp_fake", None) is None
    assert providers.get("dp_fake") is None


def test_dict_write_under_another_name_is_refused(withdraw):
    class Fake:
        name = "dp_real"

    with pytest.raises(ValueError, match="named 'dp_real'"):
        providers["dp_other"] = Fake()


def test_off_main_thread_registration_is_marshalled(withdraw, monkeypatch):
    """A notebook cell runs on the kernel thread; the provider must still register (on the main thread)."""
    import threading
    from SciQLop.user_api import threading as sq_threading
    marshalled = []

    def fake_invoker(func, *args, **kwargs):
        marshalled.append(func)
        return None  # the call is recorded, not run: this test pins the marshalling, not Qt's queue

    monkeypatch.setattr(sq_threading, "_invoker", fake_invoker)
    worker = threading.Thread(target=lambda: data_provider.register_provider(type("P", (), {"name": "dp_kernel"})()))
    worker.start()
    worker.join()
    assert len(marshalled) == 1
