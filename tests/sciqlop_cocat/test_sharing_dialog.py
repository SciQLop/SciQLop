import asyncio

import cocat_rs

from SciQLop.plugins.sciqlop_cocat.sharing import SharingState
from SciQLop.plugins.sciqlop_cocat.sharing_dialog import SharingDialog
from .test_sharing import GROUPS, INVITATIONS, MEMBERS

OWNER = SharingState(members=MEMBERS, invitations=INVITATIONS, groups=GROUPS, can_manage=True,
                     editors_can_share=True)
MANAGER = SharingState(members=MEMBERS, invitations=INVITATIONS, groups=GROUPS, can_manage=True,
                       editors_can_share=None)
READER = SharingState(members=MEMBERS, invitations=[], groups=[], can_manage=False, editors_can_share=None)


class FakeSharing:
    project_id = "p"

    def __init__(self, state, refuse=()):
        self.state, self.calls, self._refuse = state, [], set(refuse)

    async def _record(self, name, *args):
        self.calls.append((name, *args))
        if name in self._refuse:
            error = cocat_rs.Forbidden("refused")
            error.detail = "The caller may not change roles"
            raise error

    async def load(self):
        await self._record("load")
        return self.state

    async def set_role(self, user_id, role):
        await self._record("set_role", user_id, role)

    async def remove(self, user_id):
        await self._record("remove", user_id)

    async def invite(self, role, email):
        await self._record("invite", role, email)
        return {"id": 9, "token": "t", "link": "https://h/ui/invitation#t"}

    async def revoke(self, invitation_id):
        await self._record("revoke", invitation_id)

    async def set_editors_can_share(self, allowed):
        await self._record("set_editors_can_share", allowed)


def make(qtbot, sharing):
    dialog = SharingDialog(sharing, "Bepi MSA", "https://h/ui/rooms/p/browse#share")
    dialog._run = lambda coroutine, then=None, on_error=None: dialog._finish(
        asyncio.run(_settle(coroutine)), then, on_error)
    qtbot.addWidget(dialog)
    dialog.refresh()
    return dialog


async def _settle(coroutine):
    try:
        return await coroutine
    except Exception as error:
        return error


def test_a_manager_sees_members_groups_invitations_and_can_invite(qtbot):
    dialog = make(qtbot, FakeSharing(MANAGER))
    assert dialog.member_rows() == [("me@x.org", "owner", False), ("bob@x.org", "editor", True)]
    assert dialog.invitation_rows() == [("anyone with the link", "viewer", "2026-11-22")]
    assert "Bepi team (viewer)" in dialog.groups_text()
    assert dialog.can_invite()


def test_someone_who_cannot_share_sees_who_has_access_read_only(qtbot):
    dialog = make(qtbot, FakeSharing(READER))
    assert dialog.member_rows() == [("me@x.org", "owner", False), ("bob@x.org", "editor", False)]
    assert not dialog.can_invite() and dialog.invitation_rows() == []


def test_changing_a_role_goes_to_the_server_then_reloads(qtbot):
    sharing = FakeSharing(MANAGER)
    dialog = make(qtbot, sharing)
    dialog.choose_role("bob@x.org", "viewer")
    assert sharing.calls == [("load",), ("set_role", "u2", "viewer"), ("load",)]


def test_inviting_shows_the_link_to_send(qtbot):
    sharing = FakeSharing(MANAGER)
    dialog = make(qtbot, sharing)
    dialog.invite_as("editor", "new@x.org")
    assert ("invite", "editor", "new@x.org") in sharing.calls
    assert dialog.invitation_link() == "https://h/ui/invitation#t"


def test_revoking_an_invitation(qtbot):
    sharing = FakeSharing(MANAGER)
    make(qtbot, sharing).revoke_invitation(7)
    assert ("revoke", 7) in sharing.calls


def test_a_refused_change_shows_the_server_reason_and_what_the_server_still_has(qtbot):
    sharing = FakeSharing(MANAGER, refuse={"set_role"})
    dialog = make(qtbot, sharing)
    dialog.choose_role("bob@x.org", "viewer")
    assert "The caller may not change roles" in dialog.status_text()
    assert sharing.calls == [("load",), ("set_role", "u2", "viewer"), ("load",)]
    assert ("bob@x.org", "editor", True) in dialog.member_rows()


def test_only_the_owner_gets_the_editors_can_share_switch(qtbot):
    assert make(qtbot, FakeSharing(OWNER)).editors_can_share() is True
    assert make(qtbot, FakeSharing(MANAGER)).editors_can_share() is None


def test_the_owner_can_keep_sharing_to_themselves(qtbot):
    sharing = FakeSharing(OWNER)
    make(qtbot, sharing).allow_editors_to_share(False)
    assert sharing.calls == [("load",), ("set_editors_can_share", False), ("load",)]
