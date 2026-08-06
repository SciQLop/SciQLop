"""The reindex job's entry point -- runs inside a spawned subprocess via
JobsBackend.submit_function. Must stay a real module-level function: the
spawn context re-imports it by dotted path in the child.

Cache-aware: loads a per-domain on-disk cache keyed by model_name, embeds
only new/changed text, drops entries no longer in the current snapshot,
persists the merged result, and returns it -- see docs/superpowers/specs/
2026-07-19-smart-search-model2vec-incremental-indexing-design.md.

The cache is a pickle file written and read only by this module, under
SciQLop's own platformdirs cache directory -- never sourced from anywhere
untrusted, so pickle's arbitrary-code-execution risk on load doesn't apply
here.

run() also builds a BM25F index from the same snapshot on every call (no
incremental caching needed -- a full rebuild is a couple of seconds even
at 77k entries) and returns both alongside each other as an IndexResult --
see docs/superpowers/specs/2026-07-20-smart-search-bm25-ranking-design.md."""
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from SciQLop.components.smart_search import bm25_index, model_fetch
from SciQLop.components.smart_search.domain import NodeSnapshot

if TYPE_CHECKING:
    import numpy as np

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IndexResult:
    embeddings: dict[str, "np.ndarray"]
    bm25: bm25_index.BM25Index


def _load_cache(index_cache_path: str, model_name: str) -> dict:
    path = Path(index_cache_path)
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            cache = pickle.load(f)
        if not isinstance(cache, dict) or cache.get("model_name") != model_name:
            return {}
    except Exception:
        return {}
    return cache.get("entries", {})


def _save_cache(index_cache_path: str, model_name: str, entries: dict) -> None:
    path = Path(index_cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump({"model_name": model_name, "entries": entries}, f)


def _save_cache_best_effort(index_cache_path: str, model_name: str, entries: dict) -> None:
    try:
        _save_cache(index_cache_path, model_name, entries)
    except Exception:
        _logger.warning("Failed to persist smart-search index cache to %s", index_cache_path, exc_info=True)


def _run_embeddings(snapshot: Sequence[NodeSnapshot], model_name: str, cache_dir: str, index_cache_path: str) -> dict:
    current = {n.path_key: n.raw_text for n in snapshot}
    if not current:
        _save_cache_best_effort(index_cache_path, model_name, {})
        return {}

    cached = _load_cache(index_cache_path, model_name)
    to_embed = [
        NodeSnapshot(path_key, raw_text)
        for path_key, raw_text in current.items()
        if path_key not in cached or cached[path_key][0] != raw_text
    ]

    newly_embedded = {}
    if to_embed:
        model = model_fetch.load_model(model_name, cache_dir)
        vectors = model.encode([n.raw_text for n in to_embed], use_multiprocessing=False)
        newly_embedded = {n.path_key: (n.raw_text, vectors[i]) for i, n in enumerate(to_embed)}

    merged = {**{k: v for k, v in cached.items() if k in current}, **newly_embedded}
    _save_cache_best_effort(index_cache_path, model_name, merged)
    return {path_key: vector for path_key, (raw_text, vector) in merged.items()}


def run(snapshot: Sequence[NodeSnapshot], model_name: str, cache_dir: str, index_cache_path: str) -> IndexResult:
    embeddings = _run_embeddings(snapshot, model_name, cache_dir, index_cache_path)
    return IndexResult(embeddings=embeddings, bm25=bm25_index.build(snapshot))
