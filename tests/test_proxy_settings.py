"""Proxy support for the workspace-prep uv subprocess and the app.

Reproducer for "launcher hangs at 'Preparing workspace…' behind an HTTP proxy":
SciQLop launched from a desktop / Start Menu shortcut inherits no shell
environment, so uv has no ``HTTP(S)_PROXY`` and stalls on a direct connection
that a corporate network blackholes.

The valuable test here is ``test_uv_routes_through_our_configured_proxy``: it
stands up a real local proxy listener, points SciQLop's proxy setting at it,
and proves the actual ``uv`` binary dials *our* proxy (HTTPS CONNECT) instead
of connecting to the index directly.  No external network and no corporate
proxy required — only loopback — so it runs on GitHub CI.
"""
from .fixtures import *
import os
import socket
import subprocess
import sys
import time
import yaml
from unittest.mock import patch

import pytest

from SciQLop.components.settings.backend.network import (
    SciQLopNetworkSettings,
    apply_proxy_settings,
)
from SciQLop.components.workspaces.backend.uv import find_uv


@pytest.fixture
def tmp_config_dir(tmp_path):
    with patch("SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR", str(tmp_path)):
        yield tmp_path


def _write_proxy_setting(proxy_url: str = "", no_proxy: str = "") -> None:
    with open(SciQLopNetworkSettings.config_file(), "w") as f:
        yaml.safe_dump({"proxy_url": proxy_url, "no_proxy": no_proxy}, f)


class TestPrecedence:
    """In-app setting overrides the environment; an empty setting honors it."""

    def test_in_app_overrides_environment(self, tmp_config_dir):
        _write_proxy_setting(proxy_url="http://override:8080")
        env = {"HTTPS_PROXY": "http://stale-shell-value:9999"}
        apply_proxy_settings(env)
        assert env["HTTPS_PROXY"] == "http://override:8080"
        assert env["HTTP_PROXY"] == "http://override:8080"

    def test_empty_setting_honors_environment(self, tmp_config_dir):
        _write_proxy_setting(proxy_url="")
        env = {"HTTPS_PROXY": "http://from-the-os:8080"}
        apply_proxy_settings(env)
        assert env["HTTPS_PROXY"] == "http://from-the-os:8080"


class TestLauncherWiring:
    """The launcher must apply the proxy to os.environ before workspace prep,
    so the in-process uv runs and the spawned app subprocess inherit it."""

    def test_launcher_applies_proxy_to_os_environ(self, tmp_config_dir):
        _write_proxy_setting(proxy_url="http://launch-proxy:8080")
        from SciQLop.sciqlop_launcher import _apply_proxy_settings

        keys = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")
        saved = {k: os.environ.get(k) for k in keys}
        try:
            for k in keys:
                os.environ.pop(k, None)
            _apply_proxy_settings()
            assert os.environ["HTTPS_PROXY"] == "http://launch-proxy:8080"
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class TestQtApplicationProxy:
    """Qt WebEngine and in-process Qt networking honor the application proxy
    (QNetworkProxy.setApplicationProxy), set from the same configured value."""

    def test_application_proxy_is_set(self, qapp, tmp_config_dir):
        from PySide6.QtNetwork import QNetworkProxy
        from SciQLop.components.settings.backend.network import apply_qt_application_proxy

        _write_proxy_setting(proxy_url="http://proxy.corp:3128")
        try:
            apply_qt_application_proxy()
            proxy = QNetworkProxy.applicationProxy()
            assert proxy.type() == QNetworkProxy.ProxyType.HttpProxy
            assert proxy.hostName() == "proxy.corp"
            assert proxy.port() == 3128
        finally:
            QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))

    def test_application_proxy_noop_when_empty(self, qapp, tmp_config_dir):
        from PySide6.QtNetwork import QNetworkProxy
        from SciQLop.components.settings.backend.network import apply_qt_application_proxy

        _write_proxy_setting(proxy_url="")
        QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        apply_qt_application_proxy()
        assert QNetworkProxy.applicationProxy().type() == QNetworkProxy.ProxyType.NoProxy


class _ProxyProbe:
    """A loopback listener that stands in for an HTTP proxy.

    For HTTPS traffic an HTTP proxy is contacted with ``CONNECT host:443``
    before any TLS, so capturing the first request line proves the client
    routed through us rather than connecting to the index directly.
    """

    def __init__(self):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(1)
        self._srv.settimeout(1.0)
        self.port = self._srv.getsockname()[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def first_request(self, proc: subprocess.Popen, timeout: float = 30.0) -> bytes | None:
        """Return the first request bytes, or None if ``proc`` exits first."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                conn, _ = self._srv.accept()
            except socket.timeout:
                if proc.poll() is not None:
                    return None
                continue
            with conn:
                conn.settimeout(5.0)
                data = b""
                while b"\r\n" not in data and len(data) < 256:
                    chunk = conn.recv(64)
                    if not chunk:
                        break
                    data += chunk
                return data
        return None

    def close(self) -> None:
        self._srv.close()


@pytest.mark.skipif(find_uv() is None, reason="uv binary not available")
def test_uv_routes_through_our_configured_proxy(tmp_config_dir, tmp_path):
    """End-to-end: a configured proxy makes the real uv binary CONNECT to our
    proxy instead of the index host. Regression guard for the proxy hang."""
    uv = find_uv()
    probe = _ProxyProbe()
    _write_proxy_setting(proxy_url=probe.url)

    venv_dir = tmp_path / "probe-venv"
    subprocess.run(
        [uv, "venv", str(venv_dir), "--python", sys.executable],
        check=True, capture_output=True, text=True,
    )
    venv_py = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    env = os.environ.copy()
    for var in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        env.pop(var, None)
    apply_proxy_settings(env)  # SciQLop's own code injects probe.url

    proc = subprocess.Popen(
        [uv, "pip", "install", "--python", str(venv_py), "--no-cache",
         "--index-url", "https://sciqlop-proxy-probe.invalid/simple/",
         "sciqlop-proxy-probe-pkg"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True,
    )
    try:
        request = probe.first_request(proc)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        probe.close()

    assert request is not None, \
        "uv exited without ever contacting the configured proxy (proxy env ignored)"
    assert request.startswith(b"CONNECT"), \
        f"expected an HTTPS CONNECT via the proxy, got {request!r}"
    assert b"sciqlop-proxy-probe.invalid" in request
