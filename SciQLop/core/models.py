from SciQLopPlots import ProductsModel, ProductsModelNode, ProductsModelNodeType

from SciQLop.user_api.threading import on_main_thread


def __getattr__(name):
    """`products` is looked up on each access, never kept: the one shared Python wrapper of the model can be
    marked deleted while the C++ model lives on (a Python-side proxy given it with setSourceModel takes it down
    when the proxy dies), and ProductsModel.instance() then hands out a fresh, valid wrapper."""
    if name == "products":
        return ProductsModel.instance()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@on_main_thread
def add_product_node(path, *node_args, display_name=None):
    """Build a ProductsModelNode and add it under `path`, on the GUI thread.

    Kernel-thread callers (notebook cells, agent tools) must not build the node
    or touch the model themselves: the node's QObject parenting and the model's
    signals both require GUI-thread affinity (#138).
    """
    node = ProductsModelNode(*node_args)
    if display_name:
        node.set_display_name(display_name)
    ProductsModel.instance().add_node(path, node)


@on_main_thread
def remove_product_node(path: list[str]) -> None:
    """Remove the node at `path`, on the GUI thread. A path with no node is ignored."""
    # simplify: empty parent folders stay; prune them when a plugin's withdrawal leaves visible empty folders that users complain about.
    ProductsModel.instance().remove_node(path)
