"""Regression: MMS's leaf-level CDF metadata only ever uses instrument
acronyms (SCM, FGM, MEC...), never the spelled-out English name -- but
speasy's own inventory DOES carry that spelled-out name on the ANCESTOR
folder nodes (e.g. the real tree.cda.MMS.MMS1.SCM.description ==
"Search Coil Magnetometer"), sourced from CDAWeb's own catalog XML.
explore_nodes() discarded it (folder-only metadata, used for that folder's
own tooltip), so it never reached the leaf's own raw_text() -- meaning
search (native fuzzy AND smart_search/BM25 alike) has zero vocabulary
overlap for a query like "MMS1 Search Coil" against the real Search Coil
Magnetometer data. Found live 2026-07-21, see feature-smart-search-component
memory. Real values pinned via a live check against speasy's own inventory
(not guessed); stubbed here since the test suite runs with
SPEASY_SKIP_INIT_PROVIDERS=1 and no real network/cache access."""
import pytest

from SciQLop.plugins.speasy_provider.speasy_provider import explore_nodes
from SciQLopPlots import ProductsModelNode, ProductsModelNodeType


class FakeParameterIndex:
    """Minimal stand-in for speasy's real ParameterIndex, shaped after the
    real MMS1 SCM leaf: CATDESC/FIELDNAM present, no "description" of its
    own -- only ancestor folders carry that."""

    def __init__(self, name, catdesc, fieldnam):
        self.CATDESC = catdesc
        self.FIELDNAM = fieldnam
        self.DISPLAY_TYPE = "time_series"
        self._name = name

    def spz_uid(self):
        return self._name

    def spz_provider(self):
        return "cda"

    def spz_name(self):
        return self._name


class FakeFolder:
    """Minimal stand-in for speasy's SpeasyIndex folder nodes (mission,
    spacecraft, instrument, dataset)."""

    def __init__(self, name, description=None, **children):
        self.name = name
        if description is not None:
            self.description = description
        for child_name, child in children.items():
            setattr(self, child_name, child)


@pytest.fixture
def fake_speasy_classes(monkeypatch):
    class _NeverMatches:
        pass

    monkeypatch.setattr(
        "SciQLop.plugins.speasy_provider.speasy_provider.ParameterIndex",
        FakeParameterIndex, raising=False)
    monkeypatch.setattr(
        "SciQLop.plugins.speasy_provider.speasy_provider.CatalogIndex",
        _NeverMatches, raising=False)
    monkeypatch.setattr(
        "SciQLop.plugins.speasy_provider.speasy_provider.TimetableIndex",
        _NeverMatches, raising=False)


def _collect_leaves(node):
    if node.node_type() == ProductsModelNodeType.PARAMETER:
        return [node]
    leaves = []
    for child in node.children_nodes():
        leaves.extend(_collect_leaves(child))
    return leaves


def test_leaf_metadata_includes_ancestor_instrument_description(
        qtbot, fake_speasy_classes):
    leaf = FakeParameterIndex(
        "mms1_scm_acb_gse_schb_brst_l2",
        catdesc="L2 AC magnetic field in GSE frame",
        fieldnam="mms1_scm_acb_gse_schb_brst_l2")
    dataset = FakeFolder(
        "MMS1_SCM_BRST_L2_SCHB",
        description="Level 2 Search Coil Magnetometer AC Magnetic Field "
                     "High Burst Data",
        mms1_scm_acb_gse_schb_brst_l2=leaf)
    scm = FakeFolder("SCM", description="Search Coil Magnetometer",
                      MMS1_SCM_BRST_L2_SCHB=dataset)

    root = ProductsModelNode("TestRoot")
    explore_nodes(scm, root, provider="cda")

    leaves = _collect_leaves(root)
    assert len(leaves) == 1
    meta_text = " ".join(str(v) for v in leaves[0].metadata().values())
    assert "Search Coil Magnetometer" in meta_text, (
        f"leaf metadata has no trace of the ancestor instrument "
        f"description: {leaves[0].metadata()}")
