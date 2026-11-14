import asyncio
from datetime import date, datetime

import cocat_rs

from SciQLop.plugins.sciqlop_cocat.history import Version
from SciQLop.plugins.sciqlop_cocat.history_dialog import HistoryDialog, day_label

VERSIONS = [Version(3, datetime(2026, 11, 9, 15, 0), "a@x.org", "", "1 event added", colour="#835a3c"),
            Version(2, datetime(2026, 11, 9, 11, 5), "a@x.org", "first draft", "2 events added", named=True),
            Version(1, datetime(2026, 11, 2, 9, 30), "b@x.org", "", "restored version 0", restore=True)]
TODAY = date(2026, 11, 9)


class FakeHistory:
    project_id, catalogue = "p", None

    def __init__(self, refuse=()):
        self.calls, self._refuse = [], set(refuse)

    async def _record(self, name, *args):
        self.calls.append((name, *args))
        if name in self._refuse:
            raise cocat_rs.Forbidden("viewers cannot restore")

    async def load(self):
        await self._record("load")
        return VERSIONS

    async def restore(self, version):
        await self._record("restore", version)

    async def name(self, version, name):
        await self._record("name", version, name)

    async def copy(self, version, name):
        await self._record("copy", version, name)
        return "new-id"


async def _settle(coroutine):
    try:
        return await coroutine
    except Exception as error:
        return error


def make(qtbot, history, on_copied=None):
    dialog = HistoryDialog(history, "Team", on_copied, today=TODAY)
    dialog._run = lambda coroutine, then=None, failure="Failed": dialog._finish(
        asyncio.run(_settle(coroutine)), then, failure)
    qtbot.addWidget(dialog)
    dialog.refresh()
    return dialog


def test_versions_are_grouped_by_day_newest_first(qtbot):
    dialog = make(qtbot, FakeHistory())
    assert dialog.days() == ["Today", "Monday 02 November"]
    assert dialog.rows() == [("15:00", "a@x.org", "", "1 event added"),
                             ("11:05", "a@x.org", "first draft", "2 events added"),
                             ("09:30", "b@x.org", "", "restored version 0")]


def test_days_read_naturally():
    assert day_label(date(2026, 11, 9), TODAY) == "Today"
    assert day_label(date(2026, 11, 8), TODAY) == "Yesterday"
    assert day_label(date(2025, 12, 31), TODAY) == "Wednesday 31 December 2025"
    assert day_label(None, TODAY) == "Not closed yet"


def test_actions_wait_for_a_chosen_version(qtbot):
    dialog = make(qtbot, FakeHistory())
    assert not dialog.buttons_enabled()
    dialog.select(1)
    assert dialog.buttons_enabled() and dialog._selected() is VERSIONS[1]


def test_restore_then_reload(qtbot):
    history = FakeHistory()
    dialog = make(qtbot, history)
    dialog.restore(VERSIONS[2])
    assert history.calls == [("load",), ("restore", 1), ("load",)]
    assert "Restored the version of 2026-11-02 09:30" in dialog.status_text()


def test_a_refused_restore_says_what_failed(qtbot):
    dialog = make(qtbot, FakeHistory(refuse={"restore"}))
    dialog.restore(VERSIONS[0])
    assert dialog.status_text() == "Could not restore: viewers cannot restore"


def test_a_history_that_cannot_load_says_so(qtbot):
    dialog = make(qtbot, FakeHistory(refuse={"load"}))
    assert dialog.placeholder_text() == "The history could not be loaded."
    assert dialog.status_text().startswith("Could not load the history")


def test_naming_reloads(qtbot):
    history = FakeHistory()
    dialog = make(qtbot, history)
    dialog.name(VERSIONS[0], "before cleanup")
    assert history.calls[1:] == [("name", 3, "before cleanup"), ("load",)]


def test_a_copy_is_handed_on(qtbot):
    copied = []
    dialog = make(qtbot, FakeHistory(), on_copied=lambda *a: copied.append(a))
    dialog.copy(VERSIONS[1], "trial")
    assert copied == [("new-id", "trial")]


def test_an_empty_history_says_how_to_start_one(qtbot):
    history = FakeHistory()

    async def nothing():
        return []
    history.load = nothing
    assert "Save version" in make(qtbot, history).placeholder_text()


def test_an_empty_catalogue_history_says_no_version_changed_it(qtbot):
    history = FakeHistory()
    history.catalogue = "c1"

    async def nothing():
        return []
    history.load = nothing
    assert "changed this catalogue" in make(qtbot, history).placeholder_text()

