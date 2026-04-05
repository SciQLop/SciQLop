"""SciQLop IPython magics — registration entry point."""


def register_all_magics(shell):
    """Register all SciQLop magics and their tab completers."""
    from SciQLop.user_api.virtual_products.magic import vp_magic
    from SciQLop.user_api.magics.plot_magic import plot_magic
    from SciQLop.user_api.magics.timerange_magic import timerange_magic
    from SciQLop.user_api.magics.install_magic import install_magic
    from SciQLop.user_api.magics.workspace_magic import workspace_magic
    from SciQLop.user_api.magics.completions import _match_plot, _match_timerange, _match_vp

    shell.register_magic_function(vp_magic, magic_kind="cell", magic_name="vp")
    shell.register_magic_function(plot_magic, magic_kind="line", magic_name="plot")
    shell.register_magic_function(timerange_magic, magic_kind="line", magic_name="timerange")
    shell.register_magic_function(install_magic, magic_kind="line", magic_name="install")
    shell.register_magic_function(workspace_magic, magic_kind="line", magic_name="workspace")

    # Matcher API v2 — works across JupyterLab, QtConsole, and terminal
    shell.Completer.custom_matchers.append(_match_plot)
    shell.Completer.custom_matchers.append(_match_timerange)
    shell.Completer.custom_matchers.append(_match_vp)
