# Tier 3a: quickstart, tours, search domains, catalog providers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four existing registries become owner-tagged extension points, so a withdrawn plugin's quickstart shortcuts, tours, search domains and catalog providers go away and the UI follows.

**Architecture:** Each registry's storage moves into an `ExtensionPoint` (`SciQLop/core/extensions.py`). The existing public functions become thin wrappers that contribute under the current owner; consumers follow the point's `added`/`removed` signals. Nothing outside SciQLop changes.

**Tech Stack:** Python 3.14, PySide6, pytest + pytest-qt (+ pytest-xvfb on Linux).

**Spec:** `docs/superpowers/specs/2026-10-16-tier3-extension-points-design.md` §3 (parent: `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md`).

## Global Constraints

- Approach A: the extension point is the source of truth; existing public functions keep their signatures and contribute under the current owner.
- Existing callers unchanged: `add_quickstart_shortcut`, `register_tour`/`get_tour`/`all_tours`, `register_domain`/`unregister_domain`, subclassing `CatalogProvider`, `CatalogRegistry` methods and signals. `sciqlop_msa`'s provider keeps working.
- Process-lifetime EP signals connect to plain functions or to slots guarded by `shiboken6.isValid(self)` (`docs/qt-lifetime-patterns.md`).
- The four public wrappers work from any thread (notebook cells and agent tools run on the kernel thread or a worker): each captures `current_owner()` on the calling thread and contributes through an `@on_main_thread` helper (`SciQLop.user_api.threading.on_main_thread`, imported lazily from core modules) with that owner — the `register_agent_backend` pattern in `SciQLop/components/agents/registry.py:50-60`.
- Core contributions use `CORE_OWNER` (`SciQLop.core.name_follower.CORE_OWNER == "sciqlop"`).
- Run tests with `uv run pytest` (never `--no-xvfb`), one invocation at a time, in the foreground. Never `uv sync`.
- Commit on `main` with explicit pathspecs; end each commit message with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. Never push.

## Rulings made while writing this plan

- Every wrapper marshals to the main thread, not only catalog providers: today's providers are all built on the main thread, but a notebook cell, an agent tool or a labelling pipeline may build one (or register a tour, a domain, a shortcut) from another thread, and those calls work today because the old registries are plain dicts and lists.
- Tests that silently drop providers through `registry._providers` move to `CatalogRegistry._forget_for_tests(provider)`, which keeps today's no-signal behaviour.
- `SmartSearchRegistry.register_domain` stops the previous domain's reindex timer when a name is registered again (it leaked a running timer before); the facade relies on it when a lazily built registry replays the point.

## Review Focus

- A plugin contributing a quickstart shortcut named like a core one ("JupyterLab") is refused with `DuplicateContribution`, not silently overwriting the core's (Task 1 test).
- `unregister_domain` of a name never registered stays a no-op, as today (Task 3 test).
- A plugin reinstalled after withdrawal can register the same tour id again (Task 2 test).
- A provider destroyed while still registered leaves the point without `provider_unregistered` being handed a dead object (Task 4 test).
- A withdrawn provider's catalogs leave the catalog tree (Task 4 test).
- Each wrapper called from a worker thread contributes under the worker's owner (one test per task, through `call_from_worker_thread`).

---

### Task 1: `sciqlop.quickstart`

**Files:**
- Create: `SciQLop/core/quickstart.py`
- Modify: `SciQLop/core/sciqlop_application.py:33-77`
- Modify: `SciQLop/components/welcome/backend.py:189,204-205`
- Modify: `SciQLop/core/ui/mainwindow.py` (the three `add_quickstart_shortcut` calls, near lines 498 and 545-549)
- Modify: `tests/conftest.py` (the `_quickstart_shortcuts` snapshot in `_release_gui_leftovers`)
- Modify: `tests/helpers.py` (append `call_from_worker_thread`, used by every task of this plan)
- Test: `tests/test_quickstart_point.py`

**Interfaces:**
- Produces: `SciQLop.core.quickstart.QUICKSTART` (`ExtensionPoint` id `sciqlop.quickstart`, key `name`); `QuickstartShortcut(name: str, description: str, icon, callback: Callable[[], Any])` with `as_dict() -> dict`; `SciQLopApp.quickstart_shortcuts_removed = Signal(str)`; `tests.helpers.call_from_worker_thread(qtbot, monkeypatch, fn)` returning `fn()`'s result or raising its exception.

- [ ] **Step 1: Write the failing tests**

