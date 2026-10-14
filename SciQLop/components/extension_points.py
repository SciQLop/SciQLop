"""Core extension points, declared and followed before any plugin activates.

Lives in components, not core: declaring them imports the components that own them.
"""


def prepare_extension_points() -> None:
    """Declare the core extension points and wire what follows them. Main thread only; idempotent."""
    from SciQLop.components.plotting.backend import data_provider  # noqa: F401  importing declares sciqlop.data_providers
    import SciQLop.core.mime  # noqa: F401  declares sciqlop.mime_types
    import SciQLop.core.product_kinds  # noqa: F401  declares sciqlop.product_kinds
    import SciQLop.core.source_kinds  # noqa: F401  declares sciqlop.source_kinds
    import SciQLop.core.plot_kinds  # noqa: F401  declares sciqlop.plot_kinds
    import SciQLop.core.drop_rules  # noqa: F401  declares sciqlop.drop_rules
    import SciQLop.core.menus  # noqa: F401  declares sciqlop.menus
    from SciQLop.components.command_palette.backend import registry as command_registry  # noqa: F401  declares sciqlop.commands
    from SciQLop.components.shortcuts import registry as _shortcuts  # noqa: F401  declares sciqlop.shortcuts
    from SciQLop.components.catalogs.backend import catalog_mime, event_mime  # noqa: F401
    import SciQLop.components.plotting.core_kinds  # noqa: F401  contributes sciqlop.timeseries
    import SciQLop.components.scenes.contributions  # noqa: F401  contributes sciqlop.scenes.projection
    from SciQLop.components.scenes import registry  # noqa: F401  importing declares sciqlop.scenes.*
    from SciQLop.components.scenes.tree import follow_registries
    follow_registries()
