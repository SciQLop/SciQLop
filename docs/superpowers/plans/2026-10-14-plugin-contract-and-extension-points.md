# Plugin Contract and Extension Points (Tier 1a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plugins declare dependencies on each other, load in a deterministic dependency order through a new `activate(ctx)` contract, contribute to typed owner-tagged extension points, and reach each other's APIs; scenes become the first extension-point client.

**Architecture:** A generic `ExtensionPoint` (core) replaces the scenes `Registry`. A pure resolver orders plugins from their `plugin.json` dependencies; the loader activates them in two phases (`activate`/`load`, then `ready`), records a state per plugin, and hands each new-style plugin a `PluginContext`. Live install paths go through the same resolver. Workspace manifests stop dropping unknown tables.

**Tech Stack:** Python 3.14, PySide6 (signals, main-thread checks), pydantic v2 (`PluginDesc`), `packaging` (PEP 440 specifiers), pytest + pytest-qt.

**Spec:** `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` (sections 2, 3, 4.1, 6, 7, 8, 9.1, 9.4, 10). This plan is Tier 1a. Tier 1b (product kinds, source kinds, data providers, MIME types) and Tier 1c (plot kinds, drop rules, panel tree format) get their own plans after this one lands.

## Global Constraints

- Run everything with `uv run` (`uv run pytest ...`). Never run `uv sync`. Missing module: `uv pip install <pkg>`.
- Never run more than one pytest invocation at a time; never background one "just in case". The full suite takes ~9 min: `uv run pytest -q -p no:cacheprovider`.
- Resumed shells may lack `DISPLAY`: run pytest WITHOUT `--no-xvfb`.
- Work and commit on `main` with explicit pathspecs (`git commit -m ... -- <paths>`). Never stage untracked files you did not create (`importlib.metadata`, `setWidget`, `pydata/`, `.claude/`, docs drafts, `tests/noop_script.py`). Never push.
- `user_api` is published: every existing function keeps its signature, side effects and `replace` behaviour.
- Plugin id = folder name for folder plugins, entry-point name for packaged plugins. `plugin.json` `name` stays the display name.
- A plugin's `version` is its API version (semver). Dependency specifiers are PEP 440, checked against the other plugin's `version`, prereleases allowed.
- Extension-point ids: core `sciqlop.<area>` (scenes: `sciqlop.scenes.bodies`, `sciqlop.scenes.boundaries`, `sciqlop.scenes.scenes`); plugin-declared ones must start with `<plugin id>.`.
- Owners: `activate` plugins own registrations under their id; legacy `load(main_window)` plugins under `legacy:<id>`; anything outside a plugin call under `user`.
- Extension points are main-thread objects: `contribute`/`remove_owner` raise `WrongThread` off the main thread when a `QCoreApplication` exists.
- CI blocking flake8 (`uv run flake8 --select=E9,F63,F7,F82`) must stay clean on touched files.
- Code style: small functions, no comment-decorated blocks, comments only for "why" or links; `simplify:` comments on deliberate shortcuts naming ceiling and upgrade path.

## Rulings (decided while planning; spec updated in Task 9)

- `provides` is keyed by extension-point id (`"sciqlop.scenes.scenes": [...]`) plus the special key `"extension_points"` for EPs the plugin declares. A key per EP id means no schema change when an EP is added. Cost if wrong: the app store shows raw EP ids; a label map fixes it later.
- Scene, body and boundary names are published (`panel.plot_scene("Earth environment")`), so the scenes EPs stay keyed by `item.name`, not `<plugin>.<name>`. The `<plugin>.<name>` rule applies to kinds that saved panel trees reference (Tier 1b/1c).
- Scenes products-tree nodes are created from the scenes EPs' `added` signal (`scenes.tree.follow_registries()`, wired at startup), so a plugin contributing through `ctx.contribute` gets its node too; `user_api.scenes.register_*` stop calling the tree directly.
- Offering to install missing plugin dependencies needs the app-store index fields (sciqlop-appstore repo, spec §3.1). Until then a live install with a missing dependency is refused with a message naming the plugin to install. Cost if wrong: one more manual install step.
- A plugin whose `ready` raises is logged and stays `active` (its phase-1 contributions are in place and dependents already activated).
- `loaded_plugins` stores any API that is not `None` (today: any truthy one).

## Review Focus

1. An existing `load(main_window)` plugin with an old-style `plugin.json` (required fields, no new keys), or a single-file `.py` plugin with no `plugin.json`, loads exactly as before. Test: Task 4 `test_legacy_plugin_loads_as_before`, `test_plugin_without_plugin_json_loads`.
2. A dependency whose `activate` raises refuses its dependents with a message naming it, instead of the dependents crashing later. Test: Task 4 `test_runtime_failure_refuses_dependents`.
3. A malformed `plugin.json` on an already-enabled plugin does not stop it loading (no dependencies known). Test: Task 4 `test_malformed_plugin_json_still_loads`.
4. A plugin live-installed after startup that depends on an already-active plugin activates and can reach it. Test: Task 5 `test_live_plugin_reaches_an_already_active_dependency`.
5. A `.sciqlop` file holding a table SciQLop does not know keeps it through a save. Test: Task 7 `test_unknown_tables_survive_a_save`.

---

### Task 1: ExtensionPoint core

**Files:**
- Create: `SciQLop/core/extensions.py`
- Test: `tests/test_extensions.py`

**Interfaces:**
- Produces: `ExtensionPoint(id, contribution_type, what=None, key=attrgetter("id"), doc="", owner="sciqlop")` with `contribute(item, owner=None, replace=False) -> item`, `get(key) -> item`, `list(**filters) -> list`, `owner_of(key) -> str`, `contributed_by(owner) -> list[str]`, `remove_owner(owner) -> list`, `signals.added/removed: Signal(object)`, attributes `id`, `owner`, `_items`, `_owners`.
- Produces: `declare(ep) -> ep`, `get(ep_id) -> ExtensionPoint`, `all_extension_points() -> list[ExtensionPoint]`, `current_owner() -> str`, `owned_by(owner)` context manager, `USER = "user"`, exceptions `NotRegistered(LookupError)`, `DuplicateContribution(ValueError)`, `WrongThread(RuntimeError)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_extensions.py
"""Extension points: typed, owner-tagged registries (spec §4.1)."""
import threading
from dataclasses import dataclass

import pytest

from SciQLop.core import extensions
from SciQLop.core.extensions import (DuplicateContribution, ExtensionPoint, NotRegistered, WrongThread,
                                     current_owner, owned_by)


@dataclass(frozen=True)
class Kind:
    id: str
    colour: str = "red"


@pytest.fixture
def ep():
    return ExtensionPoint("test.kinds", Kind, what="kind")


@pytest.fixture
def clean_registry():
    saved = dict(extensions._EXTENSION_POINTS)
    yield
    extensions._EXTENSION_POINTS.clear()
    extensions._EXTENSION_POINTS.update(saved)


def test_contribute_then_get_and_list(ep):
    ep.contribute(Kind("a.x", "blue"), owner="a")
    ep.contribute(Kind("b.y"), owner="b")
    assert ep.get("a.x").colour == "blue"
    assert [k.id for k in ep.list(colour="red")] == ["b.y"]


def test_wrong_type_is_refused(ep):
    with pytest.raises(TypeError, match="test.kinds takes Kind, got str"):
        ep.contribute("nope", owner="a")


def test_same_owner_replaces_other_owner_raises(ep):
    ep.contribute(Kind("a.x"), owner="a")
    ep.contribute(Kind("a.x", "green"), owner="a")
    assert ep.get("a.x").colour == "green"
    with pytest.raises(DuplicateContribution, match="kind 'a.x' is already registered by a"):
        ep.contribute(Kind("a.x"), owner="b")


def test_explicit_replace_lets_another_owner_take_over(ep):
    ep.contribute(Kind("a.x"), owner="a")
    ep.contribute(Kind("a.x", "pink"), owner="b", replace=True)
    assert ep.owner_of("a.x") == "b"


def test_missing_key_names_what_exists(ep):
    ep.contribute(Kind("a.x"), owner="a")
    with pytest.raises(NotRegistered, match="no kind named 'zz'; available: a.x"):
        ep.get("zz")


def test_owner_defaults_to_the_current_owner(ep):
    assert current_owner() == "user"
    with owned_by("legacy:old"):
        ep.contribute(Kind("o.k"))
    assert ep.owner_of("o.k") == "legacy:old" and current_owner() == "user"


def test_remove_owner_removes_only_theirs_and_signals(ep, qtbot):
    ep.contribute(Kind("a.x"), owner="a")
    ep.contribute(Kind("b.y"), owner="b")
    removed = []
    ep.signals.removed.connect(removed.append)
    assert [k.id for k in ep.remove_owner("a")] == ["a.x"]
    assert [k.id for k in removed] == ["a.x"] and ep.contributed_by("b") == ["b.y"]


def test_added_signal_fires(ep, qtbot):
    added = []
    ep.signals.added.connect(added.append)
    ep.contribute(Kind("a.x"), owner="a")
    assert [k.id for k in added] == ["a.x"]


def test_contributing_off_the_main_thread_raises(ep, qapp):
    errors = []

    def worker():
        try:
            ep.contribute(Kind("a.x"), owner="a")
        except WrongThread as e:
            errors.append(e)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert errors and "main thread" in str(errors[0])


def test_declare_and_lookup(clean_registry):
    ep = extensions.declare(ExtensionPoint("test.declared", Kind, owner="tester"))
    assert extensions.get("test.declared") is ep and ep.owner == "tester"
    with pytest.raises(DuplicateContribution, match="extension point 'test.declared' is already declared by tester"):
        extensions.declare(ExtensionPoint("test.declared", Kind))
    with pytest.raises(NotRegistered, match="no extension point named 'test.nope'"):
        extensions.get("test.nope")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_extensions.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'SciQLop.core.extensions'`.

