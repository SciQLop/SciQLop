"""Option-lifted ``speasy.get_data`` for virtual-product pipelines.

``get_data`` here returns ``Something(var)``/``Nothing`` instead of a variable
or ``None``, so a chain of transformations can be written with ``pipeline`` /
``lift`` without a ``None`` check at every step. Prefer ``Depends`` in the
function signature when the inputs are fixed products; use this module when
the product list is computed at call time.
"""
import speasy as _spz

from SciQLop.core.common import lift, pipeline, Thunk, Something, Nothing

__all__ = ['get_data', 'lift', 'pipeline', 'Thunk', 'Something', 'Nothing']

get_data = lift(_spz.get_data)
