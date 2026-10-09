"""Implementation of %install line magic — install packages and record them."""
import shlex

from IPython.core.error import UsageError

from SciQLop.user_api.packages import install_packages


def _join_url_specs(tokens: list[str]) -> list[str]:
    """Re-join ``name @ url`` PEP 508 specs that shlex split on their spaces."""
    specs: list[str] = []
    for token in tokens:
        if specs and (token == "@" or specs[-1].endswith(" @")):
            specs[-1] = f"{specs[-1]} {token}"
        else:
            specs.append(token)
    return specs


def _report(result: dict) -> None:
    if result["installed"]:
        print(f"Installed and recorded: {', '.join(result['installed'])}")
    if result["already_present"]:
        print(f"Already present: {', '.join(result['already_present'])}")
    if result.get("restart_required"):
        print(f"Restart SciQLop to use the new version of: {', '.join(result['restart_required'])}")
    for name, reason in result.get("not_loaded", {}).items():
        print(f"{name} was not loaded: {reason}")


def install_magic(line: str):
    """%install <package> [package2 ...]

    Install Python packages into the current workspace using uv and record them
    in the .sciqlop manifest so they persist across restarts and venv rebuilds.
    A new plugin is loaded immediately. GitHub shorthand works too:
    ``%install gh:owner/repo@tag``.
    """
    packages = _join_url_specs(shlex.split(line))
    if not packages:
        raise UsageError("Usage: %install <package> [package2 ...]")
    options = [p for p in packages if p.startswith("-")]
    if options:
        # Every argument is recorded in the manifest as a requirement: an option
        # there breaks the next workspace sync.
        raise UsageError(f"%install takes package names only, not options ({' '.join(options)}).")

    print(f"Installing: {' '.join(packages)}")
    result = install_packages(*packages)
    if not result["ok"]:
        print(result["error"])
        raise UsageError("Installation failed")
    _report(result)
