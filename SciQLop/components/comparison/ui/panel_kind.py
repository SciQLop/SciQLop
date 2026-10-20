"""The core Comparison panel kind, with the core dimensions and views it draws, and its agent tools."""
from SciQLop.components.agents.tools.comparison_tool import COMPARISON_TOOLS
from SciQLop.components.agents.tools.contributed import AGENT_TOOLS
from SciQLop.components.comparison.backend.dimensions import contribute_core_dimensions
from SciQLop.components.comparison.backend.views import COMPARISON_VIEWS, ComparisonView
from SciQLop.components.comparison.ui import difference_view, overlay_view
from SciQLop.core.panel_kinds import PANEL_KINDS, PanelKind

COMPARISON_PANEL = "sciqlop.comparison"

CORE_VIEWS = [
    ComparisonView("overlay", "Overlay", overlay_view.applies_overlay, overlay_view.build_overlay, order=0),
    ComparisonView("difference", "Difference", difference_view.applies_difference, difference_view.build_difference,
                   default_options=dict(difference_view.default_options), order=10,
                   option_choices={"operation": ("difference", "ratio", "log_ratio"), "method": ("linear", "nearest")}),
]


def _create(name: str, config: dict):
    from SciQLop.components.comparison.backend.model import Comparison
    from SciQLop.components.comparison.ui.panel import ComparisonPanel
    from SciQLop.components.comparison.ui.wizard import edit_comparison
    panel = ComparisonPanel(name, Comparison.model_validate(config))
    panel.edit_requested.connect(lambda: edit_comparison(panel))
    return panel


def _to_config(widget) -> dict:
    return widget.comparison.model_dump(mode="json")


contribute_core_dimensions()
for _view in CORE_VIEWS:
    COMPARISON_VIEWS.contribute(_view, owner="sciqlop", replace=True)
for _tool in COMPARISON_TOOLS:
    AGENT_TOOLS.contribute(_tool, owner="sciqlop", replace=True)
PANEL_KINDS.contribute(PanelKind(COMPARISON_PANEL, "Comparison", create=_create, to_config=_to_config,
                                 icon="plot_panel", in_new_menu=False), owner="sciqlop")
