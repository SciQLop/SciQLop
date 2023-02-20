from .pipelines_model.base import model as _pipelines
from .products_model import ProductsModel as _ProductsModel

products = _ProductsModel()
pipelines = _pipelines
