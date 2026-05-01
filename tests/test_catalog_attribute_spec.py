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


def test_tscat_attribute_spec_rating_is_intknob_1_5(qapp):
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider
    from SciQLop.core.knobs import IntKnob

    provider = TscatCatalogProvider()
    cat = next(iter(provider.catalogs()), None)
    spec = provider.attribute_spec(cat, "rating")
    assert isinstance(spec, IntKnob)
    assert spec.min == 1
    assert spec.max == 5
    assert spec.name == "rating"


def test_tscat_attribute_spec_author_is_stringknob(qapp):
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider
    from SciQLop.core.knobs import StringKnob

    provider = TscatCatalogProvider()
    cat = next(iter(provider.catalogs()), None)
    spec = provider.attribute_spec(cat, "author")
    assert isinstance(spec, StringKnob)
    assert spec.name == "author"


def test_tscat_attribute_spec_unknown_key_returns_none(qapp):
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider

    provider = TscatCatalogProvider()
    cat = next(iter(provider.catalogs()), None)
    assert provider.attribute_spec(cat, "free_form_key_xyz") is None


def test_set_attribute_spec_persists_in_memory_and_emits(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.knobs import IntKnob

    provider = DummyProvider(num_catalogs=1, events_per_catalog=1)
    cat = provider.catalogs()[0]

    received = []
    provider.attribute_spec_changed.connect(lambda c, k: received.append((c.uuid, k)))

    spec = IntKnob(name="confidence", min=0, max=100, default=50)
    provider.set_attribute_spec(cat, "confidence", spec)

    assert provider.attribute_spec(cat, "confidence") == spec
    assert received == [(cat.uuid, "confidence")]


def test_user_spec_takes_precedence_over_builtin(qapp):
    """A user-declared spec for an existing built-in key must override the built-in."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.knobs import IntKnob, FloatKnob

    class BuiltinDummy(DummyProvider):
        def attribute_spec(self, catalog, key):
            user_spec = super().attribute_spec(catalog, key)
            if user_spec is not None:
                return user_spec
            if key == "rating":
                return IntKnob(name=key, min=1, max=5, default=3)
            return None

    provider = BuiltinDummy(num_catalogs=1, events_per_catalog=1)
    cat = provider.catalogs()[0]
    # Built-in "rating" is IntKnob(1, 5)
    builtin = provider.attribute_spec(cat, "rating")
    assert isinstance(builtin, IntKnob) and builtin.max == 5

    # User overrides
    user_spec = FloatKnob(name="rating", min=0.0, max=10.0, default=5.0)
    provider.set_attribute_spec(cat, "rating", user_spec)

    assert provider.attribute_spec(cat, "rating") == user_spec  # user wins


def test_set_attribute_spec_calls_persist_hook(qapp):
    """Subclasses override _persist_attribute_spec — verify it runs."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.knobs import StringKnob

    persisted = []

    class TrackingProvider(DummyProvider):
        def _persist_attribute_spec(self, catalog, key, spec):
            persisted.append((catalog.uuid, key, spec))

    provider = TrackingProvider(num_catalogs=1, events_per_catalog=1)
    cat = provider.catalogs()[0]
    spec = StringKnob(name="note", default="")
    provider.set_attribute_spec(cat, "note", spec)

    assert len(persisted) == 1
    assert persisted[0][1] == "note"


def test_remove_attribute_spec_emits_and_clears(qtbot, qapp):
    """Removing a user spec restores the provider's default (built-in or None)."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.knobs import IntKnob

    provider = DummyProvider(num_catalogs=1, events_per_catalog=1)
    cat = provider.catalogs()[0]
    provider.set_attribute_spec(cat, "x", IntKnob(name="x", default=1))
    assert provider.attribute_spec(cat, "x") is not None

    received = []
    provider.attribute_spec_changed.connect(lambda c, k: received.append(k))

    provider.remove_attribute_spec(cat, "x")
    assert provider.attribute_spec(cat, "x") is None
    assert received == ["x"]
