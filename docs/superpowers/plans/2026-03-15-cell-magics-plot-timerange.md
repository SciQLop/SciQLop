# Cell Magics: %plot, %timerange, and Tab Completion — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `%plot` and `%timerange` line magics with tab completion for all three magics (`%plot`, `%timerange`, `%%vp`).

**Architecture:** Shared completion infrastructure in a new `SciQLop/user_api/magics/` package. Each magic gets its own module with implementation + completer. A single `register_all_magics(shell)` entry point replaces the current `register_vp_magic(shell)` call.

**Tech Stack:** IPython magic API (`register_magic_function`, `set_hook('complete_command', ...)`), `ProductsFlatFilterModel` + `QueryParser` from SciQLopPlots, `shlex` for argument parsing.

---

## File Structure

```
SciQLop/user_api/magics/
├── __init__.py              # register_all_magics(shell) entry point
├── completions.py           # _parse_time(), _complete_products(), _complete_panels()
├── plot_magic.py            # %plot implementation + completer
└── timerange_magic.py       # %timerange implementation + completer
```

**Modified files:**
- `SciQLop/components/jupyter/kernel/__init__.py:81-83` — call `register_all_magics` instead of `register_vp_magic`
- `SciQLop/user_api/virtual_products/magic.py:94-99` — replace `_parse_time_arg` with import from `completions.py`

**Test files:**
- `tests/test_magics/test_completions.py`
- `tests/test_magics/test_plot_magic.py`
- `tests/test_magics/test_timerange_magic.py`

---

## Chunk 1: Shared Infrastructure and %plot

### Task 1: Shared completion helpers

**Files:**
- Create: `SciQLop/user_api/magics/__init__.py`
- Create: `SciQLop/user_api/magics/completions.py`
- Test: `tests/test_magics/test_completions.py`

- [ ] **Step 1: Write failing tests for `_complete_products` and `_complete_panels`**

Create `tests/test_magics/__init__.py` (empty) and `tests/test_magics/test_completions.py`:

```python
"""Tests for shared magic completion and parsing helpers."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone


class TestParseTime:
    def test_parse_iso_date(self):
        from SciQLop.user_api.magics.completions import _parse_time
        result = _parse_time("2024-01-01")
        expected = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp()
        assert result == expected

    def test_parse_iso_datetime(self):
        from SciQLop.user_api.magics.completions import _parse_time
        result = _parse_time("2024-01-01T12:00:00")
        expected = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp()
        assert result == expected

    def test_parse_float_timestamp(self):
        from SciQLop.user_api.magics.completions import _parse_time
        assert _parse_time("1704067200.0") == 1704067200.0

    def test_parse_tz_aware_iso(self):
        from SciQLop.user_api.magics.completions import _parse_time
        result = _parse_time("2024-01-01T02:00:00+02:00")
        expected = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()
        assert result == expected

    def test_raises_on_invalid(self):
        from SciQLop.user_api.magics.completions import _parse_time
        with pytest.raises(ValueError):
            _parse_time("not-a-time")


class TestCompleteProducts:
    @patch("SciQLop.user_api.magics.completions.ProductsFlatFilterModel")
    @patch("SciQLop.user_api.magics.completions.ProductsModel")
    @patch("SciQLop.user_api.magics.completions.QApplication")
    def test_returns_product_paths(self, mock_qapp, mock_pm, mock_flat_cls):
        from SciQLop.user_api.magics.completions import _complete_products

        mock_flat = MagicMock()
        mock_flat_cls.return_value = mock_flat
        mock_flat.rowCount.return_value = 2

        mime = MagicMock()
        mime.text.return_value = "provider/product_a\nprovider/product_b\n"
        mock_flat.mimeData.return_value = mime

        mock_qapp.instance.return_value = MagicMock()

        result = _complete_products("prod")
        assert result == ["provider/product_a", "provider/product_b"]

    @patch("SciQLop.user_api.magics.completions.ProductsFlatFilterModel")
    @patch("SciQLop.user_api.magics.completions.ProductsModel")
    @patch("SciQLop.user_api.magics.completions.QApplication")
    def test_returns_empty_on_no_match(self, mock_qapp, mock_pm, mock_flat_cls):
        from SciQLop.user_api.magics.completions import _complete_products

        mock_flat = MagicMock()
        mock_flat_cls.return_value = mock_flat
        mock_flat.rowCount.return_value = 0

        mock_qapp.instance.return_value = MagicMock()

        result = _complete_products("zzz_no_match")
        assert result == []


class TestCompletePanels:
    @patch("SciQLop.user_api.magics.completions.get_main_window")
    def test_returns_panel_names_reversed(self, mock_gmw):
        from SciQLop.user_api.magics.completions import _complete_panels

        mock_mw = MagicMock()
        mock_mw.plot_panels.return_value = ["Panel-0", "Panel-1", "Panel-2"]
        mock_gmw.return_value = mock_mw

        result = _complete_panels()
        assert result == ["Panel-2", "Panel-1", "Panel-0"]

    @patch("SciQLop.user_api.magics.completions.get_main_window")
    def test_returns_empty_when_no_main_window(self, mock_gmw):
        from SciQLop.user_api.magics.completions import _complete_panels

        mock_gmw.return_value = None
        assert _complete_panels() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_magics/test_completions.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `completions.py`**

Create `SciQLop/user_api/magics/__init__.py` (empty for now) and `SciQLop/user_api/magics/completions.py`:

```python
"""Shared completion and parsing helpers for all SciQLop cell/line magics."""
from datetime import datetime, timezone