```python
"""Quickstart shortcuts are contributions to sciqlop.quickstart (Tier 3 spec §3.1)."""
import pytest

from .fixtures import *  # noqa: F401,F403 — main_window
from SciQLop.core.extensions import DuplicateContribution, owned_by
from SciQLop.core.quickstart import QUICKSTART


@pytest.fixture
def demo(qapp):
    yield
    QUICKSTART.remove_owner("qs_demo")


def _add(qapp, name="QS demo", callback=lambda: None):
    with owned_by("qs_demo"):
        qapp.add_quickstart_shortcut(name, "A demo", None, callback)


def test_a_shortcut_is_owned_by_the_current_plugin(qapp, demo):
    _add(qapp)
    assert QUICKSTART.owner_of("QS demo") == "qs_demo"
    assert "QS demo" in qapp.quickstart_shortcuts
    assert qapp.quickstart_shortcut("QS demo")["description"] == "A demo"


def test_quickstart_shortcut_stays_a_dict_with_its_callback(qapp, demo):
    calls = []
    _add(qapp, callback=lambda: calls.append(1))
    qapp.quickstart_shortcut("QS demo")["callback"]()
    assert calls == [1]
    assert qapp.quickstart_shortcut("No such shortcut") is None


def test_added_keeps_its_name_payload(qapp, demo, qtbot):
    with qtbot.waitSignal(qapp.quickstart_shortcuts_added) as blocker:
        _add(qapp)
    assert blocker.args == ["QS demo"]


def test_withdrawing_the_plugin_removes_its_shortcut_and_says_so(qapp, demo, qtbot):
    _add(qapp)
    with qtbot.waitSignal(qapp.quickstart_shortcuts_removed) as blocker:
        QUICKSTART.remove_owner("qs_demo")
    assert blocker.args == ["QS demo"]
    assert "QS demo" not in qapp.quickstart_shortcuts


def test_the_welcome_page_refreshes_when_a_shortcut_goes(qapp, demo, qtbot):
    from SciQLop.components.welcome.backend import WelcomeBackend
    backend = WelcomeBackend()
    try:
        _add(qapp)
        with qtbot.waitSignal(backend.quickstart_changed):
            QUICKSTART.remove_owner("qs_demo")
    finally:
        backend.deleteLater()


def test_the_main_window_shortcuts_belong_to_the_core(main_window):
    from SciQLop.core.name_follower import CORE_OWNER
    assert QUICKSTART.owner_of("New plot panel") == CORE_OWNER


def test_a_plugin_cannot_take_a_core_shortcut_name(qapp, main_window):
    with owned_by("qs_demo"), pytest.raises(DuplicateContribution):
        qapp.add_quickstart_shortcut("New plot panel", "Mine", None, lambda: None)


def test_a_shortcut_added_from_a_worker_thread_keeps_its_owner(qapp, demo, qtbot, monkeypatch):
    from .helpers import call_from_worker_thread
    call_from_worker_thread(qtbot, monkeypatch, lambda: _add(qapp))
    assert QUICKSTART.owner_of("QS demo") == "qs_demo"
```

Append the helper to `tests/helpers.py` (every task of this plan uses it):

```python
def call_from_worker_thread(qtbot, monkeypatch, fn):
    """Run fn on a plain Python thread, as a notebook cell or an agent tool would, with the cross-thread
    invoker the kernel normally installs; the main thread keeps processing events meanwhile."""
    import threading
    from jupyqt.qt.proxy import MainThreadInvoker
    from SciQLop.user_api import threading as sciqlop_threading
    monkeypatch.setattr(sciqlop_threading, "_invoker", MainThreadInvoker())
    outcome = {}

    def run():
        try:
            outcome["result"] = fn()
        except BaseException as error:
            outcome["error"] = error

    worker = threading.Thread(target=run)
    worker.start()
    qtbot.waitUntil(lambda: not worker.is_alive(), timeout=10_000)
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("result")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_quickstart_point.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'SciQLop.core.quickstart'`.

- [ ] **Step 3: Create `SciQLop/core/quickstart.py`**

```python
"""Quickstart shortcuts on the welcome page: the sciqlop.quickstart extension point (Tier 3 spec §3.1)."""
from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter
from typing import Any, Callable

from SciQLop.core.extensions import ExtensionPoint, declare


@dataclass(frozen=True)
class QuickstartShortcut:
    name: str
    description: str
    icon: Any  # QIcon, QPixmap or None
    callback: Callable[[], Any]

    def as_dict(self) -> dict:
        return {"name": self.name, "description": self.description, "icon": self.icon, "callback": self.callback}


QUICKSTART = declare(ExtensionPoint("sciqlop.quickstart", QuickstartShortcut, what="quickstart shortcut",
                                    key=attrgetter("name"), doc="Welcome-page quickstart shortcuts by name."))


def contribute_shortcut(shortcut: QuickstartShortcut, owner: str) -> None:
    """From any thread: the owner is captured by the caller, since the owner context does not cross threads."""
    from SciQLop.user_api.threading import invoke_on_main_thread, _on_main_thread
    if _on_main_thread():
        QUICKSTART.contribute(shortcut, owner=owner)
    else:
        invoke_on_main_thread(QUICKSTART.contribute, shortcut, owner=owner)
```

(`on_main_thread` as a decorator would import `SciQLop.user_api` at core import time; the lazy import keeps
`SciQLop.core` free of it.)

- [ ] **Step 4: Route `SciQLopApp` through the point**

In `SciQLop/core/sciqlop_application.py`, add the removal signal next to `quickstart_shortcuts_added`:

```python
    quickstart_shortcuts_added = QtCore.Signal(str)
    quickstart_shortcuts_removed = QtCore.Signal(str)
```

Replace `self._quickstart_shortcuts: Dict[str, Dict[str, Any]] = {}` in `__init__` with:

```python
        from SciQLop.core.quickstart import QUICKSTART
        QUICKSTART.signals.added.connect(self._on_quickstart_added)
        QUICKSTART.signals.removed.connect(self._on_quickstart_removed)
```

Replace `add_quickstart_shortcut`, `quickstart_shortcuts` and `quickstart_shortcut` with:

