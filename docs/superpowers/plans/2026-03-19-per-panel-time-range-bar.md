# Per-Panel Time Range Bar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the misleading global toolbar time range widget with a per-panel bottom bar using start-date + duration input model.

**Architecture:** Each `TimeSyncPanel` gets wrapped in a `PanelContainer` (QWidget with QVBoxLayout) that holds the panel + a `TimeRangeBar` widget. The bar shows a start datetime picker, a duration combo (1m/1h/12h/1d/7d), and `[<<] [<] [>] [>>]` navigation buttons that step by one duration. The bar bidirectionally syncs with the panel's `time_range_changed` signal and `set_time_axis_range()`.

**Tech Stack:** PySide6 (QDateTimeEdit, QComboBox, QPushButton), SciQLopPlots TimeRange

---

## File Structure

| File | Responsibility |
|------|---------------|
| `SciQLop/components/plotting/ui/time_range_bar.py` | **Create** — `TimeRangeBar` widget (start picker + duration combo + nav buttons) |
| `SciQLop/components/plotting/ui/panel_container.py` | **Create** — `PanelContainer` wrapping TimeSyncPanel + TimeRangeBar in a QVBoxLayout |
| `SciQLop/components/plotting/ui/time_sync_panel.py` | **Modify** — no changes needed (kept as-is) |
| `SciQLop/core/ui/mainwindow.py` | **Modify** — `new_native_plot_panel` creates PanelContainer; update `plot_panels`/`plot_panel`/`remove_plot_panel` to unwrap containers |
| `tests/test_time_range_bar.py` | **Create** — unit tests for TimeRangeBar logic |
| `tests/test_panel_container.py` | **Create** — integration tests for PanelContainer wiring |

---

### Task 1: TimeRangeBar widget

**Files:**
- Create: `SciQLop/components/plotting/ui/time_range_bar.py`
- Create: `tests/test_time_range_bar.py`

The `TimeRangeBar` is a compact QWidget with horizontal layout:
`[start_datetime] [duration_combo ▾] [|◀] [◀] [▶] [▶|]`

Duration presets: `1m` (60s), `1h` (3600s), `12h` (43200s), `1d` (86400s), `7d` (604800s).

When the user changes start or duration, the bar emits `range_changed(TimeRange)` with `TimeRange(start, start + duration_seconds)`.
When external code calls `set_range(TimeRange)`, the bar updates its start picker and selects the closest matching duration preset. **Known limitation:** if the user zooms to a non-preset duration (e.g. 37 minutes via mouse), the bar snaps to the closest preset for display and subsequent navigation. This is acceptable for v1 — a "custom" combo entry can be added later if needed.

Navigation: `[◀]`/`[▶]` shift start by ±1 duration. `[|◀]`/`[▶|]` shift by ±5 durations.

- [ ] **Step 1: Write failing tests for TimeRangeBar**

