import pytest

from SciQLop.user_api.knobs import ChoiceKnob
from tests.fixtures import *  # noqa: F401,F403  — qapp, sciqlop_resources


@pytest.fixture
def fake_argument_index_classes(monkeypatch, qapp, sciqlop_resources):
    """Stub SpeasyIndex hierarchy minimal enough to exercise the walk."""
    class ArgumentIndex:
        def __init__(self, name, type_, choices=None, default=None):
            self.name = name
            self.type = type_
            self.choices = choices or []
            self.default = default

    class ArgumentListIndex:
        def __init__(self, args):
            self._args = list(args)

        def __iter__(self):
            return iter(self._args)

    class TemplatedParameterIndex:
        def __init__(self, args):
            self.spz_arguments_node = ArgumentListIndex(args)

        def __iter__(self):
            yield self.spz_arguments_node

    monkeypatch.setattr("SciQLop.plugins.speasy_provider.speasy_provider.ArgumentIndex",
                        ArgumentIndex, raising=False)
    monkeypatch.setattr("SciQLop.plugins.speasy_provider.speasy_provider.ArgumentListIndex",
                        ArgumentListIndex, raising=False)
    return ArgumentIndex, ArgumentListIndex, TemplatedParameterIndex


def test_get_knobs_walks_argument_list(fake_argument_index_classes, monkeypatch):
    from SciQLop.plugins.speasy_provider import speasy_provider as mod

    ArgumentIndex, ArgumentListIndex, TemplatedParameterIndex = fake_argument_index_classes

    fake_index = TemplatedParameterIndex([
        ArgumentIndex("lookdir", "list",
                      choices=[("Sun", "sun"), ("Tail", "tail")],
                      default="sun"),
        ArgumentIndex("species", "generated-list",
                      choices=[("H+", "H"), ("He+", "He")],
                      default="H"),
    ])

    plugin = mod.SpeasyPlugin.__new__(mod.SpeasyPlugin)  # bypass __init__
    monkeypatch.setattr(plugin, "_resolve_index", lambda product: fake_index, raising=False)

    specs = plugin.get_knobs("amda/jedi_i90_flux")
    by_name = {s.name: s for s in specs}
    assert isinstance(by_name["lookdir"], ChoiceKnob)
    assert by_name["lookdir"].choices == (("Sun", "sun"), ("Tail", "tail"))
    assert by_name["lookdir"].default == "sun"
    assert by_name["species"].choices == (("H+", "H"), ("He+", "He"))


def test_get_knobs_returns_empty_for_non_templated(monkeypatch, qapp, sciqlop_resources):
    from SciQLop.plugins.speasy_provider import speasy_provider as mod
    plugin = mod.SpeasyPlugin.__new__(mod.SpeasyPlugin)
    monkeypatch.setattr(plugin, "_resolve_index", lambda product: object(), raising=False)
    assert plugin.get_knobs("amda/regular_param") == []


def test_knob_name_matches_speasy_template_key(qapp, sciqlop_resources):
    """speasy substitutes ##arg.key## in templates; knob.name must equal arg.key
    so that the product_inputs dict reaches the right placeholder."""
    from SciQLop.plugins.speasy_provider.speasy_provider import _argument_to_knob

    class RealShapeArg:
        key = "side"
        name = "Side"
        type = "list"
        default = "0"
        choices = [("Side 0", "0"), ("Side 1", "1")]

    knob = _argument_to_knob(RealShapeArg())
    assert knob.name == "side", "knob.name must be arg.key for product_inputs dispatch"
    assert knob.label == "Side", "knob.label carries the human-readable name"
    assert knob.default == "0"


def test_get_knobs_synthesizes_coordinate_system_for_ssc(qapp, sciqlop_resources, monkeypatch):
    """SSC products expose a coordinate_system ChoiceKnob even though speasy
    doesn't declare it as an ArgumentListIndex."""
    from SciQLop.plugins.speasy_provider import speasy_provider as sp_mod

    class FakeSSCIndex:
        def spz_provider(self): return "ssc"

    plugin = sp_mod.SpeasyPlugin.__new__(sp_mod.SpeasyPlugin)
    monkeypatch.setattr(plugin, "_resolve_index",
                        lambda product: FakeSSCIndex(), raising=False)

    knobs = plugin.get_knobs("ssc/wind")
    names = {k.name: k for k in knobs}
    assert "coordinate_system" in names
    spec = names["coordinate_system"]
    assert isinstance(spec, ChoiceKnob)
    assert spec.default == "gse"
    values = {v for _label, v in spec.choices}
    assert {"gse", "gsm", "sm"} <= values


def test_get_knobs_does_not_synthesize_for_non_ssc(qapp, sciqlop_resources, monkeypatch):
    from SciQLop.plugins.speasy_provider import speasy_provider as sp_mod

    class FakeAmdaIndex:
        def spz_provider(self): return "amda"

    plugin = sp_mod.SpeasyPlugin.__new__(sp_mod.SpeasyPlugin)
    monkeypatch.setattr(plugin, "_resolve_index",
                        lambda product: FakeAmdaIndex(), raising=False)
    monkeypatch.setattr(sp_mod, "_find_argument_list", lambda idx: None)

    knobs = plugin.get_knobs("amda/something")
    assert "coordinate_system" not in {k.name for k in knobs}


def test_get_data_routes_coordinate_system_top_level(monkeypatch, qapp, sciqlop_resources):
    """coordinate_system from knobs must travel as a top-level spz.get_data
    kwarg, NOT inside product_inputs (which is reserved for AMDA template
    parameters)."""
    from SciQLop.plugins.speasy_provider import speasy_provider as sp_mod

    captured = {}

    def fake_get_data(speasy_id, start, stop, **kwargs):
        captured["speasy_id"] = speasy_id
        captured["kwargs"] = kwargs
        return None

    monkeypatch.setattr(sp_mod.spz, "get_data", fake_get_data)

    plugin = sp_mod.SpeasyPlugin.__new__(sp_mod.SpeasyPlugin)
    plugin.get_data("ssc/wind", 0.0, 1.0, knobs={"coordinate_system": "gsm"})

    assert captured["kwargs"].get("coordinate_system") == "gsm"
    assert "product_inputs" not in captured["kwargs"]


def test_get_data_does_not_pass_coordinate_system_for_non_ssc(monkeypatch, qapp, sciqlop_resources):
    from SciQLop.plugins.speasy_provider import speasy_provider as sp_mod

    captured = {}
    monkeypatch.setattr(sp_mod.spz, "get_data",
                        lambda s, a, b, **kw: captured.setdefault("kw", kw) or None)

    plugin = sp_mod.SpeasyPlugin.__new__(sp_mod.SpeasyPlugin)
    # AMDA product, but knobs accidentally include coordinate_system —
    # should NOT be forwarded.
    plugin.get_data("amda/something", 0.0, 1.0,
                    knobs={"coordinate_system": "gsm", "alt": "high"})

    assert "coordinate_system" not in captured["kw"]
    assert captured["kw"].get("product_inputs") == {"alt": "high"}
