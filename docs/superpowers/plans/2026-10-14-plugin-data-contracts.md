# Plugin data contracts (plan 1b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plugins contribute data providers, MIME types, source kinds and product kinds through extension points, and the hard-coded dispatch on those four moves onto them.

**Architecture:** Four new extension points built on plan 1a's `ExtensionPoint` (`SciQLop/core/extensions.py`). Each one is declared when its module is imported, the same way the scenes registries are. Core contributions are owned by `"sciqlop"`. Existing published entry points keep working as adapters: the `providers` dict, `register_mime`, legacy `GraphContext.kind` values, and `ParameterType` on product-tree nodes. Plan 1a's deferred loader and resolver items that 1b now makes reachable are fixed first.

**Tech Stack:** Python 3.10+, PySide6, SciQLopPlots (`ParameterType`, `ProductsModel`), pydantic v2, `packaging`, pytest + pytest-qt (+ pytest-xvfb).

**Spec:** `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` (§4.2, §4.3 tier-1 rows for `product_kinds`, `source_kinds`, `data_providers`, `mime_types`, §7, §9 item 2, §10). Plan 1a: `docs/superpowers/plans/2026-10-14-plugin-contract-and-extension-points.md` (implemented on main).

## Global Constraints

- Work and commit on `main`, with explicit pathspecs. Never push. Never stage these untracked files: `importlib.metadata`, `setWidget`, `pydata/`, `.claude/`, the untracked `docs/` drafts, `tests/noop_script.py`.
- One pytest invocation at a time, in the foreground: `uv run --no-sync pytest <files> -q -p no:cacheprovider`. No `--no-xvfb`, because the shell has no DISPLAY. Never `uv sync`. Never rebuild SciQLopPlots. Never edit SciQLopPlots or speasy.
- Write files with the Write/Edit tools. Never use shell heredocs, `cat` or `ls`: they are broken aliases in this tool shell.
- Ids: core contributions are `sciqlop.<name>` or `sciqlop.<component>.<name>`. A plugin's contributions are `<plugin id>.<name>` (spec §4.1).
- Core contributions are owned by `"sciqlop"`. Pass `owner="sciqlop"` explicitly at module import; never rely on the contextvar default (`"user"`) there.
- Extension points are main-thread objects: `contribute`, `remove` and `remove_owner` raise `WrongThread` elsewhere. Code that can run on the kernel thread (notebook cells creating virtual products) marshals with `SciQLop.user_api.threading.on_main_thread`.
- `user_api` is published: no signature changes. `VirtualProductType`, the VP `product_type` strings ("scalar", "vector", "multicomponent", "spectrogram") and `GraphType` keep their meaning (spec §4.2).
- Persisted legacy source kinds `speasy`, `vp`, `function` and `static` load as `sciqlop.speasy`, `sciqlop.vp`, `sciqlop.function` and `sciqlop.static` (spec §4.2, §7).
- Plugin-author docs move with the code (spec §7). The task that changes a contract updates `SciQLop/components/agents/skills/sciqlop-plugin-design/` in the same commit.
- Code style (CLAUDE.md): small functions, data over code, no comment-decorated blocks, a `simplify:` comment on deliberate shortcuts.
- Commit trailer: `Co-Authored-By: <the model writing the commit> <noreply@anthropic.com>`.

## Review Focus

1. **Notebook-created virtual product (kernel thread).** `create_virtual_product` from a notebook cell must still register its provider: it is marshalled to the main thread, and there is no `WrongThread`. → Task 3 (`register_provider` is `@on_main_thread`), and a test that calls it from a worker thread with the invoker stubbed.
2. **Template or workspace saved before 1b, with `kind: "speasy"`.** It reloads, the proxy share still exports the speasy products, and tooltips and inspector lines are unchanged. → Task 5 (legacy-value tests through `ProductModel`, `_plot_config` and `graph_tooltip`).
3. **A graph whose source-kind plugin is not installed** (its kind id is unknown on this machine). The tooltip and inspector show a stand-in naming the kind. The graph never raises and is never dropped. → Task 5 (`source_kind` stand-in test).
4. **A scene, boundary or layer node.** These nodes carry `ParameterType.Scalar`. They must not be read as scalar time series by the product-kind lookup. → Task 7 (scene and layer nodes are tagged; test).
5. **A plugin that fails halfway through `activate()`.** It must not leave a provider, MIME type or kind behind under its name. → Task 1 (withdrawal test).

---

## File map

| File | Role | Task |
|---|---|---|
| `SciQLop/components/plugins/backend/loader/loader.py` | withdraw a failed plugin's contributions | 1 |
| `SciQLop/components/plugins/backend/loader/plugin_desc.py` | unknown-key warning once per file | 1 |
| `SciQLop/components/plugins/backend/loader/resolver.py` | dependency names normalized; optional-cycle loosening per edge | 2 |
| `SciQLop/core/extensions.py` | `ExtensionPoint.remove(key)`, `__contains__` | 3 |
| `SciQLop/components/plotting/backend/data_provider.py` | `sciqlop.data_providers`, `providers` view, `register_provider` | 3 |
| `SciQLop/core/mime/__init__.py`, `SciQLop/components/catalogs/backend/{catalog_mime,event_mime}.py` | `sciqlop.mime_types` | 4 |
| `SciQLop/core/source_kinds.py` (new) | `sciqlop.source_kinds`, core kinds, legacy ids | 5 |
| `SciQLop/core/graph_context.py`, `components/plotting/panel_template.py`, `ui/graph_context_inspector/section.py`, `ui/proxy_share.py`, `ui/time_sync_panel.py`, `backend/easy_provider.py`, `plugins/speasy_provider/speasy_provider.py` | read the source kind instead of if-chains | 5 |
| `SciQLop/core/graph_context.py`, `ui/time_sync_panel.py` | `sciqlop.provider` fallback envelope (§9 item 2) | 6 |
| `SciQLop/core/product_kinds.py` (new) | `sciqlop.product_kinds`, core kinds, node → kind | 7 |
| `ui/time_sync_panel.py`, `backend/remote/plot_remote.py`, `backend/easy_provider.py`, `components/scenes/tree.py`, `user_api/layers/_provider.py` | read the product kind instead of `ParameterType` | 7 |
| `SciQLop/components/extension_points.py` | import the new declaring modules | 3–7 |
| `tests/test_plugin_interop.py` (new), skill references | interop proof, plugin-author docs | 8 |

---

### Task 1: A failed plugin leaves nothing behind; the unknown-key warning is shown once

**Files:**
- Modify: `SciQLop/components/plugins/backend/loader/loader.py` (`_activate_one`, new `_withdraw`)
- Modify: `SciQLop/components/plugins/backend/loader/plugin_desc.py` (`from_json`)
- Test: `tests/test_plugin_activation.py`, `tests/test_plugin_desc.py`

**Interfaces:**
- Consumes: `extensions.all_extension_points()`, `ExtensionPoint.remove_owner(owner)` (plan 1a).
- Produces: `loader._withdraw(name: str) -> None`. It removes every contribution owned by `name` or `legacy:<name>` from every extension point.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_plugin_activation.py`. It reuses the file's `fresh`, `_plugin` and `_desc`:

```python
def test_failed_activate_withdraws_its_contributions(tmp_path, fresh):
    ep = extensions.declare(extensions.ExtensionPoint("wd_test.things", str, key=lambda s: s))
    plugins = [_plugin(tmp_path, "wd_half", """
        def activate(ctx):
            ctx.contribute("wd_test.things", "wd_half.one")
            raise RuntimeError("half way")
    """, _desc())]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert context.STATES["wd_half"].status == "failed"
    assert ep.list() == []


def test_failed_legacy_load_withdraws_its_contributions(tmp_path, fresh):
    ep = extensions.declare(extensions.ExtensionPoint("wd_test.legacy", str, key=lambda s: s))
    plugins = [_plugin(tmp_path, "wd_legacy", """
        from SciQLop.core import extensions
        def load(main_window):
            extensions.get("wd_test.legacy").contribute("wd_legacy.one")
            raise RuntimeError("half way")
    """, _desc())]
    loader.activate_all(plugins, main_window=object(), ep_plugins={})
    assert ep.list() == []
```

Append to `tests/test_plugin_desc.py`:

```python
def test_unknown_keys_are_warned_once_per_file(tmp_path, caplog):
    from SciQLop.components.plugins.backend.loader.plugin_desc import PluginDesc
    path = tmp_path / "plugin.json"
    path.write_text('{"name": "x", "version": "1.0.0", "colour": "red"}')
    PluginDesc.from_json(str(path))
    PluginDesc.from_json(str(path))
    assert sum("unknown keys ignored: colour" in r.getMessage() for r in caplog.records) == 1
