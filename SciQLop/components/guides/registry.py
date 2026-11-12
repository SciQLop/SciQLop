"""Gesture guides: the sciqlop.guides extension point. `register_guide` contributes under the current
owner, so a withdrawn plugin's guides leave with it."""
from dataclasses import dataclass, field
from pathlib import Path

from SciQLop.core.extensions import ExtensionPoint, current_owner, declare
from SciQLop.core.name_follower import CORE_OWNER
from SciQLop.user_api.threading import on_main_thread

RESOURCES = Path(__file__).parent / "resources"


@dataclass(frozen=True)
class Guide:
    """`path`: the animated SVG. `contexts`: where the guide answers "how do I…?" - a `GuideButton(context)`
    opens the first guide registered for its context. `keywords` help the command palette find it."""
    id: str
    title: str
    caption: str
    path: Path
    keywords: tuple[str, ...] = field(default=())
    contexts: tuple[str, ...] = field(default=())


GUIDES = declare(ExtensionPoint("sciqlop.guides", Guide, what="guide", doc="Animated gesture guides by id."))


def register_guide(guide: Guide) -> None:
    """From any thread; the owner is the caller's, captured before the call moves to the main thread."""
    _contribute_guide(guide, current_owner())


@on_main_thread
def _contribute_guide(guide: Guide, owner: str) -> None:
    GUIDES.contribute(guide, owner=owner, replace=True)


def all_guides() -> list[Guide]:
    return GUIDES.list()


def get_guide(guide_id: str) -> Guide | None:
    return GUIDES.find(guide_id)


def guide_for(context: str) -> Guide | None:
    return next((g for g in all_guides() if context in g.contexts), None)


def _core(name: str, title: str, caption: str, keywords: tuple, contexts: tuple = ()) -> Guide:
    return Guide(f"sciqlop.{name}", title, caption, RESOURCES / f"{name}.svg", keywords, contexts)


# In the order a newcomer needs them.
CORE_GUIDES = (
    _core("new-panel-and-time-range", "Add a panel and set its time range",
          "Click the + button next to the panel tabs (or File › New plot panel). Under the new panel, "
          "type a start date and press Enter, then type a duration such as 3h.",
          ("panel", "time", "range", "date", "duration", "start"), ("panel.time_range",)),
    _core("plot-a-product", "Plot a product",
          "Open the Products pane with its icon on the left edge, then drag a product onto a panel. "
          "SciQLop downloads the data and plots it.",
          ("plot", "product", "data", "drag", "tree"), ("panel.empty",)),
    _core("drop-on-a-panel", "Choose where a dropped product goes",
          "The middle of a plot adds the product to it. Its top or bottom edge opens a blue placeholder; "
          "drop there for a new plot above or below.",
          ("drop", "drag", "new plot", "add", "above", "below"), ("panel.drop",)),
    _core("show-a-catalog", "Show a catalog on a panel",
          "Open the Catalogs pane with its icon on the left edge, then drag a catalog onto a panel. "
          "Its events are drawn as coloured spans on every plot.",
          ("catalog", "events", "overlay", "spans"), ("catalog.mode.view",)),
    _core("create-an-event", "Create an event",
          "Set the panel's Catalog mode to Edit. Hold Shift and click on a plot to start the event, move, "
          "then click again. It is added to the catalog named in \"Add to\".",
          ("catalog", "event", "new", "edit", "shift", "label"), ("catalog.mode.edit",)),
    _core("jump-to-an-event", "Go from event to event",
          "Set the panel's Catalog mode to Jump. Each event picked in the Catalogs pane's list moves the "
          "panel to it; with Zoom out at 2, the event fills half the panel.",
          ("catalog", "event", "jump", "navigate", "browse", "zoom"), ("catalog.mode.jump",)),
    _core("edit-an-event", "Resize, move or delete an event",
          "In Edit mode, drag an edge of an event to resize it or its middle to move it. Right-click it "
          "and choose Delete to remove it from its catalog.",
          ("catalog", "event", "edit", "resize", "move", "delete"), ("catalog.events.edit",)),
)


def register_core_guides() -> None:
    """Main thread only. Idempotent."""
    for guide in CORE_GUIDES:
        if guide.id not in GUIDES:
            GUIDES.contribute(guide, owner=CORE_OWNER)