```python
# tests/test_time_range_bar.py
import pytest
from datetime import datetime, timezone
from PySide6.QtCore import QDateTime, Qt

from SciQLop.core import TimeRange


@pytest.fixture
def bar(qtbot):
    from SciQLop.components.plotting.ui.time_range_bar import TimeRangeBar
    w = TimeRangeBar()
    qtbot.addWidget(w)
    return w


DURATIONS = {"1m": 60, "1h": 3600, "12h": 43200, "1d": 86400, "7d": 604800}


def test_initial_state(bar):
    """Bar should have a valid range on construction."""
    tr = bar.time_range
    assert tr.stop() - tr.start() > 0


def test_duration_presets_available(bar):
    """All expected durations should be in the combo box."""
    items = [bar._duration_combo.itemText(i) for i in range(bar._duration_combo.count())]
    assert items == ["1m", "1h", "12h", "1d", "7d"]


def test_set_range_updates_widgets(bar):
    """set_range should update the start picker and keep closest duration."""
    start = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    bar.set_range(TimeRange(start, start + 3600))
    assert abs(bar.time_range.start() - start) < 1
    assert abs(bar.time_range.stop() - bar.time_range.start() - 3600) < 1


def test_set_range_selects_closest_duration(bar):
    """set_range with exact duration match should select that preset."""
    start = 1_000_000.0
    bar.set_range(TimeRange(start, start + 86400))
    assert bar._duration_combo.currentText() == "1d"


def test_step_forward(bar, qtbot):
    """Clicking forward should shift start by one duration."""
    start = 1_000_000.0
    bar.set_range(TimeRange(start, start + 3600))
    with qtbot.waitSignal(bar.range_changed, timeout=1000):
        bar._forward_btn.click()
    assert abs(bar.time_range.start() - (start + 3600)) < 1


def test_step_backward(bar, qtbot):
    """Clicking backward should shift start by minus one duration."""
    start = 1_000_000.0
    bar.set_range(TimeRange(start, start + 3600))
    with qtbot.waitSignal(bar.range_changed, timeout=1000):
        bar._backward_btn.click()
    assert abs(bar.time_range.start() - (start - 3600)) < 1


def test_fast_forward(bar, qtbot):
    """Fast forward shifts by 5 durations."""
    start = 1_000_000.0
    bar.set_range(TimeRange(start, start + 3600))
    with qtbot.waitSignal(bar.range_changed, timeout=1000):
        bar._fast_forward_btn.click()
    assert abs(bar.time_range.start() - (start + 5 * 3600)) < 1


def test_fast_backward(bar, qtbot):
    """Fast backward shifts by -5 durations."""
    start = 1_000_000.0
    bar.set_range(TimeRange(start, start + 3600))
    with qtbot.waitSignal(bar.range_changed, timeout=1000):
        bar._fast_backward_btn.click()
    assert abs(bar.time_range.start() - (start - 5 * 3600)) < 1


def test_changing_duration_updates_range(bar, qtbot):
    """Changing duration combo should emit range_changed with new stop."""
    start = 1_000_000.0
    bar.set_range(TimeRange(start, start + 3600))
    with qtbot.waitSignal(bar.range_changed, timeout=1000):
        bar._duration_combo.setCurrentText("1d")
    assert abs(bar.time_range.stop() - bar.time_range.start() - 86400) < 1


def test_no_signal_during_set_range(bar, qtbot):
    """set_range should not emit range_changed (avoids feedback loops)."""
    signals = []
    bar.range_changed.connect(lambda tr: signals.append(tr))
    bar.set_range(TimeRange(1_000_000.0, 1_000_000.0 + 3600))
    assert len(signals) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_time_range_bar.py -v
```