```

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/test_plugin_activation.py tests/test_plugin_desc.py -q -p no:cacheprovider`
Expected: the three new tests FAIL. The extension points still hold the items, and the warning is counted twice.

- [ ] **Step 3: Implement**

In `loader.py`, add this next to `_activate_one`:

```python
def _withdraw(name: str) -> None:
    """A failed activation must not leave half its contributions registered under its name."""
    for ep in extensions.all_extension_points():
        ep.remove_owner(name)
        ep.remove_owner(f"legacy:{name}")
```

Import it as `from SciQLop.core import extensions`. Keep the existing `owned_by` import. In the `except` branch of `_activate_one`, call `_withdraw(entry.name)` before returning the `failed` state.

In `plugin_desc.py`:

```python
_warned: set[str] = set()
```

In `from_json`, replace the warning block with:

```python
        if desc.model_extra and path not in _warned:
            _warned.add(path)
            log.warning("%s: unknown keys ignored: %s", path, ", ".join(sorted(desc.model_extra)))
```

Why `_warned` exists: `from_json` runs several times per plugin per scan (settings scan, compat gate, `_desc`, `plugin_requirements`).

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/test_plugin_activation.py tests/test_plugin_desc.py tests/test_plugin_live_activation.py -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plugins/backend/loader/loader.py SciQLop/components/plugins/backend/loader/plugin_desc.py tests/test_plugin_activation.py tests/test_plugin_desc.py
git commit -m "fix(plugins): a failed activation withdraws its contributions; unknown plugin.json keys warned once"
```

---

### Task 2: Resolver — dependency names are normalized; loosening an optional cycle drops only its own edges

**Files:**
- Modify: `SciQLop/components/plugins/backend/loader/resolver.py`
- Test: `tests/test_plugin_resolver.py`

**Interfaces:**
- Consumes: `resolve(candidates, active) -> Resolution` (plan 1a). Its signature is unchanged.
- Produces: the same `Resolution`. `required` and `declared` now hold plugin ids as spelled by the candidate or active plugin (e.g. `planetary_scenes`), even when the dependency was written `planetary-scenes`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_plugin_resolver.py`. It reuses the file's `Candidate` import and helpers; build `Candidate`s directly if there is no helper:

```python
def test_dependency_name_matches_across_dash_underscore_and_case():
    from SciQLop.components.plugins.backend.loader.resolver import Candidate, resolve
    r = resolve({"planetary_scenes": Candidate("planetary_scenes", "1.0.0"),
                 "study": Candidate("study", "1.0.0", ("Planetary-Scenes>=1",))})
    assert r.refused == {}
    assert r.order == ("planetary_scenes", "study")
    assert r.declared["study"] == frozenset({"planetary_scenes"})


def test_normalized_name_also_matches_an_active_plugin():
    from SciQLop.components.plugins.backend.loader.resolver import Candidate, resolve
    r = resolve({"study": Candidate("study", "1.0.0", ("my-dep",))}, active={"my_dep": "2.0"})
    assert r.refused == {} and r.order == ("study",)


def test_loosening_an_optional_cycle_keeps_edges_to_plugins_outside_it():
    from SciQLop.components.plugins.backend.loader.resolver import Candidate, resolve
    r = resolve({"a": Candidate("a", "1", (), ("b", "z")),
                 "b": Candidate("b", "1", (), ("a",)),
                 "z": Candidate("z", "1")})
    assert r.refused == {}
    assert r.order.index("z") < r.order.index("a")
```

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/test_plugin_resolver.py -q -p no:cacheprovider`
Expected: the first two FAIL (refused: "not installed or not enabled"). The third FAILS on the order assertion.

- [ ] **Step 3: Implement**

The names:
1. `_Dep` takes an `ids` map from canonical name to plugin id. It resolves `self.name` through that map:

```python
from packaging.utils import canonicalize_name


class _Dep:
    """A dependency spec as written in plugin.json, kept for messages (packaging reorders specifiers).
    `name` is the plugin id it designates: `my-dep`, `My_Dep` and `my_dep` all name plugin `my_dep`."""

    def __init__(self, spec: str, ids: dict[str, str]):
        self.spec = spec
        try:
            self.req = Requirement(spec)
        except InvalidRequirement as e:
            raise InvalidRequirement(f"invalid dependency {spec!r}: {e}") from e
        self.name = ids.get(canonicalize_name(self.req.name), self.req.name)


def _parse(specs, ids) -> list[_Dep]:
    return [_Dep(s, ids) for s in specs]
```

2. In `resolve`, build `ids = {canonicalize_name(n): n for n in [*active, *candidates]}` before the parse loop. Pass it to both `_parse` calls. Candidates come last so they win.

The loosening is now per edge. `loose` becomes a `set[tuple[str, str]]` of `(plugin, optional dependency)` pairs:

```python
def _edges(cid, candidates, reqs, refused, loose=frozenset(), optional=True) -> set[str]:
    required, wanted = reqs[cid]
    present = {r.name for r in wanted if optional and (cid, r.name) not in loose and r.name in candidates
               and r.name not in refused and _in_range(r, candidates[r.name].version)}
    return {r.name for r in required if r.name in candidates} | present
```

In `_topological`, compute `deps = {c: _edges(c, candidates, reqs, refused, loose) & set(alive) for c in alive}`. Its docstring becomes "the optional edges in *loose* are ignored". `_on_cycle` keeps calling `_edges(..., optional=optional)`. Pass `loose` there too, so an edge that is already loosened is not counted again. Then:

```python
def _loosen_optional_cycles(stuck: set[str], candidates, reqs, refused, loose: set) -> None:
    """With no required cycle left, every cycle has an optional edge: drop the optional edges between its members.
    An optional edge only orders when it can, so `ctx.has()` across such a pair is reliable only in ready()."""
    members = set(_on_cycle(stuck, candidates, reqs, refused, loose, optional=True))
    loose.update((c, r.name) for c in members for r in reqs[c][1] if r.name in members)
```

Update the `_on_cycle` signature to `(stuck, candidates, reqs, refused, loose, optional)`, and update its other caller `_refuse_cycles` (which passes `loose` too). Thread `loose` from `resolve` into `_refuse_cycles`.

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/test_plugin_resolver.py tests/test_plugin_activation.py -q -p no:cacheprovider`
Expected: all PASS, including every plan-1a resolver test.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plugins/backend/loader/resolver.py tests/test_plugin_resolver.py
git commit -m "fix(plugins): dependency names match across case, dash and underscore; optional cycles keep outside edges"
```

---

### Task 3: `sciqlop.data_providers`

**Files:**
- Modify: `SciQLop/core/extensions.py` (add `remove`, `__contains__`)
- Modify: `SciQLop/components/plotting/backend/data_provider.py`
- Modify: `SciQLop/components/extension_points.py`
- Modify: `SciQLop/components/agents/skills/sciqlop-plugin-design/references/products-and-data.md`
- Test: `tests/test_extensions.py`, `tests/test_data_providers_ep.py` (new)

**Interfaces:**
- Consumes: `ExtensionPoint`, `declare`, `current_owner` (plan 1a); `SciQLop.user_api.threading.on_main_thread`.
- Produces:
  - `ExtensionPoint.remove(key: str) -> T`: emits `removed` and raises `NotRegistered` for an unknown key.
  - `key in ep`.
  - `data_provider.DATA_PROVIDERS: ExtensionPoint`, keyed by provider `name`, contribution type `object` (providers are duck-typed).
  - `data_provider.register_provider(provider) -> None`.
  - `data_provider.providers`: a `MutableMapping[str, provider]` view onto `DATA_PROVIDERS`. Same name and import path as before.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_extensions.py`:

```python
def test_remove_one_key_emits_removed(ep, qapp):
    seen = []
    ep.signals.removed.connect(seen.append)
    ep.contribute(Kind("a.x"), owner="a")
    assert "a.x" in ep
    assert ep.remove("a.x") == Kind("a.x")
    assert "a.x" not in ep and seen == [Kind("a.x")]
    with pytest.raises(NotRegistered):
        ep.remove("a.x")
```

Create `tests/test_data_providers_ep.py`:

```python
"""Data providers are contributions to sciqlop.data_providers; `providers` stays a dict-like view (spec §4.3)."""
import pytest

from SciQLop.components.plotting.backend import data_provider
from SciQLop.components.plotting.backend.data_provider import DATA_PROVIDERS, DataProvider, providers
from SciQLop.core.extensions import owned_by


@pytest.fixture
def withdraw(qapp):
    owners = []
    yield owners.append
    for owner in owners:
        DATA_PROVIDERS.remove_owner(owner)


def test_a_provider_is_owned_by_the_plugin_that_created_it(withdraw):
    withdraw("dp_demo")
    with owned_by("dp_demo"):
        p = DataProvider("dp_demo.provider")
    assert providers["dp_demo.provider"] is p
    assert DATA_PROVIDERS.owner_of("dp_demo.provider") == "dp_demo"
    assert "dp_demo.provider" in providers and "dp_demo.provider" in list(providers)


def test_recreating_a_provider_replaces_it(withdraw):
    withdraw("dp_test")
    with owned_by("dp_test"):
        first, second = DataProvider("dp_again"), DataProvider("dp_again")
    assert providers["dp_again"] is second and first is not second


def test_dict_writes_and_pops_go_through_the_extension_point(withdraw):
    withdraw("dp_test")

    class Fake:
        name = "dp_fake"

    seen = []
    DATA_PROVIDERS.signals.removed.connect(seen.append)
    with owned_by("dp_test"):
        providers["dp_fake"] = fake = Fake()
    assert DATA_PROVIDERS.get("dp_fake") is fake
    assert providers.pop("dp_fake") is fake and seen == [fake]
    assert providers.pop("dp_fake", None) is None
    assert providers.get("dp_fake") is None


def test_dict_write_under_another_name_is_refused(withdraw):
    class Fake:
        name = "dp_real"

    with pytest.raises(ValueError, match="named 'dp_real'"):
        providers["dp_other"] = Fake()


def test_off_main_thread_registration_is_marshalled(withdraw, monkeypatch):
    """A notebook cell runs on the kernel thread; the provider must still register (on the main thread)."""
    import threading
    from SciQLop.user_api import threading as sq_threading
    marshalled = []

    def fake_invoker(func, *args, **kwargs):
        marshalled.append(func)
        return None  # the call is recorded, not run: this test pins the marshalling, not Qt's queue

    monkeypatch.setattr(sq_threading, "_invoker", fake_invoker)
    worker = threading.Thread(target=lambda: data_provider.register_provider(type("P", (), {"name": "dp_kernel"})()))
    worker.start()
    worker.join()
    assert len(marshalled) == 1
```

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/test_extensions.py tests/test_data_providers_ep.py -q -p no:cacheprovider`
Expected: FAIL. `remove` and `DATA_PROVIDERS` don't exist.

- [ ] **Step 3: Implement**

In `SciQLop/core/extensions.py`, add these to `ExtensionPoint`, after `get`:

```python
    def __contains__(self, key: str) -> bool:
        return key in self._items

    def remove(self, key: str) -> T:
        _require_main_thread(f"removing from {self.id}")
        item = self.get(key)
        del self._items[key]
        self._owners.pop(key, None)
        self.signals.removed.emit(item)
        return item
```

In `data_provider.py`, replace `providers = {}` with:

```python
DATA_PROVIDERS = declare(ExtensionPoint(
    "sciqlop.data_providers", object, what="data provider", key=attrgetter("name"),
    doc="Data providers by name; a product-tree node names its provider."))


class _ProvidersView(MutableMapping):
    """The historical `providers` dict, read and written through sciqlop.data_providers."""

    def __getitem__(self, name):
        if name not in DATA_PROVIDERS:
            raise KeyError(name)
        return DATA_PROVIDERS.get(name)

    def __setitem__(self, name, provider):
        if getattr(provider, "name", None) != name:
            raise ValueError(f"provider {provider!r} is named {getattr(provider, 'name', None)!r}, not {name!r}")
        register_provider(provider)

    def __delitem__(self, name):
        if name not in DATA_PROVIDERS:
            raise KeyError(name)
        DATA_PROVIDERS.remove(name)

    def __iter__(self):
        return iter([p.name for p in DATA_PROVIDERS.list()])

    def __len__(self):
        return len(DATA_PROVIDERS.list())


providers = _ProvidersView()


@on_main_thread
def register_provider(provider) -> None:
    """A provider re-created under its name replaces the old one, as the `providers` dict always did (spec §7);
    taking over another owner's name is logged, because the spec's raise would break virtual-product re-runs."""
    owner = current_owner()
    previous = DATA_PROVIDERS.owner_of(provider.name) if provider.name in DATA_PROVIDERS else None
    if previous not in (None, owner):
        log.warning(f"data provider {provider.name!r} of {previous} is replaced by one from {owner}")
    DATA_PROVIDERS.contribute(provider, owner=owner, replace=True)
```

The imports to add:
- `from collections.abc import MutableMapping`
- `from operator import attrgetter`
- `from SciQLop.core.extensions import ExtensionPoint, current_owner, declare`
- `from SciQLop.user_api.threading import on_main_thread`

In `DataProvider.__init__`, delete `global providers` and `providers[name] = self`. Make `register_provider(self)` the **last** statement of `DataProvider.__init__`, after `self._owns_fetched_variables`, because `self.name` reads `self._name`.

In `SciQLop/components/extension_points.py`, add `from SciQLop.components.plotting.backend import data_provider  # noqa: F401  importing declares sciqlop.data_providers` inside `prepare_extension_points`. Also update its module docstring list if it has one.

Grep for anything that rebinds the name: `grep -rn "providers = {}\|global providers" SciQLop tests`. Fix any hit the same way.

Docs: in `references/products-and-data.md`, add a short "Data providers" paragraph:
- a `DataProvider` registers itself on construction, owned by the plugin whose `activate` or `load` created it;
- `sciqlop.extensions.get("sciqlop.data_providers")` lists providers;
- a plugin's failed activation removes its providers.

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/test_extensions.py tests/test_data_providers_ep.py tests/test_graph_context_integration.py tests/test_coverage_notice.py tests/test_plotting/test_data_provider_helpers.py tests/test_virtual_products -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/core/extensions.py SciQLop/components/plotting/backend/data_provider.py SciQLop/components/extension_points.py SciQLop/components/agents/skills/sciqlop-plugin-design/references/products-and-data.md tests/test_extensions.py tests/test_data_providers_ep.py
git commit -m "feat(plugins): data providers are contributions to sciqlop.data_providers"
```

---

### Task 4: `sciqlop.mime_types`

**Files:**
- Modify: `SciQLop/core/mime/__init__.py`
- Modify: `SciQLop/components/catalogs/backend/catalog_mime.py`, `SciQLop/components/catalogs/backend/event_mime.py`
- Modify: `SciQLop/components/extension_points.py`
- Modify: `SciQLop/components/agents/skills/sciqlop-plugin-design/references/plugin-contract.md`
- Test: `tests/test_mime_types_ep.py` (new); existing `tests/test_mime.py`, `tests/test_event_mime.py`, `tests/test_catalog_dnd.py`, `tests/test_catalog_tree_dnd.py`, `tests/test_event_dnd.py`

**Interfaces:**
- Consumes: `ExtensionPoint`, `declare`, `__contains__` (Task 3).
- Produces:
  - `SciQLop.core.mime.MimeType(id: str, decoder, encoder=None, obj_type=None, nested_type=None)`, a frozen dataclass.
  - `SciQLop.core.mime.MIME_TYPES: ExtensionPoint`, keyed by `id` (the MIME type string).
  - `register_mime(obj_type, mime_type, encoder, decoder, nested_type=None, owner=None)`: the published signature plus an optional `owner`.
  - `encode_mime` and `decode_mime` keep their signatures and behaviour.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mime_types_ep.py`:

```python
"""MIME types are contributions to sciqlop.mime_types; register_mime/encode_mime/decode_mime keep working."""
from dataclasses import dataclass

import pytest
from PySide6.QtCore import QMimeData

from SciQLop.core.extensions import owned_by
from SciQLop.core.mime import MIME_TYPES, MimeType, decode_mime, encode_mime, register_mime
from SciQLop.core.mime.types import (CATALOG_LIST_MIME_TYPE, EVENT_LIST_MIME_TYPE, PRODUCT_LIST_MIME_TYPE,
                                     TIME_RANGE_MIME_TYPE)


@dataclass(frozen=True)
class _Thing:
    label: str


_THING_MIME = "application/x.mime-ep-test.thing"


@pytest.fixture
def withdraw(qapp):
    yield
    MIME_TYPES.remove_owner("mt_demo")


def test_core_mime_types_are_owned_by_sciqlop(qapp):
    import SciQLop.components.catalogs.backend.catalog_mime  # noqa: F401
    import SciQLop.components.catalogs.backend.event_mime  # noqa: F401
    for mime in (TIME_RANGE_MIME_TYPE, PRODUCT_LIST_MIME_TYPE, CATALOG_LIST_MIME_TYPE, EVENT_LIST_MIME_TYPE):
        assert MIME_TYPES.owner_of(mime) == "sciqlop", mime


def test_a_plugin_mime_type_round_trips(withdraw):
    def encode(thing):
        md = QMimeData()
        md.setData(_THING_MIME, thing.label.encode())
        return md

    with owned_by("mt_demo"):
        MIME_TYPES.contribute(MimeType(_THING_MIME, lambda md: _Thing(bytes(md.data(_THING_MIME)).decode()),
                                       encode, obj_type=_Thing))
    assert decode_mime(encode_mime(_Thing("vdf"))) == _Thing("vdf")
    assert MIME_TYPES.owner_of(_THING_MIME) == "mt_demo"


def test_register_mime_replaces_and_takes_an_owner(withdraw):
    register_mime(_Thing, _THING_MIME, lambda t: QMimeData(), lambda md: "first", owner="mt_demo")
    register_mime(_Thing, _THING_MIME, lambda t: QMimeData(), lambda md: "second", owner="mt_demo")
    md = QMimeData()
    md.setData(_THING_MIME, b"x")
    assert decode_mime(md) == "second"


def test_unknown_formats_decode_to_none(qapp):
    md = QMimeData()
    md.setData("application/x.nobody", b"x")
    assert decode_mime(md) is None
    assert decode_mime(md, preferred_formats=["application/x.nobody"]) is None


def test_empty_list_encodes_to_none(qapp):
    assert encode_mime([]) is None
```

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/test_mime_types_ep.py -q -p no:cacheprovider`
Expected: FAIL with an ImportError on `MIME_TYPES` and `MimeType`.

- [ ] **Step 3: Implement**

Rewrite the registry part of `SciQLop/core/mime/__init__.py`. Keep `encode`, `decode`, and the bodies of `_register_time_range_codec`'s `_encode`/`_decode` exactly as they are:

```python
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from PySide6.QtCore import QByteArray, QDataStream, QIODevice, QMimeData

