"""Persisted settings for the agent chat dock."""
from typing import ClassVar, Dict, List

from pydantic import BaseModel, Field

from SciQLop.components.settings import SettingsCategory
from SciQLop.components.settings.backend import ConfigEntry
from SciQLop.components.settings.backend.entry import KeyringMapping


class AgentChatSettings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.APPLICATION
    subcategory: ClassVar[str] = "Agent chat"
    tool_verbosity: int = Field(
        default=1, ge=1, le=3,
        description="How much of the agent's tool activity to show in the chat "
                    "(1 = step names, 2 = + inputs, 3 = + result summaries).",
    )
    last_backend: str = Field(
        default="",
        description="Agent backend to reopen the chat with. Empty selects the "
                    "first available one.",
        json_schema_extra={"widget": "hidden"},
    )
    sessions_pane_visible: bool = Field(default=True, json_schema_extra={"widget": "hidden"})
    sessions_pane_width: int = Field(default=280, json_schema_extra={"widget": "hidden"})
    effort: Dict[str, str] = Field(
        default_factory=dict,
        description="Selected reasoning effort per agent backend, keyed by "
                    "backend display name. Empty string = backend default.",
        json_schema_extra={"widget": "hidden"},
    )


class AdsCredentialsSettings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.APPLICATION
    subcategory: ClassVar[str] = "Agent chat"
    _keyring_ = KeyringMapping("service", "username", "token")
    service: str = Field(default="nasa-ads", json_schema_extra={"widget": "hidden"})
    username: str = Field(default="ads_api_token", json_schema_extra={"widget": "hidden"})
    token: str = Field(
        default="",
        description="NASA ADS API token (https://ui.adsabs.harvard.edu/user/settings/token)",
        json_schema_extra={"widget": "password"},
    )


def _session_key(backend: str, session_id: str) -> str:
    return f"{backend}/{session_id}"


class SessionMetaEntry(BaseModel):
    name: str = ""
    pinned: bool = False
    group: str = ""
    tags: List[str] = Field(default_factory=list)


class AgentSessionMeta(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.APPLICATION
    subcategory: ClassVar[str] = "Agent chat"
    entries: Dict[str, SessionMetaEntry] = Field(
        default_factory=dict, json_schema_extra={"widget": "hidden"})

    def get(self, backend: str, session_id: str) -> SessionMetaEntry:
        return self.entries.get(_session_key(backend, session_id), SessionMetaEntry())

    def set_name(self, backend: str, session_id: str, name: str) -> None:
        entry = self.entries.setdefault(_session_key(backend, session_id), SessionMetaEntry())
        entry.name = name
        self.save()

    def set_pinned(self, backend: str, session_id: str, pinned: bool) -> None:
        entry = self.entries.setdefault(_session_key(backend, session_id), SessionMetaEntry())
        entry.pinned = pinned
        self.save()

    def set_group(self, backend: str, session_id: str, group: str) -> None:
        entry = self.entries.setdefault(_session_key(backend, session_id), SessionMetaEntry())
        entry.group = group
        self.save()

    def set_tags(self, backend: str, session_id: str, tags: List[str]) -> None:
        entry = self.entries.setdefault(_session_key(backend, session_id), SessionMetaEntry())
        entry.tags = list(tags)
        self.save()

    def rename_group(self, backend: str, old: str, new: str) -> None:
        prefix = f"{backend}/"
        changed = False
        for key, entry in self.entries.items():
            if key.startswith(prefix) and entry.group == old:
                entry.group = new
                changed = True
        if changed:
            self.save()

    def delete_group(self, backend: str, group: str) -> None:
        self.rename_group(backend, group, "")
