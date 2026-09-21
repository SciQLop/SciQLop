import time
from unittest.mock import patch, MagicMock
import numpy as np
import pytest

from SciQLop.components.smart_search.registry import SmartSearchRegistry
from SciQLop.components.smart_search.domain import NodeSnapshot
from SciQLop.components.smart_search import bm25_index, model_fetch, index_worker


class _FakeDomain:
    def __init__(self, name, nodes):
        self.name = name
        self._nodes = nodes

    def snapshot(self):
        return list(self._nodes)


def _delayed_submit(real_submit):
    def submit(fn, *args, **kwargs):
        def wrapped(*a, **kw):
            time.sleep(0.02)
            return fn(*a, **kw)
        return real_submit(wrapped, *args, **kwargs)
    return submit


@pytest.fixture
def jobs_backend(qtbot):
    # `JobsBackend.submit_function` normally runs `fn` in a spawned
    # subprocess, which re-imports every module fresh -- any
    # `unittest.mock.patch.object` applied in this test process (below) is
    # invisible there, and an already-patched MagicMock can't even be
    # pickled to send to the child (confirmed: raises PicklingError).
    # Swapping in an in-process ThreadPoolExecutor lets mocks of
    # model_fetch.download_model/load_model actually take effect.
    # A real subprocess spawn always takes long enough that
    # Future.add_done_callback never fires before submit_function's caller
    # finishes its own bookkeeping (state.job_id = ..., self._pending_enable
    # = ...); a trivial mocked function on a ThreadPoolExecutor can complete
    # so fast that add_done_callback (per concurrent.futures semantics)
    # fires immediately and *synchronously on the submitting thread* --
    # confirmed by tracing -- which would run SmartSearchRegistry's
    # _on_job_status_changed before that bookkeeping exists, silently
    # dropping the signal. The tiny delay below restores genuine asynchrony
    # so this fixture exercises the same ordering guarantees as the real
    # executor instead of a testing artifact.
    from concurrent.futures import ThreadPoolExecutor
    from SciQLop.components.jobs.backend.jobs_backend import JobsBackend
    backend = JobsBackend(workspace_dir_getter=lambda: "/tmp/unused")
    backend._executor.shutdown(wait=False)
    executor = ThreadPoolExecutor()
    executor.submit = _delayed_submit(executor.submit)
    backend._executor = executor
    yield backend
    backend._executor.shutdown(wait=True, cancel_futures=True)


@pytest.fixture
def registry(qtbot, jobs_backend, tmp_path):
    return SmartSearchRegistry(jobs_backend, model_name="fake-model", cache_dir="/tmp/cache",
                                index_cache_dir=str(tmp_path / "index_cache"), debounce_ms=20)


def test_register_domain_then_notify_changed_submits_no_job_while_disabled(registry, jobs_backend, qtbot):
    domain = _FakeDomain("products", [NodeSnapshot("a", "text a")])
    registry.register_domain(domain)
    registry.notify_changed("products")
    qtbot.wait(50)
    assert jobs_backend.list_jobs() == []


def test_unregister_domain_stops_pending_reindex(registry, jobs_backend, qtbot):
    domain = _FakeDomain("products", [])
    registry.register_domain(domain)
    registry._enabled = True
    registry.notify_changed("products")
    registry.unregister_domain("products")
    qtbot.wait(50)
    assert jobs_backend.list_jobs() == []


def test_enable_success_calls_on_ready_and_flips_enabled(registry, qtbot):
    with patch.object(model_fetch, "download_model", return_value=None), \
         patch.object(model_fetch, "load_model", return_value=MagicMock()) as mock_load:
        ready = []
        registry.set_enabled(True, on_ready=lambda: ready.append(True))
        qtbot.waitUntil(lambda: registry.is_enabled(), timeout=5000)
    assert ready == [True]
    mock_load.assert_called_once_with("fake-model", "/tmp/cache")


