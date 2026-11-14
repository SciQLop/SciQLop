import asyncio
from types import SimpleNamespace

import cocat_rs
import pytest

from SciQLop.plugins.sciqlop_cocat.sharing import ProjectSharing

MEMBERS = [{"user_id": "u1", "email": "me@x.org", "role": "owner"},
           {"user_id": "u2", "email": "bob@x.org", "role": "editor"}]
INVITATIONS = [{"id": 7, "email": None, "role": "viewer", "expires_at": "2026-11-22T00:00:00Z",
                "uses": 0, "max_uses": None}]
GROUPS = [{"id": "g1", "name": "Bepi team", "role": "viewer"}]
OWNED = [SimpleNamespace(id="other", role="editor", editors_can_share=True),
         SimpleNamespace(id="p", role="owner", editors_can_share=True)]


class FakeSession:
    url = "https://h/cocat-dev"

    def __init__(self, refuse=(), projects=OWNED):
        self.calls = []
        self._refuse = set(refuse)
        self._answers = {cocat_rs.raw.members: MEMBERS, cocat_rs.raw.invitations: INVITATIONS,
                         cocat_rs.raw.project_groups: GROUPS, cocat_rs.raw.projects: projects,
                         cocat_rs.raw.invite: {"id": 8, "token": "t", "link": "https://h/ui/invitation#t"}}

    async def call(self, function, *args, **kwargs):
        self.calls.append((function.__name__, args, kwargs))
        if function.__name__ in self._refuse:
            raise cocat_rs.Forbidden("not allowed")
        return self._answers.get(function)


def run(coroutine):
    return asyncio.run(coroutine)


def test_load_reads_members_invitations_and_groups_of_the_project():
    session = FakeSession()
    state = run(ProjectSharing(session, "p").load())
    assert state.members == MEMBERS and state.invitations == INVITATIONS and state.groups == GROUPS
    assert state.can_manage
    assert state.editors_can_share is True
    assert {(name, args) for name, args, _ in session.calls} == {
        ("members", ("p",)), ("invitations", ("p",)), ("project_groups", ("p",)), ("projects", ())}


def test_only_the_owner_sees_whether_editors_can_share():
    editor = [SimpleNamespace(id="p", role="editor", editors_can_share=True)]
    assert run(ProjectSharing(FakeSession(projects=editor), "p").load()).editors_can_share is None


def test_whoever_the_server_refuses_invitations_to_cannot_manage():
    state = run(ProjectSharing(FakeSession(refuse={"invitations"}), "p").load())
    assert not state.can_manage and state.invitations == [] and state.members == MEMBERS


def test_actions_go_to_the_server_for_this_project():
    session = FakeSession()
    sharing = ProjectSharing(session, "p")
    run(sharing.set_role("u2", "viewer"))
    run(sharing.remove("u2"))
    created = run(sharing.invite("editor", "new@x.org"))
    run(sharing.invite("viewer", ""))
    run(sharing.revoke(7))
    run(sharing.set_editors_can_share(False))
    assert created["link"] == "https://h/ui/invitation#t"
    assert session.calls == [
        ("set_role", ("p", "u2", "viewer"), {}),
        ("remove_member", ("p", "u2"), {}),
        ("invite", ("p", "editor"), {"email": "new@x.org"}),
        ("invite", ("p", "viewer"), {"email": None}),
        ("revoke_invitation", ("p", 7), {}),
        ("set_editors_can_share", ("p", False), {}),
    ]


def test_a_refused_action_raises_for_the_dialog_to_show():
    with pytest.raises(cocat_rs.Forbidden):
        run(ProjectSharing(FakeSession(refuse={"set_role"}), "p").set_role("u2", "viewer"))
