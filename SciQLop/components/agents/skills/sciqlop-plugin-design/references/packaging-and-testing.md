# Packaging, testing, debugging

## Layout and the two names

```
sciqlop_my_plugin/              # folder you add to SciQLop's plugin folders
├── pyproject.toml              # pip name: sciqlop-my-plugin
└── sciqlop_my_plugin/          # import name, = plugin id in SciQLop's settings
    ├── __init__.py             # load(main_window)
    ├── plugin.json
    └── tests/
```

Keep the plugin flat: a handful of modules named after what they do
(`products.py`, `fetch.py`, `dock.py`, `settings.py`). A folder per concept
is overkill for a plugin.

## plugin.json

```json
{
  "name": "My Plugin",
  "version": "0.1.0",
  "description": "One line shown in the plugin list",
  "authors": [{"name": "...", "email": "...", "organization": "..."}],
  "license": "MIT",
  "python_dependencies": ["SciQLop>=0.14.0,<0.15.0", "requests>=2.31"],
  "dependencies": ["speasy_provider"],
  "disabled": false
}
```

- Required for folder discovery. A plugin with only an entry point in
  `pyproject.toml` is invisible when loaded from a folder.
- `name`, `version`, `description`, `authors` and `license` are required, and
  every author needs `name`, `email` and `organization`. A missing one skips
  the plugin.
- `python_dependencies` are pip requirements. The `SciQLop>=X,<Y` range is
  the compatibility gate: SciQLop skips a plugin whose range excludes the
  running version, instead of letting `load()` crash on an API it doesn't
  have. Without a range the plugin always loads. Declare it, and cap it at the
  next minor release you have not tested. The host is compared by its base
  version, so a `0.14.1.dev0` build satisfies `>=0.14.0`: no `.dev0` floors. It does not interfere with
  SciQLop's own installation: SciQLop drops its own name from plugin
  requirements before installing them.
- Third-party requirements are installed into SciQLop's workspace
  environment by SciQLop. Never `pip install` into it by hand; inside
  SciQLop's chat, use the `sciqlop_install_package` tool.
- `dependencies` names other SciQLop plugins (for example
  `"speasy_provider"`). Don't rely on it for load order.

## pyproject.toml

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "sciqlop-my-plugin"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["SciQLop>=0.14.0,<0.15.0", "requests>=2.31"]

[project.optional-dependencies]
test = ["pytest", "pytest-qt"]

[project.entry-points."sciqlop.plugins"]
sciqlop_my_plugin = "sciqlop_my_plugin"

[tool.setuptools.packages.find]
include = ["sciqlop_my_plugin*"]

[tool.setuptools.package-data]
sciqlop_my_plugin = ["plugin.json", "*.yaml"]     # every data file you ship
```

`version` and the dependency list exist twice, here and in `plugin.json`.
Change both together on every release; they drift otherwise.

## Development loop

1. Add the plugin folder to `extra_plugins_folders` in
   `<config dir>/sciqlop/sciqloppluginssettings.yaml` and enable it:
   ```yaml
   extra_plugins_folders:
     - /path/to/sciqlop_my_plugin
   plugins:
     sciqlop_my_plugin:
       enabled: true
   ```
   SciQLop treats every subdirectory of a listed folder as a candidate plugin.
   List the folder that holds `pyproject.toml`; `build/`, `dist/` or
   `*.egg-info` in it only produce harmless "Skipping plugin" warnings.
2. Restart SciQLop. Plugins load at startup only. No install needed: SciQLop
   imports the package from the folder.
3. Delete `__pycache__` if an edit doesn't show up.

## Tests

Test in the same Python environment SciQLop runs in, so the tests see the
SciQLop version the plugin will meet.

### What to test, cheapest first

1. **Pure functions** (parsing, path building, label formatting, unit
   conversion). No SciQLop, no Qt.
2. **Callbacks, called directly** with a fake fetcher:
   `callback(start, stop)` returns the right shapes, ascending energy axis,
   `None` for an empty window, and raises on a fetch error.
3. **Callback signatures**, for knobs:
   `inspect.signature(callback, eval_str=True)` must not raise, and must list
   the knob parameters with their defaults.
4. **Widgets** with `pytest-qt` (`qtbot.addWidget(w)`): filling a table,
   sorting, signals carrying errors.
5. **The real flow** inside SciQLop: register, plot on a panel, wait for data
   (`panel.wait_for_data()`), check what was drawn.

### Fakes, not bare mocks

A bare `MagicMock()` standing in for a panel or a plot accepts any call with
any arguments. A test then passes while the real call raises. Fake only the
methods you use, with their real signatures, or use real SciQLop objects.

### Settings isolation

`ConfigEntry` reads the real user YAML, which replaces your constructor
arguments, and writes to it. A settings test passes on a clean CI machine and
fails, or passes for the wrong reason, on a machine where SciQLop was used —
and may overwrite the user's settings. Point the config directory at a fresh
temporary folder for every test:

```python
import pytest

@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    from SciQLop.components.settings.backend import entry
    monkeypatch.setattr(entry, "SCIQLOP_CONFIG_DIR", str(tmp_path))
```

`ConfigEntry.config_file()` reads that module global at call time, so this
works on every platform. (Setting `XDG_CONFIG_HOME` works on Linux only, and
only before SciQLop is imported.)

An invalid value does not raise: the entry falls back to defaults. Assert that
fallback, not `pytest.raises`.

### Qt in tests

- Some SciQLop modules need a `QApplication` at import time and abort the
  interpreter without one. Create it (or use `pytest-qt`'s `qapp`) before
  importing them.
- Headless runs need a display: `QT_QPA_PLATFORM=offscreen`, or Xvfb.

## Verify visual results by looking

Reading state back (`axis.range()`, `graph.data`) proves the API accepted a
value, not that the picture is right. For axes, labels, layout and colours:

1. Build the real panel the way the user will (no extra manual rescale).
2. Render it (test code only, hence the `_impl`): `w = panel._impl;
   w.resize(1100, 700); w.show(); qtbot.wait(800); w.grab().save("check.png")`,
   then look at the image.
3. Use a realistic selection: several channels, a multi-day span, a gap.
   Labels and axes that work for one channel often break at nine.

## Debugging "the plot is empty"

Test each layer on its own, in order, against real data:

1. **Fetch:** does the raw fetch for this window return anything? Archives lag
   real time; the last hours before "now" are often empty.
2. **Convert:** does the conversion keep everything? (Gapped data arriving as
   several pieces, with only the first one kept, is a classic.)
3. **Callback:** call it with the panel's exact `start, stop`. Check shapes,
   NaN/fill values, axis order.
4. **Registration:** is the product at the path you plot? Plot by path with
   `panel.plot_product("a//b")`; a wrong path raises `ValueError`.
5. **Panel:** time range on the data? Zoom limit clipping it? For a
   spectrogram, energy axis ascending?
6. **Errors:** look at SciQLop's log, and at the graph's `last_error` (from
   `sciqlop_describe_panel` in SciQLop's chat). If both are silent, something
   is catching exceptions — find it.
