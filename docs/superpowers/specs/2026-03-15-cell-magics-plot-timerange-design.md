# Cell Magics: %plot, %timerange, and Tab Completion

## Problem

Plotting a product from the embedded Jupyter console requires 3 lines of boilerplate. There's no tab completion for product paths or panel names in any magic. The `%%vp` magic has no completion for its flags or `--path` argument.

## Scope

1. `%plot <product> [panel]` — line magic to plot a product
2. `%timerange` — line magic to get/set panel time ranges
3. Tab completion for `%plot`, `%timerange`, and `%%vp`
4. Shared completion infrastructure reusing `ProductsFlatFilterModel`

## `%plot` Magic

**Syntax:** `%plot <product> [panel]`

- `product`: fuzzy-matched against `ProductsFlatFilterModel`. Always takes the top-ranked result (same behavior as command palette). Error if zero matches.
- `panel` (optional): existing panel name. If omitted, creates a new panel. Panel names with spaces must be quoted (`"My Panel"`).

```python
def plot_magic(line: str):
    args = shlex.split(line)
    product_path = resolve_product(args[0])
    panel_name = args[1] if len(args) > 1 else None

    if panel_name:
        panel = plot_panel(panel_name)
    else:
        panel = create_plot_panel()
    panel.plot_product(product_path, plot_type=PlotType.TimeSeries)
```

Note: `plot_type=PlotType.TimeSeries` is required when calling `plot_product` from Python (known SciQLopPlots pitfall).

`resolve_product(query)` uses `ProductsFlatFilterModel` with `QueryParser.parse()` to fuzzy-match, returning the top result's full path. Raises `UsageError` if no match.

## `%timerange` Magic

**Syntax:**

- `%timerange` — print time ranges of all panels
- `%timerange Panel-0` — print time range of that panel
- `%timerange 2024-01-01 2024-01-02 Panel-0` — set that panel's range

An explicit panel target is always required for setting. No implicit "set all panels" to avoid surprising side effects. Panel names with spaces must be quoted.

```python
def timerange_magic(line: str):
    args = shlex.split(line)
    if len(args) == 0:
        _print_all_time_ranges()
    elif len(args) == 1:
        _print_time_range(panel_name=args[0])
    elif len(args) == 3:
        _set_time_range(parse_time(args[0]), parse_time(args[1]), panel_name=args[2])
    else:
        raise UsageError("Usage: %timerange [panel] or %timerange <start> <stop> <panel>")
```

`parse_time` accepts ISO 8601 strings (`2024-01-01`, `2024-01-01T12:00:00`) and float timestamps. Extracted from `%%vp`'s existing `_parse_time_arg` for reuse.

## Shared Completion Infrastructure

A `completions.py` module providing two helpers reused by all magic completers:

```python
def _complete_products(prefix: str, max_results: int = 20) -> list[str]:
    """Fuzzy-match product paths using ProductsFlatFilterModel."""
    from SciQLopPlots import ProductsModel, ProductsFlatFilterModel, QueryParser
    from PySide6.QtWidgets import QApplication

    flat = ProductsFlatFilterModel(ProductsModel.instance())
    flat.set_query(QueryParser.parse(prefix))

    # Bounded processEvents loop — same pattern as command palette's
    # ProductArg.filtered_completions (arg_types.py lines 61-66)
    app = QApplication.instance()
    if app:
        for _ in range(100):
            app.processEvents()
            if flat.rowCount() >= max_results:
                break

    # Extract paths from mimeData (same as arg_types.py)
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
    from SciQLop.user_api.gui import get_main_window
    mw = get_main_window()
    if mw is None:
        return []
    return list(reversed(mw.plot_panels()))
```

## Completers

All completers are standalone functions. IPython's `set_hook('complete_command', fn)` calls them as `fn(completer_instance, event)` — the first arg is IPython's completer, not `self` of any class we define.

### `%plot` completer

```python
def complete_plot(completer, event):
    parts = event.line.split()
    if len(parts) <= 2:      # completing product (1st arg)
        return _complete_products(event.symbol)
    else:                     # completing panel (2nd arg)
        return [p for p in _complete_panels() if p.startswith(event.symbol)]
```

### `%timerange` completer

```python
def complete_timerange(completer, event):
    parts = event.line.split()
    # 1st arg or 4th token → panel name
    if len(parts) <= 2 or len(parts) == 4:
        return [p for p in _complete_panels() if p.startswith(event.symbol)]
    return []
```

### `%%vp` completer

```python
_VP_FLAGS = ["--path", "--debug", "--start", "--stop"]

def complete_vp(completer, event):
    parts = event.line.split()
    prev = parts[-2] if len(parts) >= 2 else ""
    if prev == "--path":
        return _complete_products(event.symbol)
    if event.symbol.startswith("-"):
        return [f for f in _VP_FLAGS if f.startswith(event.symbol)]
    return []
```

All registered via `ip.set_hook('complete_command', fn, str_key='%magic_name')`.

## File Layout

```
SciQLop/user_api/magics/
├── __init__.py          # register_all_magics(shell) entry point
├── completions.py       # _complete_products(), _complete_panels()
├── plot_magic.py        # %plot implementation + completer
└── timerange_magic.py   # %timerange implementation + completer
```

The `%%vp` magic stays in `SciQLop/user_api/virtual_products/magic.py`. Its completer lives in `completions.py`.

## Registration

`register_all_magics(shell)` is called from `InternalIPKernel._register_magics()` in `SciQLop/components/jupyter/kernel/__init__.py`. It replaces the current `register_vp_magic(shell)` call and handles everything:

1. Registers `%%vp` magic (moved from `register_vp_magic`)
2. Registers `%plot` and `%timerange` as line magics via `shell.register_magic_function()`
3. Registers all three completers via `shell.set_hook('complete_command', ...)`

This keeps magic + completer registration in one place, avoiding drift.

## Testing

- `resolve_product()`: unit test with mocked `ProductsFlatFilterModel` — exact match, fuzzy match, no match
- `parse_time()`: unit test for ISO 8601 strings, float timestamps, invalid input
- `plot_magic()`: test with mock `create_plot_panel`/`plot_panel` — new panel, existing panel, bad product
- `timerange_magic()`: test print and set modes with mock panels
- Completers: test with fake `event` objects, verify correct product/panel/flag completions per position

## Existing Code Changes

- `SciQLop/components/jupyter/kernel/__init__.py`: `_register_magics()` calls `register_all_magics(shell)` instead of `register_vp_magic(shell)`
- `SciQLop/user_api/virtual_products/magic.py`: extract `_parse_time_arg` to shared location for reuse by `%timerange`
- `SciQLop/user_api/virtual_products/__init__.py`: `register_vp_magic` still exists for backward compatibility but is called from `register_all_magics`