- [ ] **Step 3: Write the implementation**

```python
# SciQLop/core/extensions.py
"""Extension points: typed, owner-tagged registries that the core and plugins contribute to.

Design: docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md §4.
"""
import contextlib
import contextvars
from operator import attrgetter
from typing import Callable, Generic, Iterator, TypeVar

from PySide6.QtCore import QObject, Signal

T = TypeVar("T")

USER = "user"
_current_owner = contextvars.ContextVar("sciqlop_extension_owner", default=USER)
_EXTENSION_POINTS: dict = {}


class NotRegistered(LookupError):
    pass


class DuplicateContribution(ValueError):
    pass


class WrongThread(RuntimeError):
    pass


def current_owner() -> str:
    return _current_owner.get()


@contextlib.contextmanager
def owned_by(owner: str) -> Iterator[None]:
    token = _current_owner.set(owner)
    try:
        yield
    finally:
        _current_owner.reset(token)


def _require_main_thread(action: str) -> None:
    from PySide6.QtCore import QCoreApplication, QThread
    app = QCoreApplication.instance()
    if app is not None and QThread.currentThread() != app.thread():
        raise WrongThread(f"{action} must run on the main thread")


class _Signals(QObject):
    added = Signal(object)
    removed = Signal(object)


class ExtensionPoint(Generic[T]):
    """A registry of contributions of one type, each recorded with the plugin that made it."""

    def __init__(self, id: str, contribution_type: type, what: str | None = None,
                 key: Callable[[T], str] = attrgetter("id"), doc: str = "", owner: str = "sciqlop"):
        self.id, self.contribution_type, self.doc, self.owner = id, contribution_type, doc, owner
        self._what = what or id
        self._key = key
        self._items: dict[str, T] = {}
        self._owners: dict[str, str] = {}
        self.signals = _Signals()

    def contribute(self, item: T, owner: str | None = None, replace: bool = False) -> T:
        _require_main_thread(f"contributing to {self.id}")
        if not isinstance(item, self.contribution_type):
            raise TypeError(f"{self.id} takes {self.contribution_type.__name__}, got {type(item).__name__}")
        key, owner = self._key(item), owner or current_owner()
        previous = self._owners.get(key) if key in self._items else None
        if previous not in (None, owner) and not replace:
            raise DuplicateContribution(f"{self._what} {key!r} is already registered by {previous}")
        self._items[key] = item
        self._owners[key] = owner
        self.signals.added.emit(item)
        return item

    def get(self, key: str) -> T:
        if key not in self._items:
            raise NotRegistered(f"no {self._what} named {key!r}; available: {', '.join(sorted(self._items))}")
        return self._items[key]

    def list(self, **filters) -> list[T]:
        return [i for i in self._items.values() if all(getattr(i, k, None) == v for k, v in filters.items())]

    def owner_of(self, key: str) -> str:
        self.get(key)
        return self._owners[key]

    def contributed_by(self, owner: str) -> list[str]:
        return sorted(k for k in self._items if self._owners.get(k) == owner)

    def remove_owner(self, owner: str) -> list[T]:
        _require_main_thread(f"removing contributions from {self.id}")
        removed = [self._items.pop(k) for k in self.contributed_by(owner)]
        for item in removed:
            self._owners.pop(self._key(item), None)
            self.signals.removed.emit(item)
        return removed


def declare(ep: ExtensionPoint) -> ExtensionPoint:
    if ep.id in _EXTENSION_POINTS:
        raise DuplicateContribution(f"extension point {ep.id!r} is already declared by {_EXTENSION_POINTS[ep.id].owner}")
    _EXTENSION_POINTS[ep.id] = ep
    return ep


def get(ep_id: str) -> ExtensionPoint:
    if ep_id not in _EXTENSION_POINTS:
        raise NotRegistered(f"no extension point named {ep_id!r}; available: {', '.join(sorted(_EXTENSION_POINTS))}")
    return _EXTENSION_POINTS[ep_id]


def all_extension_points() -> list[ExtensionPoint]:
    return list(_EXTENSION_POINTS.values())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_extensions.py -q`
Expected: `10 passed`.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/core/extensions.py tests/test_extensions.py
git commit -m "feat(core): extension points, typed owner-tagged registries" -- SciQLop/core/extensions.py tests/test_extensions.py
```

---

### Task 2: PluginDesc gains optional dependencies and provides

**Files:**
- Modify: `SciQLop/components/plugins/backend/loader/plugin_desc.py` (whole file, 26 lines)
- Test: `tests/test_plugin_desc.py`

**Interfaces:**
- Produces: `PluginDesc` fields `name: str`, `version: str`, `description: str = ""`, `authors: list[Author] = []`, `license: str = ""`, `python_dependencies`, `dependencies: list[str]`, `optional_dependencies: list[str]`, `provides: dict[str, list[str]]`, `disabled: bool`; `PluginDesc.from_json(path)` warns on unknown keys.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_plugin_desc.py
"""plugin.json: a minimal file is name + version; new keys are dependencies, optional_dependencies, provides."""
import json

from SciQLop.components.plugins.backend.loader import plugin_desc
from SciQLop.components.plugins.backend.loader.plugin_desc import PluginDesc


def _write(tmp_path, data):
    path = tmp_path / "plugin.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_minimal_plugin_json_is_name_and_version(tmp_path):
    desc = PluginDesc.from_json(_write(tmp_path, {"name": "Mini", "version": "0.1.0"}))
    assert (desc.description, desc.authors, desc.license) == ("", [], "")
    assert (desc.dependencies, desc.optional_dependencies, desc.provides) == ([], [], {})


def test_new_keys_are_read(tmp_path):
    desc = PluginDesc.from_json(_write(tmp_path, {
        "name": "Study", "version": "1.0.0", "dependencies": ["vdf>=1.2,<2"],
        "optional_dependencies": ["mars"], "provides": {"sciqlop.scenes.scenes": ["Jupiter"]}}))
    assert desc.dependencies == ["vdf>=1.2,<2"] and desc.optional_dependencies == ["mars"]
    assert desc.provides == {"sciqlop.scenes.scenes": ["Jupiter"]}


def test_old_style_plugin_json_still_validates(tmp_path):
    desc = PluginDesc.from_json(_write(tmp_path, {
        "name": "Old", "version": "1.0", "description": "x",
        "authors": [{"name": "a", "email": "a@b.c", "organization": "o"}], "license": "MIT",
        "python_dependencies": ["numpy"], "dependencies": ["tscat_catalogs"]}))
    assert desc.dependencies == ["tscat_catalogs"]


def test_unknown_keys_are_reported_not_silently_dropped(tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr(plugin_desc.log, "warning", lambda *a: warnings.append(a))
    PluginDesc.from_json(_write(tmp_path, {"name": "T", "version": "1", "provide": {}}))
    assert warnings and "provide" in str(warnings[0])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_plugin_desc.py -q`
Expected: FAIL — `test_minimal_plugin_json_is_name_and_version` with a pydantic `ValidationError` (description/authors/license required), and `module ... has no attribute 'log'`.

- [ ] **Step 3: Write the implementation**

