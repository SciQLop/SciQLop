"""Asking for JupyterLab starts the kernel and its server if nothing did.

Batch mode never starts them, so opening JupyterLab from a --batch script
raised "Call start() before requesting widget or browser".
"""
from .fixtures import *  # noqa: F401,F403 — qapp/main_window fixtures


class _FakeKernelManager:
    def __init__(self):
        self.calls = []

    def start(self, port=0, cwd=None):
        self.calls.append("start")

    def widget(self):
        self.calls.append("widget")
        return "lab"

    def open_in_browser(self):
        self.calls.append("browser")

    def push_variables(self, variables):
        pass

    def wrap_qt(self, obj):
        return obj

    notebook_hooks = None


def _manager_without_a_started_kernel(monkeypatch):
    from SciQLop.components.workspaces.backend import workspaces_manager as wm_mod
    wm = wm_mod.workspaces_manager_instance()
    fake = _FakeKernelManager()
    monkeypatch.setattr(wm, "_kernel_manager", fake)
    monkeypatch.setattr(wm, "_kernel_started", False)
    monkeypatch.setattr("SciQLop.components.workspaces.ui.notebook_environment.install_notebook_hooks",
                        lambda *a, **k: None)
    return wm, fake


def test_requesting_the_lab_widget_starts_the_kernel_once(main_window, monkeypatch):
    wm, fake = _manager_without_a_started_kernel(monkeypatch)
    assert wm.widget() == "lab"
    wm.widget()
    assert fake.calls == ["start", "widget", "widget"]


def test_opening_lab_in_a_browser_starts_the_kernel(main_window, monkeypatch):
    wm, fake = _manager_without_a_started_kernel(monkeypatch)
    wm.open_in_browser()
    assert fake.calls == ["start", "browser"]
