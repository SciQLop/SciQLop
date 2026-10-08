"""The product node is the signal that a provider exists: GUI code reacting to
the new row looks the provider up and calls it. Registering the node before the
provider is fully built lets that code see a half-initialised object."""
import sys

import pytest

from SciQLop.core.models import products
from SciQLop.components.plotting.backend.easy_provider import (
    EasyProvider, EasyScalar, EasyVector, EasyMultiComponent, EasySpectrogram,
)


def _callback(start: float, stop: float):
    return None


def _provider_under_construction():
    frame = sys._getframe(1)
    while frame is not None:
        candidate = frame.f_locals.get("self")
        if isinstance(candidate, EasyProvider):
            return candidate
        frame = frame.f_back
    raise AssertionError("add_node not called from an EasyProvider")


@pytest.fixture
def state_at_registration(monkeypatch):
    seen = {}

    def _add_node(path, node):
        provider = _provider_under_construction()
        seen.update({name: hasattr(provider, name) for name in
                     ("_callback", "_range_stack", "_knob_specs", "_dependency_specs", "_columns")})

    monkeypatch.setattr(products, "add_node", _add_node)
    return seen


@pytest.mark.parametrize("make", [
    lambda: EasyScalar("t_order/scalar", _callback, "B", metadata={}),
    lambda: EasyVector("t_order/vector", _callback, ["X", "Y", "Z"], metadata={}),
    lambda: EasyMultiComponent("t_order/multi", _callback, ["a", "b"], metadata={}),
])
def test_node_is_registered_once_the_provider_is_complete(state_at_registration, make):
    make()
    assert state_at_registration and all(state_at_registration.values()), state_at_registration


def test_spectrogram_node_is_registered_once_the_provider_is_complete(state_at_registration):
    EasySpectrogram("t_order/spectro", _callback, metadata={})
    state_at_registration.pop("_columns")  # spectrograms have no columns
    assert all(state_at_registration.values()), state_at_registration
