"""Wires SciQLopPlots' ProductsView (the sidebar Products browser) to
components/smart_search/ -- the same BM25+semantic ranking already used by
the empty-panel search overlay (plotting/ui/product_search_overlay.py), now
reachable via ProductsView's free_text_query_changed signal and its
external-score passthrough (SciQLopPlots >= 0.31.1). See docs/superpowers/
specs/2026-07-21-productsview-score-passthrough-design.md."""
import shiboken6
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from SciQLopPlots import ScoreMergeStrategy

from SciQLop.components import smart_search
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

_SIGNAL_NAME = "smart_search"


class _SidebarSmartSearchController(QObject):
    _scores_ready = Signal(int, dict)

    def __init__(self, view):
        super().__init__(view)
        self._view = view
        self._latest_request_id = 0
        self._busy = False
        self._pending_text = None
        self._scores_ready.connect(self._apply_scores)
        view.free_text_query_changed.connect(self._on_query_changed)

    def _on_query_changed(self, tokens: list) -> None:
        if not tokens:
            self._pending_text = None
            self._latest_request_id += 1  # invalidate any in-flight/pending query
            self._view.set_score_merge_strategy(ScoreMergeStrategy.Max)
            self._view.set_signal_enabled(_SIGNAL_NAME, False)
            return
        if smart_search.is_enabled():
            self._request_query(" ".join(tokens))

    def _request_query(self, text: str) -> None:
        # Single-flight, like SmartSearchRegistry's own reindex-job dispatch
        # (_trigger_reindex's job_id-busy-gate + dirty-flag-coalesce): at
        # most one query actually runs at a time. A request that arrives
        # while busy just replaces any earlier still-pending one instead of
        # spawning a second concurrent task -- real score_query() calls take
        # ~150-210ms against the real corpus, comfortably longer than the UI
        # debounce, so without this an edit spaced just past the debounce
        # but inside that window used to race a still-running older query.
        if self._busy:
            self._pending_text = text
            return
        self._dispatch_query(text)

    def _dispatch_query(self, text: str) -> None:
        self._busy = True
        self._latest_request_id += 1
        request_id = self._latest_request_id
        view = self._view
        emit_ready = self._scores_ready.emit

        class _QueryTask(QRunnable):
            def run(self):
                scores = smart_search.query("products", text)
                if shiboken6.isValid(view):
                    emit_ready(request_id, scores)

        QThreadPool.globalInstance().start(_QueryTask())

    def _apply_scores(self, request_id: int, scores: dict) -> None:
        self._busy = False
        if self._pending_text is not None:
            pending, self._pending_text = self._pending_text, None
            self._dispatch_query(pending)
            return
        if request_id < self._latest_request_id:
            return  # superseded (e.g. query cleared) while in flight
        # Override, not the default Max: blending smart_search with the
        # native fuzzy scorer lets a leaf that's merely the corpus's best
        # NATIVE match (e.g. a coincidental literal-phrase match) tie at the
        # same normalized ceiling as smart_search's genuinely best match --
        # and since the underlying sort isn't stable, the relevant match can
        # end up buried behind an unrelated one. Once smart_search has an
        # opinion, it should be the sole authority.
        self._view.set_signal_enabled(_SIGNAL_NAME, True)
        self._view.set_score_merge_strategy(ScoreMergeStrategy.Override)
        self._view.set_override_signal(_SIGNAL_NAME)
        self._view.set_external_scores(_SIGNAL_NAME, scores)


def setup_sidebar_smart_search(view) -> None:
    """Attach smart-search wiring to the sidebar Products tree. The
    controller is parented to `view` so it dies with it."""
    _SidebarSmartSearchController(view)
