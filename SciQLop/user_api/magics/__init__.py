"""SciQLop IPython magics — registration entry point."""


def register_all_magics(shell):
    """Register all SciQLop magics and their tab completers."""
    from SciQLop.user_api.virtual_products.magic import vp_magic
    from SciQLop.user_api.magics.plot_magic import plot_magic, complete_plot
    from SciQLop.user_api.magics.timerange_magic import timerange_magic, complete_timerange
    from SciQLop.user_api.magics.completions import complete_vp

    shell.register_magic_function(vp_magic, magic_kind="cell", magic_name="vp")
    shell.register_magic_function(plot_magic, magic_kind="line", magic_name="plot")
    shell.register_magic_function(timerange_magic, magic_kind="line", magic_name="timerange")

    shell.set_hook("complete_command", complete_plot, str_key="%plot")
    shell.set_hook("complete_command", complete_timerange, str_key="%timerange")
    shell.set_hook("complete_command", complete_vp, str_key="%%vp")