```python
# SciQLop/components/plugins/backend/loader/plugin_desc.py
import json
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)


class Author(BaseModel):
    name: str
    email: str
    organization: str


class PluginDesc(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    version: str
    description: str = ""
    authors: List[Author] = Field(default_factory=list)
    license: str = ""
    python_dependencies: List[str] = Field(default_factory=list, description="Required python packages")
    dependencies: List[str] = Field(default_factory=list, description="Required plugins, PEP 440 specifiers")
    optional_dependencies: List[str] = Field(default_factory=list, description="Plugins used when present")
    provides: dict[str, List[str]] = Field(default_factory=dict,
                                           description="Extension point id -> contribution ids, for the app store")
    disabled: bool = Field(default=False, description="Whether the plugin is disabled by default")

    @staticmethod
    def from_json(path: str) -> "PluginDesc":
        with open(path, "r") as f:
            desc = PluginDesc(**json.load(f))
        if desc.model_extra:
            log.warning("%s: unknown keys ignored: %s", path, ", ".join(sorted(desc.model_extra)))
        return desc
```

- [ ] **Step 4: Run the tests to verify they pass, plus the existing loader tests**

Run: `uv run pytest tests/test_plugin_desc.py tests/test_plugin_load_gate.py tests/test_plugin_deps.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(plugins): plugin.json optional_dependencies and provides, minimal file is name + version" -- SciQLop/components/plugins/backend/loader/plugin_desc.py tests/test_plugin_desc.py
```
(`git add tests/test_plugin_desc.py` first.)

---

### Task 3: Dependency resolver

**Files:**
- Create: `SciQLop/components/plugins/backend/loader/resolver.py`
- Test: `tests/test_plugin_resolver.py`

**Interfaces:**
- Produces: `Candidate(id: str, version: str, dependencies: tuple[str, ...] = (), optional_dependencies: tuple[str, ...] = ())` (frozen dataclass).
- Produces: `Resolution(order: tuple[str, ...], refused: dict[str, str], required: dict[str, frozenset[str]], declared: dict[str, frozenset[str]])`. `required[id]` = names of required deps; `declared[id]` = names of required + optional deps.
- Produces: `resolve(candidates: dict[str, Candidate], active: dict[str, str] | None = None) -> Resolution`. `active` = id -> version of plugins already running (live install).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_plugin_resolver.py
"""Plugin load order from plugin.json dependencies (spec §3.2): deterministic, refusals named."""
from SciQLop.components.plugins.backend.loader.resolver import Candidate, resolve


def _c(id, version="1.0.0", deps=(), opt=()):
    return Candidate(id, version, tuple(deps), tuple(opt))


def test_dependencies_load_first_ties_by_name():
    r = resolve({"study": _c("study", deps=["vdf", "earth"]), "vdf": _c("vdf"), "earth": _c("earth"),
                 "aaa": _c("aaa")})
    assert r.order == ("aaa", "earth", "vdf", "study") and r.refused == {}


def test_missing_dependency_refuses_and_cascades():
    r = resolve({"study": _c("study", deps=["vdf"]), "user": _c("user", deps=["study"])})
    assert r.order == ()
    assert r.refused["study"] == "needs plugin 'vdf', which is not installed or not enabled"
    assert r.refused["user"] == "needs plugin 'study', which was refused: needs plugin 'vdf', " \
                                "which is not installed or not enabled"


def test_out_of_range_version_is_refused_with_both_versions():
    r = resolve({"study": _c("study", deps=["vdf>=1.2,<2"]), "vdf": _c("vdf", "2.0.0")})
    assert r.order == ("vdf",)
    assert r.refused["study"] == "needs plugin vdf>=1.2,<2, but vdf 2.0.0 is installed"


def test_present_optional_dependency_is_ordered_first_absent_one_ignored():
    r = resolve({"earth": _c("earth", opt=["mars", "pluto"]), "mars": _c("mars")})
    assert r.order == ("mars", "earth") and r.declared["earth"] == frozenset({"mars", "pluto"})
    assert r.required["earth"] == frozenset()


def test_cycle_members_are_refused():
    r = resolve({"a": _c("a", deps=["b"]), "b": _c("b", deps=["a"]), "c": _c("c")})
    assert r.order == ("c",)
    assert r.refused["a"] == r.refused["b"] == "dependency cycle between a, b"


def test_already_active_plugins_satisfy_dependencies():
    r = resolve({"study": _c("study", deps=["vdf>=1"])}, active={"vdf": "1.3.0"})
    assert r.order == ("study",)


def test_invalid_specifier_is_refused():
    r = resolve({"study": _c("study", deps=["vdf >>> 1"])})
    assert r.refused["study"].startswith("invalid dependency 'vdf >>> 1'")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_plugin_resolver.py -q`
Expected: collection error, `No module named '...resolver'`.

- [ ] **Step 3: Write the implementation**

```python
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


def _parse(specs) -> list[Requirement]:
    return [Requirement(s) for s in specs]


def _in_range(req: Requirement, version: str) -> bool:
    return req.specifier.contains(version, prereleases=True) if str(req.specifier) else True


def _missing_reason(req: Requirement, candidates, active, refused) -> str | None:
    name = req.name
    if name in refused:
        return f"needs plugin {name!r}, which was refused: {refused[name]}"
    version = candidates[name].version if name in candidates else active.get(name)
    if version is None:
        return f"needs plugin {name!r}, which is not installed or not enabled"
    if not _in_range(req, version):
        return f"needs plugin {req}, but {name} {version} is installed"
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


def resolve(candidates: dict[str, Candidate], active: dict[str, str] | None = None) -> Resolution:
    active = active or {}
    refused: dict[str, str] = {}
    reqs = {}
    for cid, c in candidates.items():
        try:
            reqs[cid] = (_parse(c.dependencies), _parse(c.optional_dependencies))
        except InvalidRequirement as e:
            refused[cid] = f"invalid dependency {str(e).split(chr(10))[0]}"
            reqs[cid] = ([], [])
    while True:
        _refuse_unsatisfied(candidates, active, reqs, refused)
        order = _topological(candidates, reqs, refused)
        stuck = sorted(set(candidates) - set(refused) - set(order))
        if not stuck:
            break
        for cid in stuck:
            refused[cid] = f"dependency cycle between {', '.join(stuck)}"
    return Resolution(
        order=tuple(order), refused=refused,
        required={c: frozenset(r.name for r in reqs[c][0]) for c in candidates},
        declared={c: frozenset(r.name for r in reqs[c][0] + reqs[c][1]) for c in candidates})
