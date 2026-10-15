"""list_virtual_products runs on the kernel thread while the GUI thread (or a
plugin) can register virtual products; iterating the live registry could raise
'dictionary changed size during iteration', so the listing is a snapshot."""
from tests.fixtures import *  # noqa: F401,F403


def test_the_listing_is_the_extension_point_keys(qapp):
    from SciQLop.components.plotting.backend.easy_provider import VIRTUAL_PRODUCTS
    from SciQLop.user_api.virtual_products import list_virtual_products
    assert list_virtual_products() == VIRTUAL_PRODUCTS.keys()


def test_a_registration_after_the_listing_does_not_change_it(qapp):
    from SciQLop.core.extensions import ExtensionPoint

    class Item:
        def __init__(self, id):
            self.id = id

    ep = ExtensionPoint("test.snapshot", Item)
    ep.contribute(Item("a"))
    keys = ep.keys()
    ep.contribute(Item("b"))
    assert keys == ["a"]
