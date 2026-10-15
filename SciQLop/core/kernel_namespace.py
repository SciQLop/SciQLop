"""Kernel namespace: the sciqlop.kernel_namespace extension point and the code that applies it to a shell."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.extensions import ExtensionPoint, declare
from SciQLop.core.name_follower import CORE_OWNER, Follower

log = getLogger(__name__)


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


_UNBOUND = object()


def _may_overwrite(shell, name: str, replaced: tuple) -> bool:
    current = shell.user_ns.get(name, _UNBOUND)
    return current is _UNBOUND or any(current is entry.value for entry in replaced)


def _apply(shell, entry: NamespaceEntry, replaced: tuple) -> None:
    if replaced and not _may_overwrite(shell, entry.name, replaced):
        log.warning(f"kernel name {entry.name} from {entry.id} not applied: the user rebound it")
        return
    shell.push({entry.name: entry.value})


def _unapply(shell, entry: NamespaceEntry) -> None:
    """Never clobbers the user: a name rebound since the push stays."""
    if shell.user_ns.get(entry.name, _UNBOUND) is entry.value:
        del shell.user_ns[entry.name]


_FOLLOWER = Follower(KERNEL_NAMESPACE, log, lambda e: f"kernel name {e.name}", lambda e: ("value",), _apply, _unapply)


def follow_kernel_namespace(shell, post: Optional[Callable] = None) -> None:
    """Apply every contributed name to ``shell.user_ns`` and follow the extension point. Main thread; idempotent per shell.

    ``post(function, *args)`` runs ``function`` where the shell's namespace may be touched
    (the kernel thread); by default it runs immediately.
    """
    _FOLLOWER.follow(shell, post)


def unfollow_kernel_namespace(shell) -> None:
    _FOLLOWER.unfollow(shell)
