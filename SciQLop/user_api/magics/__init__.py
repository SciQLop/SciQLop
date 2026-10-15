"""SciQLop IPython magics — registration entry point."""


def register_all_magics(shell):
    """Apply every magic contributed to sciqlop.magics (the core ones included) to ``shell`` and follow later changes."""
    from SciQLop.core.magics import contribute_core_magics, follow_magics

    contribute_core_magics()
    follow_magics(shell)
