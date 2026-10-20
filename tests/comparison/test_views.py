import pytest

from SciQLop.components.comparison.backend.model import Comparison, Variant
from SciQLop.components.comparison.backend.views import (
    COMPARISON_VIEWS, ComparisonView, available_views, options_for)
from SciQLop.core.extensions import owned_by


@pytest.fixture
def views():
    yield
    COMPARISON_VIEWS.remove_owner("cmp_test")


def _view(id, applies=lambda c, s: None, **kw):
    return ComparisonView(id=id, label=id, applies=applies, build=lambda *a: None, **kw)


def _comparison(**kw):
    return Comparison(base={}, dimension="time", variants=[Variant(label="v")], **kw)


def test_available_views_reports_reason_sorted_by_order_then_id(views):
    with owned_by("cmp_test"):
        COMPARISON_VIEWS.contribute(_view("b", order=1))
        COMPARISON_VIEWS.contribute(_view("z", lambda c, s: "needs two sides", order=0))
        COMPARISON_VIEWS.contribute(_view("a", order=1))
    result = [(v.id, why) for v, why in available_views(_comparison(), [])
              if v.id in ("a", "b", "z")]
    assert result == [("z", "needs two sides"), ("a", None), ("b", None)]


def test_options_for_merges_defaults_and_saved_options():
    v = _view("x", default_options={"a": 1, "b": 2})
    c = _comparison(view_options={"x": {"b": 3}, "other": {"a": 9}})
    assert options_for(c, v) == {"a": 1, "b": 3}
