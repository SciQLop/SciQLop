"""Several SciQLop windows of one person share the plugin's folders. A project kept on this computer
is open in one window at a time: the window that opens it holds its lock, the others show it as
open in another window and can take it once it is released."""
import subprocess
import sys

import pytest

from SciQLop.components.catalogs import CatalogEvent, CatalogRegistry
from SciQLop.components.catalogs.backend.provider import NodeType
from SciQLop.plugins.sciqlop_cocat import provider as provider_module
from SciQLop.plugins.sciqlop_cocat.locks import lock_on
from SciQLop.plugins.sciqlop_cocat.provider import CocatRsProvider
from .conftest import HOUR, T0
from .test_provider_rooms import ROOMS, FakeSession, opened, run  # noqa: F401

ELSEWHERE = "My catalogues (open in another SciQLop window)"


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    """A SciQLop window on the person's folders, started signed out unless given a session."""
    made = []
    monkeypatch.setattr(provider_module.questions, "ask_move", lambda names, target: False)

    def window(session=None):
        p = CocatRsProvider(author="me", session=session or FakeSession(signed_in=False),
                            cache_dir=tmp_path / "cache", local_dir=tmp_path / "local")
        made.append(p)
        p.errors = []
        p.error_occurred.connect(p.errors.append)
        run(p._start())
        return p

    yield window
    for p in made:
        run(p.close())
        CatalogRegistry.instance()._forget_for_tests(p)


def project_of(p) -> str:
    [project] = p._room_infos
    return project


def names(actions) -> list[str]:
    return [a.name for a in actions]


def test_the_window_that_opens_a_local_project_holds_it(window):
    first = window()
    project = project_of(first)
    first.add_event(first.create_catalog("shocks"), CatalogEvent(uuid="e1", start=T0, stop=T0 + HOUR))

    second = window()

    assert project_of(second) == project and project not in second._rooms
    assert second.catalogs() == [] and second.errors == []
    assert second.folder_display_name([project]) == ELSEWHERE
    assert names(second.folder_actions([project])) == ["Open here"]
    assert "another SciQLop window" in second.node_tooltip(NodeType.FOLDER, [project])
    assert first.folder_display_name([project]) == "My catalogues (default)"
    assert names(first.folder_actions([project]))[-1] == "Release"


def test_open_here_says_that_the_project_is_still_held(window):
    first, second = window(), window()
    project = project_of(first)

    run(second.open_here(project))

    assert project not in second._rooms
    [error] = second.errors
    assert "My catalogues is still open in another SciQLop window" in error and "Release" in error


def test_a_released_project_can_be_opened_in_another_window(window):
    first, second = window(), window()
    project = project_of(first)
    first.add_event(first.create_catalog("shocks"), CatalogEvent(uuid="e1", start=T0, stop=T0 + HOUR))
    [release] = [a for a in first.folder_actions([project]) if a.name == "Release"]

    release.callback([project])

    assert project not in first._rooms and first.catalogs() == []
    assert first.folder_display_name([project]) == "My catalogues (not open)"
    assert names(first.folder_actions([project])) == ["Open here"]

    run(second.open_here(project))

    assert second.errors == [] and [c.name for c in second.catalogs()] == ["shocks"]
    assert second.folder_display_name([project]) == "My catalogues (default)"

    run(first.open_here(project))

    assert project not in first._rooms and first.folder_display_name([project]) == ELSEWHERE


def test_closing_a_window_frees_its_projects(window):
    first, second = window(), window()
    project = project_of(first)

    run(first.close())
    run(second.open_here(project))

    assert project in second._rooms and second.errors == []


def test_a_project_that_cannot_be_opened_is_not_kept_locked(window, monkeypatch):
    def broken(folder, room_id):
        raise OSError("disk full")

    monkeypatch.setattr(provider_module, "open_room", broken)
    first = window()
    monkeypatch.undo()

    second = window()

    assert project_of(second) in second._rooms


def test_signing_in_does_not_drop_a_project_open_in_another_window(window, tmp_path):
    first = window()
    project = project_of(first)  # empty: a sign-in drops it when nobody has it open

    second = window(FakeSession(rooms=ROOMS))

    assert project in second._room_infos and project not in second._rooms
    assert second.folder_display_name([project]) == ELSEWHERE
    assert project in first._rooms
    first.create_catalog("shocks")
    run(first.close())
    run(second.open_here(project))
    assert "shocks" in [c.name for c in second.catalogs()]


def test_a_window_that_crashed_frees_its_lock(tmp_path):
    path = tmp_path / "project.lock"
    holder = subprocess.Popen(
        [sys.executable, "-c",
         "import sys, time\n"
         "from SciQLop.plugins.sciqlop_cocat.locks import lock_on\n"
         "from pathlib import Path\n"
         "lock = lock_on(Path(sys.argv[1]))\n"
         "print('held', lock.tryLock(0), flush=True)\n"
         "time.sleep(60)\n", str(path)], stdout=subprocess.PIPE, text=True)
    try:
        assert next(line for line in holder.stdout if line.startswith("held")).split() == ["held", "True"]
        lock = lock_on(path)
        assert not lock.tryLock(0)
    finally:
        holder.kill()
        holder.wait()
    assert lock.tryLock(0)
    lock.unlock()
