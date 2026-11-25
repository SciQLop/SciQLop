"""A bundled plugin's python_dependencies are installed at startup: one that also appears in
pyproject.toml must ask for the same versions, or it moves the package (cocat-rs 0.12 was downgraded
to the plugin's 0.11 on a Mac, and the CoCat search box failed)."""
import json
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = sorted((ROOT / "SciQLop" / "plugins").glob("*/plugin.json"))


def _pyproject_specifiers() -> dict[str, str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    lines = [*project["dependencies"], *(d for group in project["optional-dependencies"].values() for d in group)]
    requirements = (Requirement(line) for line in lines)
    return {canonicalize_name(r.name): str(r.specifier) for r in requirements if r.specifier}


@pytest.mark.parametrize("plugin_json", PLUGINS, ids=lambda p: p.parent.name)
def test_a_bundled_plugin_pins_what_pyproject_pins(plugin_json):
    wanted = _pyproject_specifiers()
    pins = (Requirement(line) for line in json.loads(plugin_json.read_text()).get("python_dependencies", []))
    disagreeing = {r.name: (str(r.specifier), wanted[canonicalize_name(r.name)]) for r in pins
                   if canonicalize_name(r.name) in wanted and str(r.specifier) != wanted[canonicalize_name(r.name)]}
    assert disagreeing == {}
