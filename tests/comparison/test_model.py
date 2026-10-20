from SciQLop.components.comparison.backend.model import (
    Comparison, GraphSpec, Side, Variant, base_specs, changed_keys, sides)
from SciQLop.components.plotting.panel_template import PanelTemplate, PlotModel, ProductModel


def _template(*plots):
    return PanelTemplate(name="P", plots=[PlotModel(products=[ProductModel(path=p) for p in paths])
                                          for paths in plots])


def test_base_specs_skip_products_without_path():
    t = _template(["a//b", ""], ["c//d"])
    assert [(s.plot_index, s.product_index, s.path) for s in base_specs(t)] == [(0, 0, "a//b"), (1, 0, "c//d")]


def test_base_specs_skip_non_timeseries_plots_keeping_indices():
    t = _template(["a//b"], ["c//d"])
    t.plots[0].kind = "other"
    assert [s.key for s in base_specs(t)] == [(1, 0)]


def test_base_specs_carry_colormap_flag_and_knobs():
    t = _template(["a//b"])
    t.plots[0].products[0].graph_type = "ColorMap"
    t.plots[0].products[0].knobs = {"k": 1}
    (spec,) = base_specs(t)
    assert spec.is_colormap and spec.knobs == {"k": 1}


def test_base_specs_carry_time_offset():
    t = _template(["a//b"])
    t.plots[0].products[0].time_offset = 86400.0
    (spec,) = base_specs(t)
    assert spec.time_offset == 86400.0


def test_comparison_round_trips_through_json():
    c = Comparison(base=_template(["a//b"]).to_tree(), dimension="time",
                   variants=[Variant(label="v", params={"start": 1.0, "stop": 2.0})])
    assert Comparison.model_validate_json(c.model_dump_json()) == c
    assert c.template().plots[0].products[0].path == "a//b"


def test_sides_puts_base_first_then_one_per_variant():
    c = Comparison(base=_template(["a//b"]).to_tree(), dimension="time",
                   variants=[Variant(label="v1"), Variant(label="v2")])
    result = sides(c,
                   lambda specs, comp: Side(label="base", specs=specs),
                   lambda specs, v, comp: Side(label=v.label, specs=specs))
    assert [s.label for s in result] == ["base", "v1", "v2"]


def test_changed_keys_ignores_identical_specs():
    base = Side(label="b", specs=[GraphSpec(plot_index=0, product_index=0, path="a"),
                                  GraphSpec(plot_index=1, product_index=0, path="c")])
    var = Side(label="v", specs=[GraphSpec(plot_index=0, product_index=0, path="a", time_offset=5.0),
                                 GraphSpec(plot_index=1, product_index=0, path="c")])
    assert changed_keys([base, var]) == {(0, 0)}


def test_template_at_range_replaces_only_the_time_range():
    from SciQLop.components.comparison.backend.model import template_at_range
    t = _template(["a//b"])
    assert template_at_range(t, None) is t
    moved = template_at_range(t, (0.0, 60.0))
    assert (moved.time_range.start, moved.time_range.stop) == ("1970-01-01T00:00:00+00:00", "1970-01-01T00:01:00+00:00")
    assert moved.plots == t.plots
