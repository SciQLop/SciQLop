"""Tests for SciQLop.components.workspaces.backend.workspace_project — pyproject.toml generator."""

import importlib.metadata
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.components.workspaces.backend.workspace_project import (
    _base_constraints,
    _canonical,
    _deduplicate_requirements,
    _extract_package_name,
    _normalize_url_requirement,
    _slugify,
    generate_pyproject_toml,
    host_provided_overrides,
)


class TestSlugify:
    def test_simple(self):
        assert _slugify("My Study") == "my-study"

    def test_already_slug(self):
        assert _slugify("my-study") == "my-study"

    def test_multiple_spaces_and_special_chars(self):
        assert _slugify("Hello  World! #2") == "hello--world---2"

    def test_leading_trailing_hyphens_stripped(self):
        assert _slugify("  Hello  ") == "hello"

    def test_empty_string(self):
        assert _slugify("") == ""

    def test_underscores_become_hyphens(self):
        assert _slugify("my_study") == "my-study"

    def test_non_ascii_name_slugifies_to_empty(self):
        """Documents the raw building block M5 works around: `_slugify`
        only keeps a-z0-9-, so a CJK/Cyrillic-only name strips to nothing."""
        assert _slugify("日本語") == ""


class TestProjectNameNonAsciiFallback:
    """M5: a non-ASCII workspace name must still produce a valid PEP 508
    project name. Before the fix, `_slugify("日本語")` == "" made the
    generated name "sciqlop-workspace-" — invalid, and uv rejected it
    outright, so the workspace could never start."""

    _NAME_RE = re.compile(r'name = "sciqlop-workspace-([^"]+)"')

    def _generated_slug(self, name: str) -> str:
        manifest = WorkspaceManifest(name=name)
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "pyproject.toml"
            generate_pyproject_toml(manifest, [], output)
            content = output.read_text()
        match = self._NAME_RE.search(content)
        assert match, content
        return match.group(1)

    def test_cjk_name_produces_valid_project_name(self):
        slug = self._generated_slug("日本語")
        assert re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", slug)

    def test_cyrillic_name_produces_valid_project_name(self):
        slug = self._generated_slug("Пример")
        assert re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", slug)


class TestDeduplicateRequirements:
    def test_no_duplicates(self):
        reqs = ["speasy>=1.6", "matplotlib>=3.8"]
        result = _deduplicate_requirements(reqs)
        assert result == ["speasy>=1.6", "matplotlib>=3.8"]

    def test_duplicate_keeps_last(self):
        reqs = ["speasy>=1.0", "matplotlib>=3.8", "speasy>=1.6"]
        result = _deduplicate_requirements(reqs)
        assert result == ["matplotlib>=3.8", "speasy>=1.6"]

    def test_empty(self):
        assert _deduplicate_requirements([]) == []

    def test_case_insensitive_package_names(self):
        reqs = ["Speasy>=1.0", "speasy>=1.6"]
        result = _deduplicate_requirements(reqs)
        assert result == ["speasy>=1.6"]

    def test_extras_ignored_for_dedup(self):
        # "speasy[all]>=1.0" and "speasy>=1.6" share the same base package
        reqs = ["speasy[all]>=1.0", "speasy>=1.6"]
        result = _deduplicate_requirements(reqs)
        assert result == ["speasy>=1.6"]


class TestNormalizeUrlRequirement:
    def test_regular_requirement_unchanged(self):
        assert _normalize_url_requirement("speasy>=1.6") == "speasy>=1.6"

    def test_pep508_requirement_unchanged(self):
        req = "spok @ https://github.com/LaboratoryOfPlasmaPhysics/spok/archive/refs/heads/main.zip"
        assert _normalize_url_requirement(req) == req

    def test_github_archive_url(self):
        url = "https://github.com/LaboratoryOfPlasmaPhysics/spok/archive/refs/heads/main.zip"
        assert _normalize_url_requirement(url) == f"spok @ {url}"

    def test_git_plus_https_url(self):
        url = "git+https://github.com/LaboratoryOfPlasmaPhysics/space"
        assert _normalize_url_requirement(url) == f"space @ {url}"

    def test_git_url_with_dot_git_suffix(self):
        url = "git+https://github.com/LaboratoryOfPlasmaPhysics/spok.git"
        assert _normalize_url_requirement(url) == f"spok @ {url}"

    def test_wheel_url_uses_filename_not_repo(self):
        url = "https://github.com/SciQLop/sciqlop-plugins/releases/download/cdf_workbench/v0.2.0/sciqlop_cdf_workbench-0.2.0-py3-none-any.whl"
        assert _normalize_url_requirement(url) == f"sciqlop-cdf-workbench @ {url}"

    def test_non_github_url_returned_unchanged(self):
        url = "https://example.com/some-package.tar.gz"
        assert _normalize_url_requirement(url) == url

    def test_whitespace_stripped(self):
        url = "  https://github.com/org/pkg/archive/refs/heads/main.zip  "
        assert _normalize_url_requirement(url) == f"pkg @ {url.strip()}"


