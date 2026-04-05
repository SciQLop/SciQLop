from .fixtures import *
from datetime import datetime, timezone, timedelta
from PySide6.QtGui import QColor


def _make_events(metas: list[dict]):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    return [
        CatalogEvent(uuid=f"ev-{i}", start=base + timedelta(days=i),
                     stop=base + timedelta(days=i, hours=1), meta=m)
        for i, m in enumerate(metas)
    ]


def test_uniform_mapping_returns_catalog_color(qapp):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    mapper = ColorMapper()
    catalog_color = QColor(31, 119, 180, 80)
    events = _make_events([{"class": "A"}, {"class": "B"}])
    result = mapper(events, catalog_color)
    assert len(result) == 2
    for color in result.values():
        assert color == catalog_color


def test_categorical_mapping_assigns_distinct_colors(qapp):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    mapper = ColorMapper(column="class")
    catalog_color = QColor(127, 127, 127, 80)
    events = _make_events([{"class": "A"}, {"class": "B"}, {"class": "A"}])
    result = mapper(events, catalog_color)
    assert result["ev-0"] == result["ev-2"]  # same class → same color
    assert result["ev-0"] != result["ev-1"]  # different class → different color (very likely)


def test_categorical_mapping_missing_value_falls_back(qapp):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    mapper = ColorMapper(column="class")
    catalog_color = QColor(127, 127, 127, 80)
    events = _make_events([{"class": "A"}, {}])
    result = mapper(events, catalog_color)
    assert result["ev-1"] == catalog_color


def test_continuous_mapping_varies_by_value(qapp):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    mapper = ColorMapper(column="score", colormap="viridis")
    catalog_color = QColor(127, 127, 127, 80)
    events = _make_events([{"score": 0.0}, {"score": 0.5}, {"score": 1.0}])
    result = mapper(events, catalog_color)
    assert result["ev-0"] != result["ev-1"]
    assert result["ev-1"] != result["ev-2"]
    assert result["ev-0"].alpha() == 80


def test_continuous_mapping_custom_range(qapp):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    mapper = ColorMapper(column="score", colormap="viridis", vmin=0.0, vmax=10.0)
    catalog_color = QColor(127, 127, 127, 80)
    events = _make_events([{"score": 0.0}, {"score": 10.0}])
    result = mapper(events, catalog_color)
    assert result["ev-0"] != result["ev-1"]


def test_continuous_mapping_clamps_out_of_range(qapp):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    mapper = ColorMapper(column="score", colormap="viridis", vmin=0.0, vmax=1.0)
    catalog_color = QColor(127, 127, 127, 80)
    events = _make_events([{"score": -5.0}, {"score": 0.0}, {"score": 100.0}, {"score": 1.0}])
    result = mapper(events, catalog_color)
    assert result["ev-0"] == result["ev-1"]
    assert result["ev-2"] == result["ev-3"]


def test_continuous_mapping_missing_value_falls_back(qapp):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    mapper = ColorMapper(column="score")
    catalog_color = QColor(127, 127, 127, 80)
    events = _make_events([{"score": 0.5}, {}])
    result = mapper(events, catalog_color)
    assert result["ev-1"] == catalog_color