```python
    def add_quickstart_shortcut(self, name: str, description: str, icon: QtGui.QPixmap or QtGui.QIcon,
                                callback: callable):
        from SciQLop.core.extensions import current_owner
        from SciQLop.core.quickstart import QuickstartShortcut, contribute_shortcut
        contribute_shortcut(QuickstartShortcut(name, description, icon, callback), current_owner())

    def _on_quickstart_added(self, shortcut) -> None:
        self.quickstart_shortcuts_added.emit(shortcut.name)

    def _on_quickstart_removed(self, shortcut) -> None:
        self.quickstart_shortcuts_removed.emit(shortcut.name)

    @QtCore.Property(list)
    def quickstart_shortcuts(self) -> List[str]:
        from SciQLop.core.quickstart import QUICKSTART
        return QUICKSTART.keys()

    def quickstart_shortcut(self, name: str) -> Optional[Dict[str, Any]]:
        from SciQLop.core.quickstart import QUICKSTART
        shortcut = QUICKSTART.find(name)
        return shortcut.as_dict() if shortcut is not None else None
```

Drop `Dict`/`Any` from the `typing` import only if flake8 then reports them unused.

- [ ] **Step 5: The welcome backend refreshes on removal too**

In `SciQLop/components/welcome/backend.py` `WelcomeBackend.__init__`, after the existing
`sciqlop_app().quickstart_shortcuts_added.connect(self._on_quickstart_shortcuts_added)` line, add:

```python
        sciqlop_app().quickstart_shortcuts_removed.connect(self._on_quickstart_shortcuts_added)
```

Rename the slot to `_on_quickstart_shortcuts_changed` in both connections and its definition (it ignores its argument and emits `quickstart_changed`).

- [ ] **Step 6: The main window's shortcuts belong to the core**

In `SciQLop/core/ui/mainwindow.py`, add `from SciQLop.core.name_follower import CORE_OWNER` to the imports (`owned_by` is already imported from `SciQLop.core.extensions`). Wrap the JupyterLab call (near line 498) and the two calls near lines 545-549 in `with owned_by(CORE_OWNER):`, e.g.:

```python
        with owned_by(CORE_OWNER):
            sciqlop_app().add_quickstart_shortcut("JupyterLab", "Open JupyterLab",
                                                  Icons.get_icon("Jupyter"),
                                                  self.open_jupyterlab_widget)
```

- [ ] **Step 7: The test harness snapshots the point**

In `tests/conftest.py`, add these helpers above `_release_gui_leftovers` (below `_restore_kernel_window`):

```python
def _point_state(point):
    return dict(point._items), dict(point._owners)


def _restore_point_state(point, state) -> None:
    """Silently, like the dict it replaces: a test's shortcuts vanish without signals."""
    items, owners = state
    point._items.clear()
    point._items.update(items)
    point._owners.clear()
    point._owners.update(owners)
```

In `_release_gui_leftovers`, replace `shortcuts_before = dict(app._quickstart_shortcuts)` with
`shortcuts_before = _point_state(QUICKSTART)`, and the two `app._quickstart_shortcuts.clear()/.update(...)` lines with
`_restore_point_state(QUICKSTART, shortcuts_before)`. Import it at the top of the fixture body:
`from SciQLop.core.quickstart import QUICKSTART`.

- [ ] **Step 8: Run the tests**

Run: `uv run pytest tests/test_quickstart_point.py tests/test_welcome_plugin_updates.py tests/test_destroyed_window_released.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add SciQLop/core/quickstart.py tests/test_quickstart_point.py
git commit SciQLop/core/quickstart.py SciQLop/core/sciqlop_application.py SciQLop/components/welcome/backend.py SciQLop/core/ui/mainwindow.py tests/conftest.py tests/helpers.py tests/test_quickstart_point.py -m "feat(plugins): quickstart shortcuts are contributions to sciqlop.quickstart; the welcome page follows removals"
```

---

### Task 2: `sciqlop.tours`

**Files:**
- Modify: `SciQLop/components/onboarding/backend/tour.py:26-32`
- Modify: `SciQLop/components/onboarding/backend/registry.py` (whole file)
- Modify: `tests/test_onboarding_registry.py:50-54`
- Test: `tests/test_onboarding_registry.py`

**Interfaces:**
- Produces: `SciQLop.components.onboarding.backend.registry.TOURS` (`ExtensionPoint` id `sciqlop.tours`, key `id`). `register_tour`, `get_tour`, `all_tours`, `register_builtin_tours`, `_forget_tour_for_tests`, `_reset_registry_for_tests` keep their names and signatures.

- [ ] **Step 1: Write the failing tests**

In `tests/test_onboarding_registry.py`, replace `test_register_tour_rejects_duplicate_id` with these, and add the
`owned_by` import at the top (`from SciQLop.core.extensions import owned_by`):

```python
def test_the_same_owner_registering_a_tour_again_replaces_it():
    from SciQLop.components.onboarding.backend import registry
    registry.register_tour(_make_tour())
    second = _make_tour()
    registry.register_tour(second)
    assert registry.get_tour("fake_tour") is second


def test_another_owner_cannot_take_a_tour_id():
    from SciQLop.components.onboarding.backend import registry
    registry.register_tour(_make_tour())
    with owned_by("tour_thief"), pytest.raises(ValueError, match="already registered"):
        registry.register_tour(_make_tour())


def test_a_withdrawn_plugin_takes_its_tours_away_and_can_register_them_again():
    from SciQLop.components.onboarding.backend import registry
    with owned_by("tour_demo"):
        registry.register_tour(_make_tour())
    assert registry.TOURS.owner_of("fake_tour") == "tour_demo"
    registry.TOURS.remove_owner("tour_demo")
    assert registry.get_tour("fake_tour") is None
    with owned_by("tour_demo"):
        registry.register_tour(_make_tour())
    assert registry.get_tour("fake_tour") is not None


def test_a_tour_without_steps_cannot_be_built():
    with pytest.raises(ValueError, match="no steps"):
        _make_tour(steps=[])


def test_a_tour_registered_from_a_worker_thread_keeps_its_owner(qtbot, monkeypatch):
    from SciQLop.components.onboarding.backend import registry
    from .helpers import call_from_worker_thread

    def register():
        with owned_by("tour_demo"):
            registry.register_tour(_make_tour())

    call_from_worker_thread(qtbot, monkeypatch, register)
    assert registry.TOURS.owner_of("fake_tour") == "tour_demo"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_onboarding_registry.py -q`
