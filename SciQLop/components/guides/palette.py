"""Every guide is a command of the palette, "Guide: <title>", so typing "event" or "drop" finds it."""
from SciQLop.components.command_palette.backend.registry import COMMANDS, PaletteCommand

from .registry import GUIDES, Guide


def _command_id(guide_id: str) -> str:
    return f"guides.{guide_id}"


def _show(guide_id: str) -> None:
    from SciQLop.core.sciqlop_application import sciqlop_app
    from .ui import show_guides
    show_guides(sciqlop_app().main_window, guide_id)


def _add(guide: Guide) -> None:
    COMMANDS.contribute(PaletteCommand(id=_command_id(guide.id), name=f"Guide: {guide.title}", description=guide.caption,
                                       callback=lambda guide_id=guide.id: _show(guide_id),
                                       keywords=["how", "help", "guide", *guide.keywords]),
                        owner=GUIDES.owner_of(guide.id), replace=True)


def _remove(guide: Guide) -> None:
    if _command_id(guide.id) in COMMANDS:
        COMMANDS.remove(_command_id(guide.id))


def follow_guides() -> None:
    """Main thread only. Idempotent: the commands of the guides present now and of those added later."""
    if getattr(follow_guides, "_following", False):
        return
    follow_guides._following = True
    GUIDES.signals.added.connect(_add)
    GUIDES.signals.removed.connect(_remove)
    for guide in GUIDES.list():
        _add(guide)