class TestGeneratePyprojectToml:
    def test_basic_generation(self):
        manifest = WorkspaceManifest(
            name="My Study",
            requires=["speasy>=1.6.1"],
        )
        plugin_deps = ["matplotlib>=3.8"]

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "pyproject.toml"
            generate_pyproject_toml(manifest, plugin_deps, output)

            content = output.read_text()
            assert "[project]" in content
            assert 'name = "sciqlop-workspace-my-study"' in content
            assert 'version = "0.0.0"' in content
            import sys
            expected_py = f">={sys.version_info.major}.{sys.version_info.minor}"
            assert f'requires-python = "{expected_py}"' in content
            assert '"speasy>=1.6.1"' in content
            assert '"matplotlib>=3.8"' in content
            # Should contain the auto-generated comment
            assert "Auto-generated by SciQLop" in content

    def test_empty_user_deps(self):
        manifest = WorkspaceManifest(name="Empty", requires=[])
        plugin_deps = []

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "pyproject.toml"
            generate_pyproject_toml(manifest, plugin_deps, output)

            content = output.read_text()
            assert "[project]" in content
            assert 'name = "sciqlop-workspace-empty"' in content
            # jupyqt is always injected as an implicit dependency; the real
            # jupyterlab must NOT be — it duplicates jupyterlab-js's data
            # files and uninstalling either one guts the other (see the
            # implicit_deps comment in workspace_project.py).
            assert '"jupyqt"' in content
            assert '"jupyterlab"' not in content

    def test_deduplication_across_manifest_and_plugins(self):
        manifest = WorkspaceManifest(
            name="Dedup Test",
            requires=["speasy>=1.0", "numpy>=1.24"],
        )
        # Plugin provides a newer speasy requirement
        plugin_deps = ["speasy>=1.6.1"]

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "pyproject.toml"
            generate_pyproject_toml(manifest, plugin_deps, output)

            content = output.read_text()
            # In the dependencies block, speasy should appear once (last wins)
            assert '"speasy>=1.6.1"' in content
            assert '"speasy>=1.0"' not in content
            assert '"numpy>=1.24"' in content

    def test_output_is_valid_toml(self):
        """If tomllib is available (3.11+), verify the output parses."""
        try:
            import tomllib
        except ImportError:
            pytest.skip("tomllib not available")

        manifest = WorkspaceManifest(
            name="TOML Check",
            requires=["speasy>=1.6.1"],
        )
        plugin_deps = ["matplotlib>=3.8"]

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "pyproject.toml"
            generate_pyproject_toml(manifest, plugin_deps, output)

            with open(output, "rb") as f:
                data = tomllib.load(f)

            assert data["project"]["name"] == "sciqlop-workspace-toml-check"
            assert data["project"]["version"] == "0.0.0"
            assert "speasy>=1.6.1" in data["project"]["dependencies"]
            assert "matplotlib>=3.8" in data["project"]["dependencies"]

    def test_url_dependencies_normalized_to_pep508(self):
        manifest = WorkspaceManifest(
            name="URL Test",
            requires=[
                "speasy>=1.6",
                "https://github.com/LaboratoryOfPlasmaPhysics/spok/archive/refs/heads/main.zip",
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "pyproject.toml"
            generate_pyproject_toml(manifest, [], output)

            content = output.read_text()
            assert '"speasy>=1.6"' in content
            assert '"spok @ https://github.com/LaboratoryOfPlasmaPhysics/spok/archive/refs/heads/main.zip"' in content

    def test_workspace_installs_its_own_sciqlop(self):
        """The workspace venv is self-contained, so SciQLop is a dependency of
        it rather than something inherited from the launcher's environment.
        [all] matters: the bare package is only the launcher."""
        manifest = WorkspaceManifest(name="Owned", requires=["numpy>=1.24"])

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "pyproject.toml"
            generate_pyproject_toml(manifest, [], output)

            import tomllib
            with open(output, "rb") as f:
                data = tomllib.load(f)
            deps = data["project"]["dependencies"]
            assert any(d.startswith("sciqlop[all]") for d in deps), deps
            # Nothing to pin against or hide any more.
            uv_config = data.get("tool", {}).get("uv", {})
            assert "constraint-dependencies" not in uv_config
            assert "override-dependencies" not in uv_config

    def test_sciqlop_pin_follows_the_manifest(self):
        manifest = WorkspaceManifest(name="Pinned", sciqlop_version="0.13.0")

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "pyproject.toml"
            generate_pyproject_toml(manifest, [], output)

            import tomllib
            with open(output, "rb") as f:
                data = tomllib.load(f)
            assert "sciqlop[all]==0.13.0" in data["project"]["dependencies"]

    def test_dev_versions_install_from_git_main(self):
        """A .dev version exists on no index, so pinning it or leaving it
        fully unpinned (which would resolve the latest PyPI release) both
        defeat testing a pre-release build: install straight from the
        project's main branch instead, so a dev launcher exercises the
        workspace/install flow against the code it was actually built from."""
        from SciQLop.components.workspaces.backend.workspace_project import (
            sciqlop_requirement,
        )
        assert sciqlop_requirement("0.13.0.dev0") == (
            "sciqlop[all] @ git+https://github.com/SciQLop/SciQLop.git@main"
        )
        assert sciqlop_requirement("0.13.0") == "sciqlop[all]==0.13.0"

    def test_accepts_path_as_string(self):
        manifest = WorkspaceManifest(name="StrPath")

        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "pyproject.toml")
            generate_pyproject_toml(manifest, [], output)
            assert os.path.exists(output)

    def test_plugin_requiring_sciqlop_is_no_longer_overridden(self):
        """A plugin wheel that declares Requires-Dist: SciQLop used to be
        neutralised with an always-false marker because the host owned SciQLop.
        The workspace installs it now, so the requirement must simply resolve."""
        import tomllib

        manifest = WorkspaceManifest(name="Transitive")
        plugin_deps = [
            "https://github.com/SciQLop/sciqlop-plugins/releases/download/"
            "sciqlop_claude/v0.1.0/sciqlop_claude-0.1.0-py3-none-any.whl"
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "pyproject.toml"
            generate_pyproject_toml(manifest, plugin_deps, output)

            with open(output, "rb") as f:
                data = tomllib.load(f)
            assert "override-dependencies" not in data.get("tool", {}).get("uv", {})

    def test_strip_host_provided_drops_sciqlop_keeps_rest(self):
        """The shared filter drops SciQLop (any specifier form) and keeps
        everything else, so both the uv-sync and dev pip-install paths agree."""
        from SciQLop.components.workspaces.backend.workspace_project import (
            strip_host_provided,
        )
        kept = strip_host_provided([
            "SciQLop>=0.13.0,<0.14.0", "matplotlib>=3.8",
            "sciqlop>=0.12.0", "numpy", "SciQLop",
        ])
        assert kept == ["matplotlib>=3.8", "numpy"]

    def test_host_provided_overrides_cover_every_host_package(self):
        from SciQLop.components.workspaces.backend.workspace_project import (
            _HOST_PROVIDED_PACKAGES,
        )
        overrides = host_provided_overrides()
        assert len(overrides) == len(_HOST_PROVIDED_PACKAGES)
        for pkg in _HOST_PROVIDED_PACKAGES:
            assert any(o.startswith(f"{pkg} ;") for o in overrides)
        # Always-false marker, single-quoted so it stays valid inside a
        # double-quoted TOML / requirements entry.
        assert all("python_version < '0'" in o for o in overrides)

    def test_environments_restricted_to_supported_platforms(self):
        try:
            import tomllib
        except ImportError:
            pytest.skip("tomllib not available")

        manifest = WorkspaceManifest(name="Envs")

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "pyproject.toml"
            generate_pyproject_toml(manifest, [], output)

            with open(output, "rb") as f:
                data = tomllib.load(f)

            environments = data["tool"]["uv"]["environments"]
            assert set(environments) == {
                "sys_platform == 'linux'",
                "sys_platform == 'darwin'",
                "sys_platform == 'win32'",
            }
