# Documentation Screenshots

Programmatic screenshot generation for SciQLop documentation. Scenarios are Python functions that set up UI state, apply visual tweaks, and capture PNGs via `QWidget.grab()`.

## Running

```bash
# All screenshots
uv run pytest docs/screenshots/ -v

# One scenario file
uv run pytest docs/screenshots/scenarios/test_getting_started.py

# One scenario by name
uv run pytest docs/screenshots/ -k "spectrogram"
```

Generated PNGs go to `docs/screenshots/output/` with stable paths for doc references.

## Writing scenarios

Scenarios live in `docs/screenshots/scenarios/` as regular pytest files. Each test function uses `screenshot_runner` to drive the UI:

```python
import numpy as np
from tests.fuzzing.panel_actions import create_panel
from tests.fuzzing.plot_data_actions import plot_static_data
from tests.fuzzing.screenshot_actions import (
    take_screenshot, visual_setup, VisualSetup,
)

def test_my_screenshot(screenshot_runner):
    with visual_setup(screenshot_runner.main_window, VisualSetup(theme="dark")):
        panel = screenshot_runner.run(create_panel)
        x = np.linspace(0, 100, 1000)
        y = np.sin(x * 0.1)
        screenshot_runner.run(plot_static_data, panel=panel, x=x, y=y)
        screenshot_runner.run(take_screenshot, name="my-folder/my-screenshot")
```

## Visual setup options

`VisualSetup` controls the look before capture:

- `theme` — `"light"`, `"dark"`, `"neutral"`, `"space"` (default: `None`, keeps current)
- `window_size` — `(width, height)` in pixels (default: `(1920, 1080)`)
- `time_range` — `(start, stop)` as floats, or `None` to keep current

## Screenshot targets

The `target` parameter controls what gets captured:

- `"window"` — full application window (default)
- `"panel:<name>"` — a specific plot panel by name (e.g. `"panel:Panel-0"`)