def test_enable_failure_calls_on_error_and_stays_disabled(registry, qtbot):
    def _boom_download(model_name, cache_dir):
        raise RuntimeError("no network")

    with patch.object(model_fetch, "download_model", side_effect=_boom_download):
        errors = []
        registry.set_enabled(True, on_error=lambda exc: errors.append(exc))
        qtbot.waitUntil(lambda: len(errors) == 1, timeout=5000)
    assert not registry.is_enabled()
    assert isinstance(errors[0], RuntimeError)


def test_enabling_triggers_reindex_of_already_registered_domains(registry, jobs_backend, qtbot):
    domain = _FakeDomain("products", [NodeSnapshot("a", "hi")])
    registry.register_domain(domain)
    fake_model = MagicMock()
    fake_model.encode.side_effect = lambda texts, **kwargs: np.array([[1.0, 0.0] for _ in texts])
    with patch.object(model_fetch, "download_model", return_value=None), \
         patch.object(model_fetch, "load_model", return_value=fake_model), \
         patch.object(index_worker.model_fetch, "load_model", return_value=fake_model):
        registry.set_enabled(True)
        qtbot.waitUntil(lambda: registry.is_enabled(), timeout=5000)
        qtbot.waitUntil(lambda: registry._domains["products"].matrix is not None, timeout=5000)
    assert registry._domains["products"].path_keys == ["a"]


def test_corpus_change_during_inflight_reindex_triggers_one_more_after(registry, jobs_backend, qtbot):
    domain = _FakeDomain("products", [NodeSnapshot("a", "hi")])
    registry.register_domain(domain)
    fake_model = MagicMock()
    fake_model.encode.side_effect = lambda texts, **kwargs: np.array([[1.0, 0.0] for _ in texts])
    with patch.object(model_fetch, "download_model", return_value=None), \
         patch.object(model_fetch, "load_model", return_value=fake_model), \
         patch.object(index_worker.model_fetch, "load_model", return_value=fake_model):
        registry.set_enabled(True)
        qtbot.waitUntil(lambda: registry.is_enabled(), timeout=5000)
        state = registry._domains["products"]
        qtbot.waitUntil(lambda: state.job_id is not None, timeout=5000)
        domain._nodes = [NodeSnapshot("a", "hi"), NodeSnapshot("b", "new")]
        registry.notify_changed("products")
        qtbot.waitUntil(lambda: state.matrix is not None and len(state.path_keys) == 1, timeout=5000)
        qtbot.waitUntil(lambda: state.matrix is not None and len(state.path_keys) == 2, timeout=5000)


def test_query_returns_empty_dict_when_disabled(registry):
    assert registry.query("products", "hi") == {}


def test_rapid_notify_changed_burst_submits_exactly_one_reindex(registry, jobs_backend, qtbot):
    # Counts submissions via job_added rather than a post-hoc list_jobs()
    # lookup: completed function jobs are now pruned (forget_job), so by the
    # time this test's final wait() elapses the reindex job may already be
    # done and forgotten -- list_jobs() would then undercount.
    domain = _FakeDomain("products", [NodeSnapshot("a", "hi")])
    registry.register_domain(domain)
    registry._enabled = True
    registry._debounce_ms = 300  # a loaded CI runner can stretch a 5ms wait past the fixture's 20ms
    job_ids = []
    jobs_backend.job_added.connect(job_ids.append)
    for _ in range(5):
        registry.notify_changed("products")
        qtbot.wait(5)
    qtbot.waitUntil(lambda: len(job_ids) >= 1, timeout=5000)
    qtbot.wait(100)  # a stray second submission would land right after the first
    assert len(job_ids) == 1


