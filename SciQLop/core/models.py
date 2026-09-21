from SciQLopPlots import ProductsModel, ProductsModelNode, ProductsModelNodeType

from SciQLop.user_api.threading import on_main_thread

products = ProductsModel.instance()


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
    products.add_node(path, node)