from SciQLopPlots import ProductsModel, ProductsFlatFilterModel, QueryParser
from PySide6.QtWidgets import QApplication

from SciQLop.user_api.gui import get_main_window


def _parse_time(value: str) -> float:
    """Parse a time argument as either a float timestamp or an ISO 8601 string.

    Naive ISO strings are assumed UTC. Tz-aware strings are converted to UTC.
    """
    try:
        return float(value)
    except ValueError:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).timestamp()


def _complete_products(prefix: str, max_results: int = 20) -> list[str]:
    """Fuzzy-match product paths using ProductsFlatFilterModel."""
    flat = ProductsFlatFilterModel(ProductsModel.instance())
    flat.set_query(QueryParser.parse(prefix))

    app = QApplication.instance()
    if app:
        for _ in range(100):
            app.processEvents()
            if flat.rowCount() >= max_results:
                break

    count = min(flat.rowCount(), max_results)
    if count == 0:
        return []
    indexes = [flat.index(i, 0) for i in range(count)]
    mime = flat.mimeData(indexes)
    if mime and mime.text():
        return [path.strip() for path in mime.text().strip().split("\n") if path.strip()]
    return []


def _complete_panels() -> list[str]:
    """Return panel names, most recent first."""
    mw = get_main_window()
    if mw is None:
        return []
    return list(reversed(mw.plot_panels()))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_magics/test_completions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/magics/__init__.py SciQLop/user_api/magics/completions.py tests/test_magics/__init__.py tests/test_magics/test_completions.py
git commit -m "feat: add shared completion helpers for magic tab completion"
```

---

### Task 2: `%plot` magic and completer

**Files:**
- Create: `SciQLop/user_api/magics/plot_magic.py`
- Test: `tests/test_magics/test_plot_magic.py`

- [ ] **Step 1: Write failing tests for `plot_magic` and `complete_plot`**

Create `tests/test_magics/test_plot_magic.py`:

```python
"""Tests for %plot line magic."""
import pytest
from unittest.mock import MagicMock, patch