Expected: FAIL (`AttributeError: ... has no attribute 'TOURS'`, and `test_a_tour_without_steps_cannot_be_built` does not raise).

- [ ] **Step 3: Move the checks into `Tour`**

In `SciQLop/components/onboarding/backend/tour.py`, give `Tour` this method (messages unchanged from `register_tour`):

```python
    def __post_init__(self):
        if not self.steps:
            raise ValueError(f"Tour {self.id!r} has no steps")
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError(f"Tour {self.id!r} has duplicate step_id values: {step_ids}")
```

Before moving on, grep for `Tour(` in `SciQLop/` and `tests/`: a tour built with no steps outside a `pytest.raises` would now fail at construction.

- [ ] **Step 4: Replace `SciQLop/components/onboarding/backend/registry.py`**

```python
"""Guided tours: the sciqlop.tours extension point (Tier 3 spec §3.2). `register_tour` contributes under the
current owner, so a withdrawn plugin's tours leave with it."""
from SciQLop.components.onboarding.backend.tour import Tour
from SciQLop.core.extensions import ExtensionPoint, current_owner, declare, owned_by
from SciQLop.core.name_follower import CORE_OWNER
from SciQLop.user_api.threading import on_main_thread

TOURS = declare(ExtensionPoint("sciqlop.tours", Tour, what="tour", doc="Guided tours by id."))


def register_tour(tour: Tour) -> None:
    """From any thread; the owner is the caller's, captured before the call moves to the main thread."""
    _contribute_tour(tour, current_owner())


@on_main_thread
def _contribute_tour(tour: Tour, owner: str) -> None:
    TOURS.contribute(tour, owner=owner)


def get_tour(tour_id: str) -> Tour | None:
    return TOURS.find(tour_id)


def all_tours() -> list[Tour]:
    return TOURS.list()


def register_builtin_tours() -> None:
    from SciQLop.components.onboarding.backend.getting_started import GETTING_STARTED
    if get_tour(GETTING_STARTED.id) is None:
        with owned_by(CORE_OWNER):
            register_tour(GETTING_STARTED)


def _forget_tour_for_tests(tour_id: str) -> None:
    if tour_id in TOURS:
        TOURS.remove(tour_id)


def _reset_registry_for_tests() -> None:
    for tour_id in TOURS.keys():
        TOURS.remove(tour_id)
```

Keep the `getting_started` import path exactly as it is in the current file.

- [ ] **Step 5: Run the onboarding tests**

Run: `uv run pytest tests/test_onboarding_registry.py tests/test_onboarding_plugin_api.py tests/test_onboarding_tour_picker.py tests/test_onboarding_tour_getting_started.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git commit SciQLop/components/onboarding/backend/tour.py SciQLop/components/onboarding/backend/registry.py tests/test_onboarding_registry.py -m "feat(plugins): guided tours are contributions to sciqlop.tours; a Tour checks its own steps"
```

---

### Task 3: `sciqlop.search_domains`

**Files:**
- Modify: `SciQLop/components/smart_search/domain.py`
- Modify: `SciQLop/components/smart_search/__init__.py:26-44`
- Modify: `SciQLop/components/smart_search/registry.py:85-89`
- Modify: `tests/test_smart_search_facade.py:40-55`
- Test: `tests/test_search_domains_point.py`

**Interfaces:**
- Produces: `SciQLop.components.smart_search.domain.SEARCH_DOMAINS` (`ExtensionPoint` id `sciqlop.search_domains`, key `name`); `SearchDomain` is `@runtime_checkable`. `register_domain(domain)`, `unregister_domain(name)` keep their signatures.

- [ ] **Step 1: Write the failing tests**

