import numpy as np
import pytest
from SciQLop.components.plotting.backend.remote.protocol import (
    pack_arrays, unpack_arrays, total_nbytes, ArrayLayout,
)


def test_pack_then_unpack_roundtrips_values_and_dtypes():
    x = np.linspace(0, 1, 5).astype(np.float64)
    z = np.arange(6, dtype=np.float32).reshape(2, 3)
    buf = bytearray(total_nbytes([x, z]))
    layout = pack_arrays(memoryview(buf), [x, z])
    assert [l.dtype for l in layout] == [x.dtype.str, z.dtype.str]
    out = unpack_arrays(memoryview(buf), layout)
    np.testing.assert_array_equal(out[0], x)
    np.testing.assert_array_equal(out[1], z)
    assert out[1].shape == (2, 3)


def test_offsets_are_8_byte_aligned():
    a = np.ones(3, dtype=np.float32)   # 12 bytes -> next offset padded to 16
    b = np.ones(2, dtype=np.float64)
    layout = pack_arrays(memoryview(bytearray(total_nbytes([a, b]))), [a, b])
    assert layout[0].offset == 0
    assert layout[1].offset % 8 == 0
    assert layout[1].offset >= a.nbytes


def test_unpack_returns_views_not_copies():
    a = np.arange(4, dtype=np.float64)
    buf = bytearray(total_nbytes([a]))
    layout = pack_arrays(memoryview(buf), [a])
    out = unpack_arrays(memoryview(buf), layout)
    out[0][0] = 999.0
    assert np.frombuffer(buf, dtype=np.float64, count=1)[0] == 999.0


def test_unpacked_views_keep_the_segment_mapped():
    """Closing a segment under a live view must refuse, not unmap memory the view still reads."""
    from multiprocessing import shared_memory
    a = np.arange(6, dtype=np.float32).reshape(2, 3)
    shm = shared_memory.SharedMemory(create=True, size=total_nbytes([a]), track=False)
    try:
        layout = pack_arrays(shm.buf, [a])
        views = unpack_arrays(shm.buf, layout)
        with pytest.raises(BufferError):
            shm.close()
        np.testing.assert_array_equal(views[0], a)
        del views
        shm.close()
    finally:
        shm.unlink()


def test_unpack_handles_empty_arrays():
    a = np.empty((0, 3), dtype=np.float64)
    buf = bytearray(total_nbytes([a]) or 8)
    out = unpack_arrays(memoryview(buf), pack_arrays(memoryview(buf), [a]))
    assert out[0].shape == (0, 3)