class TestResolvProduct:
    @patch("SciQLop.user_api.magics.plot_magic._complete_products")
    def test_returns_top_match(self, mock_cp):
        from SciQLop.user_api.magics.plot_magic import _resolve_product
        mock_cp.return_value = ["speasy/amda/imf_mag"]
        assert _resolve_product("imf") == "speasy/amda/imf_mag"

    @patch("SciQLop.user_api.magics.plot_magic._complete_products")
    def test_raises_on_no_match(self, mock_cp):
        from SciQLop.user_api.magics.plot_magic import _resolve_product
        mock_cp.return_value = []
        with pytest.raises(Exception, match="No product matching"):
            _resolve_product("zzz_nothing")


class TestPlotMagic:
    @patch("SciQLop.user_api.magics.plot_magic.plot_panel")
    @patch("SciQLop.user_api.magics.plot_magic._resolve_product")
    def test_plot_in_existing_panel(self, mock_resolve, mock_pp):
        from SciQLop.user_api.magics.plot_magic import plot_magic
        from SciQLopPlots import PlotType
        mock_resolve.return_value = "speasy/amda/imf"
        mock_panel = MagicMock()
        mock_pp.return_value = mock_panel

        plot_magic('imf "Panel-0"')

        mock_pp.assert_called_once_with("Panel-0")
        mock_panel.plot_product.assert_called_once_with("speasy/amda/imf", plot_type=PlotType.TimeSeries)

    @patch("SciQLop.user_api.magics.plot_magic.create_plot_panel")
    @patch("SciQLop.user_api.magics.plot_magic._resolve_product")
    def test_plot_in_new_panel(self, mock_resolve, mock_create):
        from SciQLop.user_api.magics.plot_magic import plot_magic
        mock_resolve.return_value = "speasy/amda/imf"
        mock_panel = MagicMock()
        mock_create.return_value = mock_panel

        plot_magic("imf")

        mock_create.assert_called_once()
        mock_panel.plot_product.assert_called_once()

    def test_empty_input_raises(self):
        from SciQLop.user_api.magics.plot_magic import plot_magic
        with pytest.raises(Exception, match="Usage"):
            plot_magic("")