```python
"""Smart-search domains are contributions to sciqlop.search_domains (Tier 3 spec §3.3)."""
from unittest.mock import MagicMock

import pytest

import SciQLop.components.smart_search as facade
from SciQLop.components.smart_search.domain import SEARCH_DOMAINS
from SciQLop.components.smart_search.registry import SmartSearchRegistry
from SciQLop.core.extensions import owned_by


class _Domain:
    def __init__(self, name):
        self.name = name

    def snapshot(self):
        return []


@pytest.fixture
def fake_registry(qapp, monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(facade, "_get_registry", lambda: fake)
    yield fake
    SEARCH_DOMAINS.remove_owner("sd_demo")


def test_register_domain_contributes_under_the_current_owner(fake_registry):
    domain = _Domain("sd_demo.events")
    with owned_by("sd_demo"):
        facade.register_domain(domain)
    assert SEARCH_DOMAINS.owner_of("sd_demo.events") == "sd_demo"
    fake_registry.register_domain.assert_called_once_with(domain)


def test_a_withdrawn_domain_leaves_the_index(fake_registry):
    with owned_by("sd_demo"):
        facade.register_domain(_Domain("sd_demo.events"))
    SEARCH_DOMAINS.remove_owner("sd_demo")
    fake_registry.unregister_domain.assert_called_once_with("sd_demo.events")


def test_unregistering_an_unknown_domain_is_a_no_op(fake_registry):
    facade.unregister_domain("sd_demo.never_registered")
    fake_registry.unregister_domain.assert_not_called()


def test_a_registry_built_later_takes_the_domains_already_contributed(qapp, monkeypatch, fake_registry, tmp_path):
    with owned_by("sd_demo"):
        facade.register_domain(_Domain("sd_demo.early"))
    monkeypatch.undo()  # the real _get_registry again
    monkeypatch.setattr(facade, "_jobs_backend_instance", lambda: MagicMock())
    monkeypatch.setattr(facade, "_cache_dir", lambda: str(tmp_path / "models"))
    monkeypatch.setattr(facade, "_index_cache_dir", lambda: str(tmp_path / "index"))
    monkeypatch.setattr(facade, "_registry", None)
    assert "sd_demo.early" in facade._get_registry()._domains


def test_a_domain_registered_from_a_worker_thread_keeps_its_owner(fake_registry, qtbot, monkeypatch):
    from .helpers import call_from_worker_thread

    def register():
        with owned_by("sd_demo"):
            facade.register_domain(_Domain("sd_demo.threaded"))

    call_from_worker_thread(qtbot, monkeypatch, register)
    assert SEARCH_DOMAINS.owner_of("sd_demo.threaded") == "sd_demo"


def test_registering_a_domain_again_stops_its_old_reindex_timer(qapp, tmp_path):
    registry = SmartSearchRegistry(MagicMock(), model_name="m", cache_dir=str(tmp_path),
                                   index_cache_dir=str(tmp_path))
    registry.register_domain(_Domain("x"))
    old_timer = registry._domains["x"].reindex_timer
    old_timer.start(60_000)
    registry.register_domain(_Domain("x"))
    assert not old_timer.isActive()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_search_domains_point.py -q`
Expected: FAIL with `ImportError: cannot import name 'SEARCH_DOMAINS'`.

- [ ] **Step 3: Declare the point next to the contract**

In `SciQLop/components/smart_search/domain.py`, make the protocol runtime-checkable and declare the point after it:

```python
from operator import attrgetter
from typing import Iterable, NamedTuple, Protocol, runtime_checkable

from SciQLop.core.extensions import ExtensionPoint, declare


class NodeSnapshot(NamedTuple):
    path_key: str
    raw_text: str


@runtime_checkable
class SearchDomain(Protocol):
    name: str

    def snapshot(self) -> Iterable[NodeSnapshot]:
        ...


SEARCH_DOMAINS = declare(ExtensionPoint("sciqlop.search_domains", SearchDomain, what="search domain",
                                        key=attrgetter("name"), doc="Smart-search domains by name."))
```

- [ ] **Step 4: The facade contributes, and routes the point to the current registry**

In `SciQLop/components/smart_search/__init__.py`, import the point
(`from SciQLop.components.smart_search.domain import SEARCH_DOMAINS, SearchDomain`), `current_owner`
(`from SciQLop.core.extensions import current_owner`) and `on_main_thread`
(`from SciQLop.user_api.threading import on_main_thread`), replay the point when the registry is built, and replace
`register_domain`/`unregister_domain`:

```python
def _get_registry() -> SmartSearchRegistry:
    global _registry
    if _registry is None:
        with SmartSearchSettings() as settings:
            model_name = settings.model
        _registry = SmartSearchRegistry(
            _jobs_backend_instance(), model_name=model_name, cache_dir=_cache_dir(),
            index_cache_dir=_index_cache_dir())
        for domain in SEARCH_DOMAINS.list():
            _registry.register_domain(domain)
    return _registry


def register_domain(domain: SearchDomain) -> None:
    """From any thread; the owner is the caller's, captured before the call moves to the main thread."""
    _contribute_domain(domain, current_owner())


@on_main_thread
def _contribute_domain(domain: SearchDomain, owner: str) -> None:
    SEARCH_DOMAINS.contribute(domain, owner=owner)


@on_main_thread
def unregister_domain(name: str) -> None:
    if name in SEARCH_DOMAINS:
        SEARCH_DOMAINS.remove(name)


def _on_domain_added(domain: SearchDomain) -> None:
    _get_registry().register_domain(domain)


def _on_domain_removed(domain: SearchDomain) -> None:
    _get_registry().unregister_domain(domain.name)


# Plain functions, not a registry's bound methods: tests replace the lazily built registry.
SEARCH_DOMAINS.signals.added.connect(_on_domain_added)
SEARCH_DOMAINS.signals.removed.connect(_on_domain_removed)
```

- [ ] **Step 5: Re-registering a name stops the old timer**

In `SciQLop/components/smart_search/registry.py` `SmartSearchRegistry.register_domain`, before creating the new timer:

```python
        previous = self._domains.get(domain.name)
        if previous is not None:
            previous.reindex_timer.stop()
```

- [ ] **Step 6: The facade test uses a real domain object**

In `tests/test_smart_search_facade.py::test_register_domain_and_query_delegate_to_registry`, a `MagicMock(name="products")` has no string `name` attribute, so the point cannot key it. Replace `domain = MagicMock(name="products")` with an instance of a small class defined in that test module:

```python
class _ProductsDomain:
    name = "products"

    def snapshot(self):
        return []
```

and `domain = _ProductsDomain()`.

- [ ] **Step 7: Run the smart-search tests**

