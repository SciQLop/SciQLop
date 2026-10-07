"""Which SciQLop releases the installer we run under can start.

An installer ships the native launcher, a Python interpreter, uv and the
SciQLop that prepares workspaces at every start (``sciqlop_launcher``). A
workspace can move to a newer SciQLop in place only while that installer can
still run it: otherwise the user needs a new installer. Each release declares
the oldest installer it runs under in its ``pyproject.toml``::

    [tool.sciqlop.launcher]
    minimum = "0.14.0"   # the SciQLop version that installer shipped
"""
import logging
import os
import platform
import tomllib
import urllib.request
from typing import NamedTuple, Optional

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

log = logging.getLogger(__name__)

# Set by sciqlop_launcher for the app it starts; installers before 0.14.2 don't.
LAUNCHER_VERSION_ENV = "SCIQLOP_LAUNCHER_VERSION"
INSTALLER_DOWNLOAD_URL = "https://github.com/SciQLop/SciQLop/releases/latest"
# PyPI's JSON has no field to carry the launcher minimum, so read the release's
# own pyproject from the tag it was published from.
_RELEASE_PYPROJECT_URL = "https://raw.githubusercontent.com/SciQLop/SciQLop/v{version}/pyproject.toml"


class ReleaseNeeds(NamedTuple):
    requires_python: str
    minimum_launcher: str  # "" for releases from before it was declared


_needs_cache: dict[str, ReleaseNeeds] = {}


def parse_release_needs(pyproject_text: str) -> ReleaseNeeds:
    data = tomllib.loads(pyproject_text)
    launcher = data.get("tool", {}).get("sciqlop", {}).get("launcher", {})
    return ReleaseNeeds(data.get("project", {}).get("requires-python", ""), launcher.get("minimum", ""))


def _fetch_release_pyproject(version: str, timeout: float) -> str:
    with urllib.request.urlopen(_RELEASE_PYPROJECT_URL.format(version=version), timeout=timeout) as resp:
        return resp.read().decode()


def fetch_release_needs(version: str, timeout: float = 5.0) -> Optional[ReleaseNeeds]:
    """What SciQLop *version* needs from the installer, or None when it cannot be fetched.

    Only successes are cached, so a later call retries after being offline.
    """
    if version not in _needs_cache:
        try:
            _needs_cache[version] = parse_release_needs(_fetch_release_pyproject(version, timeout))
        except Exception as exc:
            log.debug("Could not fetch what SciQLop %s needs: %s", version, exc)
            return None
    return _needs_cache[version]


def launcher_version() -> str:
    """The SciQLop version of the launcher that started this process, "" when unknown."""
    return os.environ.get(LAUNCHER_VERSION_ENV, "")


def supports(needs: Optional[ReleaseNeeds], launcher: str, python: str) -> Optional[bool]:
    """Whether *launcher* (a launcher's SciQLop version) on *python* can run a
    release needing *needs*; None when that cannot be told."""
    if needs is None:
        return None
    try:
        if needs.requires_python and not SpecifierSet(needs.requires_python).contains(python, prereleases=True):
            return False
        if not needs.minimum_launcher:
            return True
        if not launcher:
            return None
        return Version(launcher) >= Version(needs.minimum_launcher)
    except (InvalidSpecifier, InvalidVersion):
        return None


def runs_here(version: str, launcher: Optional[str] = None) -> Optional[bool]:
    """Whether this installer can run SciQLop *version*; *launcher* defaults to ours."""
    return supports(fetch_release_needs(version),
                    launcher_version() if launcher is None else launcher,
                    platform.python_version())
