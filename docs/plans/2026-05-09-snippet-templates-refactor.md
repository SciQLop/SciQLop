# Snippet Templates Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace inline string-concatenation snippet generation across providers with a small Jinja2-template system, switch product-path emission from list-literal to slash-joined string form, and drop the implicit `"root"` prefix.

**Architecture:** A new `SciQLop.core.snippets` package owns a Jinja2 `Environment` rooted at a `templates/` resources directory and exposes two functions: `render_snippet(template_name, **vars)` and `format_product_path(path)` (drops `"root"`, joins with `/`). Providers stay responsible for assembling template variables (callable identity, knob values, time range, etc.) but stop concatenating Python source by hand. The receiver side (`panel.plot_product`) already accepts strings via `to_product_path` (`SciQLop/user_api/plot/_plots.py:79`) — and `ProductsModel::node` already strips a leading `"root"` (`SciQLopPlots/src/ProductsModel.cpp:228`) — so this is purely a producer-side cleanup.

**Tech Stack:** Python 3.13, Jinja2 (already a dep, see `pyproject.toml:55`; precedents in `SciQLop/components/theming/stylesheet.py` and `SciQLop/core/web_channel_page.py`), pytest + pytest-qt.

---

## Files

- **Create**
  - `SciQLop/core/snippets/__init__.py` — public surface: `render_snippet`, `format_product_path`
  - `SciQLop/core/snippets/_renderer.py` — Jinja2 environment, loader pinned to `templates/`
  - `SciQLop/core/snippets/templates/sciqlop_panel.j2` — header (imports + panel + time range)
  - `SciQLop/core/snippets/templates/sciqlop_reproducer.j2` — single-product reproducer
  - `SciQLop/core/snippets/templates/notebook_matplotlib.j2` — speasy + matplotlib notebook
  - `SciQLop/core/snippets/templates/vp_reproducer.j2` — VP reproducer (importable callback)
  - `SciQLop/core/snippets/templates/vp_reproducer_unimportable.j2` — VP reproducer (lambda/closure)
  - `SciQLop/core/snippets/templates/panel_reproducer.j2` — whole-panel reproducer
  - `SciQLop/core/snippets/templates/plot_reproducer.j2` — single-plot reproducer
  - `tests/test_snippet_renderer.py` — tests for `render_snippet` + `format_product_path`

- **Modify**
  - `SciQLop/plugins/speasy_provider/speasy_provider.py:217-274` — replace `_speasy_sciqlop_snippet` and `_speasy_matplotlib_snippet` with template calls
  - `SciQLop/components/plotting/backend/easy_provider.py:182-260` — replace `python_snippets` body with template calls
  - `SciQLop/components/plotting/ui/graph_context_snippets.py:51-155` — drop `_product_path_arg`, `_header`, `_plot_product_lines`; use templates
  - `tests/test_provider_snippets.py` — assert string-form product path, no `"root"` prefix
  - `tests/test_graph_context_integration.py` — same assertions for the menu-driven path

---

## Self-Review Notes (built into the plan)

- Type/name consistency: `render_snippet(template, **vars)` and `format_product_path(path)` are referenced by every task that uses them — both are defined in Task 2 and Task 1.
- Spec coverage: (a) Jinja2 templating ✓ Task 2 + 3-7; (b) slash-joined string form ✓ Task 1; (c) drop `"root"` ✓ Task 1; (d) verify both paths still resolve via `panel.plot_product` ✓ Task 8 integration test.
- The `panel.plot_product` signature does NOT change. The user_api wrapper already handles both `list[str]` and `"a/b/c"` and `"a//b//c"` (see `_split_path`). No `feedback_user_api_public.md` violation.

---

## Task 1: Product-path formatter

**Files:**
- Create: `SciQLop/core/snippets/__init__.py`
- Test: `tests/test_snippet_renderer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_snippet_renderer.py
def test_format_product_path_joins_with_slash():
    from SciQLop.core.snippets import format_product_path
    assert format_product_path(["root", "speasy", "amda", "ACE", "b_gsm"]) \
        == "speasy/amda/ACE/b_gsm"


def test_format_product_path_keeps_path_when_no_root():
    from SciQLop.core.snippets import format_product_path
    assert format_product_path(["speasy", "amda", "b_gsm"]) \
        == "speasy/amda/b_gsm"


def test_format_product_path_handles_empty():
    from SciQLop.core.snippets import format_product_path
    assert format_product_path([]) == ""
    assert format_product_path(None) == ""


def test_format_product_path_single_segment():
    from SciQLop.core.snippets import format_product_path
    assert format_product_path(["root"]) == ""
    assert format_product_path(["b_gsm"]) == "b_gsm"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_snippet_renderer.py::test_format_product_path_joins_with_slash -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'SciQLop.core.snippets'`

