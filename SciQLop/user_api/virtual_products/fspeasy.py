import speasy as _spz

from SciQLop.core.common import lift, pipeline, Thunk, Something, Nothing

__all__ = ['get_data', 'lift', 'pipeline', 'Thunk', 'Something', 'Nothing']

get_data = lift(_spz.get_data)