Expected: ImportError (module doesn't exist yet).

- [ ] **Step 3: Implement TimeRangeBar**

```python
# SciQLop/components/plotting/ui/time_range_bar.py
from PySide6.QtCore import Qt, Signal, QDateTime
from PySide6.QtWidgets import QWidget, QHBoxLayout, QDateTimeEdit, QComboBox, QPushButton

from SciQLop.core import TimeRange

DURATION_PRESETS = [("1m", 60), ("1h", 3600), ("12h", 43200), ("1d", 86400), ("7d", 604800)]


def _make_start_picker(parent):
    w = QDateTimeEdit(parent)
    w.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
    w.setCalendarPopup(True)
    w.setTimeSpec(Qt.TimeSpec.UTC)
    return w


def _make_duration_combo(parent):
    w = QComboBox(parent)
    for label, _ in DURATION_PRESETS:
        w.addItem(label)
    w.setCurrentText("1d")
    return w


def _make_nav_button(text, parent):
    b = QPushButton(text, parent)
    b.setFixedWidth(32)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return b


def _closest_duration_index(seconds):
    return min(range(len(DURATION_PRESETS)), key=lambda i: abs(DURATION_PRESETS[i][1] - seconds))


class TimeRangeBar(QWidget):
    range_changed = Signal(TimeRange)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suppressing = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)

        self._start_picker = _make_start_picker(self)
        self._duration_combo = _make_duration_combo(self)
        self._fast_backward_btn = _make_nav_button("|◀", self)
        self._backward_btn = _make_nav_button("◀", self)
        self._forward_btn = _make_nav_button("▶", self)
        self._fast_forward_btn = _make_nav_button("▶|", self)

        layout.addWidget(self._fast_backward_btn)
        layout.addWidget(self._backward_btn)
        layout.addWidget(self._start_picker, 1)
        layout.addWidget(self._duration_combo)
        layout.addWidget(self._forward_btn)
        layout.addWidget(self._fast_forward_btn)

        self._start_picker.dateTimeChanged.connect(self._on_user_changed)
        self._duration_combo.currentTextChanged.connect(self._on_user_changed)
        self._backward_btn.clicked.connect(lambda: self.step(-1))
        self._forward_btn.clicked.connect(lambda: self.step(1))
        self._fast_backward_btn.clicked.connect(lambda: self.step(-5))
        self._fast_forward_btn.clicked.connect(lambda: self.step(5))

    @property
    def _duration_seconds(self):
        return dict(DURATION_PRESETS).get(self._duration_combo.currentText(), 86400)

    @property
    def time_range(self):
        start = self._start_picker.dateTime().toMSecsSinceEpoch() / 1000.0
        return TimeRange(start, start + self._duration_seconds)

    def set_range(self, tr: TimeRange):
        self._suppressing = True
        try:
            self._start_picker.setDateTime(tr.datetime_start())
            dt = tr.stop() - tr.start()
            self._duration_combo.setCurrentIndex(_closest_duration_index(dt))
        finally:
            self._suppressing = False

    def _on_user_changed(self, _=None):
        if not self._suppressing:
            self.range_changed.emit(self.time_range)

    def step(self, n):
        start = self._start_picker.dateTime().toMSecsSinceEpoch() / 1000.0
        new_start = start + n * self._duration_seconds
        self._suppressing = True
        try:
            self._start_picker.setDateTime(
                QDateTime.fromMSecsSinceEpoch(int(new_start * 1000), Qt.TimeSpec.UTC)
            )
        finally:
            self._suppressing = False
        self.range_changed.emit(self.time_range)
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
uv run pytest tests/test_time_range_bar.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/ui/time_range_bar.py tests/test_time_range_bar.py
git commit -m "feat: add TimeRangeBar widget with start+duration input model"
```

---

### Task 2: PanelContainer wrapper

**Files:**
- Create: `SciQLop/components/plotting/ui/panel_container.py`
- Create: `tests/test_panel_container.py`

`PanelContainer` is a thin QWidget with a QVBoxLayout holding `[TimeSyncPanel (stretch=1), TimeRangeBar (stretch=0)]`. It wires:
- `panel.time_range_changed` → `bar.set_range` (panel → bar sync)
- `bar.range_changed` → `panel.set_time_axis_range` (bar → panel sync)

It exposes `.panel` for code that needs the underlying `TimeSyncPanel`.

- [ ] **Step 1: Write failing tests for PanelContainer**

```python
# tests/test_panel_container.py
import pytest
from SciQLop.core import TimeRange


@pytest.fixture
def container(qtbot):
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    panel = TimeSyncPanel(name="TestPanel", time_range=TimeRange(1_000_000.0, 1_086_400.0))
    c = PanelContainer(panel)
    qtbot.addWidget(c)
    return c


def test_container_has_panel(container):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    assert isinstance(container.panel, TimeSyncPanel)


def test_bar_reflects_panel_range(container):
    """Bar should be initialized with the panel's current time range."""
    tr = container.panel.time_range
    bar_tr = container.time_range_bar.time_range
    assert abs(bar_tr.start() - tr.start()) < 1
    assert abs(bar_tr.stop() - tr.stop()) < 2


def test_window_title_delegates_to_panel(container):
    """Container should use the panel's window title (for dock tab label)."""
    assert container.windowTitle() == container.panel.windowTitle()


def test_bar_change_updates_panel(container):
    """Changing the bar should propagate to the panel's time range."""
    start = 2_000_000.0
    container.time_range_bar.range_changed.emit(TimeRange(start, start + 3600))
    tr = container.panel.time_range
    assert abs(tr.start() - start) < 1


def test_panel_change_updates_bar(container):
    """Changing the panel's time range should update the bar (no signal loop)."""
    start = 3_000_000.0
    container.panel.time_range = TimeRange(start, start + 86400)
    bar_tr = container.time_range_bar.time_range
    assert abs(bar_tr.start() - start) < 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_panel_container.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement PanelContainer**

```python
# SciQLop/components/plotting/ui/panel_container.py
from PySide6.QtWidgets import QWidget, QVBoxLayout

from SciQLop.components.plotting.ui.time_range_bar import TimeRangeBar
from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
from SciQLop.core import TimeRange


class PanelContainer(QWidget):

    def __init__(self, panel: TimeSyncPanel, parent=None):
        super().__init__(parent)
        self.panel = panel
        self.time_range_bar = TimeRangeBar(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(panel, 1)
        layout.addWidget(self.time_range_bar, 0)

        self.setWindowTitle(panel.windowTitle())
        self.setObjectName(panel.objectName())

        self.time_range_bar.set_range(panel.time_range)
        panel.time_range_changed.connect(self._on_panel_range_changed)
        self.time_range_bar.range_changed.connect(self._on_bar_range_changed)

    def _on_panel_range_changed(self, tr: TimeRange):
        self.time_range_bar.set_range(tr)

    def _on_bar_range_changed(self, tr: TimeRange):
        self.panel.set_time_axis_range(tr)
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
uv run pytest tests/test_panel_container.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/ui/panel_container.py tests/test_panel_container.py
git commit -m "feat: add PanelContainer wrapping TimeSyncPanel with TimeRangeBar"
```

---

### Task 3: Wire PanelContainer into MainWindow

**Files:**
- Modify: `SciQLop/core/ui/mainwindow.py` (lines 322–349)

Three changes:
1. `new_native_plot_panel` wraps panel in `PanelContainer` before docking
2. `plot_panels()` looks for `PanelContainer` and unwraps to get panel name
3. `plot_panel()` looks for `PanelContainer` and returns its `.panel`

- [ ] **Step 1: Update `new_native_plot_panel` to use PanelContainer**

In `mainwindow.py`, change `new_native_plot_panel`:

```python
# Before:
def new_native_plot_panel(self, name: Optional[str] = None) -> TimeSyncPanel:
    panel = TimeSyncPanel(parent=None, name=auto_name(base="Panel", name=name),
                          time_range=self._dt_range_action.range)
    self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, panel, delete_on_close=True)
    self.panel_added.emit(panel)
    self._notify_panels_list_changed()
    panel.destroyed.connect(self._notify_panels_list_changed)
    return panel

# After:
def new_native_plot_panel(self, name: Optional[str] = None) -> TimeSyncPanel:
    panel = TimeSyncPanel(parent=None, name=auto_name(base="Panel", name=name),
                          time_range=self._dt_range_action.range)
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    container = PanelContainer(panel)
    self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, container, delete_on_close=True)
    self.panel_added.emit(panel)
    self._notify_panels_list_changed()
    panel.destroyed.connect(self._notify_panels_list_changed)
    return panel
