"""Core extension points, declared and followed before any plugin activates.

Lives in components, not core: declaring them imports the components that own them.
"""


def prepare_extension_points() -> None:
    """Declare the core extension points and wire what follows them. Main thread only; idempotent."""
    from SciQLop.components.plotting.backend import data_provider  # noqa: F401  importing declares sciqlop.data_providers
    import SciQLop.core.mime  # noqa: F401  declares sciqlop.mime_types
    from SciQLop.components.catalogs.backend import catalog_mime, event_mime  # noqa: F401
    from SciQLop.components.scenes import registry  # noqa: F401  importing declares sciqlop.scenes.*
    from SciQLop.components.scenes.tree import follow_registries
    follow_registries()