Run: `uv run pytest tests/test_search_domains_point.py tests/test_smart_search_facade.py tests/test_smart_search_registry.py tests/test_products_smart_search_domain.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add tests/test_search_domains_point.py
git commit SciQLop/components/smart_search/domain.py SciQLop/components/smart_search/__init__.py SciQLop/components/smart_search/registry.py tests/test_smart_search_facade.py tests/test_search_domains_point.py -m "feat(plugins): smart-search domains are contributions to sciqlop.search_domains"
```

---

### Task 4: `sciqlop.catalog_providers`

**Files:**
- Modify: `SciQLop/components/catalogs/backend/registry.py` (whole file)
- Modify: `tests/conftest.py:468-482` (the provider snapshot fixture)
- Modify: `tests/test_event_dnd.py:20-28,95-102,128-132`, `tests/test_event_table_drag.py:38-45`
- Test: `tests/test_catalog_providers_point.py`

**Interfaces:**
- Produces: `SciQLop.components.catalogs.backend.registry.CATALOG_PROVIDERS` (`ExtensionPoint` id `sciqlop.catalog_providers`); `provider_key(provider) -> str` (`f"{provider.name}#{id(provider):x}"`); `CatalogRegistry._forget_for_tests(provider)`. `CatalogRegistry.register/unregister/providers/provider_by_name/all_catalogs/instance` and the signals `provider_registered`/`provider_unregistered` keep their signatures.

- [ ] **Step 1: Write the failing tests**

```python
"""Catalog providers are contributions to sciqlop.catalog_providers (Tier 3 spec §3.4)."""
import pytest

from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
from SciQLop.components.catalogs.backend.registry import CATALOG_PROVIDERS, CatalogRegistry, provider_key
from SciQLop.core.extensions import owned_by


@pytest.fixture
def registry(qapp):
    yield CatalogRegistry.instance()
    CATALOG_PROVIDERS.remove_owner("cp_demo")


def _provider(**kw):
    with owned_by("cp_demo"):
        return DummyProvider(num_catalogs=1, events_per_catalog=0, **kw)


def test_a_provider_built_by_a_plugin_is_owned_by_it(registry):
    p = _provider()
    assert CATALOG_PROVIDERS.owner_of(provider_key(p)) == "cp_demo"
    assert p in registry.providers()
    assert registry.provider_by_name("DummyProvider") is not None


def test_withdrawing_the_plugin_unregisters_its_providers(registry, qtbot):
    p = _provider()
    with qtbot.waitSignal(registry.provider_unregistered) as blocker:
        CATALOG_PROVIDERS.remove_owner("cp_demo")
    assert blocker.args == [p]
    assert p not in registry.providers()


def test_two_providers_may_share_a_name(registry):
    a, b = _provider(), _provider()
    assert a in registry.providers() and b in registry.providers()


def test_registering_twice_is_a_no_op(registry):
    p = _provider()
    registry.register(p)
    assert registry.providers().count(p) == 1


def test_a_destroyed_provider_leaves_without_a_signal(registry, qtbot):
    p = _provider()
    key, seen = provider_key(p), []
    registry.provider_unregistered.connect(seen.append)
    try:
        p.deleteLater()
        qtbot.waitUntil(lambda: key not in CATALOG_PROVIDERS)
    finally:
        registry.provider_unregistered.disconnect(seen.append)
    assert seen == []


def test_a_withdrawn_providers_catalogs_leave_the_catalog_tree(registry):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    p = _provider()
    model = CatalogTreeModel()
    assert model._provider_node(p) is not None
    CATALOG_PROVIDERS.remove_owner("cp_demo")
    assert model._provider_node(p) is None


def test_a_provider_built_on_a_worker_thread_registers_under_its_owner(registry, qtbot, monkeypatch):
    # A notebook cell, an agent tool or a live labelling pipeline may build a provider off the main thread.
    from .helpers import call_from_worker_thread
    p = call_from_worker_thread(qtbot, monkeypatch, _provider)
    assert CATALOG_PROVIDERS.owner_of(provider_key(p)) == "cp_demo"
    assert p in registry.providers()


def test_a_provider_built_like_sciqlop_msa_registers_and_lists_its_catalogs(registry):
    from SciQLop.components.catalogs.backend.provider import Catalog, CatalogProvider

    class FlybyProvider(CatalogProvider):
        def __init__(self):
            # sciqlop_msa sets its catalogs before super().__init__: registering asks for catalogs() right away.
            self._flybys = [Catalog(uuid="cp-demo-flyby", name="Flybys", provider=self)]
            super().__init__(name="CP demo flybys", description="Flybys.")

        def catalogs(self):
            return self._flybys

    with owned_by("cp_demo"):
        p = FlybyProvider()
    assert [c.name for c in registry.all_catalogs() if c.provider is p] == ["Flybys"]
```

Check `Catalog`'s constructor in `SciQLop/components/catalogs/backend/provider.py` before running; adapt the keyword arguments of the `Catalog(...)` call to its real fields if they differ (the point of the test is the subclass pattern, not the catalog fields).

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_catalog_providers_point.py -q`
Expected: FAIL with `ImportError: cannot import name 'CATALOG_PROVIDERS'`.

- [ ] **Step 3: Replace `SciQLop/components/catalogs/backend/registry.py`**

```python
"""Catalog providers: the sciqlop.catalog_providers extension point (Tier 3 spec §3.4).

A CatalogProvider registers itself when it is built, under the current owner, so a withdrawn plugin's providers
leave with it. CatalogRegistry keeps its methods and signals, driven by the point.
"""
from __future__ import annotations

import shiboken6
from PySide6.QtCore import QObject, Signal

from SciQLop.core.extensions import ExtensionPoint, current_owner, declare
from SciQLop.user_api.threading import on_main_thread

