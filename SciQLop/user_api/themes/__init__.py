from typing import Literal

PaletteName = Literal["light", "dark", "neutral", "space"]

_VALID_THEMES = ["light", "dark", "neutral", "space"]


def apply_theme(name: PaletteName) -> None:
    """Switch the running SciQLop application to the named palette."""
    if name not in _VALID_THEMES:
        raise ValueError(f"unknown theme {name!r}; expected one of: {_VALID_THEMES}")
    from SciQLop.core.sciqlop_application import sciqlop_app
    sciqlop_app().apply_theme(name)


def current_theme() -> PaletteName:
    from SciQLop.core.sciqlop_application import sciqlop_app
    return sciqlop_app().current_theme()


def list_themes() -> list[PaletteName]:
    return list(_VALID_THEMES)