from SciQLop.core.extensions import ExtensionPoint, declare


@dataclass(frozen=True)
class MimeType:
    id: str                                              # the MIME type string, e.g. "application/x.vdf.slice"
    decoder: Callable[[QMimeData], Any]
    encoder: Optional[Callable[[Any], QMimeData]] = None
    obj_type: Optional[type] = None                      # encode_mime(obj) picks the encoder by exact type(obj)
    nested_type: Optional[type] = None                   # with obj_type list: the type of the list's items


MIME_TYPES = declare(ExtensionPoint("sciqlop.mime_types", MimeType, what="MIME type",
                                    doc="Drag-and-drop payloads: how each MIME type is encoded and decoded."))


def register_mime(obj_type: type, mime_type: str, encoder: Callable[[Any], QMimeData],
                  decoder: Callable[[QMimeData], Any], nested_type: type = None, owner: str = None):
    MIME_TYPES.contribute(MimeType(mime_type, decoder, encoder, obj_type, nested_type), owner=owner, replace=True)


def _encoder_key(obj) -> tuple:
    return (list, type(obj[0])) if type(obj) is list else (type(obj), None)


def encode_mime(object_to_encode: Any) -> QMimeData:
    if type(object_to_encode) is list and not object_to_encode:
        return None
    key = _encoder_key(object_to_encode)
    found = next((m for m in MIME_TYPES.list() if m.encoder and (m.obj_type, m.nested_type) == key), None)
    if found is None:
        raise KeyError(f"no MIME type encodes {key[0].__name__}")
    return found.encoder(object_to_encode)


def decode_mime(mime_data: QMimeData, preferred_formats: List[str] = None) -> Any:
    for f in [*(preferred_formats or []), *mime_data.formats()]:
        if f in MIME_TYPES and mime_data.hasFormat(f):
            return MIME_TYPES.get(f).decoder(mime_data)
    return None
```

The product-list decoder becomes a contribution:

```python
def _register_product_list_decoder():
    from .types import PRODUCT_LIST_MIME_TYPE
    from SciQLopPlots import ProductsModel
    MIME_TYPES.contribute(MimeType(PRODUCT_LIST_MIME_TYPE, ProductsModel.decode_mime_data), owner="sciqlop")
```

The time-range codec ends with `register_mime(TimeRange, TIME_RANGE_MIME_TYPE, _encode, _decode, owner="sciqlop")`. Delete `_MIME_ENCODERS_` and `_MIME_DECODERS_`. Grep for them (`grep -rn "_MIME_ENCODERS_\|_MIME_DECODERS_" SciQLop tests`) and migrate any hit to `MIME_TYPES`.

In `catalog_mime.py`, add `owner="sciqlop"` to the `register_mime(...)` call.

At the end of `event_mime.py`:

```python
MIME_TYPES.contribute(MimeType(EVENT_LIST_MIME_TYPE, decode_event_list), owner="sciqlop")
```

It has no encoder: `encode_event_list` takes three arguments, not one object, and its callers keep calling it directly. Import `MIME_TYPES, MimeType` from `SciQLop.core.mime`.

In `prepare_extension_points`, add `import SciQLop.core.mime  # noqa: F401  declares sciqlop.mime_types` and `from SciQLop.components.catalogs.backend import catalog_mime, event_mime  # noqa: F401`.

Docs: in `references/plugin-contract.md`, add one subsection, "Drag-and-drop payloads (`sciqlop.mime_types`)", with the `MimeType` fields and a 6-line contribution example.

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/test_mime_types_ep.py tests/test_mime.py tests/test_event_mime.py tests/test_catalog_dnd.py tests/test_catalog_tree_dnd.py tests/test_event_dnd.py tests/test_event_table_drag.py tests/test_wf_drag_and_drop.py -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/core/mime/__init__.py SciQLop/components/catalogs/backend/catalog_mime.py SciQLop/components/catalogs/backend/event_mime.py SciQLop/components/extension_points.py SciQLop/components/agents/skills/sciqlop-plugin-design/references/plugin-contract.md tests/test_mime_types_ep.py
git commit -m "feat(plugins): MIME types are contributions to sciqlop.mime_types"
```

---

### Task 5: `sciqlop.source_kinds` replaces the `GraphContext.kind` if-chains

**Files:**
- Create: `SciQLop/core/source_kinds.py`
- Modify: `SciQLop/core/graph_context.py` (the `kind` field, builders, `graph_tooltip`)
- Modify: `SciQLop/components/plotting/panel_template.py` (`ProductModel.kind`, `context_product_path`)
- Modify: `SciQLop/components/plotting/ui/graph_context_inspector/section.py` (`_source_line`)
- Modify: `SciQLop/components/plotting/ui/proxy_share.py` (`_plot_config`)
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py` (`ctx.kind == "vp"` near line 530)
- Modify: `SciQLop/components/plotting/backend/easy_provider.py` (`ctx.kind != "vp"` near line 337)
- Modify: `SciQLop/plugins/speasy_provider/speasy_provider.py` (`ctx.kind != "speasy"` near lines 553, 561)
- Modify: `SciQLop/components/extension_points.py`, `references/products-and-data.md`
- Test: `tests/test_source_kinds.py` (new). Update the legacy-value assertions in `tests/test_graph_context.py` and `tests/test_graph_context_integration.py`.

**Interfaces:**
- Consumes: `ExtensionPoint`, `declare`, `__contains__` (Task 3).
- Produces (in `SciQLop/core/source_kinds.py`):
  - the constants `SPEASY`, `VP`, `FUNCTION`, `STATIC`, `PROVIDER`;
  - `LEGACY_IDS: dict[str, str]`;
  - the frozen dataclass `SourceKind(id, tooltip, inspector_line, product_path=<returns "">, shareable=False)`;
  - `SOURCE_KINDS: ExtensionPoint`;
  - `canonical_id(kind: str) -> str`;
  - `source_kind(kind: str) -> SourceKind`, which returns a stand-in for unknown ids.
  
  `GraphContext.kind` and `ProductModel.kind` hold canonical ids. Task 6 uses `PROVIDER`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_source_kinds.py`:

```python
"""Source kinds (spec §4.2): legacy values load, core kinds drive tooltips, a plugin kind is used like a core one."""
import pytest

from SciQLop.core.extensions import owned_by
from SciQLop.core.graph_context import GraphContext, graph_tooltip
from SciQLop.core.source_kinds import (FUNCTION, PROVIDER, SOURCE_KINDS, SPEASY, STATIC, VP, SourceKind,
                                       source_kind)


def _ctx(**kw):
    return GraphContext(**{"graph_id": "g", "panel_name": "P", "plot_index": 0, "graph_type": "Line", **kw})


class _Graph:
    """Just enough of a SciQLopPlots graph for context_of/graph_tooltip."""

    def __init__(self, ctx):
        self._md = ctx.to_meta_data()

    def meta_data(self):
        return self._md

    def objectName(self):
        return "g"

    name = "B"


@pytest.fixture
def withdraw(qapp):
    yield
    SOURCE_KINDS.remove_owner("sk_demo")


@pytest.mark.parametrize("legacy, canonical", [("speasy", SPEASY), ("vp", VP), ("function", FUNCTION),
                                               ("static", STATIC)])
