from pathlib import Path

import pytest


WELCOME_JS = Path("SciQLop/components/welcome/resources/welcome.js")
BACKEND = Path("SciQLop/components/welcome/backend.py")


def test_new_workspace_requires_name_confirmation_and_passes_name():
    javascript = WELCOME_JS.read_text()
    backend = BACKEND.read_text()

    assert "showNewWorkspaceDialog()" in javascript
    assert "backend.create_workspace(name)" in javascript
    assert "backend.create_workspace();" not in javascript
    assert "@Slot(str)\n    def create_workspace(self, name: str)" in backend


@pytest.mark.parametrize("name", ["", " ", "\t"])
def test_backend_rejects_blank_workspace_names(qapp, monkeypatch, name):
    from SciQLop.components.welcome.backend import WelcomeBackend

    def unexpected_manager():
        raise AssertionError("blank workspace name reached the manager")

    monkeypatch.setattr(
        "SciQLop.components.welcome.backend.workspaces_manager_instance",
        unexpected_manager,
    )
    with pytest.raises(ValueError, match="name"):
        WelcomeBackend().create_workspace(name)