```

Note on the invalid-specifier message: `packaging` raises `InvalidRequirement` whose first line quotes the spec; the test only checks the prefix `invalid dependency 'vdf >>> 1'`. If the installed `packaging` words it differently, build the message as `f"invalid dependency {spec!r}: {e}"` by parsing each spec in a loop that knows `spec` — keep the test's prefix.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_plugin_resolver.py -q`
Expected: `7 passed`. A cycle member's dependents (none here) are refused on the next `_refuse_unsatisfied` pass.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plugins/backend/loader/resolver.py tests/test_plugin_resolver.py
git commit -m "feat(plugins): resolve plugin load order from plugin.json dependencies" -- SciQLop/components/plugins/backend/loader/resolver.py tests/test_plugin_resolver.py
```

---

### Task 4: PluginContext and two-phase activation at startup

**Files:**
- Create: `SciQLop/components/plugins/backend/loader/context.py`
- Modify: `SciQLop/components/plugins/backend/loader/loader.py` (replace `load_plugin` lines 70-84, `_load_entry_point_plugin` lines 159-170, `load_one`/`load_all` lines 214-226; keep everything else)
- Modify: `SciQLop/components/plugins/backend/loader/__init__.py` (export `activate_all`, `STATES`)
- Test: `tests/test_plugin_activation.py`

**Interfaces:**
- Consumes: Task 1 `extensions.declare/get/ExtensionPoint/owned_by`; Task 2 `PluginDesc`; Task 3 `resolve/Candidate/Resolution`.
- Produces (context.py): `PluginState(status: str, version: str, reason: str = "", api=None, module=None, context=None)` dataclass, `STATES: dict[str, PluginState]`, `active_versions() -> dict[str, str]`, `UndeclaredDependency(LookupError)`, `PluginUnavailable(LookupError)`, `PluginContext(name, version, main_window, declared: frozenset[str])` with `extension_point(id, contribution_type, doc="", key=attrgetter("id"))`, `contribute(ep_id, item, replace=False)`, `plugin(name)`, `has(name)`.
- Produces (loader.py): `activate_all(plugin_list: list[tuple[str | None, str]], main_window, ep_plugins=None) -> dict[str, object]`; `load_one`, `load_all`, `load_plugin` keep their signatures.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_plugin_activation.py
"""Two-phase plugin activation (spec §3.2-3.3): order, states, ctx, legacy plugins unchanged."""
import json
import textwrap

import pytest

from SciQLop.components.plugins.backend.loader import context, loader
from SciQLop.core import extensions


@pytest.fixture
def fresh(qapp):
    saved = (dict(context.STATES), set(loader._attempted), dict(vars(loader.loaded_plugins)),
             dict(extensions._EXTENSION_POINTS))
    yield
    for live, old in zip((context.STATES, loader._attempted, vars(loader.loaded_plugins),
                          extensions._EXTENSION_POINTS), saved):
        live.clear()
        live.update(old)


def _plugin(folder, name, code, desc=None):
    pkg = folder / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(textwrap.dedent(code))
    if desc is not None:
        (pkg / "plugin.json").write_text(desc if isinstance(desc, str) else json.dumps(desc))
    return (str(folder), name)


def _desc(**kw):
    return {"name": kw.pop("display", "x"), "version": kw.pop("version", "1.0.0"), **kw}


def test_dependencies_activate_first_and_reach_each_other(tmp_path, fresh):
    plugins = [
        _plugin(tmp_path, "act_study", """
            GOT = []
            def activate(ctx):
                GOT.append(ctx.plugin("act_vdf").answer)
        """, _desc(dependencies=["act_vdf>=1"])),
        _plugin(tmp_path, "act_vdf", """
            class Api:
                answer = 42
            def activate(ctx):
                return Api()
        """, _desc()),
    ]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    import sys
    assert sys.modules["act_study"].GOT == [42]
    assert [n for n in context.STATES if n.startswith("act_")] == ["act_vdf", "act_study"]


def test_undeclared_dependency_raises(tmp_path, fresh):
    plugins = [
        _plugin(tmp_path, "und_a", "def activate(ctx):\n    return 1\n", _desc()),
        _plugin(tmp_path, "und_b", "def activate(ctx):\n    ctx.plugin('und_a')\n", _desc()),
    ]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert context.STATES["und_b"].status == "failed"
    assert "und_b uses plugin 'und_a' without declaring it" in context.STATES["und_b"].reason


def test_runtime_failure_refuses_dependents(tmp_path, fresh):
    plugins = [
        _plugin(tmp_path, "rf_base", "def activate(ctx):\n    raise RuntimeError('boom')\n", _desc()),
        _plugin(tmp_path, "rf_user", "def activate(ctx):\n    return 1\n", _desc(dependencies=["rf_base"])),
    ]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert context.STATES["rf_base"].status == "failed" and "boom" in context.STATES["rf_base"].reason
    assert context.STATES["rf_user"].status == "refused"
    assert "needs plugin 'rf_base', which failed: RuntimeError: boom" == context.STATES["rf_user"].reason


def test_missing_dependency_is_refused_and_named(tmp_path, fresh):
    plugins = [_plugin(tmp_path, "md_user", "def activate(ctx):\n    return 1\n", _desc(dependencies=["md_gone"]))]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert context.STATES["md_user"].reason == "needs plugin 'md_gone', which is not installed or not enabled"


def test_legacy_plugin_loads_as_before(tmp_path, fresh):
    old_desc = {"name": "Old", "version": "1.0", "description": "x", "authors": [], "license": "MIT"}
    plugins = [_plugin(tmp_path, "legacy_p", """
        from SciQLop.core.extensions import current_owner
        def load(main_window):
            return ("LOADED", main_window, current_owner())
    """, old_desc)]
    mw = object()
    result = loader.activate_all(plugins, main_window=mw, ep_plugins={})
    assert result["legacy_p"] == ("LOADED", mw, "legacy:legacy_p")
    assert loader.loaded_plugins.legacy_p == ("LOADED", mw, "legacy:legacy_p")


def test_plugin_without_plugin_json_loads(tmp_path, fresh):
    plugins = [_plugin(tmp_path, "nojson_p", "def load(main_window):\n    return 'ok'\n")]
    assert loader.activate_all(plugins, main_window=object(), ep_plugins={})["nojson_p"] == "ok"


def test_malformed_plugin_json_still_loads(tmp_path, fresh):
    plugins = [_plugin(tmp_path, "bad_json_p", "def load(main_window):\n    return 'ok'\n", "{ not json")]
    assert loader.activate_all(plugins, main_window=object(), ep_plugins={})["bad_json_p"] == "ok"


def test_none_api_is_active_but_not_stored(tmp_path, fresh):
    plugins = [_plugin(tmp_path, "none_api", "def activate(ctx):\n    return None\n", _desc())]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert context.STATES["none_api"].status == "active" and not hasattr(loader.loaded_plugins, "none_api")


def test_plugin_declares_an_extension_point_others_fill_in_ready(tmp_path, fresh):
    plugins = [
        _plugin(tmp_path, "ep_owner", """
            from dataclasses import dataclass
            @dataclass(frozen=True)
            class Method:
                id: str
            SEEN = []
            def activate(ctx):
                ctx.extension_point("ep_owner.methods", Method)
                return Method
            def ready(ctx):
                from SciQLop.core import extensions
                SEEN.extend(m.id for m in extensions.get("ep_owner.methods").list())
        """, _desc()),
        _plugin(tmp_path, "ep_filler", """
            def activate(ctx):
                Method = ctx.plugin("ep_owner")
                ctx.contribute("ep_owner.methods", Method("ep_filler.fast"))
        """, _desc(dependencies=["ep_owner"])),
    ]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    import sys
    assert sys.modules["ep_owner"].SEEN == ["ep_filler.fast"]
    assert extensions.get("ep_owner.methods").owner_of("ep_filler.fast") == "ep_filler"


def test_extension_point_id_must_start_with_the_plugin_id(tmp_path, fresh):
    plugins = [_plugin(tmp_path, "badid_p", "def activate(ctx):\n    ctx.extension_point('other.x', object)\n",
                       _desc())]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert "must start with 'badid_p.'" in context.STATES["badid_p"].reason


def test_has_reports_present_optional_dependency(tmp_path, fresh):
    plugins = [
        _plugin(tmp_path, "opt_mars", "def activate(ctx):\n    return 1\n", _desc()),
        _plugin(tmp_path, "opt_earth", """
            FOUND = []
            def activate(ctx):
                FOUND.extend([ctx.has("opt_mars"), ctx.has("opt_pluto")])
        """, _desc(optional_dependencies=["opt_mars", "opt_pluto"])),
    ]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    import sys
    assert sys.modules["opt_earth"].FOUND == [True, False]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_plugin_activation.py -q`
Expected: FAIL — `ImportError: cannot import name 'context'`.

- [ ] **Step 3: Write `context.py`**

```python
# SciQLop/components/plugins/backend/loader/context.py
"""What a plugin's activate(ctx) receives, and the state of every plugin SciQLop tried (spec §3.3)."""
from dataclasses import dataclass
from operator import attrgetter

from SciQLop.core import extensions


class UndeclaredDependency(LookupError):
    pass


class PluginUnavailable(LookupError):
    pass


@dataclass
class PluginState:
    status: str              # "active", "failed" or "refused"
    version: str
    reason: str = ""
    api: object = None
    module: object = None
    context: object = None


STATES: dict[str, PluginState] = {}


def active_versions() -> dict[str, str]:
    return {name: s.version for name, s in STATES.items() if s.status == "active"}


def _describe(name: str) -> str:
    state = STATES.get(name)
    if state is None:
        return "not loaded"
    return f"{state.status}: {state.reason}" if state.reason else state.status


class PluginContext:
    def __init__(self, name: str, version: str, main_window, declared: frozenset[str]):
        self.name, self.version, self.main_window = name, version, main_window
        self._declared = declared

    def extension_point(self, id: str, contribution_type: type, doc: str = "", key=attrgetter("id")):
        if not id.startswith(f"{self.name}."):
            raise ValueError(f"extension point {id!r} of plugin {self.name} must start with {self.name + '.'!r}")
        return extensions.declare(extensions.ExtensionPoint(id, contribution_type, key=key, doc=doc,
                                                            owner=self.name))

    def contribute(self, ep_id: str, item, replace: bool = False):
        return extensions.get(ep_id).contribute(item, owner=self.name, replace=replace)

    def plugin(self, name: str):
        if name not in self._declared:
            raise UndeclaredDependency(f"{self.name} uses plugin {name!r} without declaring it in plugin.json "
                                       f"dependencies or optional_dependencies")
        if STATES.get(name) is None or STATES[name].status != "active":
            raise PluginUnavailable(f"{self.name} needs plugin {name!r}, which is {_describe(name)}")
        return STATES[name].api

    def has(self, name: str) -> bool:
        return name in self._declared and STATES.get(name) is not None and STATES[name].status == "active"
```

- [ ] **Step 4: Rewrite the activation part of `loader.py`**

Replace `load_plugin` (lines 70-84) with:

