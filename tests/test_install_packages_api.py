"""user_api.install_packages: resolve active workspace and delegate to add_packages."""
from unittest.mock import MagicMock

import pytest

import SciQLop.user_api.packages as pkgs

VDF = "sciqlop-vdf @ git+https://github.com/nicolasaunai/sciqlop-vdf@v0.3.0"


def test_no_active_workspace(monkeypatch):
    monkeypatch.setattr(pkgs, "workspaces_manager_instance", lambda: None)
    result = pkgs.install_packages("astropy")
    assert result == {"ok": False, "installed": [],
                      "already_present": [], "error": "no active workspace"}


def test_delegates_to_add_packages(monkeypatch):
    ws = MagicMock()
    ws.add_packages.return_value = {"ok": True, "installed": ["scipy"],
                                    "already_present": [], "error": ""}
    wm = MagicMock(has_workspace=True, workspace=ws)
    monkeypatch.setattr(pkgs, "workspaces_manager_instance", lambda: wm)
    result = pkgs.install_packages("scipy", "astropy>=5")
    ws.add_packages.assert_called_once_with(["scipy", "astropy>=5"])
    assert result["installed"] == ["scipy"]


@pytest.fixture
def venv(monkeypatch):
    """A fake workspace venv: installing sets each dist to the version in ``venv["next"]``."""
    state = {"versions": {}, "next": {}, "loaded": [], "load_result": None}

    def add_packages(specs):
        state["versions"].update(state["next"])
        return {"ok": True, "installed": specs, "already_present": [], "error": ""}

    def hot_load(name):
        state["loaded"].append(name)
        return state["load_result"]

    ws = MagicMock()
    ws.add_packages.side_effect = add_packages
    monkeypatch.setattr(pkgs, "workspaces_manager_instance",
                        lambda: MagicMock(has_workspace=True, workspace=ws))
    monkeypatch.setattr(pkgs, "_installed_version", lambda name: state["versions"].get(name))
    monkeypatch.setattr(pkgs, "_hot_load", hot_load)
    state["workspace"] = ws
    return state


def test_a_newly_installed_plugin_is_loaded_without_restart(venv):
    """%install used to need a restart to load a plugin while the app store
    hot-loaded it right away; both now go through the same hot-load."""
    venv["next"] = {"sciqlop-vdf": "0.3.0"}

    result = pkgs.install_packages(VDF)

    assert venv["loaded"] == ["sciqlop-vdf"]
    assert result["restart_required"] == []
    assert result["not_loaded"] == {}


def test_a_gated_plugin_reports_why_it_was_not_loaded(venv):
    venv["next"] = {"future-plugin": "1.0"}
    venv["load_result"] = "needs SciQLop >=9"

    result = pkgs.install_packages("future-plugin")

    assert result["not_loaded"] == {"future-plugin": "needs SciQLop >=9"}


def test_an_upgrade_asks_for_a_restart_instead_of_loading_twice(venv):
    venv["versions"] = {"sciqlop-vdf": "0.2.0"}
    venv["next"] = {"sciqlop-vdf": "0.3.0"}

    result = pkgs.install_packages(VDF)

    assert venv["loaded"] == []
    assert result["restart_required"] == ["sciqlop-vdf"]


def test_an_unchanged_version_needs_neither_load_nor_restart(venv):
    venv["versions"] = {"scipy": "1.14.0"}

    result = pkgs.install_packages("scipy>=1.11")

    assert venv["loaded"] == []
    assert result["restart_required"] == []


@pytest.mark.parametrize("shorthand, expected", [
    ("gh:nicolasaunai/sciqlop-vdf@v0.3.0", VDF),
    ("gh:nicolasaunai/sciqlop-vdf", "sciqlop-vdf @ git+https://github.com/nicolasaunai/sciqlop-vdf"),
    ("https://github.com/nicolasaunai/sciqlop-vdf@v0.3.0", VDF),
    ("https://github.com/nicolasaunai/sciqlop-vdf.git",
     "sciqlop-vdf @ git+https://github.com/nicolasaunai/sciqlop-vdf"),
    ("scipy>=1.11", "scipy>=1.11"),
    (VDF, VDF),
])
def test_github_shorthand_expands_to_a_pep508_spec(venv, shorthand, expected):
    pkgs.install_packages(shorthand)
    venv["workspace"].add_packages.assert_called_once_with([expected])
