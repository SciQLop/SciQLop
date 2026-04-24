from SciQLop.user_api.layers.types import Marker, Span, HLine


def test_partition_markers_only():
    from SciQLop.user_api.layers._renderer import _partition
    items = [Marker(time=1.0, value=2.0), Marker(time=3.0, value=4.0)]
    groups = _partition(items)
    assert len(groups["marker"]) == 2
    assert len(groups["span"]) == 0
    assert len(groups["hline"]) == 0


def test_partition_mixed():
    from SciQLop.user_api.layers._renderer import _partition
    items = [Marker(time=1.0, value=2.0), Span(start=1.0, stop=2.0), HLine(value=3.0)]
    groups = _partition(items)
    assert len(groups["marker"]) == 1
    assert len(groups["span"]) == 1
    assert len(groups["hline"]) == 1


def test_partition_empty():
    from SciQLop.user_api.layers._renderer import _partition
    groups = _partition([])
    assert len(groups["marker"]) == 0
    assert len(groups["span"]) == 0
    assert len(groups["hline"]) == 0
