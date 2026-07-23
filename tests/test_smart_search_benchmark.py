"""Smart-search ranking benchmark: each case asserts a real query surfaces
its expected result within top-N against the actual product corpus. Only
runs where that corpus exists (a dev machine that's used smart search for
real) -- never in CI. See docs/superpowers/specs/
2026-07-22-smart-search-benchmark-corpus-design.md."""
import pytest

from tests.smart_search_benchmark.cases import CASES, DEFAULT_TOP_N
from tests.smart_search_benchmark.harness import CACHE_PATH, evaluate, load_real_corpus

pytestmark = pytest.mark.skipif(
    not CACHE_PATH.exists(),
    reason="needs the real product corpus cache; not available in CI")

# Known-open ranking gaps as of 2026-07-22 (docs/plans/
# 2026-07-22-handover-smart-search-ranking-and-perf.md). Marked xfail(strict=True)
# so the suite stays green today but hard-fails -- forcing this set to be
# updated -- the moment a real fix makes one of them pass.
_KNOWN_FAILING = {
    "MMS spacecraft 1 magnetic field",
    "MMS1 spacecraft magnetic field",
    "MMS1 trajectory",
    "MMS1 electrons",
    "MMS1 ion",       # FPI DIS missing -- see cases.py's comment for this case
    "MMS1 ion flux",  # same gap
}


def _case_param(case):
    marks = [pytest.mark.xfail(strict=True, reason="known ranking gap, see docs/plans/2026-07-22-handover-smart-search-ranking-and-perf.md")] \
        if case.query in _KNOWN_FAILING else []
    return pytest.param(case, id=case.query, marks=marks)


@pytest.fixture(scope="module")
def real_corpus():
    return load_real_corpus()


@pytest.mark.parametrize("case", [_case_param(c) for c in CASES])
def test_benchmark_case(case, real_corpus):
    result = evaluate(case, real_corpus)
    assert result.passed, (
        f"best match at rank {result.best_rank} "
        f"(needed top {case.top_n if case.top_n is not None else DEFAULT_TOP_N})")
