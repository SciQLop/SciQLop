"""list_virtual_products runs on the kernel thread while the GUI thread (or a
plugin) can register providers; iterating the live dict could raise
'dictionary changed size during iteration'."""


def test_a_registration_during_the_listing_does_not_break_it(monkeypatch):
    from SciQLop.components.plotting.backend import data_provider
    from SciQLop.components.plotting.backend.easy_provider import EasyProvider
    from SciQLop.user_api.virtual_products import list_virtual_products

    live = {}

    class _RegistersWhileListed(EasyProvider):
        def __init__(self):
            pass

        @property
        def path(self):
            live[f"late{len(live)}"] = object()  # another thread registering meanwhile
            return ["folder", "vp"]

    live["vp"] = _RegistersWhileListed()
    monkeypatch.setattr(data_provider, "providers", live)

    assert list_virtual_products() == ["folder//vp"]
