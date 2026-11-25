"""The bundled plugins' python_dependencies come with SciQLop itself: sciqlop[all] must list each one
with the same versions. The launcher no longer reads them (it may be an older SciQLop: it wrote
cocat-rs 0.11 into a workspace whose SciQLop needed 0.12)."""
import json
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = sorted((ROOT / "SciQLop" / "plugins").glob("*/plugin.json"))


def _runtime_specifiers() -> dict[str, str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    requirements = (Requirement(line) for line in [*project["dependencies"], *project["optional-dependencies"]["all"]])
    return {canonicalize_name(r.name): str(r.specifier) for r in requirements}


@pytest.mark.parametrize("plugin_json", PLUGINS, ids=lambda p: p.parent.name)
def test_sciqlop_all_brings_each_bundled_plugin_dependency_at_its_versions(plugin_json):
    runtime = _runtime_specifiers()
    pins = [Requirement(line) for line in json.loads(plugin_json.read_text()).get("python_dependencies", [])]
    wrong = {r.name: (str(r.specifier), runtime.get(canonicalize_name(r.name), "missing from [all]")) for r in pins
             if runtime.get(canonicalize_name(r.name)) != str(r.specifier)}
    assert wrong == {}