def test_query_falls_back_to_semantic_band_when_bm25_has_no_match(registry, qtbot):
    # "queryterm" shares no vocabulary with "hi"/"bye" at all, so BM25F
    # finds nothing confident and query() falls back entirely to the
    # semantic band (0-50), never the raw 0-100 cosine score.
    domain = _FakeDomain("products", [NodeSnapshot("a", "hi"), NodeSnapshot("b", "bye")])
    registry.register_domain(domain)
    fake_model = MagicMock()

    def _encode(texts, **kwargs):
        return np.array([[1.0, 0.0] if t in ("hi", "queryterm") else [0.0, 1.0] for t in texts])
    fake_model.encode.side_effect = _encode

    with patch.object(model_fetch, "download_model", return_value=None), \
         patch.object(model_fetch, "load_model", return_value=fake_model), \
         patch.object(index_worker.model_fetch, "load_model", return_value=fake_model):
        registry.set_enabled(True)
        qtbot.waitUntil(lambda: registry._domains["products"].matrix is not None, timeout=5000)
        scores = registry.query("products", "queryterm")

    assert scores["a"] == pytest.approx(50.0)
    assert scores["b"] == pytest.approx(0.0)


def test_query_ranks_confident_bm25_match_above_higher_semantic_score(registry, qtbot):
    # Regression test for the reported bug: an entry that lexically matches
    # the query on its identifying path terms ("mms1 fgm") must outrank a
    # decoy entry that only wins on raw semantic similarity -- mirrors the
    # real REACH-vs-MMS1 case this design fixes (see docs/superpowers/specs/
    # 2026-07-20-smart-search-bm25-ranking-design.md). Fails against the
    # pre-BM25F query() (pure cosine), which ranks the decoy first.
    domain = _FakeDomain("products", [
        NodeSnapshot("mms1 fgm", "mms1 fgm magnetic field instrument"),
        NodeSnapshot("decoy", "decoy entry about spacecraft magnetic field"),
    ])
    registry.register_domain(domain)
    fake_model = MagicMock()

    def _encode(texts, **kwargs):
        vectors = []
        for t in texts:
            if "decoy" in t or t == "mms1 fgm magnetic field":
                vectors.append([1.0, 0.0])  # query vector deliberately closest to the decoy
            else:
                vectors.append([0.0, 1.0])  # the true lexical match is semantically "far"
        return np.array(vectors)
    fake_model.encode.side_effect = _encode

    with patch.object(model_fetch, "download_model", return_value=None), \
         patch.object(model_fetch, "load_model", return_value=fake_model), \
         patch.object(index_worker.model_fetch, "load_model", return_value=fake_model):
        registry.set_enabled(True)
        qtbot.waitUntil(lambda: registry._domains["products"].matrix is not None, timeout=5000)
        scores = registry.query("products", "mms1 fgm magnetic field")

    assert scores["mms1 fgm"] > scores["decoy"]


def test_query_confident_band_maps_top_score_to_100_and_half_threshold_to_50(registry, qtbot):
    domain = _FakeDomain("products", [NodeSnapshot("a", "hi"), NodeSnapshot("b", "bye")])
    registry.register_domain(domain)
    fake_model = MagicMock()
    fake_model.encode.side_effect = lambda texts, **kwargs: np.array([[0.0, 0.0] for _ in texts])

    with patch.object(model_fetch, "download_model", return_value=None), \
         patch.object(model_fetch, "load_model", return_value=fake_model), \
         patch.object(index_worker.model_fetch, "load_model", return_value=fake_model):
        registry.set_enabled(True)
        qtbot.waitUntil(lambda: registry._domains["products"].matrix is not None, timeout=5000)

        with patch.object(bm25_index, "score", return_value={"a": 10.0, "b": 5.0}):
            scores = registry.query("products", "anything")

    assert scores["a"] == pytest.approx(100.0)
    assert scores["b"] == pytest.approx(50.0)


