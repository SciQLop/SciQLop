from .speasy_provider import load
# Importing settings has the side effect of dynamically constructing
# `ConfigEntry` subclasses for each Speasy ConfigSection, registering them
# with `ConfigEntry._entries_` so the settings UI can list them.
from . import settings  # noqa: F401
