"""End-to-end persistence of user-declared attribute schemas."""
import time
from .fixtures import *
import pytest


SCHEMA_PREFIX = "sciqlop_schema__"


def _drain(qapp, rounds=15):
    """Process events to let tscat's async QThread actions complete."""
    for _ in range(rounds):
        qapp.processEvents()
        time.sleep(0.05)
    qapp.processEvents()


@pytest.fixture(scope="module")
def tscat_provider(qapp):
    """Module-scoped tscat provider. Backend pre-initialized in conftest."""
    from tscat_gui.tscat_driver.model import tscat_model
    tscat_model.tscat_root()
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    provider = TscatCatalogProvider()
    yield provider
    CatalogRegistry.instance().unregister(provider)


@pytest.mark.xfail(reason="Absorbs the first-run alembic Qt-event-loop noise; "
                          "subsequent tscat tests run cleanly. Same pattern "
                          "as in test_catalog_tscat_integration.py.")
def test_tscat_warmup_triggers_alembic(qapp, tscat_provider):
    tscat_provider.create_catalog("__warmup__")
    _drain(qapp)
    raise AssertionError("absorb alembic noise")


def test_tscat_set_attribute_spec_writes_attribute(qapp, tscat_provider):
    """Setting a user spec writes sciqlop_schema__<key> as JSON to the tscat catalog."""
    import json
    from SciQLop.core.knobs import IntKnob

    provider = tscat_provider
    cat = provider.create_catalog("schema_persist_t1")
    _drain(qapp)

    spec = IntKnob(name="confidence", min=0, max=100, default=50)
    provider.set_attribute_spec(cat, "confidence", spec)
    _drain(qapp)

    from tscat_gui.tscat_driver.model import tscat_model
    entity = next(
        (n.node for n in tscat_model.tscat_root().catalogue_nodes(in_trash=False)
         if n.node.uuid == cat.uuid),
        None,
    )
    assert entity is not None
    var_attrs = entity.variable_attributes()
    schema_attr = var_attrs.get(SCHEMA_PREFIX + "confidence")
    assert schema_attr is not None
    parsed = json.loads(schema_attr) if isinstance(schema_attr, str) else schema_attr
    assert parsed["type"] == "IntKnob"
    assert parsed["name"] == "confidence"


def test_tscat_remove_attribute_spec_drops_attribute(qapp, tscat_provider):
    from SciQLop.core.knobs import IntKnob

    provider = tscat_provider
    cat = provider.create_catalog("schema_persist_t2")
    _drain(qapp)

    provider.set_attribute_spec(cat, "x", IntKnob(name="x", default=1))
    _drain(qapp)
    provider.remove_attribute_spec(cat, "x")
    _drain(qapp)

    from tscat_gui.tscat_driver.model import tscat_model
    entity = next(
        (n.node for n in tscat_model.tscat_root().catalogue_nodes(in_trash=False)
         if n.node.uuid == cat.uuid),
        None,
    )
    var_attrs = entity.variable_attributes()
    assert SCHEMA_PREFIX + "x" not in var_attrs


def test_tscat_loads_persisted_schema_on_provider_creation(qapp, tscat_provider):
    """A schema persisted to a catalog must be readable on a fresh provider instance."""
    import json
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider
    from SciQLop.core.knobs import IntKnob, spec_to_dict
    from tscat_gui.tscat_driver.model import tscat_model
    from tscat_gui.tscat_driver.actions import SetAttributeAction

    cat = tscat_provider.create_catalog("schema_persist_t3")
    _drain(qapp)

    spec = IntKnob(name="precision", min=0, max=100, default=10)
    payload = json.dumps(spec_to_dict(spec))
    tscat_model.do(SetAttributeAction(
        user_callback=None,
        uuids=[cat.uuid],
        name=SCHEMA_PREFIX + "precision",
        values=[payload],
    ))
    _drain(qapp)

    provider2 = TscatCatalogProvider()
    _drain(qapp)
    cat2 = next(c for c in provider2.catalogs() if c.uuid == cat.uuid)
    loaded = provider2.attribute_spec(cat2, "precision")
    assert loaded == spec


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("cocat"),
    reason="cocat library not installed",
)
def test_cocat_set_attribute_spec_writes_to_crdt(qapp):
    import json
    from cocat.db import DB
    from SciQLop.plugins.collaborative_catalogs.cocat_provider import CocatCatalogProvider
    from SciQLop.components.catalogs.backend.provider import Catalog
    from SciQLop.core.knobs import IntKnob

    db = DB()
    cocat_cat = db.create_catalogue(name="t_room_persist", author="test")

    provider = CocatCatalogProvider()
    cat = Catalog(uuid=str(cocat_cat.uuid), name="t_room_persist",
                  provider=provider, path=[])
    provider._catalog_map[cat.uuid] = cat
    provider._cocat_catalogues[cat.uuid] = cocat_cat

    spec = IntKnob(name="confidence", min=0, max=100, default=50)
    provider.set_attribute_spec(cat, "confidence", spec)
    qapp.processEvents()

    raw = cocat_cat.attributes.get(SCHEMA_PREFIX + "confidence")
    assert raw is not None
    parsed = json.loads(raw) if isinstance(raw, str) else raw
    assert parsed["type"] == "IntKnob"


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("cocat"),
    reason="cocat library not installed",
)
def test_cocat_remote_schema_change_emits_signal(qtbot, qapp):
    """When a cocat catalog's _sciqlop_schema__<key> attribute changes remotely,
    the provider's in-memory store updates and attribute_spec_changed fires."""
    import json
    from cocat.db import DB
    from SciQLop.plugins.collaborative_catalogs.cocat_provider import CocatCatalogProvider
    from SciQLop.components.catalogs.backend.provider import Catalog
    from SciQLop.core.knobs import IntKnob, spec_to_dict

    db = DB()
    cocat_cat = db.create_catalogue(name="t_remote", author="test")
    provider = CocatCatalogProvider()
    cat = Catalog(uuid=str(cocat_cat.uuid), name="t_remote",
                  provider=provider, path=[])
    provider._catalog_map[cat.uuid] = cat
    provider._cocat_catalogues[cat.uuid] = cocat_cat

    provider._subscribe_catalogue(cocat_cat, cat)
    qapp.processEvents()

    received = []
    provider.attribute_spec_changed.connect(lambda c, k: received.append(k))

    spec = IntKnob(name="remote_field", min=0, max=10, default=5)
    cocat_cat.set_attributes(**{
        SCHEMA_PREFIX + "remote_field": json.dumps(spec_to_dict(spec)),
    })
    qapp.processEvents()

    assert "remote_field" in received
    assert provider.attribute_spec(cat, "remote_field") == spec
