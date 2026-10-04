"""A/B workspace environments: two venv slots, one live, the other staged for updates."""
from pathlib import Path

import pytest

from SciQLop.components.workspaces.backend import venv_slots
from SciQLop.components.workspaces.backend.workspace_venv import WorkspaceVenv


def test_a_workspace_starts_on_slot_a(tmp_path):
    assert venv_slots.active_slot(tmp_path) == ".venv"
    assert venv_slots.inactive_slot(tmp_path) == ".venv-b"


def test_activating_the_other_slot_swaps_the_roles(tmp_path):
    venv_slots.set_active(tmp_path, ".venv-b")
    assert venv_slots.active_slot(tmp_path) == ".venv-b"
    assert venv_slots.inactive_slot(tmp_path) == ".venv"


@pytest.mark.parametrize("garbage", ["", "../etc", ".venv-c", "\n"])
def test_an_unreadable_pointer_falls_back_to_slot_a(tmp_path, garbage):
    (tmp_path / venv_slots.POINTER).write_text(garbage)
    assert venv_slots.active_slot(tmp_path) == ".venv"


def test_set_active_rejects_unknown_slots(tmp_path):
    with pytest.raises(ValueError):
        venv_slots.set_active(tmp_path, ".venv-c")


def test_pending_slot_round_trip(tmp_path):
    assert venv_slots.pending_slot(tmp_path) is None
    venv_slots.mark_pending(tmp_path, ".venv-b")
    assert venv_slots.pending_slot(tmp_path) == ".venv-b"
    venv_slots.clear_pending(tmp_path)
    assert venv_slots.pending_slot(tmp_path) is None


def test_activate_pending_makes_the_staged_slot_live(tmp_path):
    venv_slots.mark_pending(tmp_path, ".venv-b")
    assert venv_slots.activate_pending(tmp_path) == ".venv-b"
    assert venv_slots.active_slot(tmp_path) == ".venv-b"
    assert venv_slots.pending_slot(tmp_path) is None


def test_a_pending_marker_naming_the_live_slot_is_dropped(tmp_path):
    venv_slots.mark_pending(tmp_path, ".venv")
    assert venv_slots.activate_pending(tmp_path) is None
    assert venv_slots.pending_slot(tmp_path) is None


def test_workspace_venv_follows_the_active_slot(tmp_path):
    assert WorkspaceVenv(tmp_path).venv_dir == tmp_path / ".venv"
    venv_slots.set_active(tmp_path, ".venv-b")
    assert WorkspaceVenv(tmp_path).venv_dir == tmp_path / ".venv-b"
    assert WorkspaceVenv(tmp_path, slot=".venv").venv_dir == tmp_path / ".venv"


def test_sync_targets_its_own_slot(tmp_path, monkeypatch):
    from SciQLop.components.workspaces.backend import workspace_venv
    seen = {}

    def fake_run_uv(cmd, on_output=None, **kw):
        seen.update(kw)

    monkeypatch.setattr(workspace_venv, "_run_uv", fake_run_uv)
    WorkspaceVenv(tmp_path, slot=".venv-b").sync()
    assert seen["env"]["UV_PROJECT_ENVIRONMENT"] == str(tmp_path / ".venv-b")
    assert seen["cwd"] == str(tmp_path)


def _fake_installed(venv_dir: Path, version: str):
    site = venv_dir / "lib" / "python3.14" / "site-packages"
    (site / f"sciqlop-{version}.dist-info").mkdir(parents=True)
    (site / f"sciqlop-{version}.dist-info" / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: SciQLop\nVersion: {version}\n")


def test_installed_version_is_read_from_the_live_slot(tmp_path):
    from SciQLop.components.workspaces.backend.workspace_project import installed_sciqlop_version
    _fake_installed(tmp_path / ".venv", "0.14.0")
    _fake_installed(tmp_path / ".venv-b", "0.15.0")
    assert installed_sciqlop_version(tmp_path) == "0.14.0"
    venv_slots.set_active(tmp_path, ".venv-b")
    assert installed_sciqlop_version(tmp_path) == "0.15.0"


def test_both_slots_and_their_markers_stay_out_of_archives():
    from SciQLop.components.workspaces.backend.workspace_archive import is_excluded
    for path in (".venv-b/lib/x.py", ".sciqlop_venv", ".sciqlop_venv_next", ".venv-b.reset-20261004-070000"):
        assert is_excluded(Path(path)), path


def test_reset_clears_both_slots_and_returns_to_slot_a(tmp_path):
    from SciQLop.components.workspaces.backend import workspace_reset
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv-b").mkdir()
    venv_slots.set_active(tmp_path, ".venv-b")
    venv_slots.mark_pending(tmp_path, ".venv")
    workspace_reset.reset_environment(tmp_path, latest_versions=lambda: [])
    assert not any((tmp_path / s).exists() for s in venv_slots.SLOTS)
    assert venv_slots.active_slot(tmp_path) == ".venv"
    assert venv_slots.pending_slot(tmp_path) is None
