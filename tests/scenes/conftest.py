import pytest

from .helpers import RE, FakeVariable, threedview_meta


@pytest.fixture
def earth(monkeypatch):
    from scipy.spatial.transform import Rotation
    from SciQLop.components.scenes import registry, scene_plot, summary
    from SciQLop.components.scenes.boundary import RadialBoundary
    from SciQLop.plugins.planetary_scenes import register_all
    for reg in (registry.BODIES, registry.BOUNDARIES, registry.SCENES):
        monkeypatch.setattr(reg, "_items", {})
    register_all()
    monkeypatch.setattr(summary, "rotation", lambda f, t, times: Rotation.identity(len(times)))
    monkeypatch.setattr(RadialBoundary, "n_samples", 10)   # 18 curves stay well inside the waits
    scene_plot._cached_summary.cache_clear()
    yield
    scene_plot._cached_summary.cache_clear()


@pytest.fixture
def fake_speasy(monkeypatch):
    requests = []

    def get_data(product, start, stop, **kwargs):
        requests.append((product, kwargs))
        if product.startswith("cdpp3dview/"):
            return FakeVariable([[RE, 0, 0], [2 * RE, 0, 0]], threedview_meta("GSM"))
        if product.endswith("r_gse"):
            return FakeVariable([[RE, 0, 0, RE], [0, RE, 0, RE]], {"UNITS": "km", "COORDINATE_SYSTEM": "GSE>x"})
        if product.endswith("rtn"):
            return FakeVariable([[1, 0, 0]] * 2, {"UNITS": "km", "COORDINATE_SYSTEM": "RTN"})
        if product.endswith("r_gsm"):
            return FakeVariable([[RE, 0, 0]] * 2, {"UNITS": "km", "COORDINATE_SYSTEM": "GSM"})
        return FakeVariable([[1, 0, 0]] * 2, {"UNITS": "km"})

    import speasy
    monkeypatch.setattr(speasy, "get_data", get_data)
    return requests


@pytest.fixture
def registered(main_window, earth):
    """The built-in scenes registered through the user_api, so the products tree lists them;
    tree roots this test created are removed afterwards."""
    from SciQLopPlots import ProductsModel
    from SciQLop.plugins.planetary_scenes import load
    roots = [r for r in ("Scenes", "Models") if ProductsModel.node([r]) is None]
    load(main_window)
    yield
    for root in roots:
        ProductsModel.instance().remove_node([root])
