"""Core extension points, declared and followed before any plugin activates.

Lives in components, not core: declaring them imports the components that own them.
"""


def prepare_extension_points() -> None:
    """Declare the core extension points and wire what follows them. Main thread only; idempotent."""
    from SciQLop.components.plotting.backend import data_provider  # noqa: F401  importing declares sciqlop.data_providers
    from SciQLop.components.plotting.backend import easy_provider  # importing declares sciqlop.virtual_products
    import SciQLop.core.mime  # noqa: F401  declares sciqlop.mime_types
    import SciQLop.core.product_kinds  # noqa: F401  declares sciqlop.product_kinds
    import SciQLop.core.source_kinds  # noqa: F401  declares sciqlop.source_kinds
    import SciQLop.core.plot_kinds  # noqa: F401  declares sciqlop.plot_kinds
    import SciQLop.core.drop_rules  # noqa: F401  declares sciqlop.drop_rules
    import SciQLop.core.menus  # noqa: F401  declares sciqlop.menus
    import SciQLop.core.docks  # noqa: F401  declares sciqlop.docks; every main window follows it on its own
    import SciQLop.core.inspector_sections  # noqa: F401  declares sciqlop.inspector_sections
    import SciQLop.core.kernel_namespace  # noqa: F401  declares sciqlop.kernel_namespace
    import SciQLop.components.settings.backend.entry  # noqa: F401  declares sciqlop.settings
    import SciQLop.components.workspaces.backend.workspace_sections  # noqa: F401  declares sciqlop.workspace_sections
    from SciQLop.user_api.magics import contribute_core_magics
    contribute_core_magics()  # declares sciqlop.magics, contributes the core magics
    import SciQLop.components.plotting.export  # noqa: F401  declares sciqlop.export_targets, contributes the core formats
    from SciQLop.components.command_palette.backend import registry as command_registry  # noqa: F401  declares sciqlop.commands
    from SciQLop.components.shortcuts import registry as _shortcuts  # noqa: F401  declares sciqlop.shortcuts
    from SciQLop.components.agents import registry as _agent_backends  # noqa: F401  declares sciqlop.agent_backends
    from SciQLop.components.agents.tools import contributed as _agent_tools  # noqa: F401  declares sciqlop.agent_tools
    from SciQLop.components.catalogs.backend import catalog_mime, event_mime  # noqa: F401
    import SciQLop.components.plotting.core_kinds  # noqa: F401  contributes sciqlop.timeseries
    import SciQLop.components.scenes.contributions  # noqa: F401  contributes sciqlop.scenes.projection
    from SciQLop.components.scenes import registry  # noqa: F401  importing declares sciqlop.scenes.*
    from SciQLop.components.scenes.tree import follow_registries
    follow_registries()
    easy_provider.follow_virtual_products()
    from SciQLop.user_api.layers import _provider as layer_provider  # importing declares sciqlop.layers
    layer_provider.follow_layers()
    from SciQLop.components.plotting.ui.contributed_sections import follow_inspector_sections
    follow_inspector_sections()


def start_plugins(app, main_window) -> None:
    """The built-in commands first, so menu actions they replace are not harvested, then the plugins.
    ``load_all`` ends with a palette harvest, so none is needed here."""
    from SciQLop.components.command_palette.commands import register_builtin_commands
    from SciQLop.components.plugins import load_all
    from SciQLop.core.extensions import owned_by
    with owned_by("sciqlop"):
        register_builtin_commands(app.command_registry)
    load_all(main_window)
