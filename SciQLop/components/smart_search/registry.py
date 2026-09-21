"""SmartSearchRegistry: owns one vector index per registered SearchDomain,
the shared embedding model, and reindex debouncing. See docs/superpowers/
specs/2026-07-17-smart-search-component-design.md."""
from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np
from PySide6.QtCore import QObject, QTimer

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.components.smart_search import bm25_index, index_worker, model_fetch
from SciQLop.components.smart_search.domain import SearchDomain

log = getLogger(__name__)

_DEFAULT_DEBOUNCE_MS = 200


@dataclass
class _DomainState:
    domain: SearchDomain
    reindex_timer: QTimer
    job_id: Optional[str] = None
    dirty: bool = False
    path_keys: list = field(default_factory=list)
    matrix: Optional[np.ndarray] = None
    bm25: Optional[bm25_index.BM25Index] = None


_BM25_CONFIDENT_FRAC = 0.5
_CONFIDENT_BAND_MAX = 100.0
_FALLBACK_BAND_MAX = 50.0


def _semantic_scores(path_keys: list, matrix: np.ndarray, query_model, text: str) -> dict:
    query_vec = query_model.encode([text])[0]
    norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_vec)
    norms[norms == 0] = 1.0
    cosine = (matrix @ query_vec) / norms
    return {path_key: float(max(0.0, sim)) * 100.0
            for path_key, sim in zip(path_keys, cosine)}


def score_query(
    text: str,
    path_keys: list,
    matrix: np.ndarray,
    bm25: Optional[bm25_index.BM25Index],
    query_model,
    bm25_confident_frac: float = _BM25_CONFIDENT_FRAC,
    confident_band_max: float = _CONFIDENT_BAND_MAX,
    fallback_band_max: float = _FALLBACK_BAND_MAX,
) -> dict:
    bm25_scores = bm25_index.score(bm25, text) if bm25 is not None else {}
    max_bm25 = max(bm25_scores.values(), default=0.0)
    confident = {
        path_key: s for path_key, s in bm25_scores.items()
        if max_bm25 > 0 and s >= bm25_confident_frac * max_bm25
    }

    result = {k: confident_band_max * (v / max_bm25) for k, v in confident.items()}
    for path_key, sim in _semantic_scores(path_keys, matrix, query_model, text).items():
        if path_key not in result:
            result[path_key] = fallback_band_max * (sim / 100.0)
    return result


class SmartSearchRegistry(QObject):
    def __init__(self, jobs_backend, model_name: str, cache_dir: str, index_cache_dir: str,
                 debounce_ms: int = _DEFAULT_DEBOUNCE_MS, parent=None):
        super().__init__(parent)
        self._jobs_backend = jobs_backend
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._index_cache_dir = index_cache_dir
        self._debounce_ms = debounce_ms
        self._domains: Dict[str, _DomainState] = {}
        self._job_to_domain: Dict[str, str] = {}
        self._enabled = False
        self._query_model = None
        self._pending_enable = None
        self._jobs_backend.job_status_changed.connect(self._on_job_status_changed)

    # --- domain registration -------------------------------------------------
    def register_domain(self, domain: SearchDomain) -> None:
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda name=domain.name: self._reindex_if_dirty(name))
        self._domains[domain.name] = _DomainState(domain=domain, reindex_timer=timer)

    def unregister_domain(self, name: str) -> None:
        state = self._domains.pop(name, None)
        if state is not None:
            state.reindex_timer.stop()

    # --- reindexing -----------------------------------------------------------
    def notify_changed(self, domain_name: str) -> None:
        state = self._domains.get(domain_name)
        if state is None:
            return
        state.dirty = True
        state.reindex_timer.start(self._debounce_ms)

    def _reindex_if_dirty(self, domain_name: str) -> None:
        state = self._domains.get(domain_name)
        if state is not None and state.dirty:
            self._trigger_reindex(domain_name)

    def _trigger_reindex(self, domain_name: str) -> None:
        state = self._domains.get(domain_name)
        if state is None or state.job_id is not None or not self._enabled:
            return
        state.dirty = False
        snapshot = list(state.domain.snapshot())
        index_cache_path = f"{self._index_cache_dir}/{domain_name}.pkl"
        job_id = self._jobs_backend.submit_function(
            index_worker.run, (snapshot, self._model_name, self._cache_dir, index_cache_path),
            f"Smart search: reindex {domain_name}")
        state.job_id = job_id
        self._job_to_domain[job_id] = domain_name

    def _on_job_status_changed(self, job_id: str, status: str) -> None:
        if self._pending_enable is not None and self._pending_enable[0] == job_id:
            self._handle_enable_job(status)
            return
        domain_name = self._job_to_domain.get(job_id)
        if domain_name is not None:
            self._handle_reindex_job(domain_name, job_id, status)

    def _handle_reindex_job(self, domain_name: str, job_id: str, status: str) -> None:
        state = self._domains.get(domain_name)
        if state is None:
            del self._job_to_domain[job_id]
            return
        if status == "done":
            result = self._jobs_backend.job_result(job_id)
            state.path_keys = list(result.embeddings.keys())
            state.matrix = np.stack(list(result.embeddings.values())) if result.embeddings else None
            state.bm25 = result.bm25
            self._jobs_backend.forget_job(job_id)
        elif status == "crashed":
            log.error("Smart search reindex failed for domain %r", domain_name)
            self._jobs_backend.forget_job(job_id)
        state.job_id = None
        del self._job_to_domain[job_id]
        if state.dirty:
            self._trigger_reindex(domain_name)

    # --- resource gate ----------------------------------------------------------
    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool, on_ready=None, on_error=None) -> None:
        if not enabled:
            self._enabled = False
            self._query_model = None
            return
        job_id = self._jobs_backend.submit_function(
            model_fetch.download_model, (self._model_name, self._cache_dir),
            "Loading smart-search model...")
        self._pending_enable = (job_id, on_ready, on_error)

    def _handle_enable_job(self, status: str) -> None:
        job_id, on_ready, on_error = self._pending_enable
        self._pending_enable = None
        if status == "done":
            try:
                self._jobs_backend.job_result(job_id)
                self._query_model = model_fetch.load_model(self._model_name, self._cache_dir)
            except Exception as exc:
                self._jobs_backend.forget_job(job_id)
                if on_error is not None:
                    on_error(exc)
                return
            self._jobs_backend.forget_job(job_id)
            self._enabled = True
            for name in list(self._domains):
                self._trigger_reindex(name)
            if on_ready is not None:
                on_ready()
        elif status == "crashed" and on_error is not None:
            try:
                self._jobs_backend.job_result(job_id)
            except Exception as exc:
                on_error(exc)
            finally:
                self._jobs_backend.forget_job(job_id)

    # --- query -------------------------------------------------------------
    def query(self, domain_name: str, text: str) -> dict:
        if not self._enabled or self._query_model is None:
            return {}
        state = self._domains.get(domain_name)
        if state is None or state.matrix is None:
            return {}
        return score_query(text, state.path_keys, state.matrix, state.bm25, self._query_model)
