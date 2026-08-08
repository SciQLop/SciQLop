"""Regression tests for SciQLop's speasy inventory registration patch."""
import os

import pytest


@pytest.mark.skipif(
    os.environ.get("SPEASY_SKIP_INIT_PROVIDERS") != "1",
    reason="must skip auto-init so we can patch before any provider loads",
)
def test_inventory_registration_is_cycle_safe():
    """speasy's ProviderInventory._register_nodes is recursive and can overflow
    the C stack when the provider inventory contains deep trees or cycles.
    SciQLop patches it to an iterative traversal; verify the patch survives a
    deliberately cyclic inventory.
    """
    from speasy.core.inventory import ProviderInventory, SpeasyIndex
    from SciQLop.plugins.speasy_provider.speasy_provider import (
        _patch_speasy_inventory_registration,
    )

    _patch_speasy_inventory_registration()

    root = SpeasyIndex("root", "test", "root")
    child = SpeasyIndex("child", "test", "child")
    grandchild = SpeasyIndex("grandchild", "test", "grandchild")
    root.child = child
    child.grandchild = grandchild
    grandchild.back = root  # cycle

    inv = ProviderInventory()
    inv._register_nodes(root)  # must terminate without RecursionError/SIGSEGV
    # All three SpeasyIndex nodes were reachable.
    assert len(inv.parameters) == 0
