import os
import json
from pathlib import Path

from SciQLop.components.workspaces.backend.workspaces_manager import WorkspaceManager
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest


def _create_example(tmp_path, name="mms", deps=None, extra_files=None):
    example_dir = tmp_path / "examples" / name
    example_dir.mkdir(parents=True)
    spec = {
        "name": name,
        "description": f"Test {name} example",
        "image": "image.png",
        "notebook": "index.ipynb",
        "tags": ["test"],
        "dependencies": deps or [],
    }
    (example_dir / "example.json").write_text(json.dumps(spec))
    (example_dir / "image.png").write_bytes(b"fake-png")
    (example_dir / "index.ipynb").write_text('{"cells": []}')
    if extra_files:
        for rel_path, content in extra_files.items():
            p = example_dir / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
    return str(example_dir)


def _create_workspace(tmp_path, name="test-ws", deps=None):
    ws_dir = tmp_path / "workspaces" / name
    ws_dir.mkdir(parents=True)
    manifest = WorkspaceManifest(name=name, requires=deps or [])
    manifest.save(ws_dir / "workspace.sciqlop")
    return str(ws_dir)


class TestAddExampleToWorkspace:
    def test_copies_notebook_into_subfolder(self, tmp_path):
        example_path = _create_example(tmp_path)
        ws_dir = _create_workspace(tmp_path)

        missing = WorkspaceManager.add_example_to_workspace(example_path, ws_dir)

        assert os.path.exists(os.path.join(ws_dir, "mms", "index.ipynb"))
        assert missing == []

    def test_skips_metadata_files(self, tmp_path):
        example_path = _create_example(tmp_path)
        ws_dir = _create_workspace(tmp_path)

        WorkspaceManager.add_example_to_workspace(example_path, ws_dir)

        assert not os.path.exists(os.path.join(ws_dir, "mms", "example.json"))
        assert not os.path.exists(os.path.join(ws_dir, "mms", "image.png"))

    def test_copies_subdirectories(self, tmp_path):
        example_path = _create_example(tmp_path, extra_files={
            "Notebooks/demo.ipynb": '{"cells": []}',
        })
        ws_dir = _create_workspace(tmp_path)

        WorkspaceManager.add_example_to_workspace(example_path, ws_dir)

        assert os.path.exists(os.path.join(ws_dir, "mms", "Notebooks", "demo.ipynb"))

    def test_returns_missing_dependencies(self, tmp_path):
        example_path = _create_example(tmp_path, deps=["spok", "numpy"])
        ws_dir = _create_workspace(tmp_path, deps=["numpy"])

        missing = WorkspaceManager.add_example_to_workspace(example_path, ws_dir)

        assert missing == ["spok"]

    def test_overwrites_existing_subfolder(self, tmp_path):
        example_path = _create_example(tmp_path)
        ws_dir = _create_workspace(tmp_path)

        WorkspaceManager.add_example_to_workspace(example_path, ws_dir)
        Path(example_path, "index.ipynb").write_text('{"cells": ["updated"]}')
        WorkspaceManager.add_example_to_workspace(example_path, ws_dir)

        content = Path(ws_dir, "mms", "index.ipynb").read_text()
        assert "updated" in content
