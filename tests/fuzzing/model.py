from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AppModel:
    panels: list[str] = field(default_factory=list)
    products_on: dict[str, list[str]] = field(default_factory=dict)
    time_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)

    @property
    def panel_count(self) -> int:
        return len(self.panels)

    @property
    def has_panels(self) -> bool:
        return self.panel_count > 0

    def remove_panel(self, name: str):
        self.panels.remove(name)
        self.products_on.pop(name, None)
        self.time_ranges.pop(name, None)

    def reset(self):
        self.panels.clear()
        self.products_on.clear()
        self.time_ranges.clear()
