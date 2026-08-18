"""Plugin discovery and loading.

``load_all`` and ``loaded_plugins`` are resolved lazily: importing them pulls in
the Qt-based logger and the whole GUI stack, which the launcher does not have
when it prepares a workspace for a thin (``pip install sciqlop``) install.
Attribute access keeps the historical ``from SciQLop.components.plugins import
load_all`` spelling working unchanged.
"""

__all__ = ["load_all", "loaded_plugins"]


def __getattr__(name):
    if name in __all__:
        from .backend import loader
        return getattr(loader, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
