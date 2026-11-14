import asyncio

import cocat_rs

from SciQLop.plugins.sciqlop_cocat.history import ProjectHistory, describe_changes, version_of

ENTRY = {"id": 3, "author_color": "#835a3c", "ended_ms": 1794239566259, "started_ms": 1794239566259, "author_email": "a@x.org", "name": None,
         "auto_name": "Tuesday edits", "events_added": 2, "events_changed": 1, "events_removed": 0,
         "rules_changed": [], "catalogues": ["c1"], "restored_from": None}


class RecordingSession:
    def __init__(self, answer=None):
        self.calls, self._answer = [], answer

    async def call(self, function, *args):
        self.calls.append((function, *args))
        return self._answer


def test_a_version_says_who_when_and_what():
    version = version_of(ENTRY)
    assert (version.id, version.who, version.name) == (3, "a@x.org", "Tuesday edits")
    assert version.changes == "2 events added, 1 event changed"
    assert version.when.year == 2026


def test_the_changes_name_restores_rules_and_catalogues():
    assert describe_changes({**ENTRY, "restored_from": 1}) == "restored version 1"
    assert describe_changes({**ENTRY, "events_added": 0, "events_changed": 0,
                             "rules_changed": ["c1"]}) == "1 rule changed"
    assert describe_changes({**ENTRY, "events_added": 0, "events_changed": 0}) == "1 catalogue changed"
    assert describe_changes({**ENTRY, "events_added": 0, "events_changed": 0, "catalogues": []}) == "no change"


def test_calls_name_the_project_and_the_catalogue():
    session = RecordingSession([ENTRY])
    history = ProjectHistory(session, "p", catalogue="c1")
    [version] = asyncio.run(history.load())
    asyncio.run(history.restore(3))
    asyncio.run(history.name(3, ""))
    asyncio.run(history.copy(3, "trial"))
    assert version.id == 3
    assert session.calls == [(cocat_rs.raw.history, "p", "c1"), (cocat_rs.raw.restore, "p", 3, "c1"),
                             (cocat_rs.raw.name_version, "p", 3, None),
                             (cocat_rs.raw.copy_version, "p", 3, "trial")]


def test_a_version_still_open_has_no_end_time():
    open_version = version_of({**ENTRY, "ended_ms": None})
    assert open_version.when == version_of(ENTRY).when  # started_ms is the same in ENTRY
    assert version_of({**ENTRY, "ended_ms": None, "started_ms": None}).when is None


def test_a_version_knows_whether_a_person_named_it():
    assert not version_of(ENTRY).named and version_of(ENTRY).colour == "#835a3c"
    named = version_of({**ENTRY, "name": "first draft"})
    assert named.named and named.name == "first draft"
    assert version_of({**ENTRY, "restored_from": 1}).restore
