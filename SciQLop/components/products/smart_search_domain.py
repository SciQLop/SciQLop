"""Registers "products" as a smart-search domain -- ProductsModel is a
shared singleton fed by speasy_provider, virtual products, and any other
plugin, so this adapter lives in components/products/ (core), not in any
one provider plugin. See docs/superpowers/specs/
2026-07-17-smart-search-component-design.md."""
from SciQLopPlots import ProductsFlatFilterModel, ProductsModel

from SciQLop.components.smart_search import notify_changed, register_domain
from SciQLop.components.smart_search.domain import NodeSnapshot


class ProductsDomain:
    name = "products"

    def __init__(self):
        self._corpus_source = ProductsFlatFilterModel(ProductsModel.instance())
        model = ProductsModel.instance()
        model.rowsInserted.connect(self._on_changed)
        model.rowsRemoved.connect(self._on_changed)
        model.modelReset.connect(self._on_changed)

    def snapshot(self):
        """corpus_snapshot()'s key is the clean mission/instrument/variable
        path (e.g. "root speasy cda MMS MMS1 FGM ..."); its value is verbose
        CDF metadata (CATDESC/FIELDNAM/UNITS/...) with no mission/instrument
        names in it. Prepending the path gives the embedding model the
        clean hierarchy alongside the descriptive metadata -- embedding
        metadata alone buried mission-specific queries under generically-
        named fields from unrelated missions (measured against a real
        product catalog)."""
        return [NodeSnapshot(k, f"{k} {v}") for k, v in self._corpus_source.corpus_snapshot().items()]

    def _on_changed(self, *args) -> None:
        notify_changed(self.name)


def register_smart_search_domain() -> None:
    from SciQLop.core.extensions import owned_by
    from SciQLop.core.name_follower import CORE_OWNER
    with owned_by(CORE_OWNER):
        register_domain(ProductsDomain())
