PaletteName = str  # a theme id: the core ones (see list_themes()) or one a plugin contributed


def apply_theme(name: PaletteName) -> None:
    """Switch the running SciQLop application to the named palette.

    Examples
    --------
    >>> apply_theme("dark")
    """
    from SciQLop.components.theming.themes import THEMES

    if name not in THEMES:
        raise ValueError(f"unknown theme {name!r}; expected one of: {THEMES.keys()}")
    from SciQLop.core.sciqlop_application import sciqlop_app

    sciqlop_app().apply_theme(name)


def current_theme() -> PaletteName:
    """Return the currently active palette name.

    Examples
    --------
    >>> current_theme()
    'dark'
    """
    from SciQLop.core.sciqlop_application import sciqlop_app

    return sciqlop_app().current_theme()


def list_themes() -> list[PaletteName]:
    """Return the list of available palette names.

    Examples
    --------
    >>> list_themes()
    ['light', 'dark', 'neutral', 'space', 'github_light', 'nord_light',
     'catppuccin_latte', 'high_contrast_light']
    """
    from SciQLop.components.theming.themes import THEMES

    return THEMES.keys()