- [ ] **Step 3: Write minimal implementation**

```python
# SciQLop/core/snippets/__init__.py
"""Snippet rendering primitives for graph-context "Copy Python code" actions."""
from __future__ import annotations

from typing import Iterable, Optional


def format_product_path(path: Optional[Iterable[str]]) -> str:
    """Render a product-tree path as ``"a/b/c"``, dropping the implicit
    ``"root"`` prefix.

    ``ProductsModel::node`` (SciQLopPlots) strips a leading ``"root"`` when
    looking up by name, and ``to_product_path`` (user_api) splits on ``/``
    or ``//`` — so the receiver accepts this form unchanged. The list-literal
    form was harder to read in clipboard output.
    """
    if not path:
        return ""
    segments = [str(s) for s in path]
    if segments and segments[0] == "root":
        segments = segments[1:]
    return "/".join(segments)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_snippet_renderer.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add SciQLop/core/snippets/__init__.py tests/test_snippet_renderer.py
git commit -m "feat(snippets): format_product_path drops root + joins with /"
```

---

## Task 2: Jinja2 renderer

**Files:**
- Create: `SciQLop/core/snippets/_renderer.py`
- Create: `SciQLop/core/snippets/templates/_smoke.j2`
- Modify: `SciQLop/core/snippets/__init__.py`
- Test: `tests/test_snippet_renderer.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_snippet_renderer.py
def test_render_snippet_loads_template_and_substitutes():
    from SciQLop.core.snippets import render_snippet
    out = render_snippet("_smoke.j2", name="world")
    assert out == "hello world\n"


def test_render_snippet_unknown_template_raises():
    import jinja2
    from SciQLop.core.snippets import render_snippet
    with pytest.raises(jinja2.TemplateNotFound):
        render_snippet("does_not_exist.j2")
```

Add `import pytest` at the top of the file if not already present.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_snippet_renderer.py::test_render_snippet_loads_template_and_substitutes -v`
Expected: FAIL with `ImportError: cannot import name 'render_snippet'`

- [ ] **Step 3: Write the renderer**

```python
# SciQLop/core/snippets/_renderer.py
"""Jinja2 environment for snippet templates.

Templates live next to this module under ``templates/``. Same convention as
``SciQLop/components/theming/stylesheet.py`` and ``core/web_channel_page.py``.
"""
from __future__ import annotations

import os
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=StrictUndefined,
)


def render_snippet(template_name: str, **variables: Any) -> str:
    """Render a template under ``SciQLop/core/snippets/templates/``."""
    return _env.get_template(template_name).render(**variables)
