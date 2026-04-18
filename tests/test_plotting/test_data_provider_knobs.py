from SciQLop.components.plotting.backend.data_provider import DataProvider


class _Toy(DataProvider):
    def __init__(self):
        super().__init__(name="toy")
        self.last_knobs = "unset"

    def get_data(self, product, start, stop, knobs=None):
        self.last_knobs = knobs
        return None


def test_default_get_knobs_returns_empty_list():
    p = DataProvider(name="empty-knobs")
    assert p.get_knobs("any") == []


def test_get_data_forwards_knobs():
    p = _Toy()
    p._get_data("prod", 0.0, 1.0, knobs={"fft": 256})
    assert p.last_knobs == {"fft": 256}


def test_get_data_default_knobs_is_none():
    p = _Toy()
    p._get_data("prod", 0.0, 1.0)
    assert p.last_knobs is None