```

- [ ] **Step 2: Add a helper to extract panel from dock widget**

Add a module-level helper near the top of `mainwindow.py`:

```python
from SciQLop.components.plotting.ui.panel_container import PanelContainer

def _extract_panel(dock_widget):
    """Get the TimeSyncPanel from a dock widget, whether wrapped in PanelContainer or not."""
    w = dock_widget.widget()
    if isinstance(w, PanelContainer):
        return w.panel
    if isinstance(w, SciQLopMultiPlotPanel):
        return w
    return None
```

- [ ] **Step 3: Update `plot_panels` and `plot_panel`**

```python
# Before:
def plot_panels(self) -> List[str]:
    return list(
        map(lambda dw: dw.widget().name,
            filter(lambda dw: isinstance(dw.widget(), SciQLopMultiPlotPanel), self.dock_manager.dockWidgets())))

def plot_panel(self, name: str) -> Union[TimeSyncPanel, None]:
    widget: QtAds.CDockWidget = self.dock_manager.findDockWidget(name)
    if widget and isinstance(widget.widget(), SciQLopMultiPlotPanel):
        return widget.widget()
    return None

# After:
def plot_panels(self) -> List[str]:
    panels = [_extract_panel(dw) for dw in self.dock_manager.dockWidgets()]
    return [p.name for p in panels if p is not None]

def plot_panel(self, name: str) -> Union[TimeSyncPanel, None]:
    dw: QtAds.CDockWidget = self.dock_manager.findDockWidget(name)
    if dw:
        return _extract_panel(dw)
    return None
```

- [ ] **Step 4: Update `remove_native_plot_panel` and `remove_panel` to handle container**

After wrapping, `dw.takeWidget()` returns the `PanelContainer`, not the `TimeSyncPanel`. The panel is a child of the container, so deleting the container deletes the panel too. Update both methods:

```python
# Before:
def remove_native_plot_panel(self, panel: TimeSyncPanel):
    dw = self.dock_manager.findDockWidget(panel.name)
    if dw:
        dw.takeWidget()
        dw.closeDockWidget()
        panel.deleteLater()

