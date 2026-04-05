# Doc Screenshot Generation

## Problem

Documentation screenshots drift out of sync with the UI. Manually capturing and updating them is tedious and error-prone. We need a way to programmatically generate screenshots so docs stay current with minimal effort.

## Approach

Extend the existing StoryRunner test infrastructure with screenshot capabilities. Scenarios are Python functions in `docs/screenshots/scenarios/` that set up UI state, apply visual tweaks (theme, window size, time range), and capture PNGs via `QWidget.grab()`. Run with pytest; output committed to the repo.

## New Components

### `take_screenshot` action

New `@ui_action` in `tests/fuzzing/screenshot_actions.py`:

```python
@ui_action(
    narrate="Captured screenshot '{name}'",
    settle_timeout_ms=200,
    model_update=lambda model: None,
    verify=lambda main_window, model: True,
)
def take_screenshot(main_window, model, name: str, target: str = "window",
                    output_dir: str | Path = "docs/screenshots/output") -> Path:
    widget = find_widget(main_window, target)
    pixmap = widget.grab()
    path = Path(output_dir) / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path), "PNG")
    return path
```

Note: `model_update` and `verify` are required by `@ui_action` but screenshots don't modify app state, so both are no-ops.

### Widget targeting via `find_widget`

Resolves `"kind:name"` strings to QWidgets:

```python
def find_widget(main_window, target: str) -> QWidget:
    resolvers = {
        "window": lambda mw: mw,
        "panel": lambda mw, name: find_panel_by_name(mw, name),
        "toolbar": lambda mw: mw.toolbar,
        "welcome": lambda mw: mw.welcome_widget,
    }
    parts = target.split(":", 1)
    kind = parts[0]
    args = parts[1:]
    if kind not in resolvers:
        raise ValueError(f"Unknown screenshot target kind '{kind}'. Available: {list(resolvers)}")
    return resolvers[kind](main_window, *args)
```

The resolver map grows one line at a time as new widget types appear in docs.

### `VisualSetup` and `visual_setup()` context manager

Controls theme, window size, and time range for a screenshot sequence:

```python
@dataclass
class VisualSetup:
    theme: str = "dark"
    window_size: tuple[int, int] = (1920, 1080)
    time_range: tuple[float, float] | None = None

@contextmanager
def visual_setup(main_window, setup: VisualSetup):
    original_theme = SciQLopStyle().color_palette
    original_size = main_window.size()
    original_time_range = get_global_time_range(main_window)

    _apply_theme(main_window, setup.theme)
    main_window.resize(*setup.window_size)
    if setup.time_range:
        set_global_time_range(main_window, setup.time_range)
    settle(timeout_ms=500)  # theme + resize needs more than the default 50ms

    yield

    _apply_theme(main_window, original_theme)
    main_window.resize(original_size.width(), original_size.height())
    if original_time_range:
        set_global_time_range(main_window, original_time_range)
    settle(timeout_ms=200)
```

**Theme switching:** `setup_palette()` returns a `QPalette` but does not apply it to the application. `_apply_theme()` is a small helper that calls `setup_palette()`, applies the palette via `QApplication.setPalette()`, and reloads stylesheets via `load_stylesheets()`.

**Current theme:** Read from `SciQLopStyle().color_palette` (the persisted settings value). No new module-level state needed.

**Settle timeout:** 500ms for the initial setup (theme switch + resize + stylesheet reload under Xvfb with OpenGL contexts). 200ms for teardown restore.

## File Layout

```
docs/screenshots/
├── conftest.py              # screenshot_runner fixture, output dir config
├── scenarios/
│   ├── test_getting_started.py
│   ├── test_catalogs.py
│   └── test_settings.py
└── output/                  # generated PNGs (committed to repo)
    ├── getting-started/
    └── catalogs/

tests/fuzzing/
└── screenshot_actions.py    # take_screenshot action, find_widget, VisualSetup
```

### `docs/screenshots/conftest.py`

- Re-exports shared fixtures from `tests/conftest.py` and `tests/fixtures.py` (via `pytest_plugins` list pointing to those modules)
- Provides a `screenshot_runner` fixture wrapping `StoryRunner` with default output dir `docs/screenshots/output/`

**Fixture sharing strategy:** The `docs/screenshots/conftest.py` uses `pytest_plugins = ["tests.conftest", "tests.fixtures"]` to pull in the `pytest_configure` hook (env vars, XDG dirs, Xvfb, Qt attributes) and the `main_window` fixture. This requires `tests/` to be on `sys.path`, which is handled by adding both `tests` and `docs/screenshots` to `testpaths` in `pyproject.toml`. The `rootdir` conftest's `pytest_configure` thus fires for screenshot runs too.

## Scenario Example

```python
from tests.fuzzing.panel_actions import create_panel
from tests.fuzzing.plot_data_actions import plot_static_spectro
from tests.fuzzing.screenshot_actions import take_screenshot, visual_setup, VisualSetup

def test_spectrogram_dark(screenshot_runner):
    with visual_setup(screenshot_runner.main_window, VisualSetup(theme="dark")):
        panel = screenshot_runner.run(create_panel)
        screenshot_runner.run(plot_static_spectro, panel=panel, x=..., y=..., z=...)
        screenshot_runner.run(take_screenshot, name="getting-started/spectrogram-dark")
```

## Running

```bash
# All screenshots
uv run pytest docs/screenshots/ -v

# One scenario file
uv run pytest docs/screenshots/scenarios/test_getting_started.py

# One scenario by name
uv run pytest docs/screenshots/ -k "spectrogram_dark"
```

## Output Strategy

PNGs are committed to the repo under `docs/screenshots/output/`. Paths are stable so documentation can reference them directly (e.g., `![](screenshots/output/getting-started/spectrogram-dark.png)`). Regenerate locally with pytest and commit updated images.

Consider adding `docs/screenshots/output/**/*.png` to `.gitattributes` with `binary` or Git LFS if image count/size grows significantly. For the initial implementation, standard git is fine.

## Dependencies

No new dependencies. Uses:
- `QWidget.grab()` for capture
- `setup_palette()` + `load_stylesheets()` from `SciQLop.components.theming` for theme switching
- `QApplication.setPalette()` for applying the palette at runtime
- `SciQLopStyle().color_palette` for reading the current theme name
- `StoryRunner`, `@ui_action`, and existing actions from `tests/fuzzing/`
- pytest + pytest-xvfb (already in dev deps)

## Existing Code Changes

Minimal:
- `pyproject.toml`: add `docs/screenshots` to `testpaths`
- `_apply_theme()` helper wraps `setup_palette()` + `QApplication.setPalette()` + `load_stylesheets()` — this could live in `screenshot_actions.py` or be promoted to the theming module if useful elsewhere
