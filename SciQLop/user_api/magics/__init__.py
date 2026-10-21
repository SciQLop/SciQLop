"""SciQLop IPython magics — registration entry point."""
from functools import cache
from typing import Callable, Optional


@cache
def _core_magics() -> tuple:
    from SciQLop.core.magics import CELL, LINE, Magic
    from SciQLop.user_api.virtual_products.magic import vp_magic
    from SciQLop.user_api.layers.magic import layer_magic
    from SciQLop.user_api.magics.plot_magic import plot_magic
    from SciQLop.user_api.magics.timerange_magic import timerange_magic
    from SciQLop.user_api.magics.install_magic import install_magic
    from SciQLop.user_api.magics.workspace_magic import workspace_magic
    from SciQLop.user_api.magics.job_magic import job_magic
    from SciQLop.user_api.magics.restart_magic import restart_magic
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
        Magic("sciqlop.restart", "restart", LINE, restart_magic),
    )


def contribute_core_magics() -> None:
    """Idempotent. Called by prepare_extension_points and register_all_magics, whichever runs first."""
    from SciQLop.core.magics import MAGICS
    from SciQLop.core.name_follower import CORE_OWNER
    for magic in _core_magics():
        if magic.id not in MAGICS:
            MAGICS.contribute(magic, owner=CORE_OWNER)


def register_all_magics(shell, post: Optional[Callable] = None):
    """Apply every magic contributed to sciqlop.magics (the core ones included) to ``shell`` and follow later changes.

    ``post(function, *args)`` runs the registrations where the shell may be touched; default: immediately.
    """
    from SciQLop.core.magics import follow_magics

    contribute_core_magics()
    follow_magics(shell, post)
