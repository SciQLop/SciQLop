"""Speasy trajectory providers (SSC, CDPP 3DView) expose their per-request
options as knobs, routed to top-level ``spz.get_data`` kwargs."""
import pytest

from SciQLop.core.knobs import ChoiceKnob, IntKnob
from SciQLop.core.enums import ParameterType
from SciQLop.plugins.speasy_provider import speasy_provider as sp


class _Index:
    def __init__(self, provider, uid, **attrs):
        self._provider, self._uid = provider, uid
        self.__dict__.update(attrs)

    def spz_provider(self): return self._provider

    def spz_uid(self): return self._uid

    def spz_name(self): return self._uid


class _Node:
    def __init__(self, speasy_id):
        self._id = speasy_id

    def metadata(self, key=None):
        return self._id if key == "speasy_id" else {}


def _plugin(index):
    p = sp.SpeasyPlugin.__new__(sp.SpeasyPlugin)
    p._name = "Speasy"
    p._resolve_index = lambda product: index
    return p


def test_3dview_bodies_are_xyz_vectors():
    index = _Index("cdpp3dview", "ACE", description="ACE trajectories")
    assert sp.get_components(index) == ["x", "y", "z"]
    assert sp.data_serie_type(index) == ParameterType.Vector


def test_3dview_knobs_are_frame_choice_and_sampling(monkeypatch):
    monkeypatch.setattr(sp, "_3dview_frames", lambda: ["J2000", "GSE", "GSM"])
    knobs = _plugin(_Index("cdpp3dview", "ACE")).get_knobs(_Node("cdpp3dview/ACE"))
    by_name = {k.name: k for k in knobs}
    assert set(by_name) == {"coordinate_frame", "sampling"}
    frame = by_name["coordinate_frame"]
    assert isinstance(frame, ChoiceKnob)
    assert frame.default == "J2000"
    assert [c[1] for c in frame.choices] == ["J2000", "GSE", "GSM"]
    sampling = by_name["sampling"]
    assert isinstance(sampling, IntKnob)
    assert sampling.default == 600 and sampling.min == 1


def test_3dview_frames_fall_back_when_the_service_is_unreachable(monkeypatch):
    monkeypatch.setattr(sp.spz, "cdpp3dview", None)
    frames = sp._3dview_frames()
    assert "J2000" in frames and "GSE" in frames


def test_ssc_knob_unchanged():
    knobs = _plugin(_Index("ssc", "ace")).get_knobs(_Node("ssc/ace"))
    assert [k.name for k in knobs] == ["coordinate_system"]


@pytest.mark.parametrize("speasy_id, knobs, expected", [
    ("cdpp3dview/ACE", {"coordinate_frame": "GSE", "sampling": 60},
     {"coordinate_frame": "GSE", "sampling": "60"}),
    ("ssc/ace", {"coordinate_system": "gsm"}, {"coordinate_system": "gsm"}),
    ("amda/imf", {"a": 1}, {"product_inputs": {"a": 1}}),
    ("amda/imf", {}, {}),
])
def test_knobs_route_to_speasy_kwargs(speasy_id, knobs, expected):
    assert sp.speasy_kwargs(speasy_id, knobs) == expected


def test_get_data_passes_3dview_options_as_top_level_kwargs(monkeypatch):
    calls = []

    def fake_get_data(speasy_id, start, stop, **kwargs):
        calls.append((speasy_id, kwargs))
        return None

    monkeypatch.setattr(sp.spz, "get_data", fake_get_data)
    plugin = _plugin(_Index("cdpp3dview", "ACE"))
    plugin.get_data(_Node("cdpp3dview/ACE"), 0.0, 3600.0,
                    knobs={"coordinate_frame": "GSM", "sampling": 300})
    assert calls == [("cdpp3dview/ACE", {"coordinate_frame": "GSM", "sampling": "300"})]


def test_notebook_snippet_renders_provider_kwargs():
    from SciQLop.core.graph_context import GraphContext
    ctx = GraphContext(kind="speasy", graph_id="g", panel_name="P", plot_index=0,
                       graph_type="Line", speasy_id="cdpp3dview/ACE", provider_name="Speasy",
                       knobs={"coordinate_frame": "GSE", "sampling": 60})
    snippet = _plugin(_Index("cdpp3dview", "ACE")).python_snippets(ctx)["Notebook (matplotlib)"]
    assert 'spz.get_data("cdpp3dview/ACE", start, stop, coordinate_frame=\'GSE\', sampling=\'60\')' in snippet
