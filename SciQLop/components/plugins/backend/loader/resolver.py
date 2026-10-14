# SciQLop/components/plugins/backend/loader/resolver.py
"""Plugin load order from plugin.json dependencies (spec §3.2).

Pure: no imports of plugin code, no Qt. Ties are broken by plugin id so every machine loads in the same order.
"""
import heapq
from dataclasses import dataclass

from packaging.requirements import InvalidRequirement, Requirement


@dataclass(frozen=True)
class Candidate:
    id: str
    version: str
    dependencies: tuple[str, ...] = ()
    optional_dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class Resolution:
    order: tuple[str, ...]
    refused: dict[str, str]
    required: dict[str, frozenset[str]]
    declared: dict[str, frozenset[str]]


class _Dep:
    """A dependency spec as written in plugin.json, kept for messages (packaging reorders specifiers)."""

    def __init__(self, spec: str):
        self.spec = spec
        try:
            self.req = Requirement(spec)
        except InvalidRequirement as e:
            raise InvalidRequirement(f"invalid dependency {spec!r}: {e}") from e
        self.name = self.req.name


def _parse(specs) -> list[_Dep]:
    return [_Dep(s) for s in specs]


def _in_range(dep: _Dep, version: str) -> bool:
    return dep.req.specifier.contains(version, prereleases=True) if str(dep.req.specifier) else True


def _missing_reason(dep: _Dep, candidates, active, refused) -> str | None:
    name = dep.name
    if name in refused:
        return f"needs plugin {name!r}, which was refused: {refused[name]}"
    version = candidates[name].version if name in candidates else active.get(name)
    if version is None:
        return f"needs plugin {name!r}, which is not installed or not enabled"
    if not _in_range(dep, version):
        return f"needs plugin {dep.spec}, but {name} {version} is installed"
    return None


def _refuse_unsatisfied(candidates, active, reqs, refused) -> None:
    changed = True
    while changed:
        changed = False
        for cid in sorted(set(candidates) - set(refused)):
            reason = next(filter(None, (_missing_reason(r, candidates, active, refused) for r in reqs[cid][0])), None)
            if reason:
                refused[cid] = reason
                changed = True


def _edges(cid, candidates, reqs, refused) -> set[str]:
    required, optional = reqs[cid]
    present = {r.name for r in optional if r.name in candidates and r.name not in refused
               and _in_range(r, candidates[r.name].version)}
    return {r.name for r in required if r.name in candidates} | present


def _topological(candidates, reqs, refused) -> list[str]:
    alive = sorted(set(candidates) - set(refused))
    deps = {c: _edges(c, candidates, reqs, refused) & set(alive) for c in alive}
    ready = [c for c in alive if not deps[c]]
    heapq.heapify(ready)
    order = []
    while ready:
        c = heapq.heappop(ready)
        order.append(c)
        for other in alive:
            if c in deps[other]:
                deps[other].discard(c)
                if not deps[other]:
                    heapq.heappush(ready, other)
    return order


def _reachable(start: str, edges: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    todo = list(edges[start])
    while todo:
        node = todo.pop()
        if node not in seen:
            seen.add(node)
            todo.extend(edges[node])
    return seen


def _refuse_cycles(stuck: set[str], candidates, reqs, refused) -> None:
    """Refuse only the plugins that lie on a cycle; their dependents cascade on the next pass.

    simplify: a per-node DFS, O(n * (n + e)) over the stuck set; fine for the few dozen plugins a user installs.
    """
    edges = {c: _edges(c, candidates, reqs, refused) & stuck for c in stuck}
    members = [c for c in sorted(stuck) if c in _reachable(c, edges)]
    message = f"dependency cycle between {', '.join(members)}"
    for cid in members:
        refused[cid] = message


def resolve(candidates: dict[str, Candidate], active: dict[str, str] | None = None) -> Resolution:
    active = active or {}
    refused: dict[str, str] = {}
    reqs = {}
    for cid, c in candidates.items():
        try:
            reqs[cid] = (_parse(c.dependencies), _parse(c.optional_dependencies))
        except InvalidRequirement as e:
            refused[cid] = str(e).splitlines()[0]
            reqs[cid] = ([], [])
    while True:
        _refuse_unsatisfied(candidates, active, reqs, refused)
        order = _topological(candidates, reqs, refused)
        stuck = set(candidates) - set(refused) - set(order)
        if not stuck:
            break
        _refuse_cycles(stuck, candidates, reqs, refused)
    return Resolution(
        order=tuple(order), refused=refused,
        required={c: frozenset(r.name for r in reqs[c][0]) for c in candidates},
        declared={c: frozenset(r.name for r in reqs[c][0] + reqs[c][1]) for c in candidates})