def test_query_non_confident_bm25_match_falls_back_to_semantic_band(registry, qtbot):
    domain = _FakeDomain("products", [NodeSnapshot("a", "hi"), NodeSnapshot("b", "bye")])
    registry.register_domain(domain)
    fake_model = MagicMock()

    def _encode(texts, **kwargs):
        return np.array([[1.0, 0.0] if t in ("hi", "anything") else [0.0, 1.0] for t in texts])
    fake_model.encode.side_effect = _encode

    with patch.object(model_fetch, "download_model", return_value=None), \
         patch.object(model_fetch, "load_model", return_value=fake_model), \
         patch.object(index_worker.model_fetch, "load_model", return_value=fake_model):
        registry.set_enabled(True)
        qtbot.waitUntil(lambda: registry._domains["products"].matrix is not None, timeout=5000)

        # "b" matched some BM25 term but scored well below the confident
        # threshold (10% of max, not >= 50%) -- must fall back to its
        # semantic score, not get a BM25-derived score.
        with patch.object(bm25_index, "score", return_value={"a": 10.0, "b": 1.0}):
            scores = registry.query("products", "anything")

    assert scores["a"] == pytest.approx(100.0)
    assert scores["b"] == pytest.approx(0.0)


def test_completed_enable_and_reindex_jobs_are_forgotten(registry, jobs_backend, qtbot):
    domain = _FakeDomain("products", [NodeSnapshot("a", "hi")])
    registry.register_domain(domain)
    fake_model = MagicMock()
    fake_model.encode.side_effect = lambda texts, **kwargs: np.array([[1.0, 0.0] for _ in texts])
    job_ids = []
    jobs_backend.job_added.connect(job_ids.append)

    with patch.object(model_fetch, "download_model", return_value=None), \
         patch.object(model_fetch, "load_model", return_value=fake_model), \
         patch.object(index_worker.model_fetch, "load_model", return_value=fake_model):
        registry.set_enabled(True)
        qtbot.waitUntil(lambda: registry.is_enabled(), timeout=5000)
        qtbot.waitUntil(lambda: registry._domains["products"].matrix is not None, timeout=5000)

    assert len(job_ids) == 2  # the enable job, then the auto-triggered reindex job
    assert all(job_id not in jobs_backend._futures for job_id in job_ids)


def test_trigger_reindex_passes_index_cache_path_to_submit_function(qtbot, tmp_path):
    mock_backend = MagicMock()
    registry = SmartSearchRegistry(mock_backend, model_name="fake-model", cache_dir="/tmp/cache",
                                    index_cache_dir=str(tmp_path / "index_cache"), debounce_ms=20)
    registry._enabled = True
    domain = _FakeDomain("products", [NodeSnapshot("a", "hi")])
    registry.register_domain(domain)
    registry._trigger_reindex("products")

    mock_backend.submit_function.assert_called_once()
    args, kwargs = mock_backend.submit_function.call_args
    fn, call_args, name = args
    assert fn is index_worker.run
    snapshot, model_name, cache_dir, index_cache_path = call_args
    assert index_cache_path == str(tmp_path / "index_cache" / "products.pkl")
    assert model_name == "fake-model"
    assert cache_dir == "/tmp/cache"


from SciQLop.components.smart_search.registry import score_query


def test_score_query_is_callable_without_a_live_registry():
    # score_query must work from raw ingredients alone -- no SmartSearchRegistry,
    # no QObject, no jobs backend. This is what tests/smart_search_benchmark/
    # relies on to score the real corpus outside the app.
    path_keys = ["a", "b"]
    matrix = np.array([[1.0, 0.0], [0.0, 1.0]])
    bm25 = bm25_index.build([NodeSnapshot("a", "a hi"), NodeSnapshot("b", "b bye")])
    fake_model = MagicMock()
    fake_model.encode.side_effect = lambda texts, **kwargs: np.array([[1.0, 0.0] for _ in texts])

    scores = score_query("hi", path_keys, matrix, bm25, fake_model)

    assert scores["a"] == pytest.approx(100.0)
    assert scores["b"] == pytest.approx(0.0)
