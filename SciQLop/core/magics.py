"""IPython magics: the sciqlop.magics extension point and the code that applies it to a shell."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.extensions import ExtensionPoint, declare
from SciQLop.core.name_follower import Follower

log = getLogger(__name__)

LINE, CELL, LINE_CELL = "line", "cell", "line_cell"


@dataclass(frozen=True)
class Magic:
    id: str
    name: str                              # without the leading %
    kind: str                              # LINE, CELL or LINE_CELL
    function: Callable
    completer: Optional[Callable] = None   # an IPython matcher API v2 function

    def __post_init__(self):
        if self.kind not in (LINE, CELL, LINE_CELL):
            raise ValueError(f"magic {self.id}: kind must be line, cell or line_cell, got {self.kind!r}")
        if not self.name.isidentifier():
            raise ValueError(f"magic {self.id}: name must be a valid identifier without %, got {self.name!r}")


MAGICS = declare(ExtensionPoint("sciqlop.magics", Magic, what="magic",
                                doc="IPython magics: name, kind, function and an optional tab completer."))


def _kinds(magic: Magic) -> tuple[str, ...]:
    return (LINE, CELL) if magic.kind == LINE_CELL else (magic.kind,)


def _may_register(shell, magic: Magic, replaced: tuple) -> bool:
    registered = shell.magics_manager.magics
    return all(registered[kind].get(magic.name) in (None, *(p.function for p in replaced)) for kind in _kinds(magic))


def _apply(shell, magic: Magic, replaced: tuple) -> None:
    if replaced and not _may_register(shell, magic, replaced):
        log.warning(f"magic %{magic.name} from {magic.id} not applied: the user registered another")
        return
    shell.register_magic_function(magic.function, magic_kind=magic.kind, magic_name=magic.name)
    matchers = shell.Completer.custom_matchers
    if magic.completer is not None and magic.completer not in matchers:
        matchers.append(magic.completer)


def _unapply(shell, magic: Magic) -> None:
    """Never clobbers the user: a registered function that is not the contributed one stays."""
    registered = shell.magics_manager.magics
    for kind in _kinds(magic):
        if registered[kind].get(magic.name) is magic.function:
            del registered[kind][magic.name]
    matchers = shell.Completer.custom_matchers
    if magic.completer in matchers:
        matchers.remove(magic.completer)


_FOLLOWER = Follower(MAGICS, log, lambda m: f"magic %{m.name}", _kinds, _apply, _unapply)


def follow_magics(shell, post: Optional[Callable] = None) -> None:
    """Apply every contributed magic to ``shell`` and follow the extension point. Main thread; idempotent per shell.

    ``post(function, *args)`` runs ``function`` where the shell's tables may be touched
    (the kernel thread); by default it runs immediately.
    """
    _FOLLOWER.follow(shell, post)


def unfollow_magics(shell) -> None:
    """Stop applying contributions to ``shell``; what it already has stays registered."""
    _FOLLOWER.unfollow(shell)