def test_legacy_values_load_as_canonical_ids(legacy, canonical):
    from SciQLop.components.plotting.panel_template import ProductModel
    assert _ctx(kind=legacy).kind == canonical
    assert ProductModel(path="a//b", kind=legacy).kind == canonical
    assert ProductModel(path="a//b").kind is None


def test_core_kinds_are_owned_by_sciqlop(qapp):
    for kid in (SPEASY, VP, FUNCTION, STATIC, PROVIDER):
        assert SOURCE_KINDS.owner_of(kid) == "sciqlop"


def test_core_tooltips_are_unchanged(qapp):
    assert graph_tooltip(_Graph(_ctx(kind="speasy", speasy_id="amda/imf"))).splitlines()[0] == "B: amda/imf — Speasy"
    assert graph_tooltip(_Graph(_ctx(kind="vp", vp_path="a/b"))).splitlines()[0] == "B: a/b — Virtual"
    assert graph_tooltip(_Graph(_ctx(kind="static"))).splitlines()[0] == "B: static data"
    fn = _ctx(kind="function", callback_module="m", callback_qualname="f")
    assert graph_tooltip(_Graph(fn)).splitlines()[0] == "B: function m.f"


def test_a_plugin_source_kind_drives_tooltip_inspector_and_template(withdraw):
    from SciQLop.components.plotting.panel_template import context_product_path
    from SciQLop.components.plotting.ui.graph_context_inspector.section import _source_line
    with owned_by("sk_demo"):
        SOURCE_KINDS.contribute(SourceKind("sk_demo.cdf", tooltip=lambda c: f"{c.provider_name} file",
                                           inspector_line=lambda c: "CDF file",
                                           product_path=lambda c: "cdf//x"))
    ctx = _ctx(kind="sk_demo.cdf", provider_name="CDF")
    assert graph_tooltip(_Graph(ctx)).splitlines()[0] == "B: CDF file"
    assert _source_line(ctx) == "CDF file"
    assert context_product_path(ctx) == "cdf//x"


def test_a_kind_whose_plugin_is_missing_gets_a_stand_in(qapp):
    from SciQLop.components.plotting.panel_template import context_product_path
    ctx = _ctx(kind="sk_gone.cdf")
    assert ctx.kind == "sk_gone.cdf"
    assert "sk_gone.cdf" in source_kind(ctx.kind).inspector_line(ctx)
    assert "B: sk_gone.cdf" in graph_tooltip(_Graph(ctx))
    assert context_product_path(ctx) == ""


def test_saved_speasy_products_are_still_shared(qapp):
    from SciQLop.components.plotting.panel_template import PlotModel, ProductModel
    from SciQLop.components.plotting.ui.proxy_share import _plot_config
    plot = PlotModel(products=[ProductModel(path="speasy//amda//imf", kind="speasy", speasy_id="amda/imf")])
    assert _plot_config(plot) is not None
    plot = PlotModel(products=[ProductModel(path="vp//x", kind="vp", speasy_id="amda/imf")])
    assert _plot_config(plot) is None
```

In `tests/test_graph_context.py` and `tests/test_graph_context_integration.py`, change each assertion of a legacy value. That is `.kind == "speasy"`, `"vp"`, `"static"` and `"function"`, and `md["kind"] == "speasy"`. Use the constants from `SciQLop.core.source_kinds` instead (`SPEASY`, `VP`, `STATIC`, `FUNCTION`). Constructors that pass `kind="speasy"` stay as they are, because they exercise the alias.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/test_source_kinds.py -q -p no:cacheprovider`
Expected: FAIL with an ImportError on `SciQLop.core.source_kinds`.

- [ ] **Step 3: Implement**

Create `SciQLop/core/source_kinds.py`:

```python
"""Where a graph's data comes from: the sciqlop.source_kinds extension point (spec §4.2)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from SciQLop.core.extensions import ExtensionPoint, declare

if TYPE_CHECKING:
    from SciQLop.core.graph_context import GraphContext

SPEASY, VP, FUNCTION, STATIC, PROVIDER = (
    "sciqlop.speasy", "sciqlop.vp", "sciqlop.function", "sciqlop.static", "sciqlop.provider")
# Values written before source kinds were contributions; saved workspaces and templates still hold them.
LEGACY_IDS = {"speasy": SPEASY, "vp": VP, "function": FUNCTION, "static": STATIC}


def _nothing(ctx: GraphContext) -> str:
    return ""


@dataclass(frozen=True)
class SourceKind:
    id: str
    tooltip: Callable[[GraphContext], str]                 # after "<graph name>: " in the inspector tree tooltip
    inspector_line: Callable[[GraphContext], str]          # the source line of the graph inspector
    product_path: Callable[[GraphContext], str] = _nothing  # "a//b//c" to re-plot from (templates), "" if none
    shareable: bool = False                                # Export & Share can send it to the Speasy proxy


SOURCE_KINDS = declare(ExtensionPoint("sciqlop.source_kinds", SourceKind, what="source kind",
                                      doc="Where a graph's data comes from: tooltip, inspector line, template path."))


def canonical_id(kind: str) -> str:
    return LEGACY_IDS.get(kind, kind)


def _missing(kid: str) -> SourceKind:
    text = f"{kid} (plugin not loaded)"
    return SourceKind(kid, tooltip=lambda ctx: text, inspector_line=lambda ctx: text)


def source_kind(kind: str) -> SourceKind:
    """The registered kind, or a stand-in naming it when the plugin that provides it is not loaded."""
    kid = canonical_id(kind)
    return SOURCE_KINDS.get(kid) if kid in SOURCE_KINDS else _missing(kid)


def _path(parts) -> str:
    from SciQLop.core.snippets import format_product_path
    return format_product_path(parts) if parts else ""


def _callback(ctx: GraphContext) -> str:
    return f"{ctx.callback_module}.{ctx.callback_qualname}".strip(".")


def _speasy_path(ctx: GraphContext) -> str:
    return _path(ctx.product_path) or (ctx.speasy_id or "")


def _vp_path(ctx: GraphContext) -> str:
    return _path(ctx.product_path) or (_path(ctx.vp_path.split("/")) if ctx.vp_path else "")


def _provider_path(ctx: GraphContext) -> str:
    return _path(ctx.product_path)


_CORE = (
    SourceKind(SPEASY, lambda c: f"{c.speasy_id} — Speasy", lambda c: f"Speasy: {c.speasy_id}", _speasy_path,
               shareable=True),
    SourceKind(VP, lambda c: f"{c.vp_path} — Virtual", lambda c: f"Virtual: {c.vp_path}", _vp_path),
    SourceKind(FUNCTION, lambda c: f"function {_callback(c)}", lambda c: f"Function: {_callback(c)}"),
    SourceKind(STATIC, lambda c: "static data", lambda c: "Static data"),
    SourceKind(PROVIDER, lambda c: f"{_provider_path(c) or c.graph_id} — {c.provider_name}",
               lambda c: f"{c.provider_name}: {_provider_path(c) or c.graph_id}", _provider_path),
)

for _kind in _CORE:
    SOURCE_KINDS.contribute(_kind, owner="sciqlop")
```

In `core/graph_context.py`:
- Delete `GraphKind`. Change the field to `kind: str`.
- Add a validator, and import `field_validator` from pydantic:

```python
    @field_validator("kind", mode="before")
    @classmethod
    def _canonical_kind(cls, kind):
        """Saved contexts may hold the pre-extension-point values ("speasy", "vp", ...)."""
        return canonical_id(kind) if isinstance(kind, str) else kind
```

- The builders use `SPEASY`, `VP`, `FUNCTION` and `STATIC`.
- In `graph_tooltip`, replace the if-chain with `title = f"{name}: {source_kind(ctx.kind).tooltip(ctx)}"`.
- Import with `from SciQLop.core.source_kinds import FUNCTION, SPEASY, STATIC, VP, canonical_id, source_kind`.

In `panel_template.py`:
- Give `ProductModel.kind` the same `before` validator. `None` passes through: `canonical_id(kind) if isinstance(kind, str) else kind`.
- `context_product_path(ctx)` becomes `return source_kind(ctx.kind).product_path(ctx)`. Keep its docstring.

In `section.py`, `_source_line(ctx)` becomes `return source_kind(ctx.kind).inspector_line(ctx)`.

In `proxy_share.py`, the filter becomes `if source_kind(p.kind or "").shareable and p.speasy_id`.

These checks use the constants instead of the string literals:
- `time_sync_panel.py` around line 530: `ctx.kind == VP`;
- `easy_provider.py` around line 337: `ctx.kind != VP`;
- `speasy_provider.py` around lines 553 and 561: `ctx.kind != SPEASY`.

Then run `grep -rn '\.kind *[!=]= *"\(speasy\|vp\|static\|function\)"' SciQLop`. Expected output: none.

In `prepare_extension_points`, add `import SciQLop.core.source_kinds  # noqa: F401  declares sciqlop.source_kinds`.

