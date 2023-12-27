from SciQLop.backend import models
from SciQLop.backend import Product


def test_add_nodes():
    models.products.add_product(path="test/node",
                                product=Product(name="test", metadata={}, provider="test", uid="test1"))
    models.products.add_product(path="test/node",
                                product=Product(name="test", metadata={}, provider="test", uid="test2"))
    models.products.add_product(path="test/node",
                                product=Product(name="test", metadata={}, provider="test", uid="test3"))
    assert models.products.product("test/node/test") is not None
    assert models.products.product("test/node/test").uid == "test3"
