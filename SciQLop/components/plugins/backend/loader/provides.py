"""Compare a plugin's plugin.json `provides` with what its code registered (spec §3.1)."""
from SciQLop.core import extensions

EXTENSION_POINTS_KEY = "extension_points"


def registered_by(plugin_id: str) -> dict[str, list[str]]:
    points = extensions.all_extension_points()
    found = {ep.id: ep.contributed_by(plugin_id) for ep in points}
    declared = sorted(ep.id for ep in points if ep.owner == plugin_id)
    if declared:
        found[EXTENSION_POINTS_KEY] = declared
    return {k: v for k, v in found.items() if v}


def provides_drift(plugin_id: str, provides: dict[str, list[str]]) -> list[str]:
    actual = registered_by(plugin_id)
    problems = []
    for key in sorted(set(actual) | set(provides)):
        declared, registered = set(provides.get(key, [])), set(actual.get(key, []))
        if declared - registered:
            problems.append(f"{key}: declared in plugin.json but not registered: {', '.join(sorted(declared - registered))}")
        if registered - declared:
            problems.append(f"{key}: registered but not declared in plugin.json: {', '.join(sorted(registered - declared))}")
    return problems
