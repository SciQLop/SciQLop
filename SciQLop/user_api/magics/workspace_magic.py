"""Implementation of %workspace line magic — inspect and manage the current workspace."""
import os
import shlex

from IPython.core.error import UsageError


SUBCOMMANDS = {
    "status": "Show workspace name, path, and summary",
    "deps": "List recorded dependencies",
    "install": "Install packages and record in manifest (alias for %install)",
    "plugins": "List plugin overrides (add/remove)",
    "examples": "List available examples",
    "add-example": "Copy an example into the workspace",
    "help": "Show this help",
}


def _get_workspace():
    from SciQLop.user_api.threading import invoke_on_main_thread

    def _fetch():
        from SciQLop.components.workspaces import workspaces_manager_instance
        wm = workspaces_manager_instance()
        return wm.workspace if wm and wm.has_workspace else None

    return invoke_on_main_thread(_fetch)


def _get_manifest():
    ws = _get_workspace()
    if ws is None:
        raise UsageError("No workspace loaded.")
    return ws._manifest


def _cmd_status():
    ws = _get_workspace()
    if ws is None:
        print("No workspace loaded.")
        return
    m = ws._manifest
    lines = [
        f"Workspace: {m.name}",
        f"Path:      {m.directory}",
    ]
    if m.description:
        lines.append(f"Desc:      {m.description}")
    lines.append(f"Deps:      {len(m.requires)}")
    if m.plugins_add:
        lines.append(f"Plugins+:  {', '.join(m.plugins_add)}")
    if m.plugins_remove:
        lines.append(f"Plugins-:  {', '.join(m.plugins_remove)}")
    print("\n".join(lines))


def _cmd_deps():
    m = _get_manifest()
    if not m.requires:
        print("No dependencies recorded.")
        return
    for dep in m.requires:
        print(f"  {dep}")


def _cmd_install(args: list[str]):
    from SciQLop.user_api.magics.install_magic import install_magic
    install_magic(" ".join(args))


def _cmd_plugins():
    m = _get_manifest()
    if not m.plugins_add and not m.plugins_remove:
        print("No plugin overrides in this workspace.")
        return
    if m.plugins_add:
        print("Enabled (+):")
        for p in m.plugins_add:
            print(f"  + {p}")
    if m.plugins_remove:
        print("Disabled (-):")
        for p in m.plugins_remove:
            print(f"  - {p}")


def _list_examples():
    from SciQLop.components.workspaces.backend.example import Example
    examples_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "examples")
    if not os.path.isdir(examples_root):
        return []
    results = []
    for entry in sorted(os.listdir(examples_root)):
        json_path = os.path.join(examples_root, entry, "example.json")
        if os.path.isfile(json_path):
            try:
                ex = Example(json_path)
                if ex.is_valid:
                    results.append(ex)
            except Exception:
                pass
    return results


def _cmd_examples():
    examples = _list_examples()
    if not examples:
        print("No examples found.")
        return
    for ex in examples:
        tags = f" [{', '.join(ex.tags)}]" if ex.tags else ""
        print(f"  {ex.name}{tags}")
        if ex.description:
            print(f"    {ex.description}")


def _cmd_add_example(args: list[str]):
    if not args:
        raise UsageError("Usage: %workspace add-example <name>")
    target_name = " ".join(args)
    examples = _list_examples()
    match = next((ex for ex in examples if ex.name.lower() == target_name.lower()), None)
    if match is None:
        names = [ex.name for ex in examples]
        raise UsageError(f"Example '{target_name}' not found. Available: {', '.join(names)}")

    from SciQLop.user_api.threading import invoke_on_main_thread

    def _do_add():
        from SciQLop.components.workspaces import workspaces_manager_instance
        wm = workspaces_manager_instance()
        ws = wm.workspace
        missing_deps = wm.add_example_to_workspace(match.directory, ws.workspace_dir)
        return missing_deps

    missing = invoke_on_main_thread(_do_add)
    print(f"Added example '{match.name}' to workspace.")
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print("Run: %workspace install " + " ".join(missing))


def _cmd_help():
    print("Usage: %workspace <subcommand> [args...]\n")
    print("Subcommands:")
    for name, desc in SUBCOMMANDS.items():
        print(f"  {name:<15} {desc}")


DISPATCH = {
    "status": lambda _: _cmd_status(),
    "deps": lambda _: _cmd_deps(),
    "install": _cmd_install,
    "plugins": lambda _: _cmd_plugins(),
    "examples": lambda _: _cmd_examples(),
    "add-example": _cmd_add_example,
    "help": lambda _: _cmd_help(),
}


def workspace_magic(line: str):
    """%workspace [subcommand] [args...]

    Inspect and manage the current SciQLop workspace.

    Subcommands:
      status       Show workspace name, path, and summary (default)
      deps         List recorded dependencies
      install      Install packages and record in manifest
      plugins      List plugin overrides (add/remove)
      examples     List available examples
      add-example  Copy an example into the workspace
      help         Show this help
    """
    parts = shlex.split(line) if line.strip() else []
    subcmd = parts[0] if parts else "status"
    args = parts[1:]

    handler = DISPATCH.get(subcmd)
    if handler is None:
        raise UsageError(f"Unknown subcommand '{subcmd}'. Run %workspace help")
    handler(args)
