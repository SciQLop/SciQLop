"""Network / proxy configuration applied before any outbound request.

SciQLop launched from a desktop shortcut inherits no shell environment, so uv
(and speasy, JupyterLab, the appstore) never see ``HTTP(S)_PROXY`` and stall on
a direct connection that a corporate network drops.  The launcher injects the
effective proxy into the environment before workspace preparation; both the
in-process uv runs and the spawned app subprocess then inherit it.

Precedence: an explicit in-app setting overrides the inherited environment;
when the setting is empty, any pre-existing environment proxy is left untouched
(honored).
"""
from __future__ import annotations

from collections.abc import MutableMapping

from pydantic import Field

from SciQLop.components.settings.backend.entry import ConfigEntry, SettingsCategory

_PROXY_ENV_VARS = ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy")
_NO_PROXY_ENV_VARS = ("NO_PROXY", "no_proxy")


class SciQLopNetworkSettings(ConfigEntry):
    category = SettingsCategory.APPLICATION
    subcategory = "network"
    proxy_url: str = Field(
        default="",
        description="HTTP proxy URL (e.g. http://proxy.example:8080) used for "
                    "package installation and data downloads. Leave empty to "
                    "use the system / environment proxy.",
    )
    no_proxy: str = Field(
        default="",
        description="Comma-separated hosts that bypass the proxy "
                    "(e.g. localhost,127.0.0.1,.internal).",
    )


def proxy_env_overrides(proxy_url: str, no_proxy: str) -> dict[str, str]:
    """Map the configured proxy to the env vars uv / requests / speasy read.

    Returns an empty dict when nothing is configured, so the caller leaves the
    inherited environment untouched.
    """
    overrides: dict[str, str] = {}
    if proxy_url:
        overrides.update({var: proxy_url for var in _PROXY_ENV_VARS})
    if no_proxy:
        overrides.update({var: no_proxy for var in _NO_PROXY_ENV_VARS})
    return overrides


def apply_proxy_settings(env: MutableMapping[str, str]) -> None:
    """Inject the configured proxy into ``env`` (overriding any present value).

    Covers everything that reads the standard proxy environment variables: uv
    (workspace prep, plugin installs), speasy data downloads, ``requests`` and
    ``httpx`` clients, and the Jupyter server subprocess.
    """
    settings = SciQLopNetworkSettings()
    env.update(proxy_env_overrides(settings.proxy_url, settings.no_proxy))


def apply_qt_application_proxy() -> None:
    """Set the configured proxy as Qt's application-wide proxy.

    Covers in-process Qt networking and Qt WebEngine, which honor
    ``QNetworkProxy.setApplicationProxy``.  Must be called after the
    QApplication exists.  No-op when no proxy is configured.
    """
    settings = SciQLopNetworkSettings()
    if not settings.proxy_url:
        return
    from urllib.parse import urlparse
    from PySide6.QtNetwork import QNetworkProxy

    raw = settings.proxy_url if "://" in settings.proxy_url else f"http://{settings.proxy_url}"
    parsed = urlparse(raw)
    if not parsed.hostname:
        return
    proxy = QNetworkProxy(QNetworkProxy.ProxyType.HttpProxy, parsed.hostname, parsed.port or 0)
    if parsed.username:
        proxy.setUser(parsed.username)
    if parsed.password:
        proxy.setPassword(parsed.password)
    QNetworkProxy.setApplicationProxy(proxy)
