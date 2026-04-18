from SciQLopPlots import (SciQLopOverlay as _SciQLopOverlay,
                          OverlayLevel as _OverlayLevel,
                          OverlaySizeMode as _OverlaySizeMode,
                          OverlayPosition as _OverlayPosition)

from .enums import OverlayLevel, OverlaySizeMode, OverlayPosition
from .._annotations import experimental_api
from ._thread_safety import on_main_thread

__all__ = ['Overlay']


def _to_sqp_level(level: OverlayLevel) -> _OverlayLevel:
    return _OverlayLevel(level.value)


def _from_sqp_level(level: _OverlayLevel) -> OverlayLevel:
    return OverlayLevel(level.value)


def _to_sqp_size_mode(size_mode: OverlaySizeMode) -> _OverlaySizeMode:
    return _OverlaySizeMode(size_mode.value)


def _from_sqp_size_mode(size_mode: _OverlaySizeMode) -> OverlaySizeMode:
    return OverlaySizeMode(size_mode.value)


def _to_sqp_position(position: OverlayPosition) -> _OverlayPosition:
    return _OverlayPosition(position.value)


def _from_sqp_position(position: _OverlayPosition) -> OverlayPosition:
    return OverlayPosition(position.value)


class Overlay:
    """A class wrapping the in-canvas message overlay attached to a plot.

    Use `plot.overlay` to access it. The overlay can show informational, warning,
    or error messages at a chosen position with a chosen sizing behavior, and can
    be made user-collapsible.
    """

    def __init__(self, impl: _SciQLopOverlay):
        self._impl = impl

    @experimental_api()
    @on_main_thread
    def show(self, text: str, *,
             level: OverlayLevel = OverlayLevel.Info,
             size_mode: OverlaySizeMode = OverlaySizeMode.FitContent,
             position: OverlayPosition = OverlayPosition.Top) -> None:
        """Show a message in the overlay.

        Parameters
        ----------
        text : str
            The message to display.
        level : OverlayLevel
            Severity level (Info, Warning, Error).
        size_mode : OverlaySizeMode
            Sizing behavior (Compact, FitContent, FullWidget).
        position : OverlayPosition
            Anchor position (Top, Bottom, Left, Right).
        """
        self._impl.show_message(text,
                                _to_sqp_level(level),
                                _to_sqp_size_mode(size_mode),
                                _to_sqp_position(position))

    @experimental_api()
    @on_main_thread
    def clear(self) -> None:
        """Clear the overlay message."""
        self._impl.clear_message()

    @property
    @on_main_thread
    def text(self) -> str:
        return self._impl.text()

    @property
    @on_main_thread
    def level(self) -> OverlayLevel:
        return _from_sqp_level(self._impl.level())

    @property
    @on_main_thread
    def position(self) -> OverlayPosition:
        return _from_sqp_position(self._impl.position())

    @property
    @on_main_thread
    def size_mode(self) -> OverlaySizeMode:
        return _from_sqp_size_mode(self._impl.size_mode())

    @property
    @on_main_thread
    def collapsible(self) -> bool:
        return self._impl.is_collapsible()

    @collapsible.setter
    @on_main_thread
    def collapsible(self, v: bool) -> None:
        self._impl.set_collapsible(v)

    @property
    @on_main_thread
    def collapsed(self) -> bool:
        return self._impl.is_collapsed()

    @collapsed.setter
    @on_main_thread
    def collapsed(self, v: bool) -> None:
        self._impl.set_collapsed(v)

    @property
    @on_main_thread
    def opacity(self) -> float:
        return self._impl.opacity()

    @opacity.setter
    @on_main_thread
    def opacity(self, v: float) -> None:
        self._impl.set_opacity(v)

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("Overlay(...)")
        else:
            p.text(f"Overlay({self._impl})")
