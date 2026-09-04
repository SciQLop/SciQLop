"""The launcher must work without the GUI stack installed.

``pip install sciqlop`` (without the app extra) provides only the launcher's own
dependencies; the heavy stack lives in the workspace venv it creates. If any
module on the launcher's path imports PySide6, SciQLopPlots, speasy or qasync at
import time, that install cannot start — so pin the boundary with a test rather
than rediscovering it from a user's traceback.

The check runs in a subprocess with a meta-path finder that makes those modules
unimportable, because they are installed in the development environment and
cannot be hidden from an in-process import.

That blocklist only catches packages we know to forbid. It can't catch the
opposite mistake -- a launcher-path module importing a package that was never
declared in the base ``dependencies`` at all (e.g. ``packaging``, added by
mistake in a commit that only added it to ``[all]``'s transitive closure).
Such a package is typically present in a dev venv anyway (pulled in
transitively by something in ``dev``/``all``), so the blocklist probe above
can't see the gap. ``test_launcher_thin_install_has_declared_deps`` below
closes that hole by installing *only* the declared base ``dependencies``
(mirroring ``scripts/macos/make_dmg.sh``'s ``uv pip install`` of the launcher)
into an isolated directory and running the same probe against it.
"""

import subprocess
import sys
import textwrap

# Roots the launcher must never pull in at import time. speasy is included
# because SciQLop.core imports it beside SciQLopPlots.
GUI_STACK = [
    "PySide6",
    "shiboken6",
    "SciQLopPlots",
    "speasy",
    "qasync",
    "matplotlib",
    "seaborn",
    "scipy",
    "jupyqt",
    "qtconsole",
    "ipywidgets",
]

_PROBE = textwrap.dedent(
    '''
    import sys, pathlib, tempfile

    BLOCKED = {blocked!r}

    class _Blocker:
        """Make the GUI stack unimportable, as it is in a thin install."""

        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in BLOCKED:
                raise ModuleNotFoundError(f"blocked by test: {{fullname}}")
            return None

    sys.meta_path.insert(0, _Blocker())
    sys.path.insert(0, {repo_root!r})

    # The launcher entry point itself, including the console front end it uses
    # when the GUI stack is absent and the proxy setup it runs before uv.
    from SciQLop.sciqlop_launcher import (
        parse_args,
        resolve_workspace_dir,
        _qt_available,
        _run_on_console,
        _apply_proxy_settings,
    )

    assert _qt_available() is False, "the probe must look like a thin install"
    _apply_proxy_settings()

    # Workspace preparation: manifest, plugin discovery, pyproject, venv, sync.
    from SciQLop.components.workspaces.backend.workspace_setup import (
        prepare_workspace,
        get_globally_enabled_plugins,
        get_plugin_folders,
    )
    from SciQLop.components.workspaces.backend.workspace_project import generate_pyproject_toml
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
    from SciQLop.components.workspaces.backend.workspace_venv import WorkspaceVenv

    # Exercise the pure logic, not just the imports.
    get_plugin_folders()
    get_globally_enabled_plugins()

    workspace = pathlib.Path(tempfile.mkdtemp())
    generate_pyproject_toml(
        WorkspaceManifest.default_manifest("thin"), [], workspace / "pyproject.toml"
    )
    assert (workspace / "pyproject.toml").is_file()

    for name in BLOCKED:
        assert name not in sys.modules, f"{{name}} was imported by the launcher path"

    print("thin launcher chain OK")
    '''
)


def _run_probe(repo_root: str, *, isolated: bool = False) -> subprocess.CompletedProcess:
    # -S: skip the interpreter's own site-packages, so only stdlib plus
    # whatever `repo_root` was set to (an isolated thin install) is visible.
    args = [sys.executable, "-S"] if isolated else [sys.executable]
    return subprocess.run(
        args + ["-c", _PROBE.format(blocked=GUI_STACK, repo_root=repo_root)],
        capture_output=True,
        text=True,
    )


def test_launcher_imports_without_gui_stack(pytestconfig):
    result = _run_probe(str(pytestconfig.rootpath))
    assert result.returncode == 0, (
        "the launcher must import without the GUI stack:\n" + result.stdout + result.stderr
    )
    assert "thin launcher chain OK" in result.stdout


def test_launcher_thin_install_has_declared_deps(pytestconfig, tmp_path):
    """Every launcher-path import must be covered by pyproject.toml's base
    ``dependencies`` -- not just present in the dev venv, where deps of the
    ``dev``/``all`` extras (e.g. ``packaging``) can transitively mask a
    missing declaration.

    Installs only those base dependencies (mirroring the ``uv pip install``
    scripts/macos/make_dmg.sh runs for the launcher) into an isolated
    directory and runs the same probe against that, with the dev venv's own
    site-packages hidden.
    """
    target = tmp_path / "site-packages"
    subprocess.run(
        ["uv", "pip", "install", "-q", "--target", str(target), "--python", sys.executable, str(pytestconfig.rootpath)],
        check=True,
        capture_output=True,
        text=True,
    )

    result = _run_probe(str(target), isolated=True)
    assert result.returncode == 0, (
        "the launcher must import with only its declared base dependencies "
        "installed (no [all] extra):\n" + result.stdout + result.stderr
    )
    assert "thin launcher chain OK" in result.stdout
