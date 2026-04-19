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