Docs: in `references/products-and-data.md`, add a "Source kinds" subsection:
- the `SourceKind` fields;
- that `GraphContext.kind` now holds ids such as `sciqlop.speasy`, and that the old short values are still read;
- how a plugin contributes one (plugin code comparing `ctx.kind == "speasy"` must compare to `SciQLop.core.source_kinds.SPEASY`).

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/test_source_kinds.py tests/test_graph_context.py tests/test_graph_context_integration.py tests/test_provider_snippets.py tests/test_proxy_share.py tests/test_panel_template.py tests/test_panel_template_integration.py tests/test_panel_container.py tests/test_tooltips.py tests/test_template_axes.py tests/test_speasy_provider_knobs.py -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/core/source_kinds.py SciQLop/core/graph_context.py SciQLop/components/plotting/panel_template.py SciQLop/components/plotting/ui/graph_context_inspector/section.py SciQLop/components/plotting/ui/proxy_share.py SciQLop/components/plotting/ui/time_sync_panel.py SciQLop/components/plotting/backend/easy_provider.py SciQLop/plugins/speasy_provider/speasy_provider.py SciQLop/components/extension_points.py SciQLop/components/agents/skills/sciqlop-plugin-design/references/products-and-data.md tests/test_source_kinds.py tests/test_graph_context.py tests/test_graph_context_integration.py
git commit -m "feat(plugins): source kinds are contributions to sciqlop.source_kinds; legacy kind values still load"
```

---

### Task 6: Graphs of third-party providers get a `sciqlop.provider` envelope (spec §9 item 2)

**Files:**
- Modify: `SciQLop/core/graph_context.py` (new `build_provider_ctx`)
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py` (`_attach_graph_context`: the final "unknown provider" branch and the docstring)
- Test: `tests/test_graph_context_integration.py`

**Interfaces:**
- Consumes: `PROVIDER` and `GraphContext.kind` validation (Task 5).
- Produces: `build_provider_ctx(graph, *, panel_name, plot_index, provider, graph_type, product_path=None, knobs=None) -> GraphContext`. Its kind is `getattr(provider, "source_kind", PROVIDER)`, so a plugin provider names its own source kind with a `source_kind` attribute.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_graph_context_integration.py`, reusing the shape of `test_post_plot_invokes_attach_context_for_speasy` at the top of the file:

```python
def _post_plot_with(monkeypatch, provider, node):
    from SciQLop.components.plotting.ui import time_sync_panel as tsp
    from PySide6.QtCore import QObject
    captured = {}
    monkeypatch.setattr(tsp, "attach_context", lambda graph, ctx, rich=None: captured.update(ctx=ctx))
    monkeypatch.setattr(tsp, "_set_product_path", lambda *a, **kw: None)
    monkeypatch.setattr(tsp, "_register_graph_hints", lambda *a, **kw: None)
    monkeypatch.setattr(tsp, "_attach_knob_state", lambda *a, **kw: None)

    class _Graph(QObject):
        def set_name(self, n): self.setObjectName(n)
        def name(self): return self.objectName()

    class _Plot(QObject):
        pass

    class _Target:
        def plots(self): return [_Plot()]
        def windowTitle(self): return "PanelX"

    graph = _Graph()
    graph.setObjectName("g0")
    tsp._post_plot((_Plot(), graph), provider, node, type("C", (), {"_post_fetch": None})(), _Target(),
                   "demo//b", existing_plot=None)
    return captured.get("ctx")


class _PathNode:
    def name(self): return "b"
    def path(self): return ["demo", "b"]
    def metadata(self, key=None): return None if key else {}


def test_third_party_provider_gets_the_provider_envelope(qtbot, monkeypatch):
    from SciQLop.core.source_kinds import PROVIDER

    class ThirdParty:
        name = "ThirdParty"

    ctx = _post_plot_with(monkeypatch, ThirdParty(), _PathNode())
    assert ctx is not None and ctx.kind == PROVIDER
    assert ctx.provider_name == "ThirdParty" and ctx.product_path == ["demo", "b"]


def test_provider_names_its_own_source_kind(qtbot, monkeypatch):
    class CdfProvider:
        name = "Cdf"
        source_kind = "cdf_plugin.file"

    ctx = _post_plot_with(monkeypatch, CdfProvider(), _PathNode())
    assert ctx.kind == "cdf_plugin.file"
```

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/test_graph_context_integration.py -q -p no:cacheprovider -k "provider_envelope or own_source_kind"`
Expected: FAIL. `ctx` is `None`, because nothing is attached.

- [ ] **Step 3: Implement**

In `core/graph_context.py`, next to the other builders:

```python
def build_provider_ctx(graph, *, panel_name: str, plot_index: int, provider, graph_type: str,
                       product_path: Optional[list] = None, knobs: Optional[dict] = None) -> GraphContext:
    """Any other provider: its own source kind if it names one, else the generic sciqlop.provider envelope."""
    return GraphContext(
        kind=getattr(provider, "source_kind", PROVIDER),
        graph_id=graph.objectName(),
        panel_name=panel_name,
        plot_index=plot_index,
        graph_type=graph_type,
        provider_name=getattr(provider, "name", None),
        product_path=list(product_path) if product_path else None,
        knobs=knobs or {},
    )
```

In `time_sync_panel.py` `_attach_graph_context`, replace the trailing `log.debug("graph_context: unknown provider %r — skipping attach", ...)` with:

```python
        ctx = build_provider_ctx(graph, panel_name=panel_name, plot_index=plot_index, provider=provider,
                                 graph_type=graph_type, product_path=product_path, knobs=knobs)
        attach_context(graph, ctx, GraphRichRefs(fetch_callback=fetch_callback))
        _install_graph_context_ui(plot, graph)
```