def remove_panel(self, panel: Union[TimeSyncPanel, str]):
    log.debug(f"Removing panel {panel}")
    if isinstance(panel, str):
        panel = self.plot_panel(panel)
    if panel:
        dw = self.dock_manager.findDockWidget(panel.name)
        if dw:
            dw.takeWidget()
            dw.closeDockWidget()
            panel.deleteLater()
            self._notify_panels_list_changed()

# After:
def remove_native_plot_panel(self, panel: TimeSyncPanel):
    dw = self.dock_manager.findDockWidget(panel.name)
    if dw:
        container = dw.takeWidget()
        dw.closeDockWidget()
        container.deleteLater()  # deletes panel as child widget

def remove_panel(self, panel: Union[TimeSyncPanel, str]):
    log.debug(f"Removing panel {panel}")
    if isinstance(panel, str):
        panel = self.plot_panel(panel)
    if panel:
        dw = self.dock_manager.findDockWidget(panel.name)
        if dw:
            container = dw.takeWidget()
            dw.closeDockWidget()
            container.deleteLater()  # deletes panel as child widget
            self._notify_panels_list_changed()
```

- [ ] **Step 5: Run existing tests**

```bash
uv run pytest tests/ -v -x
```

Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/core/ui/mainwindow.py
git commit -m "feat: wrap TimeSyncPanel in PanelContainer for per-panel time range bar"
```

---

### Task 4: Remove global toolbar time range widget (optional — discuss first)

**Files:**
- Modify: `SciQLop/core/ui/mainwindow.py` (lines ~108-122)

The global `DateTimeRangeWidgetAction` is now redundant since each panel has its own bar. However, it's still used to set the **initial** time range of new panels. Options:

1. **Keep it** as "default range for new panels" — least disruptive
2. **Remove it** and use a sensible default (e.g., last 24h) — cleaner

- [ ] **Step 1: Discuss with user whether to remove or keep the global widget**

If removing: delete `_dt_range_action` creation/usage, use `TimeRange((now - 1day).timestamp(), now.timestamp())` as default for new panels.

If keeping: no changes needed — it serves as the "seed range" for new panels.

- [ ] **Step 2: Apply chosen approach and commit**

---

### Task 5: User API integration

**Files:**
- Modify: `SciQLop/user_api/plot/_panel.py`

Expose the time range bar's duration on the `PlotPanel` user API so Jupyter users can do `panel.duration = "1h"` or `panel.step_forward()`.

First, add a `_time_range_bar` attribute to `TimeSyncPanel` that `PanelContainer` sets, so we don't rely on fragile `parent()` traversal.

- [ ] **Step 1: Add `_time_range_bar` backref in PanelContainer**

In `panel_container.py`, after creating the bar, store a reference on the panel:

```python
# In PanelContainer.__init__, after self.time_range_bar = TimeRangeBar(self):
panel._time_range_bar = self.time_range_bar
```

- [ ] **Step 2: Add duration property and navigation to PlotPanel**

```python
# In PlotPanel class:

def _get_time_range_bar(self):
    return getattr(self._get_impl_or_raise(), '_time_range_bar', None)

@property
@on_main_thread
def duration(self) -> str:
    bar = self._get_time_range_bar()
    return bar.duration_text if bar else ""

@duration.setter
@on_main_thread
def duration(self, value: str):
    bar = self._get_time_range_bar()
    if bar:
        bar.duration_text = value

@on_main_thread
def step_forward(self, n: int = 1):
    bar = self._get_time_range_bar()
    if bar:
        bar.step(n)

@on_main_thread
def step_backward(self, n: int = 1):
    bar = self._get_time_range_bar()
    if bar:
        bar.step(-n)
```

Also add `duration_text` property to `TimeRangeBar`:

```python
# In TimeRangeBar class:

@property
def duration_text(self) -> str:
    return self._duration_combo.currentText()

@duration_text.setter
def duration_text(self, value: str):
    self._duration_combo.setCurrentText(value)
```

- [ ] **Step 2: Run all tests**

```bash
uv run pytest tests/ -v -x
```

- [ ] **Step 3: Commit**

```bash
git add SciQLop/user_api/plot/_panel.py
git commit -m "feat: expose duration and step navigation on PlotPanel user API"
```
