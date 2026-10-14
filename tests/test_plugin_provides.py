"""plugin.json provides is a summary; the loader warns when it drifts from what the code registered."""
import json

import pytest

from SciQLop.components.plugins.backend.loader.provides import provides_drift, registered_by
from SciQLop.core import extensions
from SciQLop.core.extensions import ExtensionPoint
from tests.test_extensions import Kind, clean_registry  # noqa: F401  (fixture)


@pytest.fixture
def kinds(clean_registry, qapp):  # noqa: F811
    ep = extensions.declare(ExtensionPoint("test.kinds", Kind))
    extensions.declare(ExtensionPoint("vdfp.methods", Kind, owner="vdfp"))
    ep.contribute(Kind("vdfp.slice"), owner="vdfp")
    return ep


def test_registered_by_lists_contributions_and_declared_points(kinds):
    assert registered_by("vdfp") == {"test.kinds": ["vdfp.slice"], "extension_points": ["vdfp.methods"]}


def test_matching_provides_has_no_drift(kinds):
    assert provides_drift("vdfp", {"test.kinds": ["vdfp.slice"], "extension_points": ["vdfp.methods"]}) == []


def test_drift_names_both_directions(kinds):
    assert provides_drift("vdfp", {"test.kinds": ["vdfp.ghost"]}) == [
        "extension_points: registered but not declared in plugin.json: vdfp.methods",
        "test.kinds: declared in plugin.json but not registered: vdfp.ghost",
        "test.kinds: registered but not declared in plugin.json: vdfp.slice",
    ]


def test_assert_helper_fails_on_drift(kinds, tmp_path):
    from SciQLop.components.plugins.testing import assert_provides_matches
    path = tmp_path / "plugin.json"
    path.write_text(json.dumps({"name": "V", "version": "1", "provides": {"test.kinds": ["vdfp.slice"]}}))
    with pytest.raises(AssertionError, match="extension_points: registered but not declared"):
        assert_provides_matches("vdfp", str(path))
