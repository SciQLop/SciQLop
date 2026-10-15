"""IPython magics: the sciqlop.magics extension point and the code that applies it to a shell."""
from __future__ import annotations

import weakref
from dataclasses import dataclass
from functools import partial
from typing import Callable, Optional

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.extensions import ExtensionPoint, declare

log = getLogger(__name__)

LINE, CELL, LINE_CELL = "line", "cell", "line_cell"
CORE_OWNER = "sciqlop"


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


def _by_precedence(candidates: list[Magic]) -> list[Magic]:
    """Core magics first, then contribution order (the sort is stable)."""
    return sorted(candidates, key=lambda m: MAGICS.owner_of(m.id) != CORE_OWNER)


def _winners(candidates: list[Magic]) -> list[Magic]:
    taken: set[str] = set()
    winners = []
    for magic in _by_precedence(candidates):
        if not taken & set(_kinds(magic)):
            winners.append(magic)
            taken |= set(_kinds(magic))
    return winners


def _core_magics() -> tuple[Magic, ...]:
    from SciQLop.user_api.virtual_products.magic import vp_magic
    from SciQLop.user_api.layers.magic import layer_magic
    from SciQLop.user_api.magics.plot_magic import plot_magic
    from SciQLop.user_api.magics.timerange_magic import timerange_magic
    from SciQLop.user_api.magics.install_magic import install_magic
    from SciQLop.user_api.magics.workspace_magic import workspace_magic
    from SciQLop.user_api.magics.job_magic import job_magic
    from SciQLop.user_api.magics.completions import (
        _match_plot, _match_timerange, _match_vp, _match_workspace, _match_job,
    )
    return (
        Magic("sciqlop.vp", "vp", CELL, vp_magic, _match_vp),
        Magic("sciqlop.layer", "layer", CELL, layer_magic),
        Magic("sciqlop.plot", "plot", LINE, plot_magic, _match_plot),
        Magic("sciqlop.timerange", "timerange", LINE, timerange_magic, _match_timerange),
        Magic("sciqlop.install", "install", LINE, install_magic),
        Magic("sciqlop.workspace", "workspace", LINE, workspace_magic, _match_workspace),
        Magic("sciqlop.job", "job", LINE, job_magic, _match_job),
    )


CORE_MAGICS = _core_magics()


def contribute_core_magics() -> None:
    """Idempotent. Called by prepare_extension_points and register_all_magics, whichever runs first."""
    for magic in CORE_MAGICS:
        if magic.id not in MAGICS:
            MAGICS.contribute(magic, owner=CORE_OWNER)


# Keyed weakly: a shell nobody references any more takes its state with it. Value: applied magics by id.
_APPLIED: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _apply(shell, magic: Magic) -> None:
    shell.register_magic_function(magic.function, magic_kind=magic.kind, magic_name=magic.name)
    matchers = shell.Completer.custom_matchers
    if magic.completer is not None and magic.completer not in matchers:
        matchers.append(magic.completer)
    _APPLIED[shell][magic.id] = magic


def _unapply(shell, magic: Magic) -> None:
    """Never clobbers the user: a registered function that is not the contributed one stays."""
    registered = shell.magics_manager.magics
    for kind in _kinds(magic):
        if registered[kind].get(magic.name) is magic.function:
            del registered[kind][magic.name]
    matchers = shell.Completer.custom_matchers
    if magic.completer in matchers:
        matchers.remove(magic.completer)
    _APPLIED[shell].pop(magic.id, None)


def _settle(shell, name: str) -> tuple[list[Magic], list[Magic]]:
    """Make the shell match the winners for ``name``. Returns (withdrawn, ignored)."""
    candidates = MAGICS.list(name=name)
    winners = _winners(candidates)
    applied = [m for m in _APPLIED[shell].values() if m.name == name]
    withdrawn = [m for m in applied if not any(m is w for w in winners)]
    for magic in withdrawn:
        _unapply(shell, magic)
    for magic in winners:
        if _APPLIED[shell].get(magic.id) is not magic:
            _apply(shell, magic)
    return withdrawn, [m for m in candidates if not any(m is w for w in winners)]


def _log_ignored(magic: Magic, winners_of_name: list[Magic]) -> None:
    holder = next(w for w in winners_of_name if set(_kinds(w)) & set(_kinds(magic)))
    log.error(f"magic %{magic.name} from {magic.id} ignored: already provided by {holder.id}")


def _report(name: str, ignored: list[Magic]) -> None:
    winners = _winners(MAGICS.list(name=name))
    for magic in ignored:
        _log_ignored(magic, winners)


def _followed(shell_ref):
    shell = shell_ref()
    return shell if shell in _APPLIED else None


def _on_added(shell_ref, magic: Magic) -> None:
    shell = _followed(shell_ref)
    if shell is None:
        return
    previous = _APPLIED[shell].get(magic.id)
    if previous is not None:
        _unapply(shell, previous)
    withdrawn, ignored = _settle(shell, magic.name)
    _report(magic.name, [m for m in ignored if m.id == magic.id or any(m.id == w.id for w in withdrawn)])


def _on_removed(shell_ref, magic: Magic) -> None:
    shell = _followed(shell_ref)
    if shell is None:
        return
    applied = _APPLIED[shell].get(magic.id)
    if applied is not None:
        _unapply(shell, applied)
    _settle(shell, magic.name)


def _replay(shell) -> None:
    for name in dict.fromkeys(m.name for m in MAGICS.list()):
        _, ignored = _settle(shell, name)
        _report(name, ignored)


def follow_magics(shell) -> None:
    """Apply every contributed magic to ``shell`` and follow the extension point. Main thread; idempotent per shell."""
    if shell in _APPLIED:
        return
    _APPLIED[shell] = {}
    _replay(shell)
    shell_ref = weakref.ref(shell)
    MAGICS.signals.added.connect(partial(_on_added, shell_ref))
    MAGICS.signals.removed.connect(partial(_on_removed, shell_ref))


def unfollow_magics(shell) -> None:
    """Stop applying contributions to ``shell``; what it already has stays registered."""
    _APPLIED.pop(shell, None)