```python
def load_plugin(path, name, main_window):
    return load_one(path, name, main_window)
```

Delete `_load_entry_point_plugin` (lines 159-170). Replace `load_one` and `load_all` (lines 214-226) with the block below, and add `from dataclasses import dataclass` plus `from pathlib import Path` to the imports at the top:

```python
@dataclass(frozen=True)
class _Entry:
    folder: Optional[str]
    name: str
    desc: object  # PluginDesc or None

    @property
    def candidate(self):
        from .resolver import Candidate
        if self.desc is None:
            return Candidate(self.name, "0")
        return Candidate(self.name, self.desc.version, tuple(self.desc.dependencies),
                         tuple(self.desc.optional_dependencies))


def _read_desc(path) -> object:
    from .plugin_desc import PluginDesc
    if path is None or not os.path.isfile(path):
        return None
    try:
        return PluginDesc.from_json(str(path))
    except Exception as e:
        log.warning(f"Ignoring {path}: {e}")
        return None


def _entry_point_desc_path(ep) -> Optional[Path]:
    """plugin.json shipped next to the entry point's module, found in the distribution's file list.

    simplify: editable installs often list no package files, so their plugin.json is not found and the
    plugin loads without dependencies. Upgrade path: fall back to importlib.util.find_spec(ep.module)."""
    files = ep.dist.files if ep.dist is not None else None
    if not files:
        return None
    parts = ep.module.split(".")
    wanted = {"/".join(parts + ["plugin.json"]), "/".join(parts[:-1] + ["plugin.json"])}
    found = next((f for f in files if f.as_posix() in wanted), None)
    return Path(ep.dist.locate_file(found)) if found is not None else None


def _desc(folder, name, ep_plugins):
    if folder is None:
        return _read_desc(_entry_point_desc_path(ep_plugins[name]))
    return _read_desc(os.path.join(folder, name, "plugin.json"))


def _import(entry: _Entry, ep_plugins):
    mod = ep_plugins[entry.name].load() if entry.folder is None else load_module(entry.folder, entry.name)
    if mod is None:
        raise ImportError(f"could not import plugin {entry.name} (see the log)")
    return mod


def _call_entry_function(mod, ctx, main_window):
    if hasattr(mod, "activate"):
        with owned_by(ctx.name):
            return mod.activate(ctx)
    with owned_by(f"legacy:{ctx.name}"):
        return mod.load(main_window)


def _activate_one(entry: _Entry, main_window, declared, ep_plugins) -> PluginState:
    version = entry.candidate.version
    ctx = PluginContext(entry.name, version, main_window, declared)
    try:
        mod = _import(entry, ep_plugins)
        log.info(f"Loading {entry.name}")
        api = _call_entry_function(mod, ctx, main_window)
    except Exception as e:
        log.error(f"Plugin {entry.name} failed to load: {e}")
        log.error(f"Traceback: {traceback.format_exc()}")
        return PluginState("failed", version, reason=f"{type(e).__name__}: {e}")
    if api is not None:
        loaded_plugins.__dict__[entry.name] = api
    return PluginState("active", version, api=api, module=mod, context=ctx)


def _ready(name: str) -> None:
    state = STATES[name]
    ready = getattr(state.module, "ready", None)
    if state.status != "active" or ready is None or not hasattr(state.module, "activate"):
        return
    try:
        with owned_by(name):
            ready(state.context)
    except Exception as e:
        log.error(f"Plugin {name}: ready() failed, its activate() contributions stay: {e}")
        log.error(f"Traceback: {traceback.format_exc()}")


def _refuse(name: str, version: str, reason: str) -> None:
    STATES[name] = PluginState("refused", version, reason=reason)
    log.warning(f"Plugin {name} not loaded: {reason}")


def _blocked_by(required) -> Optional[str]:
    failed = sorted(d for d in required if d in STATES and STATES[d].status != "active")
    if not failed:
        return None
    state = STATES[failed[0]]
    return f"needs plugin {failed[0]!r}, which {state.status}: {state.reason}"


def activate_all(plugin_list, main_window, ep_plugins=None) -> dict:
    """Activate *plugin_list* [(folder or None, name)] in dependency order, then run their ready() hooks."""
    from .resolver import resolve
    ep_plugins = ep_plugins if ep_plugins is not None else _discover_entry_point_plugins()
    entries = {name: _Entry(folder, name, _desc(folder, name, ep_plugins)) for folder, name in plugin_list}
    _attempted.update(entries)
    resolution = resolve({n: e.candidate for n, e in entries.items()}, active_versions())
    for name, reason in resolution.refused.items():
        _refuse(name, entries[name].candidate.version, reason)
    for name in resolution.order:
        blocked = _blocked_by(resolution.required[name])
        if blocked:
            _refuse(name, entries[name].candidate.version, blocked)
        else:
            STATES[name] = _activate_one(entries[name], main_window, resolution.declared[name], ep_plugins)
    for name in resolution.order:
        _ready(name)
    return {name: STATES[name].api for name in entries}


def load_one(folder, name, main_window, ep_plugins=None):
    return activate_all([(folder, name)], main_window, ep_plugins).get(name)


def load_all(main_window):
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings
    ep_plugins = _discover_entry_point_plugins()
    with SciQLopPluginsSettings() as settings:
        plugin_list = _enabled_plugins(settings, ep_plugins)
    return activate_all(plugin_list, main_window, ep_plugins)
```

Add near the top of `loader.py` (after the logger):

```python
from SciQLop.core.extensions import owned_by
from .context import STATES, PluginContext, PluginState, active_versions
```

Update `SciQLop/components/plugins/backend/loader/__init__.py`:

```python
from .loader import activate_all, load_all, loaded_plugins, load_plugin, plugins_folders
from .context import STATES
```

- [ ] **Step 5: Run the new tests, then the existing plugin tests**

Run: `uv run pytest tests/test_plugin_activation.py -q`
Expected: `11 passed`.
Run: `uv run pytest tests/test_plugin_load_gate.py tests/test_plugins_live_loading.py tests/test_appstore_install.py tests/test_plugin_compat.py tests/test_sciqlop_app_incompatible_plugins_notice.py -q`
Expected: all pass. If one fails because it asserted on the removed `_load_entry_point_plugin`, point it at `load_one(None, name, mw, {name: ep})` with the same assertion.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/plugins/backend/loader/context.py tests/test_plugin_activation.py
git commit -m "feat(plugins): activate(ctx) contract, dependency-ordered two-phase loading, plugin states" -- SciQLop/components/plugins/backend/loader/context.py SciQLop/components/plugins/backend/loader/loader.py SciQLop/components/plugins/backend/loader/__init__.py tests/test_plugin_activation.py
```

---

### Task 5: Live install goes through the resolver and reports failures

**Files:**
- Modify: `SciQLop/components/plugins/backend/live_loader.py:61-66` (`_load`)
- Modify: `SciQLop/components/appstore/backend.py:135-171` (`_try_load_plugin`)
- Test: `tests/test_plugin_live_activation.py`

**Interfaces:**
- Consumes: Task 4 `loader.activate_all`, `context.STATES`.
- Produces: `_try_load_plugin(dist_name) -> str | None` now also returns a reason when a matching plugin failed or was refused (existing callers already report it as "not loaded").

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_plugin_live_activation.py
"""Plugins loaded after startup go through the same resolver (spec §3.2, live install)."""
import json
import textwrap
from types import SimpleNamespace

import pytest

from SciQLop.components.plugins.backend.loader import context, loader
from tests.test_appstore_install import tmp_config_dir  # noqa: F401  (fixture)
from tests.test_plugin_activation import fresh  # noqa: F401  (fixture)


def _plugin(folder, name, code, deps=()):
    pkg = folder / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(textwrap.dedent(code))
    (pkg / "plugin.json").write_text(json.dumps({"name": name, "version": "1.0.0", "dependencies": list(deps)}))
    return (str(folder), name)


def test_live_plugin_reaches_an_already_active_dependency(tmp_path, fresh):  # noqa: F811
    base = _plugin(tmp_path, "live_base", "def activate(ctx):\n    return 7\n")
    loader.activate_all([base], main_window=object(), ep_plugins={})
    late = _plugin(tmp_path, "live_late", """
        GOT = []
        def activate(ctx):
            GOT.append(ctx.plugin("live_base"))
    """, deps=["live_base"])
    from SciQLop.components.plugins.backend.live_loader import PluginsLiveLoader
    PluginsLiveLoader._load(SimpleNamespace(_main_window=object()), [late])
    import sys
    assert sys.modules["live_late"].GOT == [7] and context.STATES["live_late"].status == "active"


def _broken_activate(ctx):
    raise RuntimeError("no luck")


def test_hot_loaded_entry_point_failure_is_reported(monkeypatch, fresh, tmp_config_dir):  # noqa: F811
    mod = SimpleNamespace(activate=_broken_activate)
    ep = SimpleNamespace(name="ep_broken", module="ep_broken", load=lambda: mod,
                         dist=SimpleNamespace(name="ep-broken", requires=None, files=None))
    import importlib.metadata
    monkeypatch.setattr(importlib.metadata, "entry_points", lambda group: [ep])
    from SciQLop.core import sciqlop_application
    monkeypatch.setattr(sciqlop_application, "sciqlop_app", lambda: SimpleNamespace(main_window=object()))
    from SciQLop.components.appstore.backend import _try_load_plugin
    assert _try_load_plugin("ep-broken") == "ep_broken: RuntimeError: no luck"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_plugin_live_activation.py -q`
