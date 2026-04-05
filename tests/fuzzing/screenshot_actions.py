from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import QApplication

from tests.fuzzing.actions import ui_action, settle


@dataclass
class VisualSetup:
    theme: str | None = None
    window_size: tuple[int, int] = (1920, 1080)
    time_range: tuple[float, float] | None = None


def _apply_theme(app, palette_name: str):
    """Switch theme using the app's own machinery to avoid segfaults."""
    from SciQLop.components.theming import setup_palette

    qpalette = setup_palette(palette_name)
    app._current_palette_name = palette_name
    app._current_palette = qpalette
    app.setPalette(qpalette)
    app.load_stylesheet()


def _get_time_range(main_window) -> tuple[float, float] | None:
    panels = main_window.plot_panels()
    if not panels:
        return None
    first_panel = main_window.plot_panel(list(panels)[0])
    if first_panel is None:
        return None
    tr = first_panel.time_range
    return (tr.start(), tr.stop())


def _set_global_time_range(main_window, time_range: tuple[float, float]):
    from SciQLop.core import TimeRange

    tr = TimeRange(time_range[0], time_range[1])
    for name in main_window.plot_panels():
        panel = main_window.plot_panel(name)
        if panel is not None:
            panel.set_time_axis_range(tr)


@contextmanager
def visual_setup(main_window, setup: VisualSetup):
    app = QApplication.instance()

    original_palette_name = app._current_palette_name
    original_size = main_window.size()
    original_time_range = _get_time_range(main_window)

    if setup.theme and setup.theme != original_palette_name:
        _apply_theme(app, setup.theme)
    main_window.resize(*setup.window_size)
    if setup.time_range:
        _set_global_time_range(main_window, setup.time_range)
    settle(timeout_ms=500)

    yield

    if setup.theme and setup.theme != original_palette_name:
        _apply_theme(app, original_palette_name)
    main_window.resize(original_size.width(), original_size.height())
    if original_time_range:
        _set_global_time_range(main_window, original_time_range)
    settle(timeout_ms=200)


def find_widget(main_window, target: str):
    resolvers = {
        "window": lambda mw: mw,
        "panel": lambda mw, name: mw.plot_panel(name),
    }
    parts = target.split(":", 1)
    kind = parts[0]
    args = parts[1:]
    if kind not in resolvers:
        raise ValueError(f"Unknown screenshot target '{kind}'. Available: {list(resolvers)}")
    return resolvers[kind](main_window, *args)


@ui_action(
    narrate="Captured screenshot '{name}'",
    settle_timeout_ms=200,
    model_update=lambda model: None,
    verify=lambda main_window, model: True,
)
def take_screenshot(
    main_window, model, name: str, target: str = "window",
    output_dir: str | Path = "docs/screenshots/output",
) -> Path:
    widget = find_widget(main_window, target)
    pixmap = widget.grab()
    path = Path(output_dir) / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path), "PNG")
    return path
