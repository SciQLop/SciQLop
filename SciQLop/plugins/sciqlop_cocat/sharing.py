"""Who has access to one CoCat project, and the calls that change it.

The server decides who may share. The plugin never guesses from roles: whoever the server lets list
invitations can manage sharing, and any refused change surfaces as a cocat_rs.ServerError.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import cocat_rs

ASSIGNABLE_ROLES = ("editor", "viewer")


@dataclass(frozen=True)
class SharingState:
    members: list[dict]
    invitations: list[dict]
    groups: list[dict]
    can_manage: bool
    editors_can_share: bool | None  # None unless the caller owns the project: only the owner may change it


class ProjectSharing:
    def __init__(self, session, project_id: str):
        self._session = session
        self.project_id = project_id

    async def _call(self, function, *args, **kwargs):
        return await self._session.call(function, self.project_id, *args, **kwargs)

    async def _invitations(self) -> list[dict] | None:
        try:
            return await self._call(cocat_rs.raw.invitations)
        except cocat_rs.Forbidden:
            return None

    async def _editors_can_share(self) -> bool | None:
        projects = await self._session.call(cocat_rs.raw.projects)
        info = next((p for p in projects if p.id == self.project_id), None)
        return info.editors_can_share if info is not None and info.role == "owner" else None

    async def load(self) -> SharingState:
        members, groups, invitations, editors_can_share = await asyncio.gather(
            self._call(cocat_rs.raw.members), self._call(cocat_rs.raw.project_groups), self._invitations(),
            self._editors_can_share())
        return SharingState(members=members, invitations=invitations or [], groups=groups,
                            can_manage=invitations is not None, editors_can_share=editors_can_share)

    async def set_role(self, user_id: str, role: str) -> None:
        await self._call(cocat_rs.raw.set_role, user_id, role)

    async def remove(self, user_id: str) -> None:
        await self._call(cocat_rs.raw.remove_member, user_id)

    async def invite(self, role: str, email: str) -> dict:
        """An empty email makes an invitation link anyone holding it can use."""
        return await self._call(cocat_rs.raw.invite, role, email=email or None)

    async def revoke(self, invitation_id: int) -> None:
        await self._call(cocat_rs.raw.revoke_invitation, invitation_id)

    async def set_editors_can_share(self, allowed: bool) -> None:
        await self._call(cocat_rs.raw.set_editors_can_share, allowed)