```

```jinja2
{# SciQLop/core/snippets/templates/_smoke.j2 #}
hello {{ name }}
```

```python
# SciQLop/core/snippets/__init__.py — append
from ._renderer import render_snippet  # noqa: E402

__all__ = ["format_product_path", "render_snippet"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_snippet_renderer.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add SciQLop/core/snippets/_renderer.py SciQLop/core/snippets/__init__.py SciQLop/core/snippets/templates/_smoke.j2 tests/test_snippet_renderer.py
git commit -m "feat(snippets): jinja2-backed render_snippet helper"
```

---

## Task 3: Speasy notebook (matplotlib) template

**Files:**
- Create: `SciQLop/core/snippets/templates/notebook_matplotlib.j2`
- Modify: `SciQLop/plugins/speasy_provider/speasy_provider.py:258-274`
- Test: `tests/test_provider_snippets.py`

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_provider_snippets.py
def test_speasy_notebook_uses_string_path_no_root_via_template(qtbot):
    """The matplotlib notebook snippet must use the slash-joined product
    path (no list literal, no ``root`` prefix). Regression: emitting
    ``ctx.product_path`` via ``repr`` produced ['root', 'speasy', ...].
    """
    from SciQLop.core.graph_context import build_speasy_ctx
    from SciQLop.plugins.speasy_provider.speasy_provider import (
        _speasy_matplotlib_snippet,
    )
    from PySide6.QtCore import QObject

    class _G(QObject):
        def __init__(self): super().__init__(); self.setObjectName("g")

    ctx = build_speasy_ctx(
        _G(), panel_name="P", plot_index=0,
        speasy_id="amda/ACE/b_gsm", graph_type="Line",
        product_path=["root", "speasy", "amda", "ACE", "b_gsm"],
    )
    out = _speasy_matplotlib_snippet(ctx, graph=None)
    assert "['root'" not in out, "list-literal product path leaked"
    assert "'amda/ACE/b_gsm'" in out, f"expected slash form; got: {out!r}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_provider_snippets.py::test_speasy_notebook_uses_string_path_no_root_via_template -v`
Expected: FAIL with `assert "['root'" not in out` (list literal still present)

- [ ] **Step 3: Add the template**

```jinja2
{# SciQLop/core/snippets/templates/notebook_matplotlib.j2 #}
import speasy as spz
import matplotlib.pyplot as plt

start = "{{ start_iso }}"
stop  = "{{ stop_iso }}"
v = spz.get_data("{{ speasy_id }}", start, stop{% if knobs %}, product_inputs={{ knobs }}{% endif %})

fig, ax = plt.subplots()
v.plot(ax=ax)
fig.autofmt_xdate()
plt.show()
```

- [ ] **Step 4: Migrate the producer**

Replace `_speasy_matplotlib_snippet` (currently lines 258-274 of `SciQLop/plugins/speasy_provider/speasy_provider.py`) with:

```python
def _speasy_matplotlib_snippet(ctx, graph=None) -> str:
    """Standalone notebook snippet: speasy.get_data + matplotlib plot."""
    from SciQLop.core.snippets import render_snippet
    start_iso, stop_iso = _resolve_iso_range(graph)
    return render_snippet(
        "notebook_matplotlib.j2",
        start_iso=start_iso,
        stop_iso=stop_iso,
        speasy_id=ctx.speasy_id,
        knobs=repr(ctx.knobs) if ctx.knobs else None,
    )
```

Note: `speasy.get_data`'s `product` argument accepts the speasy UID string directly — that's `ctx.speasy_id`, not the product-tree path. We only switch to slash-joined paths for `panel.plot_product` calls. The test above asserts `"'amda/ACE/b_gsm'"` because the ctx fixture uses that as `speasy_id`; in practice they differ.

- [ ] **Step 5: Run the test**

Run: `uv run pytest tests/test_provider_snippets.py -v`
Expected: all pass, including the new test.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/core/snippets/templates/notebook_matplotlib.j2 SciQLop/plugins/speasy_provider/speasy_provider.py tests/test_provider_snippets.py
git commit -m "feat(snippets): notebook_matplotlib via jinja2 template"
```

---

## Task 4: Speasy SciQLop reproducer template

**Files:**
- Create: `SciQLop/core/snippets/templates/sciqlop_panel.j2`
- Create: `SciQLop/core/snippets/templates/sciqlop_reproducer.j2`
- Modify: `SciQLop/plugins/speasy_provider/speasy_provider.py:239-255`
- Test: `tests/test_provider_snippets.py`

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_provider_snippets.py
def test_speasy_sciqlop_reproducer_emits_slash_path_no_root():
    from SciQLop.core.graph_context import build_speasy_ctx
    from SciQLop.plugins.speasy_provider.speasy_provider import (
        _speasy_sciqlop_snippet,
    )
    from PySide6.QtCore import QObject

    class _G(QObject):
        def __init__(self): super().__init__(); self.setObjectName("g")

    ctx = build_speasy_ctx(
        _G(), panel_name="P", plot_index=0,
        speasy_id="amda/ACE/b_gsm", graph_type="Line",
        product_path=["root", "speasy", "amda", "ACE", "b_gsm"],
    )
    out = _speasy_sciqlop_snippet(ctx, graph=None)
    assert "['root'" not in out
    assert 'panel.plot_product("speasy/amda/ACE/b_gsm")' in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_provider_snippets.py::test_speasy_sciqlop_reproducer_emits_slash_path_no_root -v`
Expected: FAIL — current snippet emits `panel.plot_product(['root', 'speasy', ...])`.

- [ ] **Step 3: Add the templates**

```jinja2
{# SciQLop/core/snippets/templates/sciqlop_panel.j2 #}
{# Header used by every "Reproduce in SciQLop" snippet. Always followed by
   one or more `panel.plot_product(...)` lines from the caller. #}
from datetime import datetime
from SciQLop.user_api.plot import create_plot_panel
from SciQLop.core import TimeRange

start = datetime.fromisoformat("{{ start_iso }}")
stop  = datetime.fromisoformat("{{ stop_iso }}")

panel = create_plot_panel()
panel.time_range = TimeRange(start.timestamp(), stop.timestamp())
```

```jinja2
{# SciQLop/core/snippets/templates/sciqlop_reproducer.j2 #}
{% include "sciqlop_panel.j2" %}
panel.plot_product("{{ product_path }}"{% if knobs %}, product_inputs={{ knobs }}{% endif %})
```

- [ ] **Step 4: Migrate the producer**

Replace `_speasy_sciqlop_snippet` (currently lines 239-255 of `SciQLop/plugins/speasy_provider/speasy_provider.py`) with:

```python
def _speasy_sciqlop_snippet(ctx, graph=None) -> str:
    """Snippet that recreates the panel + plot inside SciQLop using the
    live panel time range when available."""
    from SciQLop.core.snippets import render_snippet, format_product_path
    start_iso, stop_iso = _resolve_iso_range(graph)
    product_path = format_product_path(ctx.product_path) or ctx.speasy_id
    return render_snippet(
        "sciqlop_reproducer.j2",
        start_iso=start_iso,
        stop_iso=stop_iso,
        product_path=product_path,
        knobs=repr(ctx.knobs) if ctx.knobs else None,
    )
```

- [ ] **Step 5: Run the test**

Run: `uv run pytest tests/test_provider_snippets.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/core/snippets/templates/sciqlop_panel.j2 SciQLop/core/snippets/templates/sciqlop_reproducer.j2 SciQLop/plugins/speasy_provider/speasy_provider.py tests/test_provider_snippets.py
git commit -m "feat(snippets): speasy SciQLop reproducer via jinja2 template"
```

---

## Task 5: VP reproducer templates (importable + unimportable)

**Files:**
- Create: `SciQLop/core/snippets/templates/vp_reproducer.j2`
- Create: `SciQLop/core/snippets/templates/vp_reproducer_unimportable.j2`
- Modify: `SciQLop/components/plotting/backend/easy_provider.py:182-260`
- Test: `tests/test_provider_snippets.py`

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_provider_snippets.py
def test_vp_reproducer_uses_slash_path(tmp_path, qtbot):
    """VP reproducer must emit a slash-joined product path."""
    import importlib.util
    import textwrap

    src = tmp_path / "_vp_target.py"
    src.write_text(textwrap.dedent("""
        def my_callback(start, stop):
            return None
    """))
    spec = importlib.util.spec_from_file_location("_vp_target", src)
    mod = importlib.util.module_from_spec(spec)
    import sys; sys.modules["_vp_target"] = mod
    spec.loader.exec_module(mod)

    from SciQLop.components.plotting.backend.easy_provider import EasyProvider
    from SciQLop.core.graph_context import build_vp_ctx
    from PySide6.QtCore import QObject

    class _G(QObject):
        def __init__(self): super().__init__(); self.setObjectName("g")

    p = EasyProvider("custom/my_vp", components_str="x;y",
                     callback=mod.my_callback)
    ctx = build_vp_ctx(
        _G(), panel_name="P", plot_index=0,
        vp_path=["custom", "my_vp"], provider_name=p.name,
        callback=mod.my_callback, graph_type="Line",
        product_path=["custom", "my_vp"],
    )
    out = p.python_snippets(ctx, graph=None)
    assert "Reproduce in SciQLop" in out
    snippet = out["Reproduce in SciQLop"]
    assert "['custom'" not in snippet, "list literal leaked"
    assert 'panel.plot_product("custom/my_vp")' in snippet
```

(If the existing `tests/test_provider_snippets.py::test_vp_*` fixture is more idiomatic, use that pattern instead. Match the existing tests' style.)

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/test_provider_snippets.py -k vp_reproducer_uses_slash_path -v`
Expected: FAIL.

- [ ] **Step 3: Add the templates**

```jinja2
{# SciQLop/core/snippets/templates/vp_reproducer.j2 #}
{% include "sciqlop_panel.j2" %}
from {{ module }} import {{ qualname }}

# Manual fetch: data = {{ qualname }}(start, stop{% if knobs %}, {{ knobs_kwarg }}={{ knobs }}{% endif %})
panel.plot_product("{{ product_path }}")
```

```jinja2
{# SciQLop/core/snippets/templates/vp_reproducer_unimportable.j2 #}
# Virtual product '{{ product_path }}'
# callback '{{ module }}.{{ qualname }}' is not importable from this module.
# Re-execute the cell that registered the VP before running this snippet,
# then:
{% include "sciqlop_panel.j2" %}
panel.plot_product("{{ product_path }}")
```

- [ ] **Step 4: Migrate the producer**

Replace the snippet-building branches inside `EasyProvider.python_snippets` (currently lines 200-260 of `SciQLop/components/plotting/backend/easy_provider.py`):

```python
    def python_snippets(self, ctx, graph=None) -> dict:
        if ctx.kind != "vp" or self._callback is None:
            return {}
        cb = self._callback
        mod_name = getattr(cb, "__module__", None)
        qualname = getattr(cb, "__qualname__", None)
        if not (mod_name and qualname):
            return {}
        from SciQLop.core.graph_context import _is_importable
        from SciQLop.core.snippets import render_snippet, format_product_path
        from datetime import datetime, timedelta, timezone

        rng = None
        if graph is not None:
            try:
                from SciQLop.core.graph_context import graph_time_range
                rng = graph_time_range(graph)
            except Exception:
                rng = None
        if rng is not None:
            t0, t1 = rng
            start_iso = datetime.fromtimestamp(t0, tz=timezone.utc).replace(microsecond=0).isoformat()
            stop_iso = datetime.fromtimestamp(t1, tz=timezone.utc).replace(microsecond=0).isoformat()
        else:
            now = datetime.now(timezone.utc).replace(microsecond=0)
            start_iso, stop_iso = (now - timedelta(days=1)).isoformat(), now.isoformat()

        product_path = format_product_path(ctx.product_path) or format_product_path(self._path)
        knobs_repr = repr(ctx.knobs) if ctx.knobs else None
        template = ("vp_reproducer.j2" if _is_importable(mod_name, qualname, cb)
                    else "vp_reproducer_unimportable.j2")
        snippet = render_snippet(
            template,
            start_iso=start_iso,
            stop_iso=stop_iso,
            module=mod_name,
            qualname=qualname,
            product_path=product_path,
            knobs=knobs_repr,
            knobs_kwarg=self._knobs_kwarg_name,
        )
        return {"Reproduce in SciQLop": snippet}
```

- [ ] **Step 5: Run all provider tests**

Run: `uv run pytest tests/test_provider_snippets.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/core/snippets/templates/vp_reproducer.j2 SciQLop/core/snippets/templates/vp_reproducer_unimportable.j2 SciQLop/components/plotting/backend/easy_provider.py tests/test_provider_snippets.py
git commit -m "feat(snippets): EasyProvider VP reproducer via jinja2 templates"
```

---

## Task 6: Panel and per-plot reproducer templates

**Files:**
- Create: `SciQLop/core/snippets/templates/panel_reproducer.j2`
- Create: `SciQLop/core/snippets/templates/plot_reproducer.j2`
- Modify: `SciQLop/components/plotting/ui/graph_context_snippets.py`
- Test: `tests/test_provider_snippets.py` or `tests/test_graph_context_integration.py` (use whichever already covers `panel_reproducer_snippet` / `plot_reproducer_snippet`)

- [ ] **Step 1: Find existing tests for these helpers**

Run: `uv run grep -n "panel_reproducer_snippet\|plot_reproducer_snippet" tests/`
Note which test files reference them. Add the new assertions in those files.

- [ ] **Step 2: Write the failing tests**

```python
# Append to whichever file already covers panel_reproducer_snippet
def test_panel_reproducer_uses_slash_path(qtbot):
    import numpy as np
    from SciQLop.components.plotting.ui.time_sync_panel import (
        TimeSyncPanel, plot_static_data,
    )
    from SciQLop.components.plotting.ui.graph_context_snippets import (
        panel_reproducer_snippet,
    )
    # Use a speasy/VP-like context attached manually since static plots aren't
    # reproducible; or replicate the existing fixture's pattern.
    # ... (match the file's existing fixture style)
    out = panel_reproducer_snippet(panel)
    assert out is not None
    assert "['root'" not in out
    # at least one plot_product line uses slash form
    assert 'panel.plot_product("' in out


def test_plot_reproducer_uses_slash_path(qtbot):
    # ... mirror panel test with plot_reproducer_snippet
    pass
```

(Mirror the existing test fixtures in the same file — avoid inventing a different harness.)

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest -k "panel_reproducer_uses_slash_path or plot_reproducer_uses_slash_path" -v`
Expected: FAIL — list literal still emitted.

- [ ] **Step 4: Add the templates**

```jinja2
{# SciQLop/core/snippets/templates/panel_reproducer.j2 #}
{% include "sciqlop_panel.j2" %}
{% for line in plot_lines %}
{{ line }}
{% endfor %}
{% if skipped %}

# Not included in this snippet:
{% for s in skipped %}
#   - {{ s }}
{% endfor %}
{% endif %}
```

```jinja2
{# SciQLop/core/snippets/templates/plot_reproducer.j2 #}
{% include "sciqlop_panel.j2" %}
{% for line in plot_lines %}
{{ line }}
{% endfor %}
{% if skipped %}

# Not included in this snippet:
{% for s in skipped %}
#   - {{ s }}
{% endfor %}
{% endif %}
```

(Yes, the two are currently identical bodies — separate templates because the next iteration may diverge, e.g., per-plot variant adding a comment header. If they stay identical for a release cycle, collapse later.)

- [ ] **Step 5: Migrate the helpers**

Replace `_product_path_arg`, `_header`, `panel_reproducer_snippet`, `plot_reproducer_snippet` in `SciQLop/components/plotting/ui/graph_context_snippets.py` with:

```python
def _product_path_arg(ctx) -> Optional[str]:
    """Return a quoted Python string for ``plot_product``'s product
    argument, or None if this graph isn't reproducible from a path.
    """
    from SciQLop.core.snippets import format_product_path
    if ctx.kind == "speasy":
        path = format_product_path(ctx.product_path) or ctx.speasy_id
        return f'"{path}"' if path else None
    if ctx.kind == "vp":
        path = format_product_path(ctx.product_path) or (ctx.vp_path or "")
        return f'"{path}"' if path else None
    return None


def _plot_product_lines(graphs: Iterable, plot_index: int) -> tuple[list[str], list[str]]:
    # unchanged — _product_path_arg now returns the quoted string form
    ...


def panel_reproducer_snippet(panel) -> Optional[str]:
    from SciQLop.core.snippets import render_snippet
    plots = ordered_plots(panel)
    plot_lines: list[str] = []
    skipped: list[str] = []
    for i, plot in enumerate(plots):
        graphs = list(plot.findChildren(SciQLopGraphInterface))
        if not graphs:
            continue
        lines, plot_skipped = _plot_product_lines(graphs, plot_index=i)
        plot_lines.extend(lines)
        skipped.extend(plot_skipped)
    if not plot_lines:
        return None
    start_iso, stop_iso = _iso_range(panel)
    return render_snippet(
        "panel_reproducer.j2",
        start_iso=start_iso, stop_iso=stop_iso,
        plot_lines=plot_lines, skipped=skipped,
    )


def plot_reproducer_snippet(panel, plot_index: int) -> Optional[str]:
    from SciQLop.core.snippets import render_snippet
    plots = ordered_plots(panel)
    if not (0 <= plot_index < len(plots)):
        return None
    graphs = list(plots[plot_index].findChildren(SciQLopGraphInterface))
    if not graphs:
        return None
    lines, skipped = _plot_product_lines(graphs, plot_index=0)
    if not lines:
        return None
    start_iso, stop_iso = _iso_range(panel)
    return render_snippet(
        "plot_reproducer.j2",
        start_iso=start_iso, stop_iso=stop_iso,
        plot_lines=lines, skipped=skipped,
    )
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/ -k "reproducer or snippet" -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add SciQLop/core/snippets/templates/panel_reproducer.j2 SciQLop/core/snippets/templates/plot_reproducer.j2 SciQLop/components/plotting/ui/graph_context_snippets.py tests/
git commit -m "feat(snippets): panel + plot reproducer via jinja2 templates"
```

---

## Task 7: End-to-end clipboard integration test

**Files:**
- Test: `tests/test_graph_context_integration.py`

- [ ] **Step 1: Write a regression test that simulates a real "Copy Python code → Notebook" click**

```python
# Append to tests/test_graph_context_integration.py
def test_copy_python_notebook_emits_slash_path(qtbot, monkeypatch):
    """End-to-end: produce a speasy graph, fetch its provider's
    'Notebook (matplotlib)' snippet, assert the product path is the
    slash-joined string form (no list literal, no 'root' prefix).
    """
    from SciQLop.core.graph_context import build_speasy_ctx, attach_context
    from SciQLop.components.plotting.backend.data_provider import providers

    # If a SpeasyPlugin instance is already registered (loaded by the test
    # harness), use it; otherwise skip — this test exercises the live wiring.
    sp = providers.get("Speasy")
    if sp is None:
        pytest.skip("Speasy provider not loaded in test env")

    from PySide6.QtCore import QObject

    class _G(QObject):
        def __init__(self): super().__init__(); self.setObjectName("g")

    g = _G()
    ctx = build_speasy_ctx(
        g, panel_name="P", plot_index=0,
        speasy_id="amda/ACE/b_gsm", graph_type="Line",
        product_path=["root", "speasy", "amda", "ACE", "b_gsm"],
    )
    attach_context(g, ctx)

    snippets = sp.python_snippets(ctx, graph=None)
    notebook = snippets.get("Notebook (matplotlib)")
    assert notebook is not None
    assert "['root'" not in notebook
    assert "/root/" not in notebook
    sciqlop_repro = snippets.get("Reproduce in SciQLop")
    assert sciqlop_repro is not None
    assert 'panel.plot_product("speasy/amda/ACE/b_gsm")' in sciqlop_repro
```

- [ ] **Step 2: Run the integration test**

Run: `uv run pytest tests/test_graph_context_integration.py::test_copy_python_notebook_emits_slash_path -v`
Expected: PASS (or SKIP cleanly if the SpeasyPlugin isn't loaded).

- [ ] **Step 3: Run the entire affected test surface**

Run: `uv run pytest tests/test_snippet_renderer.py tests/test_provider_snippets.py tests/test_graph_context.py tests/test_graph_context_integration.py -v`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_graph_context_integration.py
git commit -m "test(snippets): end-to-end string-form product path from menu"
```

---

## Task 8: Clean up dead code paths and CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Confirm nothing still calls the old helpers**

Run: `uv run grep -rn "_product_path_arg\|_speasy_sciqlop_snippet\|_speasy_matplotlib_snippet" SciQLop/`
Expected: only the new definitions, no orphan callers.

- [ ] **Step 2: Update CHANGELOG**

Append under the next-release section (follow `changelog-convention.md`):

```markdown
### Changed
- "Copy Python code" snippets now emit the `"a/b/c"` slash-joined product
  path instead of a Python list literal, and drop the implicit `"root"`
  prefix. Generated by Jinja2 templates living under
  `SciQLop/core/snippets/templates/`.
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): note snippet path format and template refactor"
```

---

## Reflection prompts (for the human reviewer)

These do NOT block execution — they're for reading the plan critically:

1. **Is `SciQLop.core.snippets` the right home?** It's used by both a plugin (speasy_provider) and components/. Putting it under `core/` matches the import direction. Alternative: `SciQLop.components.plotting.snippets`, but then a plugin imports a component — odd.
2. **Why `StrictUndefined`?** Catches typos in variable names at render time. Aligns with the schema-strictness elsewhere (Pydantic `extra="forbid"` on `GraphContext`).
3. **Why duplicate `panel_reproducer.j2` and `plot_reproducer.j2`?** They're identical now. The hypothesis is they'll diverge (per-plot may add a header comment with the plot title, or filter the time range to that plot's x-axis). If they stay identical through one release, collapse them.
4. **Should the snippet take a Pydantic context object?** Tempting (`SnippetContext(BaseModel)` with `start_iso`, `stop_iso`, `plot_lines`, ...). Skipped here to keep the patch small — Jinja2 + kwargs is enough surface for now. Worth revisiting if more producers grow.
5. **`speasy.get_data` argument** — it takes a speasy UID (`amda/ACE/b_gsm`), NOT a product-tree path. The matplotlib template emits `ctx.speasy_id` directly, not `format_product_path(ctx.product_path)`. Don't merge them.
6. **What about `to_product_path` in user_api?** Already accepts strings. No change needed. The receiver side is already permissive.
