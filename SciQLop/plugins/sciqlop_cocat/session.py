"""The sign-in to one CoCat server, and calls to it. cocat-rs does blocking HTTP, so it runs off
the Qt thread. The sign-in happens in the browser; cocat-rs keeps its token in the system keyring."""
from __future__ import annotations

import asyncio

import cocat_rs

from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

APP_NAME = "SciQLop"  # the server lists the sign-in as "SciQLop on <hostname>"


class Session:
    def __init__(self, url: str, client=None):
        self.url = url.rstrip("/")
        self._client = client if client is not None else cocat_rs.Client(self.url)

    @property
    def cookie(self) -> str | None:
        return self._client.session

    @property
    def signed_in(self) -> bool:
        return self.cookie is not None

    async def start_sign_in(self):
        """A cocat_rs.SignIn: show its `url` and `code`, then `wait()` for it in a thread."""
        return await asyncio.to_thread(self._client.start_sign_in, APP_NAME)

    async def sign_out(self) -> None:
        await asyncio.to_thread(self._client.logout)

    async def call(self, function, *args, **kwargs):
        """A cocat_rs.raw server call (``function(url, cookie, ...)``) off the Qt thread. A refused
        token was revoked or expired: it is forgotten, so the next attempt offers to sign in."""
        try:
            return await asyncio.to_thread(function, self.url, self.cookie, *args, **kwargs)
        except cocat_rs.Unauthorized:
            await self.sign_out()
            raise

    async def projects(self) -> list | None:
        try:
            return await self.call(cocat_rs.raw.projects)
        except Exception as error:
            log.error("Cannot list CoCat projects at %s: %s", self.url, error)
            return None

    async def email(self) -> str:
        return (await self.call(cocat_rs.raw.account))["email"]
