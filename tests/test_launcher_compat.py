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


class TestPreferredRelease:
    """The release workspaces should run, per the "SciQLop version" setting."""

    @staticmethod
    def _preferred(launcher, latest, runnable=None, available=("0.16.0", "0.15.1", "0.15.0", "0.14.0")):
        asked = []

        def runs(version, launcher):
            asked.append(version)
            return (runnable or {}).get(version, True)

        with (
            patch.object(launcher_compat, "follows_latest_release", return_value=latest),
            patch.object(launcher_compat, "fetch_available_versions", return_value=list(available)),
            patch.object(launcher_compat, "runs_here", side_effect=runs),
        ):
            return launcher_compat.preferred_release(launcher), asked

    def test_latest_is_the_newest_release_the_installer_runs(self):
        assert self._preferred("0.15.0", True, runnable={"0.16.0": False})[0] == "0.15.1"

    def test_latest_never_looks_at_releases_older_than_the_installer(self):
        version, asked = self._preferred("0.15.0", True, runnable={"0.16.0": None, "0.15.1": False})
        assert version == "0.15.0"
        assert "0.14.0" not in asked

    def test_offline_falls_back_to_the_installer_version(self):
        assert self._preferred("0.15.0", True, available=())[0] == "0.15.0"

    def test_installer_mode_is_the_installer_version(self):
        version, asked = self._preferred("0.15.0", False)
        assert version == "0.15.0" and asked == []

    @pytest.mark.parametrize("launcher", ["", "0.15.1.dev2"])
    def test_a_development_or_unknown_launcher_has_no_release(self, launcher):
        assert self._preferred(launcher, True)[0] == ""


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
