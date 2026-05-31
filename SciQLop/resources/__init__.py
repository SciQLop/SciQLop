"""SciQLop shared resources (splash, drag-drop background).

These ship as package data and are loaded from disk via :func:`resource_path`.
Small, rarely-changing images are deliberately *not* baked into a generated
Qt-resource module: ``pyside6-rcc`` embeds them as a giant Python byte literal,
which turned every image change into a 100k+ line diff and doubled storage in
the ``.py``/``.pyc``. Qt icons come from SciQLopPlots' own resource bundle, not
here.
"""
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def resource_path(name: str) -> str:
    """Absolute filesystem path to a bundled resource (e.g. ``"splash.png"``)."""
    return str(_HERE / name)
