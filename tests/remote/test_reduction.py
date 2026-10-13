import numpy as np
from SciQLop.components.plotting.backend.remote.reduction import reduce_result


def test_tuple_arity2_kept_contiguous_and_time_float64():
    t = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    y = np.array([10.0, 20.0, 30.0], dtype=np.float32)
    arrays = reduce_result((t, y), arity=2)
    assert len(arrays) == 2
    assert arrays[0].dtype == np.float64          # time upcast to epoch f64
    assert arrays[1].dtype == np.float32          # values dtype preserved
    assert all(a.flags["C_CONTIGUOUS"] for a in arrays)


def test_tuple_arity3_spectrogram():
    t = np.arange(4, dtype=np.float64)
    f = np.arange(3, dtype=np.float64)
    z = np.arange(12, dtype=np.float32).reshape(4, 3)
    arrays = reduce_result((t, f, z), arity=3)
    assert len(arrays) == 3
    assert arrays[2].shape == (4, 3)
    assert arrays[2].dtype == np.float32


def test_speasy_variable_spectrogram_reduces_to_time_freq_z():
    speasy = __import__("speasy")
    from speasy.core.data_containers import DataContainer, VariableTimeAxis, VariableAxis
    from speasy.products.variable import SpeasyVariable
    times = np.array(["2020-01-01T00:00:00", "2020-01-01T00:01:00"],
                     dtype="datetime64[ns]")
    freqs = np.array([10.0, 20.0, 30.0], dtype=np.float64)
    zvals = np.arange(6, dtype=np.float32).reshape(2, 3)
    v = SpeasyVariable(
        axes=[VariableTimeAxis(values=times),
              VariableAxis(values=freqs, name="freq")],
        values=DataContainer(values=zvals, meta={}, name="spec"),
        columns=["f0", "f1", "f2"],
    )
    x, y, z = reduce_result(v, arity=3)
    assert x.dtype == np.float64
    # epoch seconds: first sample is 2020-01-01 -> 1577836800
    assert abs(x[0] - 1577836800.0) < 1.0
    np.testing.assert_array_equal(y, freqs)
    np.testing.assert_array_equal(z, zvals)


def test_reducing_plain_arrays_does_not_import_speasy():
    """Importing speasy pings every data server; with one down, a worker's
    first request waited on the network."""
    import subprocess
    import sys
    code = ("import sys, numpy as np\n"
            "from SciQLop.components.plotting.backend.remote.reduction import reduce_result\n"
            "reduce_result((np.arange(3.0), np.arange(3.0)), arity=2)\n"
            "assert 'speasy' not in sys.modules\n")
    subprocess.run([sys.executable, "-c", code], check=True, timeout=60)
