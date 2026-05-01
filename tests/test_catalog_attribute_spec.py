"""Tests for CatalogProvider.attribute_spec — typed schema for event metadata."""
from .fixtures import *


def test_base_provider_attribute_spec_returns_none(qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    provider = DummyProvider(num_catalogs=1, events_per_catalog=1)
    cat = provider.catalogs()[0]
    assert provider.attribute_spec(cat, "score") is None
    assert provider.attribute_spec(cat, "any_unknown_key") is None


def test_attribute_spec_can_be_overridden_to_return_intknob(qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.knobs import IntKnob, KnobSpec

    class TypedDummy(DummyProvider):
        def attribute_spec(self, catalog, key):
            if key == "rating":
                return IntKnob(name=key, min=1, max=5, default=3)
            return None

    provider = TypedDummy(num_catalogs=1, events_per_catalog=1)
    cat = provider.catalogs()[0]
    spec = provider.attribute_spec(cat, "rating")
    assert isinstance(spec, IntKnob)
    assert spec.min == 1
    assert spec.max == 5
    assert provider.attribute_spec(cat, "other") is None
