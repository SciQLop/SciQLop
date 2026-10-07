"""Which SciQLop releases the installer we run under can start (launcher_compat)."""
import re
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from SciQLop.components.workspaces.backend import launcher_compat
from SciQLop.components.workspaces.backend.launcher_compat import (
    ReleaseNeeds, parse_release_needs, supports,
)

ROOT = Path(__file__).resolve().parents[1]


class TestParseReleaseNeeds:
    def test_reads_python_range_and_minimum_launcher(self):
        text = ('[project]\nrequires-python = ">=3.13,<3.15"\n'
                '[tool.sciqlop.launcher]\nminimum = "0.14.0"\n')
        assert parse_release_needs(text) == ReleaseNeeds(">=3.13,<3.15", "0.14.0")

    def test_a_release_from_before_the_declaration_has_no_minimum(self):
        assert parse_release_needs('[project]\nrequires-python = ">=3.13"\n') == ReleaseNeeds(">=3.13", "")


class TestSupports:
    NEEDS = ReleaseNeeds(">=3.13,<3.15", "0.14.2")

    @pytest.mark.parametrize("launcher, expected", [("0.14.2", True), ("0.15.0", True), ("0.14.1", False)])
    def test_compares_the_launcher_with_the_minimum(self, launcher, expected):
        assert supports(self.NEEDS, launcher, "3.14.0") is expected

    def test_a_python_outside_the_release_range_cannot_run_it(self):
        assert supports(self.NEEDS, "0.15.0", "3.15.0") is False

    def test_unknown_when_the_release_needs_could_not_be_fetched(self):
        assert supports(None, "0.15.0", "3.14.0") is None

    def test_unknown_when_we_do_not_know_our_launcher(self):
        assert supports(self.NEEDS, "", "3.14.0") is None

    def test_a_release_without_a_minimum_runs_on_any_launcher(self):
        assert supports(ReleaseNeeds(">=3.13", ""), "", "3.14.0") is True


class TestFetchReleaseNeeds:
    def test_failures_are_not_cached(self):
        launcher_compat._needs_cache.clear()
        with patch.object(launcher_compat, "_fetch_release_pyproject", side_effect=[OSError, "[project]\n"]):
            assert launcher_compat.fetch_release_needs("9.9.9") is None
            assert launcher_compat.fetch_release_needs("9.9.9") == ReleaseNeeds("", "")
        launcher_compat._needs_cache.clear()


class TestThisReleaseDeclaresWhatTheInstallerShips:
    """Changing what the installers ship must come with a decision on the minimum.

    ``native`` and ``python`` only mirror the build scripts so that bumping
    either fails here: then set ``minimum`` to the release being cut, unless
    older installers still run it fine.
    """

    @pytest.fixture(scope="class")
    def declared(self):
        return tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["sciqlop"]["launcher"]

    def test_minimum_is_a_release_version(self, declared):
        assert re.fullmatch(r"\d+\.\d+\.\d+", declared["minimum"])

    def test_native_launcher_matches_the_one_installers_fetch(self, declared):
        pinned = re.search(r"^LAUNCHER_VERSION=(\S+)$", (ROOT / "scripts/launcher.version").read_text(), re.M)
        assert declared["native"] == pinned.group(1)

    @pytest.mark.parametrize("script, pattern", [
        ("scripts/appimage/build.sh", r"^PYTHON_VERSION=(\S+)$"),
        ("scripts/macos/make_dmg.sh", r"^PYTHON_VERSION=(\S+)$"),
        ("scripts/windows/bundle.ps1", r'^\$PythonVersion = "(\S+)"$'),
        ("scripts/windows/install.ps1", r'^\$PythonVersion = "(\S+)"$'),
    ])
    def test_python_matches_the_one_installers_bundle(self, declared, script, pattern):
        assert declared["python"] == re.search(pattern, (ROOT / script).read_text(), re.M).group(1)