from .provider import Catalog, CatalogProvider


def provider_key(provider: CatalogProvider) -> str:
    """Providers are instances, and two may share a name: the name keeps error messages readable."""
    return f"{provider.name}#{id(provider):x}"


CATALOG_PROVIDERS = declare(ExtensionPoint(
    "sciqlop.catalog_providers", CatalogProvider, what="catalog provider", key=provider_key,
    doc="Catalog providers; a CatalogProvider registers itself when it is built."))


class CatalogRegistry(QObject):
    """Singleton view of the catalog providers, with the signals the catalog UI listens to."""

    provider_registered = Signal(object)
    provider_unregistered = Signal(object)

    _instance: CatalogRegistry | None = None

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._silenced: set[int] = set()
        CATALOG_PROVIDERS.signals.added.connect(self._on_added)
        CATALOG_PROVIDERS.signals.removed.connect(self._on_removed)

    @classmethod
    def instance(cls) -> CatalogRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, provider: CatalogProvider) -> None:
        """From any thread (a notebook cell, an agent tool, a labelling pipeline): the owner is captured here."""
        self._contribute(provider, current_owner())

    @on_main_thread
    def _contribute(self, provider: CatalogProvider, owner: str) -> None:
        key = provider_key(provider)
        if key in CATALOG_PROVIDERS:
            return
        CATALOG_PROVIDERS.contribute(provider, owner=owner)
        provider.destroyed.connect(lambda *_, k=key, i=id(provider): self._remove_silently(k, i))

    @on_main_thread
    def unregister(self, provider: CatalogProvider) -> None:
        key = provider_key(provider)
        if key in CATALOG_PROVIDERS:
            CATALOG_PROVIDERS.remove(key)

    def _forget_for_tests(self, provider: CatalogProvider) -> None:
        self._remove_silently(provider_key(provider), id(provider))

    @on_main_thread  # `destroyed` fires on the thread that deletes the provider
    def _remove_silently(self, key: str, ident: int) -> None:
        """A destroyed provider leaves without provider_unregistered: its slots would be handed a dead object."""
        if key not in CATALOG_PROVIDERS:
            return
        self._silenced.add(ident)
        try:
            CATALOG_PROVIDERS.remove(key)
        finally:
            self._silenced.discard(ident)

    def _on_added(self, provider: CatalogProvider) -> None:
        if shiboken6.isValid(self):
            self.provider_registered.emit(provider)

    def _on_removed(self, provider: CatalogProvider) -> None:
        if shiboken6.isValid(self) and id(provider) not in self._silenced:
            self.provider_unregistered.emit(provider)

    def providers(self) -> list[CatalogProvider]:
        return CATALOG_PROVIDERS.list()

    def provider_by_name(self, name: str) -> "CatalogProvider | None":
        return next((p for p in self.providers() if p.name == name), None)

    def all_catalogs(self) -> list[Catalog]:
        return [catalog for provider in self.providers() for catalog in provider.catalogs()]
```

`CatalogProvider.__init__` (provider.py:140) already calls `CatalogRegistry.instance().register(self)`: leave it, it is the single path into the point.

- [ ] **Step 4: Tests drop providers through the helper**

In `tests/conftest.py` (the provider snapshot fixture near line 468), replace the two `registry._providers` uses:

```python
    registry = reg_mod.CatalogRegistry.instance()
    snapshot = set(id(p) for p in registry.providers())
    clean_before = [p for p in registry.providers() if not p.is_dirty()]
    yield
    for p in registry.providers():
        if id(p) not in snapshot:
            registry._forget_for_tests(p)
    _forget_dirty_state(clean_before)
```

In `tests/test_event_dnd.py` (three places) and `tests/test_event_table_drag.py` (one place), replace each
`if p in registry._providers: registry._providers.remove(p)` (and the `providers = CatalogRegistry.instance()._providers`
form) with `CatalogRegistry.instance()._forget_for_tests(p)`.

- [ ] **Step 5: Run the catalog tests**

Run: `uv run pytest tests/test_catalog_providers_point.py tests/test_event_dnd.py tests/test_event_table_drag.py tests/test_catalog_dirty_state.py $(ls tests/test_catalog*.py) -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/test_catalog_providers_point.py
git commit SciQLop/components/catalogs/backend/registry.py tests/conftest.py tests/test_event_dnd.py tests/test_event_table_drag.py tests/test_catalog_providers_point.py -m "feat(plugins): catalog providers are contributions to sciqlop.catalog_providers; CatalogRegistry follows the point"
```

---

### Task 5: Declared before plugins, interop proof, docs

**Files:**
- Modify: `SciQLop/components/extension_points.py:7-45`
- Modify: `tests/test_plugin_interop.py` (`_OWNERS` and a new test)
- Modify: `SciQLop/components/agents/skills/sciqlop-plugin-design/references/plugin-contract.md` (EP table, near line 107-123)
- Modify: `SciQLop/components/agents/skills/sciqlop-plugin-design/references/ui-and-settings.md` (new section after "Workspace sections")
- Modify: `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` (§4.3 last Tier 3 row)

**Interfaces:**
- Consumes: `QUICKSTART` (Task 1), `TOURS` (Task 2), `SEARCH_DOMAINS` (Task 3), `CATALOG_PROVIDERS` and `CatalogRegistry` (Task 4).

- [ ] **Step 1: Write the failing interop test**

In `tests/test_plugin_interop.py`, add `"tier3_maker"` to `_OWNERS`, then append:

```python
_TIER3_MAKER = """
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.onboarding import Tour, TourStep, register_tour
    from SciQLop.components.smart_search import register_domain
    from SciQLop.core.sciqlop_application import sciqlop_app

    PROVIDERS = []

    class Domain:
        name = "tier3_maker.events"

        def snapshot(self):
            return []

    def activate(ctx):
        sciqlop_app().add_quickstart_shortcut("Tier3 maker", "Demo", None, lambda: None)
        register_tour(Tour("tier3_maker.tour", "Tour", "A tour", [TourStep("s1", "Title", "Body")]))
        register_domain(Domain())
        PROVIDERS.append(DummyProvider(num_catalogs=1, events_per_catalog=0, name="Tier3 maker"))
"""