Expected: first test passes or fails depending on Task 4 (live `_load` still calls `load_one` per plugin, which works); the second FAILS (`_try_load_plugin` returns `None`).

- [ ] **Step 3: Implement**

`live_loader.py`, replace `_load`:

```python
    @Slot(object)
    def _load(self, ready):
        fresh = [(folder, name) for folder, name in ready if name not in loader._attempted]
        if fresh:
            log.info(f"Loading plugins without restart: {', '.join(name for _, name in fresh)}")
            loader.activate_all(fresh, self._main_window)
```

`appstore/backend.py`, replace the loop of `_try_load_plugin` (from `canonical_dist_name = ...` to the final `return None`):

```python
    canonical_dist_name = canonical_package_name(dist_name)
    matching = {ep.name: ep for ep in importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
                if _dist_name(ep) and canonical_package_name(_dist_name(ep)) == canonical_dist_name}
    with SciQLopPluginsSettings() as settings:
        for name in matching:
            settings.plugins.setdefault(name, PluginConfig())
    for ep in matching.values():
        if not entry_point_host_compatible(ep):
            return _incompatibility_reason(ep)
    if not matching:
        return None
    activate_all([(None, name) for name in matching], main_window, matching)
    log.info(f"Hot-loaded plugins {', '.join(matching)} from {dist_name}")
    reasons = [f"{name}: {STATES[name].reason}" for name in matching if STATES[name].status != "active"]
    return "; ".join(reasons) or None
```

with this helper above `_try_load_plugin`:

```python
def _dist_name(ep) -> str | None:
    try:
        return ep.dist.name if ep.dist else None
    except Exception:
        return None
```

and the imports inside `_try_load_plugin` changed to:

```python
    from SciQLop.components.plugins.backend.loader.loader import (
        ENTRY_POINT_GROUP, entry_point_host_compatible, activate_all,
    )
    from SciQLop.components.plugins.backend.loader.context import STATES
```

- [ ] **Step 4: Run the new and the existing live/app-store tests**

Run: `uv run pytest tests/test_plugin_live_activation.py tests/test_plugins_live_loading.py tests/test_appstore_install.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_plugin_live_activation.py
git commit -m "feat(plugins): live install resolves plugin dependencies and reports failed activation" -- SciQLop/components/plugins/backend/live_loader.py SciQLop/components/appstore/backend.py tests/test_plugin_live_activation.py
```

---

### Task 6: `provides` drift check

**Files:**
- Create: `SciQLop/components/plugins/backend/loader/provides.py`
- Create: `SciQLop/components/plugins/testing.py`
- Modify: `SciQLop/components/plugins/backend/loader/loader.py` (`activate_all`: warn after the ready loop)
- Test: `tests/test_plugin_provides.py`

**Interfaces:**
- Consumes: Task 1 `extensions.all_extension_points()`, `ExtensionPoint.contributed_by/owner`; Task 4 `STATES`, `_Entry.desc`.
- Produces: `registered_by(plugin_id) -> dict[str, list[str]]`, `provides_drift(plugin_id, provides) -> list[str]`, `EXTENSION_POINTS_KEY = "extension_points"`; `SciQLop.components.plugins.testing.assert_provides_matches(plugin_id, plugin_json_path)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_plugin_provides.py
"""plugin.json provides is a summary; the loader warns when it drifts from what the code registered."""
import json

import pytest

from SciQLop.components.plugins.backend.loader.provides import provides_drift, registered_by
from SciQLop.core import extensions
from SciQLop.core.extensions import ExtensionPoint
from tests.test_extensions import Kind, clean_registry  # noqa: F401  (fixture)


@pytest.fixture
def kinds(clean_registry, qapp):  # noqa: F811
    ep = extensions.declare(ExtensionPoint("test.kinds", Kind))
    extensions.declare(ExtensionPoint("vdfp.methods", Kind, owner="vdfp"))
    ep.contribute(Kind("vdfp.slice"), owner="vdfp")
    return ep


def test_registered_by_lists_contributions_and_declared_points(kinds):
    assert registered_by("vdfp") == {"test.kinds": ["vdfp.slice"], "extension_points": ["vdfp.methods"]}


def test_matching_provides_has_no_drift(kinds):
    assert provides_drift("vdfp", {"test.kinds": ["vdfp.slice"], "extension_points": ["vdfp.methods"]}) == []


def test_drift_names_both_directions(kinds):
    assert provides_drift("vdfp", {"test.kinds": ["vdfp.ghost"]}) == [
        "extension_points: registered but not declared in plugin.json: vdfp.methods",
        "test.kinds: declared in plugin.json but not registered: vdfp.ghost",
        "test.kinds: registered but not declared in plugin.json: vdfp.slice",
    ]


def test_assert_helper_fails_on_drift(kinds, tmp_path):
    from SciQLop.components.plugins.testing import assert_provides_matches
    path = tmp_path / "plugin.json"
    path.write_text(json.dumps({"name": "V", "version": "1", "provides": {"test.kinds": ["vdfp.slice"]}}))
    with pytest.raises(AssertionError, match="extension_points: registered but not declared"):
        assert_provides_matches("vdfp", str(path))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_plugin_provides.py -q`
Expected: collection error, `No module named '...provides'`.

- [ ] **Step 3: Write the implementation**

```python
# SciQLop/components/plugins/backend/loader/provides.py
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
```

```python
# SciQLop/components/plugins/testing.py
"""Helpers for plugin authors' own test suites."""
from SciQLop.components.plugins.backend.loader.plugin_desc import PluginDesc
from SciQLop.components.plugins.backend.loader.provides import provides_drift


def assert_provides_matches(plugin_id: str, plugin_json_path: str) -> None:
    """Fail when plugin.json `provides` differs from what the activated plugin registered."""
    problems = provides_drift(plugin_id, PluginDesc.from_json(plugin_json_path).provides)
    assert not problems, "\n".join(problems)
```

In `loader.py` `activate_all`, after the `_ready` loop, add `_warn_on_provides_drift(entries, resolution.order)` and define:

```python
def _warn_on_provides_drift(entries, order) -> None:
    from .provides import provides_drift
    for name in order:
        state = STATES[name]
        if state.status == "active" and hasattr(state.module, "activate") and entries[name].desc is not None:
            for problem in provides_drift(name, entries[name].desc.provides):
                log.warning(f"Plugin {name}: {problem}")
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_plugin_provides.py tests/test_plugin_activation.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plugins/backend/loader/provides.py SciQLop/components/plugins/testing.py tests/test_plugin_provides.py
git commit -m "feat(plugins): warn when plugin.json provides drifts from what the plugin registered" -- SciQLop/components/plugins/backend/loader/provides.py SciQLop/components/plugins/testing.py SciQLop/components/plugins/backend/loader/loader.py tests/test_plugin_provides.py
```

---

### Task 7: Workspace manifests keep tables they do not know

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspace_manifest.py` (dataclass lines 52-66, `load` lines 97-121, `save` lines 151-184)
- Test: `tests/test_workspace_manifest.py` (append)

**Interfaces:**
- Produces: `WorkspaceManifest.extra_tables: dict` (tables other than workspace/plugins/dependencies/examples), preserved through `load` → `save`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_workspace_manifest.py`)

```python
def test_unknown_tables_survive_a_save(tmp_path):
    path = tmp_path / "ws.sciqlop"
    path.write_text('[workspace]\nname = "W"\n\n[vdf_study]\nlast_event = "2015-10-16"\n'
                    '[vdf_study.layout]\ncolumns = 2\n')
    WorkspaceManifest.load(path).save(path)
    reloaded = WorkspaceManifest.load(path)
    assert reloaded.extra_tables == {"vdf_study": {"last_event": "2015-10-16", "layout": {"columns": 2}}}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_workspace_manifest.py -q -k unknown_tables`