Rewrite the function docstring. EasyProvider and Speasy get their dedicated envelopes. Every other provider gets `build_provider_ctx`. Import `build_provider_ctx` where `build_speasy_ctx` is imported.

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/test_graph_context_integration.py tests/test_graph_context.py tests/test_source_kinds.py -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/core/graph_context.py SciQLop/components/plotting/ui/time_sync_panel.py tests/test_graph_context_integration.py
git commit -m "fix(plotting): graphs of third-party providers get a sciqlop.provider context instead of none"
```

---

### Task 7: `sciqlop.product_kinds` replaces the `ParameterType` switches

**Files:**
- Create: `SciQLop/core/product_kinds.py`
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py` (`_plot_product`, the two `node.parameter_type()` branches)
- Modify: `SciQLop/components/plotting/backend/remote/plot_remote.py` (`ptype == ParameterType.Spectrogram`)
- Modify: `SciQLop/components/plotting/backend/easy_provider.py` (the arity near line 211; tag the node's metadata)
- Modify: `SciQLop/components/scenes/tree.py` (`_add_node`: tag the node)
- Modify: `SciQLop/user_api/layers/_provider.py` (tag the node)
- Modify: `SciQLop/components/extension_points.py`, `references/products-and-data.md`
- Test: `tests/test_product_kinds.py` (new)

**Interfaces:**
- Consumes: `ExtensionPoint`, `declare`, `__contains__` (Task 3).
- Produces (in `SciQLop/core/product_kinds.py`):
  - the constants `SCALAR`, `VECTOR`, `MULTICOMPONENT`, `SPECTROGRAM`, `SCENE`, `BOUNDARY`, `LAYER`, `PRODUCT_KIND_KEY`;
  - the frozen dataclass `ProductKind(id, label, arity, default_plot_kind, parameter_type=None)`;
  - `PRODUCT_KINDS: ExtensionPoint`;
  - `kind_id_for(parameter_type) -> str | None`;
  - `product_kind_of(node) -> ProductKind | None`.
  
  Plan 1c reads `default_plot_kind`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_product_kinds.py`:

```python
"""Product kinds (spec §4.2): a data shape per product; nodes say theirs, or their parameter type does."""
import pytest

from SciQLop.core.enums import ParameterType
from SciQLop.core.extensions import owned_by
from SciQLop.core.product_kinds import (BOUNDARY, LAYER, MULTICOMPONENT, PRODUCT_KIND_KEY, PRODUCT_KINDS, SCALAR,
                                        SCENE, SPECTROGRAM, VECTOR, ProductKind, product_kind_of)


class _Node:
    def __init__(self, parameter_type=ParameterType.Scalar, **metadata):
        self._pt, self._md = parameter_type, metadata

    def parameter_type(self):
        return self._pt

    def metadata(self, key=None):
        return self._md.get(key) if key else dict(self._md)


@pytest.fixture
def withdraw(qapp):
    yield
    PRODUCT_KINDS.remove_owner("pk_demo")


def test_core_kinds_are_owned_by_sciqlop(qapp):
    for kid in (SCALAR, VECTOR, MULTICOMPONENT, SPECTROGRAM, SCENE, BOUNDARY, LAYER):
        assert PRODUCT_KINDS.owner_of(kid) == "sciqlop"
    assert PRODUCT_KINDS.get(SPECTROGRAM).arity == 3 and PRODUCT_KINDS.get(VECTOR).arity == 2


@pytest.mark.parametrize("pt, kid", [(ParameterType.Scalar, SCALAR), (ParameterType.Vector, VECTOR),
                                     (ParameterType.Multicomponents, MULTICOMPONENT),
                                     (ParameterType.Spectrogram, SPECTROGRAM)])
def test_untagged_nodes_are_read_by_parameter_type(pt, kid):
    assert product_kind_of(_Node(pt)).id == kid


def test_untagged_node_without_a_data_parameter_type_has_no_kind(qapp):
    assert product_kind_of(_Node(ParameterType.NotAParameter)) is None


def test_the_tag_wins_over_the_parameter_type(withdraw):
    with owned_by("pk_demo"):
        PRODUCT_KINDS.contribute(ProductKind("pk_demo.distribution", "VDF", 3, "pk_demo.slice_plot"))
    node = _Node(ParameterType.Scalar, **{PRODUCT_KIND_KEY: "pk_demo.distribution"})
    assert product_kind_of(node).id == "pk_demo.distribution"


def test_a_tag_whose_plugin_is_missing_is_not_read_as_its_parameter_type(qapp):
    assert product_kind_of(_Node(ParameterType.Scalar, **{PRODUCT_KIND_KEY: "pk_gone.distribution"})) is None


def test_scene_and_boundary_nodes_are_tagged(qapp, monkeypatch):
    from SciQLop.components.scenes import tree
    added = []
    monkeypatch.setattr(tree, "add_product_node", lambda *args, **kw: added.append(args))
    tree._add_node(["Scenes", "pk_scene"], "scene", "d")
    tree._add_node(["Models", "Earth", "magnetopause", "pk_mp"], "boundary", "d")
    assert [a[3][PRODUCT_KIND_KEY] for a in added] == [SCENE, BOUNDARY]


def test_virtual_product_nodes_are_tagged(qapp):
    import numpy as np
    from SciQLopPlots import ProductsModel
    from SciQLop.user_api.virtual_products import VirtualProductType, create_virtual_product

    def spec(start: float, stop: float):
        t = np.arange(3.0)
        return t, np.arange(4.0), np.ones((3, 4))

    create_virtual_product("pk_tests/spec", spec, VirtualProductType.Spectrogram)
    node = ProductsModel.node(["pk_tests", "spec"])
    assert node is not None and node.metadata()[PRODUCT_KIND_KEY] == SPECTROGRAM
```

Before writing the last test, check how the existing virtual-product tests build a VP and look one up: `grep -rn "create_virtual_product(" tests | head`. Follow that pattern if it differs, for example on the path root. If `ProductsModel.node` needs a leading root element there, use that path.

The layers node gets the same tag. Add an assertion to the existing layers test that builds a layer, if one exists (`grep -rln "sciqlop_kind" tests`). Otherwise, check the tag in `_provider.py` by reading it in the review.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/test_product_kinds.py -q -p no:cacheprovider`
Expected: FAIL with an ImportError on `SciQLop.core.product_kinds`.

- [ ] **Step 3: Implement**

Create `SciQLop/core/product_kinds.py`:

```python
"""What a product's data looks like: the sciqlop.product_kinds extension point (spec §4.2).

A product kind is a data shape, not a rendering choice: GraphType stays the plot's choice of graph,
and VirtualProductType and the virtual-product type strings keep their published meaning.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from SciQLop.core.enums import ParameterType
from SciQLop.core.extensions import ExtensionPoint, declare

SCALAR, VECTOR, MULTICOMPONENT, SPECTROGRAM = (
    "sciqlop.scalar", "sciqlop.vector", "sciqlop.multicomponent", "sciqlop.spectrogram")
SCENE, BOUNDARY, LAYER = "sciqlop.scenes.scene", "sciqlop.scenes.boundary", "sciqlop.layer"
PRODUCT_KIND_KEY = "product_kind"  # product-tree node metadata; nodes without it are read by parameter type


@dataclass(frozen=True)
class ProductKind:
    id: str
    label: str
    arity: int                     # arrays per fetch: 2 = (time, values), 3 = (time, y, z), 0 = no data stream
    default_plot_kind: str         # a sciqlop.plot_kinds id (plan 1c)
    parameter_type: object = None  # the SciQLopPlots ParameterType a product-tree node of this kind carries


PRODUCT_KINDS = declare(ExtensionPoint("sciqlop.product_kinds", ProductKind, what="product kind",
                                       doc="Data shapes of products: what a fetch returns and how it plots by default."))

_CORE = (
    ProductKind(SCALAR, "Scalar", 2, "sciqlop.timeseries", ParameterType.Scalar),
    ProductKind(VECTOR, "Vector", 2, "sciqlop.timeseries", ParameterType.Vector),
    ProductKind(MULTICOMPONENT, "Multi-component", 2, "sciqlop.timeseries", ParameterType.Multicomponents),
    ProductKind(SPECTROGRAM, "Spectrogram", 3, "sciqlop.timeseries", ParameterType.Spectrogram),
    ProductKind(SCENE, "Scene", 0, "sciqlop.scenes.projection"),
    ProductKind(BOUNDARY, "Boundary model", 0, "sciqlop.scenes.projection"),
    ProductKind(LAYER, "Annotation layer", 0, "sciqlop.timeseries"),
)
# Speasy's nodes, and those of providers written before product kinds, only carry a parameter type.
_BY_PARAMETER_TYPE = {k.parameter_type: k.id for k in _CORE if k.parameter_type is not None}

for _kind in _CORE:
    PRODUCT_KINDS.contribute(_kind, owner="sciqlop")


def kind_id_for(parameter_type) -> Optional[str]:
    return _BY_PARAMETER_TYPE.get(parameter_type)


def product_kind_of(node) -> Optional[ProductKind]:
    """The node's tagged kind, else the kind of its parameter type; None when unknown here (plugin not loaded)."""
    kid = (node.metadata() or {}).get(PRODUCT_KIND_KEY) or kind_id_for(node.parameter_type())
    return PRODUCT_KINDS.get(kid) if kid in PRODUCT_KINDS else None
```

Check first that `SciQLop.core.enums` re-exports `ParameterType`; `scenes/tree.py` imports it from there. If `ParameterType` members are not hashable, key `_BY_PARAMETER_TYPE` by `int(...)` or `.name` on both sides, and say so in the report.

Migrate the sites:
1. `time_sync_panel.py` `_plot_product`: replace `log.debug(f"Parameter type: ...")` and the two `node.parameter_type()` tests:

```python
    kind = product_kind_of(node)
    log.debug(f"Product kind: {kind.id if kind else None}")
    if kind is not None and kind.arity == 2:
        ...   # the existing line-graph body, unchanged
    if kind is not None and kind.arity == 3:
        ...   # the existing colour-map body, unchanged
    return None
```

   Drop the `ParameterType` import from `time_sync_panel.py` only if nothing else uses it.
2. `plot_remote.py`: `kind = product_kind_of(node)`, then `if kind is not None and kind.arity == 3:`.
3. `easy_provider.py`: at the start of `EasyProvider.__init__`'s body, compute `kind_id = kind_id_for(parameter_type)`.
   - `arity = 3 if parameter_type == ParameterType.Spectrogram else 2` becomes `arity = PRODUCT_KINDS.get(kind_id).arity`.
   - Add `PRODUCT_KIND_KEY: kind_id` to the `metadata` dict that reaches `add_product_node`.
4. `scenes/tree.py` `_add_node`: add `PRODUCT_KIND_KEY: _PRODUCT_KINDS[kind]` to the metadata dict, with the module constant `_PRODUCT_KINDS = {"scene": SCENE, "boundary": BOUNDARY}`.
5. `user_api/layers/_provider.py`: add `PRODUCT_KIND_KEY: LAYER` to the node metadata.

Leave these unchanged:
- `speasy_provider.graph_type` (it chooses the graph to render, which is GraphType's job);
- the VP type-string tables in `user_api` (`data_types`, `virtual_products/registry.py`, `validation.py`, `layers/_renderer.py`).

In `prepare_extension_points`, add `import SciQLop.core.product_kinds  # noqa: F401  declares sciqlop.product_kinds`.

Docs: in `references/products-and-data.md`, add a "Product kinds" subsection covering:
- the `ProductKind` fields;
- the `product_kind` node-metadata tag a plugin sets on its product-tree nodes (`add_product_node(..., {PRODUCT_KIND_KEY: "vdf.distribution", ...}, ...)`);
- that rendering of a plugin kind arrives with plot kinds (plan 1c).

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/test_product_kinds.py tests/test_plot_product_inputs.py tests/test_plotting tests/remote/test_plot_remote.py tests/test_virtual_products tests/scenes tests/test_layers tests/test_speasy_plot_backend.py -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/core/product_kinds.py SciQLop/components/plotting/ui/time_sync_panel.py SciQLop/components/plotting/backend/remote/plot_remote.py SciQLop/components/plotting/backend/easy_provider.py SciQLop/components/scenes/tree.py SciQLop/user_api/layers/_provider.py SciQLop/components/extension_points.py SciQLop/components/agents/skills/sciqlop-plugin-design/references/products-and-data.md tests/test_product_kinds.py
git commit -m "feat(plugins): product kinds are contributions to sciqlop.product_kinds; plotting reads the kind, not ParameterType"
```

---

### Task 8: Interop proof and plugin-author docs

**Files:**
- Create: `tests/test_plugin_interop.py`
- Modify: `SciQLop/components/agents/skills/sciqlop-plugin-design/references/plugin-contract.md` (the 1b catalogue)
- Modify: `SciQLop/components/agents/skills/sciqlop-plugin-design/SKILL.md` (one line pointing to the data contracts)
- Modify: spec §4.3 status line (`docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md`)

**Interfaces:**
- Consumes: everything from Tasks 1–7. It also uses `loader.activate_all(plugin_list, main_window, ep_plugins={})` and `context.STATES` (plan 1a).
- Produces: none (test and docs only).

- [ ] **Step 1: Write the test**

Create `tests/test_plugin_interop.py`. The fixture is local on purpose: importing fixtures across test files is a parked hazard from plan 1a.

```python
"""Spec §10 interop proof for data contracts: one plugin declares a product kind, a source kind, a provider and
an extension point; a second uses its API and fills that extension point; a third, activated later, is seen
through `added`."""
import json
import sys
import textwrap

import pytest

from SciQLop.components.plugins.backend.loader import context, loader
from SciQLop.core import extensions

_OWNERS = ("io_vdf", "io_study", "io_late")


@pytest.fixture
def fresh(qapp):
    saved = (dict(context.STATES), set(loader._attempted), dict(vars(loader.loaded_plugins)),
             dict(extensions._EXTENSION_POINTS))
    yield
    for ep in extensions.all_extension_points():
        for owner in _OWNERS:
            ep.remove_owner(owner)
    for live, old in zip((context.STATES, loader._attempted, vars(loader.loaded_plugins),
                          extensions._EXTENSION_POINTS), saved):
        live.clear()
        live.update(old)


def _plugin(folder, name, code, **desc):
    pkg = folder / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(textwrap.dedent(code))
    (pkg / "plugin.json").write_text(json.dumps({"name": name, "version": "1.0.0", **desc}))
    return (str(folder), name)


_VDF = """
    from dataclasses import dataclass
    from SciQLop.components.plotting.backend.data_provider import DataProvider
    from SciQLop.core.product_kinds import PRODUCT_KINDS, ProductKind
    from SciQLop.core.source_kinds import SOURCE_KINDS, SourceKind

    @dataclass(frozen=True)
    class Method:
        id: str

    class VdfProvider(DataProvider):
        source_kind = "io_vdf.instrument"

    class Api:
        Method = Method
        def __init__(self, ep):
            self.seen = []
            ep.signals.added.connect(lambda m: self.seen.append(m.id))

    def activate(ctx):
        ep = ctx.extension_point("io_vdf.methods", Method)
        ctx.contribute("sciqlop.product_kinds", ProductKind("io_vdf.distribution", "VDF", 3, "io_vdf.slice_plot"))
        ctx.contribute("sciqlop.source_kinds", SourceKind("io_vdf.instrument", lambda c: "VDF", lambda c: "VDF"))
        VdfProvider("io_vdf")
        return Api(ep)
"""

_STUDY = """
    def activate(ctx):
        vdf = ctx.plugin("io_vdf")
        ctx.contribute("io_vdf.methods", vdf.Method("io_study.moments"))
"""

_LATE = """
    def activate(ctx):
        ctx.contribute("io_vdf.methods", ctx.plugin("io_vdf").Method("io_late.fit"))
"""


def test_plugins_share_kinds_providers_and_extension_points(tmp_path, fresh):
    from SciQLop.components.plotting.backend.data_provider import DATA_PROVIDERS, providers
    from SciQLop.core.product_kinds import PRODUCT_KINDS
    from SciQLop.core.source_kinds import source_kind
    loader.activate_all([_plugin(tmp_path, "io_study", _STUDY, dependencies=["io-vdf>=1"]),
                         _plugin(tmp_path, "io_vdf", _VDF)], main_window=object(), ep_plugins={})
    assert {n: context.STATES[n].status for n in ("io_vdf", "io_study")} == {"io_vdf": "active",
                                                                             "io_study": "active"}
    api = context.STATES["io_vdf"].api
    assert api.seen == ["io_study.moments"]
    assert PRODUCT_KINDS.owner_of("io_vdf.distribution") == "io_vdf"
    assert DATA_PROVIDERS.owner_of("io_vdf") == "io_vdf"
    assert source_kind(providers["io_vdf"].source_kind).inspector_line(None) == "VDF"

    loader.activate_all([_plugin(tmp_path, "io_late", _LATE, dependencies=["io_vdf"])],
                        main_window=object(), ep_plugins={})
    assert api.seen == ["io_study.moments", "io_late.fit"]
    assert sys.modules["io_late"] is not None
```

- [ ] **Step 2: Run it**

Run: `uv run --no-sync pytest tests/test_plugin_interop.py -q -p no:cacheprovider`
Expected: PASS. Tasks 1–7 already made this work, so the test pins it. If it fails, the failure is a real gap: fix it in the task's own module and report it, don't weaken the test.

- [ ] **Step 3: Docs**

In `references/plugin-contract.md`, add a section "Data contracts (extension points in SciQLop 1b)". Give one table row each for `sciqlop.data_providers`, `sciqlop.mime_types`, `sciqlop.source_kinds` and `sciqlop.product_kinds`, with these columns: the id, the contribution type, its key, and how a plugin contributes. Then add the `_VDF`-style example in fewer than 20 lines, with:
- `ctx.contribute` of a `ProductKind` and a `SourceKind`;
- a `DataProvider` subclass with `source_kind`;
- product-tree nodes tagged with `product_kind`.

State three things:
- A failed `activate()` withdraws everything the plugin contributed.
- Dependency names match across case, dash and underscore.
- Plot kinds, which make a plugin's product kind plottable, come with plan 1c.

In `SKILL.md`, add one line in the reference list pointing to that section.

In the spec §4.3 status, change "1b data contracts (...)" to say it is implemented and name this plan file.

- [ ] **Step 4: Run the skill-name test and the touched suites**

Run: `uv run --no-sync pytest tests/test_plugin_interop.py tests/test_agent_skills.py -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_plugin_interop.py SciQLop/components/agents/skills/sciqlop-plugin-design/references/plugin-contract.md SciQLop/components/agents/skills/sciqlop-plugin-design/SKILL.md docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md
git commit -m "test(plugins): interop proof for data contracts; plugin-author docs for the 1b extension points"
```

The controller then runs the full suite once (`uv run --no-sync pytest -q -p no:cacheprovider`, about 9 minutes, never in parallel with anything) and reads the real pass/fail count and exit code.

---

## Decisions this plan makes (each is a ruling; the spec stays the authority)

- **Providers keep their replace behaviour.** A provider re-created under its name replaces the old one, and a takeover by another owner is logged instead of raised. Why: spec §7 says published register functions keep their `replace` behaviour, and VP re-runs depend on it. Cost if wrong: two plugins can silently fight over one provider name, though the log names both.
- **`ProductKind` carries `arity` as its data contract**, not the spec's `contract` + `validate` pair. Why: arity is the only shape fact the current dispatch sites read. Cost if wrong: a plugin kind with a richer contract adds a field later, which is additive.
- **Only the `ParameterType` switches move to product kinds.** The published VP type strings and `VirtualProductType` stay as they are (spec §4.2 keeps those enums). The speasy rendering choice also stays, because it belongs to `GraphType`. Cost if wrong: a plugin kind cannot be a virtual-product `product_type` until those tables migrate. The trigger is a plugin that wants VPs of its own kind.
- **Source-kind snippets stay on the provider** (`python_snippets`): there is no if-chain there to replace. Cost: none.
- **The `event_table` drag stays as is.** It writes one `QMimeData` holding both the event-list and time-range formats, and builds it directly; one object with one encoder can't produce it. Cost: none; both formats decode through the extension point.
- **A failed plugin's own declared extension points stay declared.** Only its contributions are withdrawn. Why: failed plugins are never re-activated in a process. Cost: an empty EP lingers until restart.