def test_plugin_contributes_quickstart_a_tour_a_search_domain_and_a_catalog_provider(tmp_path, main_window, fresh):
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    from SciQLop.components.onboarding.backend.registry import get_tour
    from SciQLop.components.smart_search.domain import SEARCH_DOMAINS
    from SciQLop.core.quickstart import QUICKSTART

    def provider_names():
        return [p.name for p in CatalogRegistry.instance().providers()]

    loader.activate_all([_plugin(tmp_path, "tier3_maker", _TIER3_MAKER)], main_window=main_window, ep_plugins={})
    assert context.STATES["tier3_maker"].status == "active", context.STATES["tier3_maker"].reason
    assert QUICKSTART.owner_of("Tier3 maker") == "tier3_maker"
    assert get_tour("tier3_maker.tour") is not None
    assert SEARCH_DOMAINS.owner_of("tier3_maker.events") == "tier3_maker"
    assert "Tier3 maker" in provider_names()

    loader._withdraw("tier3_maker")
    assert "Tier3 maker" not in QUICKSTART.keys()
    assert get_tour("tier3_maker.tour") is None
    assert "tier3_maker.events" not in SEARCH_DOMAINS.keys()
    assert "Tier3 maker" not in provider_names()
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_plugin_interop.py -q -k tier3`
Expected: PASS already if every module was imported by the main window; FAIL with `NotRegistered` otherwise. Either way continue: Step 3 makes the points exist before any plugin activates, independently of import order.

- [ ] **Step 3: Declare the four points before plugins activate**

In `SciQLop/components/extension_points.py` `prepare_extension_points`, after the `sciqlop.workspace_sections` import line, add:

```python
    import SciQLop.core.quickstart  # noqa: F401  declares sciqlop.quickstart
    from SciQLop.components.onboarding.backend import registry as _tours  # noqa: F401  declares sciqlop.tours
    import SciQLop.components.smart_search  # noqa: F401  declares sciqlop.search_domains and routes it to the index
    from SciQLop.components.catalogs.backend import registry as _catalogs  # noqa: F401  declares sciqlop.catalog_providers
```

- [ ] **Step 4: Document the points**

In `references/plugin-contract.md`, append four rows to the extension-point table (after the `sciqlop.agent_skills` row):

```markdown
| `sciqlop.quickstart` | `QuickstartShortcut(name, description, icon, callback)`, through `sciqlop_app().add_quickstart_shortcut(...)` | `name` |
| `sciqlop.tours` | `Tour(id, title, description, steps)`, through `register_tour(tour)` | `id` |
| `sciqlop.search_domains` | a `SearchDomain` (`name`, `snapshot()`), through `register_domain(domain)` | `name` |
| `sciqlop.catalog_providers` | a `CatalogProvider` subclass instance; it registers itself when built | `name#address` |
```

In `references/ui-and-settings.md`, add after the "Workspace sections" section:

```markdown
## Quickstart shortcuts, tours, search domains, catalog providers

Each of these is owned by your plugin when you add it from `activate(ctx)`, and leaves when your plugin is
withdrawn:

- `sciqlop_app().add_quickstart_shortcut(name, description, icon, callback)` adds a welcome-page shortcut. A name
  already used by another plugin or by SciQLop is refused (`DuplicateContribution`).
- `register_tour(Tour(...))` (`SciQLop.components.onboarding`) adds a guided tour. A tour needs at least one step,
  and step ids must be unique; the `Tour` constructor checks both.
- `register_domain(domain)` (`SciQLop.components.smart_search`) adds a smart-search domain: an object with a `name`
  and a `snapshot()` returning `NodeSnapshot(path_key, raw_text)` items. Call `notify_changed(name)` when its content
  changes.
- Subclass `CatalogProvider` and build it: it registers itself. Build it on the main thread.
```

In the parent spec §4.3, change the last Tier 3 row's "Replaces" cell to end with:
`; quickstart, tours, search_domains and catalog_providers **implemented**: docs/superpowers/plans/2026-10-16-tier3a-quickstart-tours-search-catalogs.md`.

- [ ] **Step 5: Run the interop tests and lint**

Run: `uv run pytest tests/test_plugin_interop.py tests/test_plugin_panel_interop.py -q`
Expected: PASS.
Run: `git ls-files '*.py' | grep -v '^docs/' | xargs uv run flake8 --select=E9,F63,F7,F82 --count`
Expected: `0`.

- [ ] **Step 6: Commit**

```bash
git commit SciQLop/components/extension_points.py tests/test_plugin_interop.py SciQLop/components/agents/skills/sciqlop-plugin-design/references/plugin-contract.md SciQLop/components/agents/skills/sciqlop-plugin-design/references/ui-and-settings.md docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md -m "feat(plugins): Tier 3a points are declared before plugins activate; interop proof and docs"
```
