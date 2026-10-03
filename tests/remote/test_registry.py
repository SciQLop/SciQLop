import threading
import pytest
from SciQLop.components.plotting.backend.remote.registry import (
    RemoteRegistry, plugin_key_for,
)


def test_register_pickles_and_stores_blob():
    reg = RemoteRegistry()
    reg.register("radio/eovsa", lambda s, e: None, arity=3)
    assert reg.is_remote(["radio", "eovsa"])
    blob, arity = reg.spec_for(["radio", "eovsa"])
    assert isinstance(blob, bytes) and arity == 3


@pytest.mark.parametrize("registered, looked_up", [
    ("pyspedas/MMS/FPI ions/energy", ["root", "pyspedas", "MMS", "FPI ions", "energy"]),  # tree drop
    ("radio//eovsa", ["radio", "eovsa"]),
    ("amda//final / prelim//b", ["amda", "final / prelim", "b"]),  # "/" inside a segment
    ("/radio/eovsa/", ["radio", "eovsa"]),
])
def test_lookups_match_the_product_tree_path(registered, looked_up):
    reg = RemoteRegistry()
    reg.register(registered, lambda s, e: None, arity=2, colored=True)
    assert reg.is_remote(looked_up)
    assert reg.is_colored(looked_up)
    assert reg.spec_for(looked_up)[1] == 2


def test_segments_are_not_merged_across_slashes():
    reg = RemoteRegistry()
    reg.register("amda//final / prelim//b", lambda s, e: None, arity=2)
    assert not reg.is_remote(["amda", "final ", " prelim", "b"])


def test_register_unpicklable_raises_named_error():
    reg = RemoteRegistry()
    lock = threading.Lock()  # locks are not picklable, even by cloudpickle
    with pytest.raises(ValueError, match="radio/bad"):
        reg.register("radio/bad", lambda s, e, _l=lock: _l, arity=2)


def test_plugin_key_is_top_level_module():
    def cb(s, e):
        return None
    assert plugin_key_for(cb) == cb.__module__.split(".")[0]
