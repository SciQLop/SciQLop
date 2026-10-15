# Layers and virtual products (plan 2d) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Virtual products and annotation layers are contributions to extension points, keyed by their product-tree path; withdrawing a plugin (or calling the new `remove_*` functions) takes their product-tree nodes back out.

**Architecture:** Two extension points on plan 1a's `ExtensionPoint`:
- `sciqlop.virtual_products` holds every `EasyProvider` (what `create_virtual_product`, `%%vp` and the `Virtual*`/`Easy*` classes build), keyed by its `//`-joined path. `EasyProvider.__init__` contributes itself (replace on the same path). A follower on `removed` removes the product node, the data provider, and the out-of-process registration. `list_virtual_products()` reads the EP; `remove_virtual_product(path)` is new.
- `sciqlop.layers` holds every `LayerProvider`, keyed by its tree path (`Layers/...`). It replaces the module dict `_layer_providers` and the `LayerRegistry` near copy: the EP entry *is* the hot-reload state (same path + same knob signature → swap the callback inside the existing `MutableCallback`). A follower on `removed` removes the node. `remove_layer(path)` is new.

Both followers remove nodes through one new helper, `core.models.remove_product_node(path)` (SciQLopPlots `ProductsModel.remove_node`, available since 0.37; verified on 0.51.3: removes the leaf through the model's row-removal path, leaves empty parent folders). Task 1 uses the same helper to fix plan 1a's open item "tree nodes ignore `removed`" for scenes and boundaries.

`VPRegistry` stays: it carries `%%vp`-only state (product type, labels, colored flag, debug panel). Its `MutableCallback` and signature helper become subclasses/uses of the layer ones, so the two near copies share one base.

**Tech Stack:** Python 3.10+, PySide6, SciQLopPlots `ProductsModel`, pytest + pytest-qt (+ pytest-xvfb).

**Spec:** `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` — §4.3 tier-2 row `sciqlop.layers`, `sciqlop.virtual_products` ("VPRegistry and LayerRegistry (near copies) on one hot-reload EP"), §6 (consumers listen to `removed`), §7 (migration rules), §8 (wrong type raises). Plans 1a–2c are implemented and pushed.

## Global Constraints

- Work and commit on `main`, with explicit pathspecs. Never push. Never stage these untracked files: `importlib.metadata`, `setWidget`, `pydata/`, `.claude/`, the untracked `docs/` drafts, `tests/noop_script.py`.
- Run one pytest invocation at a time, in the foreground: `uv run --no-sync pytest <files> -q -p no:cacheprovider`, with Bash `timeout: 600000`. Never `--no-xvfb`. Never `uv sync`. Never edit SciQLopPlots, speasy or jupyqt.
- Write files with the Write/Edit tools. Never use shell heredocs, `cat` or `ls`.
- SciQLop loggers bypass pytest's `caplog`; tests that check a log call monkeypatch the module's `log.warning`/`log.error`.
- Extension points are main-thread objects. Kernel-thread callers (notebook cells, agent tools) reach them through `@on_main_thread` functions; `ExtensionPoint.keys()` (Task 2) is the one read that is safe from any thread.
- Owners: a contribution made inside `owned_by(<plugin>)` (plugin `activate`) belongs to that plugin; a notebook or script contribution belongs to `"user"` (the default). Taking over a path held by another owner is allowed (`replace=True`, as `register_provider` does) and logged with `log.warning` naming both owners.
- Published API keeps working (spec §7): `create_virtual_product` (signature, return value, "a virtual product already exists at the given path, it will be replaced"), `VirtualScalar/Vector/MultiComponent/Spectrogram`, `list_virtual_products()` (full `//`-joined paths, one per path), `register_layer(path, scope)` stays a decorator returning the function, `%%vp` and `%%layer` hot-reload (an unchanged knob signature swaps the callback in place: already-plotted graphs and attached layers run the new body). The `providers` mapping keeps its behaviour for everything that is not withdrawn.
- Redeclaring a virtual product at the same path does not remove the earlier `EasyProvider` from `providers` (already-plotted graphs and their inspector look it up by name). Only withdrawal (`removed`) removes a provider.
- Plugin-author docs move with the code (spec §7): `SciQLop/components/agents/skills/sciqlop-plugin-design/references/products-and-data.md` (virtual products, layers) and `references/plugin-contract.md` (EP list) change in the same commit as the code they document. New user_api functions go in the global `/home/jeandet/.claude/memory/sciqlop-user-api.md` in the same task (that file is outside the repo: edit it, don't stage it).
- Code style (CLAUDE.md): small functions, data over code, no comment-decorated blocks, a `simplify:` comment on deliberate shortcuts.
- Commit trailer: `Co-Authored-By: <the model writing the commit> <noreply@anthropic.com>`.

## Review Focus

1. **A `%%vp` cell is re-run after `remove_virtual_product`.** The product comes back in the tree (the `%%vp` cache must not think it still exists). → Task 2.
2. **A plugin's virtual product is withdrawn while plotted.** No crash; the graph keeps its data; a pan after withdrawal does not raise. → Task 2.
3. **An out-of-process virtual product is removed.** `remote_registry().is_remote(path)` is False afterwards; a new in-process product at the same path plots in-process. → Task 2.
4. **Re-running a `%%layer` cell with an edited body** updates layers already dropped on a plot (hot reload kept), and the same function registered at two paths gives two layers. → Task 3.
5. **A scene or boundary contributed by a plugin is withdrawn.** Its tree node goes; an already-open scene plot does not crash. → Task 1.

---

## File map

| File | Role | Task |
|---|---|---|
| `SciQLop/core/models.py` | `remove_product_node(path)` | 1 |
| `SciQLop/components/scenes/tree.py` | scenes/boundaries nodes follow `removed` | 1 |
| `SciQLop/core/extensions.py` | `ExtensionPoint.keys()` | 2 |
| `SciQLop/components/plotting/backend/easy_provider.py` | `VIRTUAL_PRODUCTS` EP, contribution in `__init__`, `follow_virtual_products()` | 2 |
| `SciQLop/components/plotting/backend/remote/registry.py` | `RemoteRegistry.unregister(path)` | 2 |
| `SciQLop/user_api/virtual_products/__init__.py` | `list_virtual_products` reads the EP; `remove_virtual_product` | 2 |
| `SciQLop/user_api/virtual_products/magic.py` | `%%vp` re-registers a removed path | 2 |
| `SciQLop/user_api/layers/_provider.py` | `LAYERS` EP, `define_layer`, `follow_layers()`, `remove_layer` backend | 3 |
| `SciQLop/user_api/layers/registry.py` | `MutableCallback` + `signature_kwargs` only (`LayerRegistry` deleted) | 3 |
| `SciQLop/user_api/layers/__init__.py`, `layers/magic.py` | both go through `define_layer`; `remove_layer` | 3 |
| `SciQLop/user_api/virtual_products/registry.py` | reuses the layer `MutableCallback`/`signature_kwargs` | 3 |
| `SciQLop/components/plotting/ui/time_sync_panel.py` | `attach_layer` looks the layer up in `LAYERS` | 3 |
| `SciQLop/components/extension_points.py` | declares and follows both EPs | 2, 3 |
| tests | see each task | 1–4 |
| skill docs, spec §4.3 | docs | 2–4 |

---

### Task 1: Product nodes follow withdrawal (helper + scenes)

**Files:**
- Modify: `SciQLop/core/models.py`
- Modify: `SciQLop/components/scenes/tree.py` (`follow_registries`)
- Test: `tests/scenes/test_scene_tree.py` (add tests); `tests/scenes/` must pass.

**Interfaces:**
- Produces: `remove_product_node(path: list[str]) -> None`, decorated `@on_main_thread` like `add_product_node`; calls `products.remove_node(path)`. Removing a path with no node is a no-op (SciQLopPlots already returns quietly). Leaves empty parent folders: add `# simplify: empty parent folders stay; prune them when a plugin's withdrawal leaves visible empty folders that users complain about.`
- `follow_registries()` also connects `BOUNDARIES.signals.removed` and `SCENES.signals.removed` to functions that call `remove_product_node(_boundary_path(model))` and `remove_product_node(["Scenes", scene.name])`. Keep the existing idempotence flag (one flag covers both connections). Module-level functions only (Qt lifetime rule).

- [ ] **Step 1: Write the failing tests** in `tests/scenes/test_scene_tree.py`, using the fixtures that file already uses for contributing a scene/boundary (read it first):
  - `test_a_withdrawn_boundary_leaves_the_tree`: contribute a boundary under `owned_by("tree_demo")`, assert `ProductsModel.node(path)` is not None; `BOUNDARIES.remove_owner("tree_demo")`; assert the node is None.
  - `test_a_withdrawn_scene_leaves_the_tree`: same for a scene.
  - `test_removing_an_absent_node_is_a_no_op`: `remove_product_node(["no", "such", "node"])` does not raise.
- [ ] **Step 2: Run them, expect the first two to FAIL** (node still present).
- [ ] **Step 3: Implement** `remove_product_node` and the two `removed` connections.
- [ ] **Step 4: Run `tests/scenes/`**; all pass.
- [ ] **Step 5: Commit** `feat(plugins): product nodes follow withdrawal; scenes and boundaries leave the tree`.

---

### Task 2: `sciqlop.virtual_products`

**Files:**
- Modify: `SciQLop/core/extensions.py` (`keys()`)
- Modify: `SciQLop/components/plotting/backend/easy_provider.py`
- Modify: `SciQLop/components/plotting/backend/remote/registry.py`
- Modify: `SciQLop/user_api/virtual_products/__init__.py`, `SciQLop/user_api/virtual_products/magic.py`
- Modify: `SciQLop/components/extension_points.py` (declare: importing `easy_provider` declares it; then call `follow_virtual_products()` next to the other followers)
- Modify: `tests/test_user_api_thread_classification.py` only if `remove_virtual_product` needs listing (it is `@on_main_thread`, so it should not); `tests/test_list_virtual_products_snapshot.py` (rewrite for the EP, see Step 1); `tests/test_virtual_products/test_vp_lifecycle.py` (docstring: removal now exists).
- Test: `tests/test_virtual_product_contributions.py` (new); `tests/test_virtual_products/`, `tests/test_vp_magic*.py`, `tests/test_colored_vp_magic.py`, `tests/remote/`, `tests/test_agent_vp_tools.py`, `tests/test_list_virtual_products_snapshot.py` must pass.
- Docs: `references/products-and-data.md` (a short "Removing and withdrawing" paragraph: `remove_virtual_product(path)`, plugin VPs leave the tree when the plugin is withdrawn); `references/plugin-contract.md` EP list; global `sciqlop-user-api.md` (`remove_virtual_product`).

**Interfaces:**
- Produces:
  - `ExtensionPoint.keys() -> list[str]`: `return list(self._items)` with a docstring saying it is a snapshot safe from any thread (one C-level copy under the GIL). No main-thread check.
  - `VIRTUAL_PRODUCTS = declare(ExtensionPoint("sciqlop.virtual_products", EasyProvider, what="virtual product", key=_vp_key, doc="Virtual products by '//'-joined product path."))`, declared in `easy_provider.py` right after `class EasyProvider`, with `def _vp_key(provider) -> str: return "//".join(provider.path)`.
  - In `EasyProvider.__init__`, after `add_product_node(...)` (keep it last-but-one; the contribution is the last statement): `_contribute_virtual_product(self)`, an `@on_main_thread` module function that logs a takeover (`log.warning(f"virtual product {key!r} of {previous} is replaced by one from {owner}")` when the previous owner differs) and calls `VIRTUAL_PRODUCTS.contribute(provider, owner=current_owner(), replace=True)`. Mirror `register_provider` in `data_provider.py`.
  - `follow_virtual_products() -> None`: main thread, idempotent (flag on the signals object, as `follow_registries` does); connects `VIRTUAL_PRODUCTS.signals.removed` to `_withdraw_virtual_product(provider)`, which: (1) `remove_product_node(provider.path)`; (2) removes `provider.name` from `DATA_PROVIDERS` only if `DATA_PROVIDERS.get(provider.name) is provider` (the loader's `remove_owner` may already have removed it); (3) `remote_registry().unregister(provider.path)`.
  - `RemoteRegistry.unregister(product_path) -> None`: drops the spec and the colored flag for that key; no-op when absent. Workers stay alive (`# simplify: a plugin's worker outlives its last product until shutdown_all; stop it here when idle workers show up in memory reports.`).
  - `list_virtual_products() -> list[str]`: `return VIRTUAL_PRODUCTS.keys()`. Not marshalled (it stays in `NOT_MARSHALED_ON_PURPOSE`). Update its docstring: one entry per path, read from `sciqlop.virtual_products`.
  - `remove_virtual_product(path: str) -> None` in `user_api/virtual_products/__init__.py`, `@on_main_thread`, added to the module's public names: normalizes `path` with `split_product_path` and `"//".join`, then `VIRTUAL_PRODUCTS.remove(key)`. Unknown path raises `NotRegistered` (a `LookupError`; its message lists the available paths). Docstring: removes the tree node and the provider; graphs already plotted keep their data.
  - `%%vp`: `is_new` becomes true also when the path is not in `VIRTUAL_PRODUCTS` (so a re-run after removal re-registers). The key to check is `"//".join(split_product_path(args.path or func_name))`, the same normalization `create_virtual_product` uses.

- [ ] **Step 1: Write the failing tests** in `tests/test_virtual_product_contributions.py` (use `qapp`, `main_window` from `tests.fixtures`; remove every path you create in teardown, ignoring `NotRegistered`):
  - `test_a_virtual_product_is_a_contribution`: `create_virtual_product("vpc//a", f, Scalar, labels=["y"])`; `"vpc//a" in VIRTUAL_PRODUCTS`, owner `"user"`.
  - `test_a_plugin_virtual_product_is_owned_by_the_plugin`: same under `owned_by("vp_demo")`; `VIRTUAL_PRODUCTS.owner_of(...) == "vp_demo"`.
  - `test_withdrawal_removes_node_and_provider`: create under `owned_by("vp_demo")`, keep `p = VIRTUAL_PRODUCTS.get(...)`; `VIRTUAL_PRODUCTS.remove_owner("vp_demo")`; `ProductsModel.node(["vpc","a"])` is None, `p.name not in providers`, path not in `list_virtual_products()`.
  - `test_remove_virtual_product`: same through `remove_virtual_product("vpc/a")` (single slash: normalization); an unknown path raises `LookupError`.
  - `test_redeclare_keeps_the_old_provider_registered`: create twice at one path; both providers' names are still in `providers`; `list_virtual_products().count(path) == 1`.
  - `test_takeover_from_another_owner_is_logged`: create under `owned_by("a")` then `owned_by("b")`; monkeypatch `easy_provider.log.warning`; one call names both owners; owner is now `"b"`.
  - `test_wrong_type_is_refused`: `VIRTUAL_PRODUCTS.contribute(object())` raises `TypeError`.
  - `test_removing_an_out_of_process_product_unregisters_it`: create with `out_of_process=True` using a picklable module-level callback (copy the pattern from `tests/remote/test_registration_optin.py`); remove; `remote_registry().is_remote(path)` is False.
  - `test_withdrawn_while_plotted_does_not_crash` (Review Focus 2): plot the product in a panel (`plot_panel` fixture pattern from `tests/fixtures.py`), withdraw, then change the panel's time range and `qtbot.wait(200)`; no exception, the graph is still in the plot.
  - `test_vp_cell_rerun_after_removal_registers_again` (Review Focus 1): run the `%%vp` magic implementation (`_vp_magic_impl`, as `tests/test_vp_magic.py` does) with `--path vpc/cell` and an annotated function, `remove_virtual_product("vpc/cell")`, run the same cell again; the node and the EP entry exist again.
  Rewrite `tests/test_list_virtual_products_snapshot.py` for the new source: its point is that a registration racing the listing cannot break it; assert that `list_virtual_products()` returns `VIRTUAL_PRODUCTS.keys()` and that `keys()` returns a new list (mutating the EP after the call does not change the returned list). Keep the module docstring's reason.
- [ ] **Step 2: Run the new file, expect FAIL** (no `VIRTUAL_PRODUCTS`).
- [ ] **Step 3: Implement** `keys()`, the EP, the contribution, `unregister`, the follower and its wiring, `list_virtual_products`, `remove_virtual_product`, the `%%vp` check, the docstring updates.
- [ ] **Step 4: Run** the new file, then (one invocation each) `tests/test_virtual_products/`, `tests/test_vp_magic.py tests/test_colored_vp_magic.py tests/test_list_virtual_products_snapshot.py tests/test_agent_vp_tools.py`, `tests/remote/`, `tests/test_user_api_thread_classification.py`. All pass.
- [ ] **Step 5: Commit** `feat(plugins): virtual products are contributions to sciqlop.virtual_products; remove_virtual_product`.

---

### Task 3: `sciqlop.layers`

**Files:**
- Modify: `SciQLop/user_api/layers/_provider.py`, `layers/registry.py`, `layers/__init__.py`, `layers/magic.py`
- Modify: `SciQLop/user_api/virtual_products/registry.py` (reuse the shared base)
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py` (`attach_layer`)
- Modify: `SciQLop/components/extension_points.py` (import `SciQLop.user_api.layers._provider` to declare; call `follow_layers()`)
- Modify: `tests/test_user_api_thread_classification.py` (`LayerRegistry.*` entries go; add whatever the classifier asks for, with the reason), `tests/test_layers/test_registry.py` and `tests/test_layers/test_integration.py` (they use `LayerRegistry`: port each test's intent to `define_layer`; keep every behaviour they check that still exists).
- Test: `tests/test_layer_contributions.py` (new); `tests/test_layers/`, `tests/scenes/test_scene_tree.py`, `tests/test_vp_magic.py`, `tests/test_colored_vp_magic.py`, `tests/test_virtual_products/test_registry_knobs.py` must pass.
- Docs: `references/products-and-data.md` (or wherever layers are documented in the skill: grep `register_layer` under the skill dir; if absent, add a short "Layers" paragraph to `products-and-data.md`): layers are keyed by path, `remove_layer`, plugin layers leave on withdrawal; `references/plugin-contract.md` EP list; global `sciqlop-user-api.md` (`remove_layer`, path-keyed hot reload).

**Interfaces:**
- Consumes: `remove_product_node` (Task 1).
- Produces:
  - `layers/registry.py` keeps `MutableCallback` (unchanged behaviour) and exposes `signature_kwargs(callback, skip: tuple = ("start", "stop", "data")) -> tuple` (renamed from `_signature_kwargs`, now with `skip`). `LayerRegistry`, `LayerEntry` and `_registry` are deleted.
  - `virtual_products/registry.py`: its `MutableCallback` subclasses the layer one, keeping only what differs (`after_call`, range resolution in `__call__`); its `_signature_kwargs(cb)` becomes `signature_kwargs(cb, skip=("start", "stop"))`. `VPRegistry` stays.
  - `LAYERS = declare(ExtensionPoint("sciqlop.layers", LayerProvider, what="layer", key=lambda p: "/".join(p.path), doc="Annotation layers by product-tree path (Layers/...)."))`, declared in `_provider.py` after the class. `LayerProvider.__init__` contributes itself as its last statement (`owner=current_owner(), replace=True`, takeover logged as in Task 2) instead of writing `_layer_providers`. `_layer_providers` is deleted.
  - `define_layer(path: str, func, scope: str = "auto") -> LayerProvider` in `_provider.py`: the one hot-reload entry point for `register_layer` and `%%layer`. Key `f"Layers/{path}"`. If a layer exists at that key and its callback is a `MutableCallback` whose current callback has the same `signature_kwargs` as `func`: set `existing.callback.callback = func` and return it (attached layers run the new body). If it exists with another signature: `existing.update_callback(MutableCallback(func))` and return it (new drops get the new knobs; already-attached ones keep the old wrapper, as today). Otherwise create `LayerProvider(path, MutableCallback(func), scope=scope)` on the main thread (`invoke_on_main_thread`, as today) and return it.
  - `register_layer(path=None, scope="auto")` decorator: `define_layer(path or func.__name__, func, scope)`; returns `func`. `%%layer`: `define_layer(args.path or func_name, func, args.scope)`, then the same log line.
  - `attach_layer(plot, product, panel=None)`: finds the provider with `LAYERS.list(name=node.provider())` (first match, else return None).
  - `follow_layers() -> None`: idempotent; `LAYERS.signals.removed` → `remove_product_node(provider.path)`. Attached renderers keep running (`# simplify: layers already dropped on plots keep rendering after withdrawal; detach them here when a plugin's withdrawal must clear plots too.`).
  - `remove_layer(path: str) -> None` in `user_api/layers/__init__.py`, `@experimental_api()` and `@on_main_thread`, in `__all__`: `LAYERS.remove(f"Layers/{path}")`; unknown raises `NotRegistered`.

Behaviour change to state in the commit message: layers were keyed by function name; they are now keyed by path. The same function registered at two paths now gives two layers (before, the second was ignored), and two functions at one path hot-reload one layer.

- [ ] **Step 1: Write the failing tests** in `tests/test_layer_contributions.py` (fixtures `qapp`, `main_window`; remove created keys in teardown):
  - `test_a_layer_is_a_contribution`: `register_layer("lc/a")(f)`; `"Layers/lc/a" in LAYERS`; node `["Layers","lc","a"]` exists.
  - `test_same_signature_rerun_swaps_the_body`: `p1 = define_layer("lc/b", f1)`; `p2 = define_layer("lc/b", f2)` with the same knobs; `p1 is p2` and calling `p1.callback(...)` runs `f2`.
  - `test_changed_signature_refreshes_knobs`: second function adds a knob `level: float = 1.0`; same provider object, `get_knobs()` now includes `level`.
  - `test_same_function_at_two_paths_gives_two_layers`.
  - `test_withdrawal_removes_the_node`: under `owned_by("layer_demo")`, then `LAYERS.remove_owner("layer_demo")`; node gone; `attach_layer` on that product returns None.
  - `test_remove_layer`: `remove_layer("lc/a")` removes it; unknown raises `LookupError`.
  - `test_attach_layer_finds_the_provider` on a real plot (`plot_panel` fixture): register, attach by product path, a renderer comes back.
  - `test_layer_cell_rerun_updates_an_attached_layer` (Review Focus 4): attach a layer from `%%layer` (as `tests/test_layers/test_magic.py` runs it), re-run the cell with another body, the attached renderer's callback runs the new body (call the wrapper it holds, or check its `callback` attribute — read `wire_layer_renderer` to pick the observable).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement**; port `tests/test_layers/test_registry.py` and `test_integration.py` off `LayerRegistry`.
- [ ] **Step 4: Run** (one invocation each) the new file, `tests/test_layers/`, `tests/scenes/test_scene_tree.py`, `tests/test_vp_magic.py tests/test_colored_vp_magic.py tests/test_virtual_products/test_registry_knobs.py tests/test_user_api_thread_classification.py`. All pass.
- [ ] **Step 5: Commit** `feat(plugins): layers are contributions to sciqlop.layers keyed by path; remove_layer; one hot-reload base`.

---

### Task 4: Interop proof and spec bookkeeping

**Files:**
- Modify: `tests/test_plugin_interop.py` (add one test, reuse its `_plugin` helper and `fresh` fixture)
- Modify: `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` (§4.3 row: append `; **implemented**: docs/superpowers/plans/2026-10-15-layers-virtual-products.md`)

- [ ] **Step 1: Write the test** `test_plugin_contributes_a_virtual_product_and_a_layer_and_withdraws_them`: plugin `vp_maker` (`activate(ctx)`: `create_virtual_product("vp_maker/b", ...)` and `register_layer("vp_maker/peaks")(f)`); plugin `vp_user` depending on it (`activate(ctx)`: records `VIRTUAL_PRODUCTS.owner_of("vp_maker//b")` and `LAYERS.owner_of("Layers/vp_maker/peaks")` in its API). Load both through the loader as the other interop tests do; assert both owners are `"vp_maker"`; then `remove_owner("vp_maker")` on both EPs (the loader's unload path is `remove_owner` on every EP, spec §6); both nodes are gone from `ProductsModel`.
- [ ] **Step 2: Run** `tests/test_plugin_interop.py`; all pass (run it alone; a known order dependency with `test_plugin_commands_interop` exists, ledgered in plan 2b — don't chase it here).
- [ ] **Step 3: Update the spec row** and commit `test(plugins): interop proof for virtual products and layers; spec row marked implemented`.
