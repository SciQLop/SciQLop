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
from .test_tscat_first_start import SHOCKS, Tscat

ELSEWHERE = "My catalogues (open in another SciQLop window)"


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    """A SciQLop window on the person's folders, started signed out unless given a session."""
    made = []
    monkeypatch.setattr(provider_module.questions, "ask_move", lambda names, target: False)

    def window(session=None, tscat=None, start=True):
        p = CocatRsProvider(author="me", session=session or FakeSession(signed_in=False),
                            cache_dir=tmp_path / "cache", local_dir=tmp_path / "local", read_tscat=tscat)
        made.append(p)
        p.errors, p.notices = [], []
        p.error_occurred.connect(p.errors.append)
        p.notice.connect(p.notices.append)
        if start:
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


# ---- the tscat catalogues, brought in at the first start ----

def test_two_windows_starting_at_once_import_tscat_once(window, tmp_path):
    second = window(tscat=Tscat(SHOCKS), start=False)

    async def read_while_the_other_window_starts():
        await second._start()
        return SHOCKS

    first = window(tscat=read_while_the_other_window_starts)

    assert second._read_tscat.reads == 0 and second.notices == [] and second.errors == []
    [told] = first.notices
    assert "1 catalogue(s) and 1 event(s) imported from tscat" in told
    assert [c.name for c in first.catalogs()] == ["Shocks"]
    project = project_of(first)
    assert not lock_on(tmp_path / "local" / f"{project}.lock").tryLock(0)  # written while holding it


def test_a_window_started_after_the_import_does_not_read_tscat_again(window):
    window(tscat=Tscat(SHOCKS))

    second = window(tscat=Tscat(SHOCKS))

    assert second._read_tscat.reads == 0 and second.notices == []


def test_tscat_is_not_written_into_a_project_open_in_another_window(window):
    first = window()  # holds My catalogues, and did not import
    project = project_of(first)

    second = window(tscat=Tscat(SHOCKS))

    [error] = second.errors
    assert error == ("Cannot import your tscat catalogues: My catalogues is open in another "
                     "SciQLop window")
    assert list(second._room_infos) == [project] and first.catalogs() == []
    run(first.close())
    third = window(tscat=Tscat(SHOCKS))  # tried again at the next start
    assert [c.name for c in third.catalogs()] == ["Shocks"]