Expected: FAIL — `AttributeError: 'WorkspaceManifest' object has no attribute 'extra_tables'`.

- [ ] **Step 3: Implement**

Add the field at the end of the dataclass:

```python
    # Tables this class does not model (a plugin's own section): kept verbatim so a save never drops them.
    extra_tables: dict = field(default_factory=dict)
```

Add a module constant under `LAST_USED_MARKER`:

```python
_KNOWN_TABLES = ("workspace", "plugins", "dependencies", "examples")
```

In `load`, pass to the constructor:

```python
            extra_tables={k: v for k, v in data.items() if k not in _KNOWN_TABLES},
```

In `save`, build `data` starting from the extra tables so known tables win on a name clash:

```python
        data: dict = {**self.extra_tables, "workspace": {"name": self.name, "description": self.description}}
```

(replacing the existing `data: dict = {"workspace": {...}}` literal; the rest of `save` is unchanged).

- [ ] **Step 4: Run the manifest tests**

Run: `uv run pytest tests/test_workspace_manifest.py tests/test_manifest_lost_updates.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git commit -m "fix(workspaces): keep manifest tables SciQLop does not know through a save" -- SciQLop/components/workspaces/backend/workspace_manifest.py tests/test_workspace_manifest.py
```

---

### Task 8: Scenes on extension points; planetary_scenes uses activate(ctx)

**Files:**
- Modify: `SciQLop/components/scenes/registry.py` (whole file)
- Modify: `SciQLop/components/scenes/tree.py` (add `follow_registries`)
- Modify: `SciQLop/user_api/scenes/__init__.py:25-43` (`register_*` stop calling the tree)
- Modify: `SciQLop/plugins/planetary_scenes/__init__.py` (`load` → `activate`)
- Modify: `SciQLop/plugins/planetary_scenes/plugin.json` (add `provides`)
- Modify: `SciQLop/sciqlop_app.py:203-204` and `tests/fixtures.py:43` (call `follow_registries()` before `load_all`)
- Modify: `tests/scenes/conftest.py:55-64` and `tests/scenes/test_scene_tree.py:70-75` (activate through a ctx)
- Test: `tests/scenes/test_scenes_extension_points.py`

**Interfaces:**
- Consumes: Task 1 `ExtensionPoint`, `declare`, `NotRegistered`; Task 4 `PluginContext`; Task 6 `assert_provides_matches`.
- Produces: `BODIES`, `BOUNDARIES`, `SCENES` are `Registry` instances (subclass of `ExtensionPoint`) declared as `sciqlop.scenes.bodies/boundaries/scenes`, keyed by `item.name`, keeping `register(item, replace=False)`; `tree.follow_registries()` (idempotent); `planetary_scenes.activate(ctx)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/scenes/test_scenes_extension_points.py
"""Scenes are the first extension-point client: planetary_scenes contributes like a third party."""
from pathlib import Path

from SciQLop.core import extensions


def test_scene_registries_are_declared_extension_points():
    from SciQLop.components.scenes.registry import BODIES, BOUNDARIES, SCENES
    assert extensions.get("sciqlop.scenes.bodies") is BODIES
    assert extensions.get("sciqlop.scenes.boundaries") is BOUNDARIES
    assert extensions.get("sciqlop.scenes.scenes") is SCENES


def test_planetary_scenes_contributions_are_owned_and_match_plugin_json(main_window, monkeypatch):
    from SciQLop.components.scenes import registry
    from SciQLop.components.plugins.backend.loader.context import PluginContext
    from SciQLop.components.plugins.testing import assert_provides_matches
    from SciQLop.plugins import planetary_scenes
    for reg in (registry.BODIES, registry.BOUNDARIES, registry.SCENES):
        monkeypatch.setattr(reg, "_items", {})
        monkeypatch.setattr(reg, "_owners", {})
    planetary_scenes.activate(PluginContext("planetary_scenes", "1.0.0", main_window, frozenset()))
    assert registry.SCENES.owner_of("Earth environment") == "planetary_scenes"
    assert_provides_matches("planetary_scenes", str(Path(planetary_scenes.__file__).parent / "plugin.json"))


def test_a_contributed_scene_gets_its_tree_node(main_window, monkeypatch):
    from SciQLopPlots import ProductsModel
    from SciQLop.components.scenes import registry
    from SciQLop.components.scenes.model import Scene
    monkeypatch.setattr(registry.SCENES, "_items", {})
    registry.SCENES.contribute(Scene("Tree probe", "earth", "GSM", {}), owner="probe")
    assert ProductsModel.node(["Scenes", "Tree probe"]) is not None
```

(`main_window` comes from `tests/fixtures.py`; add `from tests.fixtures import *  # noqa: F401,F403` at the top of the file if `tests/scenes/conftest.py` does not already re-export it — check how `tests/scenes/test_scene_tree.py` gets `main_window` and do the same.)

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/scenes/test_scenes_extension_points.py -q`
Expected: FAIL — `NotRegistered: no extension point named 'sciqlop.scenes.bodies'`.

- [ ] **Step 3: Rewrite `registry.py`**

```python
# SciQLop/components/scenes/registry.py
"""Bodies, boundary models and scenes: three extension points keyed by their published names."""
from operator import attrgetter
from typing import TypeVar

from SciQLop.core.extensions import ExtensionPoint, NotRegistered, declare  # noqa: F401  NotRegistered re-exported

T = TypeVar("T")


class Registry(ExtensionPoint[T]):
    """An extension point keyed by `name`, with the published register(item, replace) call."""

    def __init__(self, id: str, what: str):
        # object: Boundary is a non-runtime Protocol, and Body/Scene live in model.py, which imports this module.
        super().__init__(id, object, what=what, key=attrgetter("name"))

    def register(self, item: T, replace: bool = False) -> T:
        if item.name in self._items and not replace:
            raise ValueError(f"{self._what} {item.name!r} is already registered")
        return self.contribute(item, replace=True)


BODIES: Registry = declare(Registry("sciqlop.scenes.bodies", "body"))
BOUNDARIES: Registry = declare(Registry("sciqlop.scenes.boundaries", "boundary"))
SCENES: Registry = declare(Registry("sciqlop.scenes.scenes", "scene"))
```

- [ ] **Step 4: Tree nodes follow the registries**

Change the registry import at the top of `SciQLop/components/scenes/tree.py` to `from .registry import BOUNDARIES, SCENES`, then append:

```python
_following = []


def follow_registries() -> None:
    """List every boundary and scene in the products tree as it is contributed, whoever contributes it."""
    if _following:
        return
    BOUNDARIES.signals.added.connect(add_boundary_node)
    SCENES.signals.added.connect(add_scene_node)
    _following.append(True)
```

In `SciQLop/user_api/scenes/__init__.py`, `register_boundary` and `register_scene` drop their `_tree.add_*_node(...)` lines (the docstrings keep saying the item is listed in the products tree — it still is, through the signal):

```python
@on_main_thread
def register_boundary(model: Boundary, replace: bool = False) -> Boundary:
    """Also lists the model in the products tree, under Models/<Body>/<kind>."""
    return BOUNDARIES.register(model, replace)


@on_main_thread
def register_scene(scene: Scene, replace: bool = False) -> Scene:
    """Also lists the scene in the products tree, under Scenes; drop it on a panel to plot it."""
    return SCENES.register(scene, replace)
```

and add, below the imports, `_tree.follow_registries()` so a notebook that imports `user_api.scenes` outside the app still gets nodes.

In `SciQLop/sciqlop_app.py`, before `load_all(main_windows)`:

```python
    from SciQLop.components.scenes.tree import follow_registries
    follow_registries()
```

In `tests/fixtures.py` `_build_main_window`, the same two lines before `load_all(mw)`.

- [ ] **Step 5: planetary_scenes contributes through ctx**

Replace `load` in `SciQLop/plugins/planetary_scenes/__init__.py` (keep `register_all`, which tests use):

```python
CONTRIBUTIONS = (("sciqlop.scenes.bodies", BODIES_DATA), ("sciqlop.scenes.boundaries", MODELS),
                 ("sciqlop.scenes.scenes", SCENES_DATA))


def activate(ctx):
    for ep_id, items in CONTRIBUTIONS:
        for item in items:
            ctx.contribute(ep_id, item, replace=True)
```

Update the module docstring's last sentence to "`activate` contributes them through the scenes extension points."

Add to `SciQLop/plugins/planetary_scenes/plugin.json` (after `python_dependencies`):

```json
  "provides": {
    "sciqlop.scenes.bodies": ["earth", "mars", "mercury"],
    "sciqlop.scenes.boundaries": ["jelinek2012", "shue1998", "vignes2000_bs", "vignes2000_mpb",
                                  "winslow2013_bs", "winslow2013_mp"],
    "sciqlop.scenes.scenes": ["Earth environment", "Mars environment", "Mercury environment"]
  }
