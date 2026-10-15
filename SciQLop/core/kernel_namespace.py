"""Kernel namespace: the sciqlop.kernel_namespace extension point and the code that applies it to a shell."""
from __future__ import annotations

import weakref
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Optional

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.extensions import ExtensionPoint, declare

log = getLogger(__name__)

CORE_OWNER = "sciqlop"


@dataclass(frozen=True, eq=False)
class NamespaceEntry:
    id: str
    name: str
    value: Any

    def __post_init__(self):
        if not self.name.isidentifier():
            raise ValueError(f"namespace entry {self.id}: name must be a valid identifier, got {self.name!r}")


KERNEL_NAMESPACE = declare(ExtensionPoint(
    "sciqlop.kernel_namespace", NamespaceEntry, what="kernel name",
    doc="Names available in the IPython kernel: id, name and value."))


def contribute_name(id: str, name: str, value, *, owner: str = CORE_OWNER, replace: bool = False) -> None:
    KERNEL_NAMESPACE.contribute(NamespaceEntry(id, name, value), owner=owner, replace=replace)


# Keyed weakly: a shell nobody references any more takes its state with it.
# Value: (applied entries by id, function that runs a callable on the kernel thread).
_APPLIED: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _run_now(function: Callable, *args) -> None:
    function(*args)


def _push(shell, entry: NamespaceEntry) -> None:
    shell.push({entry.name: entry.value})


def _pop_if_unchanged(shell, entry: NamespaceEntry) -> None:
    """Never clobbers the user: a name rebound since the push stays."""
    if shell.user_ns.get(entry.name) is entry.value:
        del shell.user_ns[entry.name]


def _apply(shell, entry: NamespaceEntry) -> None:
    applied, post = _APPLIED[shell]
    post(_push, shell, entry)
    applied[entry.id] = entry


def _unapply(shell, entry: NamespaceEntry) -> None:
    applied, post = _APPLIED[shell]
    post(_pop_if_unchanged, shell, entry)
    applied.pop(entry.id, None)


def _by_precedence(candidates: list[NamespaceEntry]) -> list[NamespaceEntry]:
    """Core entries first, then contribution order (the sort is stable)."""
    return sorted(candidates, key=lambda e: KERNEL_NAMESPACE.owner_of(e.id) != CORE_OWNER)


def _settle(shell, name: str) -> tuple[list[NamespaceEntry], list[NamespaceEntry]]:
    """Make the shell match the holder of ``name``. Returns (withdrawn, ignored)."""
    candidates = _by_precedence(KERNEL_NAMESPACE.list(name=name))
    holder = candidates[:1]
    applied = [e for e in _APPLIED[shell][0].values() if e.name == name]
    withdrawn = [e for e in applied if not any(e is h for h in holder)]
    for entry in withdrawn:
        _unapply(shell, entry)
    for entry in holder:
        if _APPLIED[shell][0].get(entry.id) is not entry:
            _apply(shell, entry)
    return withdrawn, candidates[1:]


def _report(name: str, ignored: list[NamespaceEntry]) -> None:
    holder = _by_precedence(KERNEL_NAMESPACE.list(name=name))[0]
    for entry in ignored:
        log.error(f"kernel name {name} from {entry.id} ignored: already provided by {holder.id}")


def _followed(shell_ref):
    shell = shell_ref()
    return shell if shell in _APPLIED else None


def _on_added(shell_ref, entry: NamespaceEntry) -> None:
    shell = _followed(shell_ref)
    if shell is None:
        return
    previous = _APPLIED[shell][0].get(entry.id)
    if previous is not None:
        _unapply(shell, previous)
    withdrawn, ignored = _settle(shell, entry.name)
    _report(entry.name, [e for e in ignored if e.id == entry.id or any(e.id == w.id for w in withdrawn)])


def _on_removed(shell_ref, entry: NamespaceEntry) -> None:
    shell = _followed(shell_ref)
    if shell is None:
        return
    applied = _APPLIED[shell][0].get(entry.id)
    if applied is not None:
        _unapply(shell, applied)
    _settle(shell, entry.name)


def _replay(shell) -> None:
    for name in dict.fromkeys(e.name for e in KERNEL_NAMESPACE.list()):
        _, ignored = _settle(shell, name)
        _report(name, ignored)


def follow_kernel_namespace(shell, post: Optional[Callable] = None) -> None:
    """Apply every contributed name to ``shell.user_ns`` and follow the extension point. Main thread; idempotent per shell.

    ``post(function, *args)`` runs ``function`` where the shell's namespace may be touched
    (the kernel thread); by default it runs immediately.
    """
    if shell in _APPLIED:
        return
    _APPLIED[shell] = ({}, post or _run_now)
    _replay(shell)
    shell_ref = weakref.ref(shell)
    KERNEL_NAMESPACE.signals.added.connect(partial(_on_added, shell_ref))
    KERNEL_NAMESPACE.signals.removed.connect(partial(_on_removed, shell_ref))


def unfollow_kernel_namespace(shell) -> None:
    """Stop applying contributions to ``shell``; what it already has stays."""
    _APPLIED.pop(shell, None)