class TestCompletePlot:
    @patch("SciQLop.user_api.magics.plot_magic._complete_products")
    def test_completes_product_on_first_arg(self, mock_cp):
        from SciQLop.user_api.magics.plot_magic import complete_plot
        mock_cp.return_value = ["speasy/amda/imf"]
        event = MagicMock()
        event.line = "%plot im"
        event.symbol = "im"

        result = complete_plot(None, event)
        assert result == ["speasy/amda/imf"]

    @patch("SciQLop.user_api.magics.plot_magic._complete_panels")
    def test_completes_panel_on_second_arg(self, mock_panels):
        from SciQLop.user_api.magics.plot_magic import complete_plot
        mock_panels.return_value = ["Panel-1", "Panel-0"]
        event = MagicMock()
        event.line = "%plot imf Pan"
        event.symbol = "Pan"

        result = complete_plot(None, event)
        assert result == ["Panel-1", "Panel-0"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_magics/test_plot_magic.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `plot_magic.py`**

Create `SciQLop/user_api/magics/plot_magic.py`:

```python
"""Implementation of %plot line magic and its tab completer."""
import shlex

from IPython.core.error import UsageError
from SciQLopPlots import PlotType

from SciQLop.user_api.magics.completions import _complete_products, _complete_panels
from SciQLop.user_api.plot import plot_panel, create_plot_panel


def _resolve_product(query: str) -> str:
    """Fuzzy-match a product query, returning the top result's full path."""
    matches = _complete_products(query, max_results=1)
    if not matches:
        raise UsageError(f"No product matching '{query}'")
    return matches[0]


def plot_magic(line: str):
    """Line magic: %plot <product> [panel]

    Plot a product in an existing or new panel.
    Product is fuzzy-matched. Panel names with spaces must be quoted.
    """
    args = shlex.split(line)
    if not args:
        raise UsageError("Usage: %plot <product> [panel]")

    product_path = _resolve_product(args[0])

    if len(args) > 1:
        panel = plot_panel(args[1])
        if panel is None:
            raise UsageError(f"Panel '{args[1]}' not found")
    else:
        panel = create_plot_panel()

    panel.plot_product(product_path, plot_type=PlotType.TimeSeries)


def complete_plot(completer, event):
    """Tab completer for %plot: product (1st arg), panel (2nd arg)."""
    parts = event.line.split()
    if len(parts) <= 2:
        return _complete_products(event.symbol)
    return [p for p in _complete_panels() if p.startswith(event.symbol)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_magics/test_plot_magic.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/magics/plot_magic.py tests/test_magics/test_plot_magic.py
git commit -m "feat: add %plot line magic with tab completion"
```

---

## Chunk 2: %timerange, %%vp Completer, and Registration

### Task 3: `%timerange` magic and completer

**Files:**
- Create: `SciQLop/user_api/magics/timerange_magic.py`
- Test: `tests/test_magics/test_timerange_magic.py`

- [ ] **Step 1: Write failing tests for `timerange_magic` and `complete_timerange`**

Create `tests/test_magics/test_timerange_magic.py`:

```python
"""Tests for %timerange line magic."""
import pytest
from unittest.mock import MagicMock, patch, call


class TestTimerangeMagic:
    @patch("SciQLop.user_api.magics.timerange_magic._print_all_time_ranges")
    def test_no_args_prints_all(self, mock_print_all):
        from SciQLop.user_api.magics.timerange_magic import timerange_magic
        timerange_magic("")
        mock_print_all.assert_called_once()

    @patch("SciQLop.user_api.magics.timerange_magic._print_time_range")
    def test_one_arg_prints_panel(self, mock_print):
        from SciQLop.user_api.magics.timerange_magic import timerange_magic
        timerange_magic("Panel-0")
        mock_print.assert_called_once_with("Panel-0")

    @patch("SciQLop.user_api.magics.timerange_magic._set_time_range")
    def test_three_args_sets_range(self, mock_set):
        from SciQLop.user_api.magics.timerange_magic import timerange_magic
        timerange_magic("2024-01-01 2024-01-02 Panel-0")
        mock_set.assert_called_once()
        args = mock_set.call_args[0]
        assert args[2] == "Panel-0"

    def test_two_args_raises(self):
        from SciQLop.user_api.magics.timerange_magic import timerange_magic
        with pytest.raises(Exception, match="Usage"):
            timerange_magic("2024-01-01 2024-01-02")


class TestCompleteTimerange:
    @patch("SciQLop.user_api.magics.timerange_magic._complete_panels")
    def test_completes_panel_on_first_arg(self, mock_panels):
        from SciQLop.user_api.magics.timerange_magic import complete_timerange
        mock_panels.return_value = ["Panel-1", "Panel-0"]
        event = MagicMock()
        event.line = "%timerange Pan"
        event.symbol = "Pan"

        result = complete_timerange(None, event)
        assert result == ["Panel-1", "Panel-0"]

    @patch("SciQLop.user_api.magics.timerange_magic._complete_panels")
    def test_completes_panel_on_fourth_token(self, mock_panels):
        from SciQLop.user_api.magics.timerange_magic import complete_timerange
        mock_panels.return_value = ["Panel-0"]
        event = MagicMock()
        event.line = "%timerange 2024-01-01 2024-01-02 Pan"
        event.symbol = "Pan"

        result = complete_timerange(None, event)
        assert result == ["Panel-0"]

    def test_no_completion_for_time_args(self):
        from SciQLop.user_api.magics.timerange_magic import complete_timerange
        event = MagicMock()
        event.line = "%timerange 2024-01-01 20"
        event.symbol = "20"

        result = complete_timerange(None, event)
        assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_magics/test_timerange_magic.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `timerange_magic.py`**

Create `SciQLop/user_api/magics/timerange_magic.py`:

```python
"""Implementation of %timerange line magic and its tab completer."""
import shlex
from datetime import datetime, timezone

from IPython.core.error import UsageError

from SciQLop.user_api.magics.completions import _parse_time, _complete_panels
from SciQLop.user_api.gui import get_main_window
from SciQLop.user_api.plot import plot_panel as _get_panel


def _panel_names():
    mw = get_main_window()
    return mw.plot_panels() if mw else []


def _print_all_time_ranges():
    for name in _panel_names():
        _print_time_range(name)


def _print_time_range(panel_name: str):
    panel = _get_panel(panel_name)
    if panel is None:
        raise UsageError(f"Panel '{panel_name}' not found")
    tr = panel.time_range
    start = datetime.fromtimestamp(tr.start(), tz=timezone.utc).isoformat()
    stop = datetime.fromtimestamp(tr.stop(), tz=timezone.utc).isoformat()
    print(f"{panel_name}: {start} → {stop}")


def _set_time_range(start: float, stop: float, panel_name: str):
    from SciQLop.core import TimeRange
    panel = _get_panel(panel_name)
    if panel is None:
        raise UsageError(f"Panel '{panel_name}' not found")
    panel.time_range = TimeRange(start, stop)


def timerange_magic(line: str):
    """Line magic: %timerange [panel] or %timerange <start> <stop> <panel>

    Print or set panel time ranges.
    """
    args = shlex.split(line)
    if len(args) == 0:
        _print_all_time_ranges()
    elif len(args) == 1:
        _print_time_range(args[0])
    elif len(args) == 3:
        _set_time_range(_parse_time(args[0]), _parse_time(args[1]), panel_name=args[2])
    else:
        raise UsageError("Usage: %timerange [panel] or %timerange <start> <stop> <panel>")


def complete_timerange(completer, event):
    """Tab completer for %timerange: panel name on 1st arg or 4th token."""
    parts = event.line.split()
    if len(parts) <= 2 or len(parts) == 4:
        return [p for p in _complete_panels() if p.startswith(event.symbol)]
    return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_magics/test_timerange_magic.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/magics/timerange_magic.py tests/test_magics/test_timerange_magic.py
git commit -m "feat: add %timerange line magic with tab completion"
```

---

### Task 4: `%%vp` completer and `register_all_magics`

**Files:**
- Modify: `SciQLop/user_api/magics/__init__.py`
- Modify: `SciQLop/components/jupyter/kernel/__init__.py:81-83`
- Modify: `SciQLop/user_api/virtual_products/magic.py:94-99` — replace `_parse_time_arg` with import from `completions.py`

- [ ] **Step 1: Write failing test for `complete_vp`**

Append to `tests/test_magics/test_completions.py`:

```python
class TestCompleteVp:
    @patch("SciQLop.user_api.magics.completions._complete_products")
    def test_completes_product_after_path_flag(self, mock_cp):
        from SciQLop.user_api.magics.completions import complete_vp
        mock_cp.return_value = ["speasy/amda/imf"]
        event = MagicMock()
        event.line = "%%vp --path im"
        event.symbol = "im"

        result = complete_vp(None, event)
        assert result == ["speasy/amda/imf"]

    def test_completes_flags(self):
        from SciQLop.user_api.magics.completions import complete_vp
        event = MagicMock()
        event.line = "%%vp --"
        event.symbol = "--"

        result = complete_vp(None, event)
        assert "--path" in result
        assert "--debug" in result
        assert "--start" in result
        assert "--stop" in result

    def test_no_completion_for_bare_text(self):
        from SciQLop.user_api.magics.completions import complete_vp
        event = MagicMock()
        event.line = "%%vp foo"
        event.symbol = "foo"

        result = complete_vp(None, event)
        assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_magics/test_completions.py::TestCompleteVp -v`
Expected: FAIL — `complete_vp` not found

- [ ] **Step 3: Add `complete_vp` to `completions.py`**

Append to `SciQLop/user_api/magics/completions.py`:

```python
_VP_FLAGS = ["--path", "--debug", "--start", "--stop"]


def complete_vp(completer, event):
    """Tab completer for %%vp: --path → product, -- → flags."""
    parts = event.line.split()
    prev = parts[-2] if len(parts) >= 2 else ""
    if prev == "--path":
        return _complete_products(event.symbol)
    if event.symbol.startswith("-"):
        return [f for f in _VP_FLAGS if f.startswith(event.symbol)]
    return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_magics/test_completions.py -v`
Expected: PASS

- [ ] **Step 5: Implement `register_all_magics` in `__init__.py`**

Write `SciQLop/user_api/magics/__init__.py`:

```python
"""SciQLop IPython magics — registration entry point."""


def register_all_magics(shell):
    """Register all SciQLop magics and their tab completers."""
    from SciQLop.user_api.virtual_products.magic import vp_magic
    from SciQLop.user_api.magics.plot_magic import plot_magic, complete_plot
    from SciQLop.user_api.magics.timerange_magic import timerange_magic, complete_timerange
    from SciQLop.user_api.magics.completions import complete_vp

    shell.register_magic_function(vp_magic, magic_kind="cell", magic_name="vp")
    shell.register_magic_function(plot_magic, magic_kind="line", magic_name="plot")
    shell.register_magic_function(timerange_magic, magic_kind="line", magic_name="timerange")

    shell.set_hook("complete_command", complete_plot, str_key="%plot")
    shell.set_hook("complete_command", complete_timerange, str_key="%timerange")
    shell.set_hook("complete_command", complete_vp, str_key="%%vp")
```

- [ ] **Step 6: Update kernel `_register_magics` to call `register_all_magics`**

In `SciQLop/components/jupyter/kernel/__init__.py`, replace lines 81-83:

```python
# Before:
    def _register_magics(self):
        from SciQLop.user_api.virtual_products import register_vp_magic
        register_vp_magic(self.ipykernel.shell)

# After:
    def _register_magics(self):
        from SciQLop.user_api.magics import register_all_magics
        register_all_magics(self.ipykernel.shell)
```

- [ ] **Step 7: Update `_parse_time_arg` in `magic.py` to reuse shared `_parse_time`**

In `SciQLop/user_api/virtual_products/magic.py`, replace `_parse_time_arg` (lines 94-99):

```python
# Before:
def _parse_time_arg(value: str) -> float:
    """Parse a time argument as either a float or an ISO 8601 date string."""
    try:
        return float(value)
    except ValueError:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()

# After:
from SciQLop.user_api.magics.completions import _parse_time as _parse_time_arg
```

- [ ] **Step 8: Run all magic tests**

Run: `uv run pytest tests/test_magics/ -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add SciQLop/user_api/magics/__init__.py SciQLop/user_api/magics/completions.py SciQLop/components/jupyter/kernel/__init__.py SciQLop/user_api/virtual_products/magic.py tests/test_magics/test_completions.py
git commit -m "feat: add %%vp completer and register_all_magics entry point

Consolidates magic registration in register_all_magics(). Adds tab
completion for %%vp flags and --path product matching. Replaces
register_vp_magic() call in kernel init."
```

---

## Notes

- `PlotType.TimeSeries` is required when calling `plot_product` from Python — this is a known SciQLopPlots pitfall.
- `_complete_products` uses the same bounded `processEvents` loop as the command palette's `ProductArg.filtered_completions` (`arg_types.py:61-66`).
- Panel names are returned most-recent-first in completions to surface the likely target.
- `register_vp_magic` in `SciQLop/user_api/virtual_products/__init__.py` still exists for backward compatibility but is no longer called from the kernel init.