```

Check the boundary names against `models.py` (`grep -n 'name = ' SciQLop/plugins/planetary_scenes/models.py`) and fix the list if one differs; the provides test will name the mismatch.

- [ ] **Step 6: Update the scenes tests that called `load(main_window)`**

In `tests/scenes/conftest.py` (`registered` fixture) and `tests/scenes/test_scene_tree.py` (line ~73), replace

```python
    from SciQLop.plugins.planetary_scenes import load
    load(main_window)
```

with

```python
    from SciQLop.components.plugins.backend.loader.context import PluginContext
    from SciQLop.plugins.planetary_scenes import activate
    activate(PluginContext("planetary_scenes", "1.0.0", main_window, frozenset()))
```

and in `tests/scenes/conftest.py` `earth` fixture and `tests/scenes/test_registry.py` `registries` fixture, also reset owners: after each `monkeypatch.setattr(reg, "_items", {})` add `monkeypatch.setattr(reg, "_owners", {})`.

- [ ] **Step 7: Run the scenes tests**

Run: `uv run pytest tests/scenes -q`
Expected: all pass (145 before this task, plus the 3 new ones).

- [ ] **Step 8: Commit**

```bash
git add tests/scenes/test_scenes_extension_points.py
git commit -m "refactor(scenes): scenes registries are extension points, planetary_scenes contributes through activate(ctx)" -- SciQLop/components/scenes/registry.py SciQLop/components/scenes/tree.py SciQLop/user_api/scenes/__init__.py SciQLop/plugins/planetary_scenes/__init__.py SciQLop/plugins/planetary_scenes/plugin.json SciQLop/sciqlop_app.py tests/fixtures.py tests/scenes/conftest.py tests/scenes/test_scene_tree.py tests/scenes/test_registry.py tests/scenes/test_scenes_extension_points.py
```

---

### Task 9: Plugin-author documentation, spec ruling, full suite

**Files:**
- Create: `SciQLop/components/agents/skills/sciqlop-plugin-design/references/plugin-contract.md`
- Modify: `SciQLop/components/agents/skills/sciqlop-plugin-design/SKILL.md` (description, Overview, Minimal plugin, link to the new page)
- Modify: `SciQLop/components/agents/skills/sciqlop-plugin-design/references/packaging-and-testing.md` (`## plugin.json` section)
- Modify: `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` (§3.1 example: `provides` keyed by EP id)
- Modify: `/home/jeandet/.claude/memory/sciqlop-user-api.md` (plugin contract paragraph; outside the repo, not committed)
- Test: `tests/test_agent_skills.py` (existing; must still pass)

- [ ] **Step 1: Write `references/plugin-contract.md`**

```markdown
# Plugin contract: activate(ctx), dependencies, extension points

## Two entry points

- `activate(ctx)` — the current contract. SciQLop calls it once, in dependency order. Return your public API (or None).
- `load(main_window)` — the old contract, still supported. A module with `activate` never gets `load` called.
- `ready(ctx)` (optional, `activate` plugins only) — runs after every plugin activated. Read what others contributed here.

## plugin.json

| Key | Meaning |
|---|---|
| `name`, `version` | display name, and the version other plugins' specifiers check (semver: a breaking API change is a major bump) |
| `dependencies` | plugins you need, by plugin id (folder or entry-point name) with PEP 440 ranges: `["vdf>=1.2,<2"]` |
| `optional_dependencies` | plugins you use when present; they load before you |
| `provides` | `{extension point id: [contribution ids]}` plus `"extension_points": [ids you declare]`; shown by the app store |
| `python_dependencies` | pip packages (numpy…); never other plugins |

A packaged plugin ships `plugin.json` next to the module its `sciqlop.plugins` entry point names, and lists it in package data.

## ctx

| Call | Does |
|---|---|
| `ctx.contribute("sciqlop.scenes.scenes", Scene(...))` | add to an extension point; you are recorded as the owner |
| `ctx.extension_point("myplugin.methods", Method)` | declare your own extension point; the id must start with `myplugin.` |
| `ctx.plugin("vdf")` | the API `vdf`'s `activate` returned; raises if `vdf` is not in your plugin.json |
| `ctx.has("mars")` | whether an optional dependency is active |
| `ctx.main_window` | the main window, for docks and menus |

## Collaborating with another plugin

```python
def activate(ctx):
    vdf = ctx.plugin("vdf")                       # declared in plugin.json dependencies
    ctx.contribute("vdf.reconstruction_methods", vdf.Method("myplugin.fast", fast))
    if ctx.has("mars"):                           # optional_dependencies
        from .with_mars import register           # code needing mars lives in its own module
        register(ctx)
    return MyApi()
```

If you keep a list built from an extension point (a menu, a cache), also connect to
`extensions.get(ep_id).signals.added`: a plugin installed later contributes after your `ready`.

## When a plugin does not load

The log says why: `Plugin study not loaded: needs plugin vdf>=1.2,<2, but vdf 2.0.0 is installed`.
Dependents of a refused or failed plugin are refused too, with the chain in the message.

## Test that plugin.json matches the code

```python
from SciQLop.components.plugins.testing import assert_provides_matches
assert_provides_matches("myplugin", "myplugin/plugin.json")   # after activating the plugin
```
```

- [ ] **Step 2: Update `SKILL.md`**

- In the frontmatter `description`, replace "loads at startup through `load(main_window)`" with "loads at startup through `activate(ctx)` (or the older `load(main_window)`)" and add "plugins that depend on or extend other plugins" to the list. Keep it ≤ 1024 characters and starting with "Use when".
- In `## Overview`, first paragraph: "A SciQLop plugin is a Python package with an `activate(ctx)` function (older plugins: `load(main_window)`). SciQLop calls it once at startup, after the plugins it depends on."
- Add a row to the mechanism table: `| Use or extend another plugin | Declare it in plugin.json dependencies, then ctx.plugin(name) / ctx.contribute(ep_id, item) — see [references/plugin-contract.md](references/plugin-contract.md) | Importing the other plugin's package directly |`
- In `## Minimal plugin`, the code block becomes:

```python
# my_plugin/__init__.py
def activate(ctx):
    from .products import register_products   # import SciQLop-heavy code lazily
    return register_products()                 # your public API, or None
```

- [ ] **Step 3: Update `references/packaging-and-testing.md` `## plugin.json`**

Add after the existing example: the new keys table from Step 1 (dependencies, optional_dependencies, provides) and the sentence "Only `name` and `version` are required." Keep the existing content about package data.

- [ ] **Step 4: Update the spec's §3.1 example**

In `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` §3.1, replace the `"provides"` block of the example with

```json
  "provides": {
    "sciqlop.plot_kinds": ["vdf_study.event_overview"],
    "extension_points": []
  }
```

and add under the `provides` bullet: "Keys are extension point ids, plus `extension_points` for the EPs the plugin declares."

- [ ] **Step 5: Update the global user_api memory**

In `/home/jeandet/.claude/memory/sciqlop-user-api.md`, add a short section "Plugin contract (2026-10)": `activate(ctx)` / `ready(ctx)`, `ctx.contribute/extension_point/plugin/has`, `plugin.json` `dependencies` / `optional_dependencies` / `provides`, `SciQLop.components.plugins.testing.assert_provides_matches`, scenes EP ids. (Not in the repo; no commit.)

- [ ] **Step 6: Run the skill tests, flake8, then the full suite**

Run: `uv run pytest tests/test_agent_skills.py tests/test_agent_guidance.py tests/test_agent_guidance_tool_names.py -q`
Expected: all pass.
Run: `uv run flake8 --select=E9,F63,F7,F82 SciQLop/core/extensions.py SciQLop/components/plugins SciQLop/components/scenes SciQLop/plugins/planetary_scenes SciQLop/components/workspaces/backend/workspace_manifest.py SciQLop/components/appstore/backend.py`
Expected: no output.
Run (once, foreground, ~9 min): `uv run pytest -q -p no:cacheprovider`
Expected: last line `N passed, 27 skipped, 1 xfailed` with N ≥ 3989 + the tests added by this plan, exit 0. Read the real count; investigate any failure before committing.

- [ ] **Step 7: Commit**

```bash
git add SciQLop/components/agents/skills/sciqlop-plugin-design/references/plugin-contract.md
git commit -m "docs(plugins): plugin contract reference for the plugin-design skill; provides keyed by extension point" -- SciQLop/components/agents/skills/sciqlop-plugin-design docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md
```
