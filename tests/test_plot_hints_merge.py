"""Tests for merge_hints and combine_hints."""
from SciQLop.core.plot_hints import AxisHints, PlotHints, combine_hints, merge_hints


def test_merge_empty_base_takes_extra():
    base = PlotHints()
    extra = PlotHints(y=AxisHints(label="Bt", unit="nT", scale="linear"))
    merged = merge_hints(base, extra)
    assert merged.y.label == "Bt"
    assert merged.y.unit == "nT"
    assert merged.y.scale == "linear"


def test_merge_base_wins_over_extra():
    base = PlotHints(y=AxisHints(label="from_inventory", unit="nT"))
    extra = PlotHints(y=AxisHints(label="from_variable", unit="T"))
    merged = merge_hints(base, extra)
    assert merged.y.label == "from_inventory"
    assert merged.y.unit == "nT"


def test_merge_fills_only_missing_fields():
    base = PlotHints(y=AxisHints(label="Bt"))
    extra = PlotHints(y=AxisHints(label="ignored", unit="nT", scale="linear"))
    merged = merge_hints(base, extra)
    assert merged.y.label == "Bt"
    assert merged.y.unit == "nT"
    assert merged.y.scale == "linear"


def test_merge_y2_from_extra():
    base = PlotHints(display_type="spectrogram", z=AxisHints(label="flux"))
    extra = PlotHints(y2=AxisHints(label="Energy", unit="eV", scale="log"))
    merged = merge_hints(base, extra)
    assert merged.y2.label == "Energy"
    assert merged.y2.unit == "eV"
    assert merged.y2.scale == "log"
    assert merged.z.label == "flux"
    assert merged.display_type == "spectrogram"


def test_merge_component_labels_base_wins():
    base = PlotHints(component_labels=["a", "b"])
    extra = PlotHints(component_labels=["x", "y", "z"])
    assert merge_hints(base, extra).component_labels == ["a", "b"]


def test_merge_component_labels_from_extra_when_base_none():
    base = PlotHints()
    extra = PlotHints(component_labels=["Bx", "By", "Bz"])
    assert merge_hints(base, extra).component_labels == ["Bx", "By", "Bz"]


def test_merge_fill_value_base_wins():
    base = PlotHints(fill_value=-1e31)
    extra = PlotHints(fill_value=0.0)
    assert merge_hints(base, extra).fill_value == -1e31


def test_merge_fill_value_from_extra():
    base = PlotHints()
    extra = PlotHints(fill_value=-1e31)
    assert merge_hints(base, extra).fill_value == -1e31


def test_combine_empty_list_is_empty():
    assert combine_hints([]) == PlotHints()


def test_combine_single_entry_y_label():
    h = PlotHints(y=AxisHints(label="Bt", unit="nT", scale="linear"))
    combined = combine_hints([h])
    assert combined.y.label == "Bt [nT]"
    assert combined.y.scale == "linear"


def test_combine_two_line_products_joins_labels():
    h1 = PlotHints(y=AxisHints(label="Bt", unit="nT"))
    h2 = PlotHints(y=AxisHints(label="|B|", unit="nT"))
    combined = combine_hints([h1, h2])
    assert combined.y.label == "Bt [nT], |B| [nT]"


def test_combine_deduplicates_identical_labels():
    h1 = PlotHints(y=AxisHints(label="Bt", unit="nT"))
    h2 = PlotHints(y=AxisHints(label="Bt", unit="nT"))
    assert combine_hints([h1, h2]).y.label == "Bt [nT]"


def test_combine_first_scale_wins():
    h1 = PlotHints(y=AxisHints(label="a", scale="linear"))
    h2 = PlotHints(y=AxisHints(label="b", scale="log"))
    assert combine_hints([h1, h2]).y.scale == "linear"


def test_combine_skips_entries_without_y_label():
    h1 = PlotHints()
    h2 = PlotHints(y=AxisHints(label="Bt", unit="nT"))
    assert combine_hints([h1, h2]).y.label == "Bt [nT]"


def test_combine_spectrogram_plus_line_keeps_z_and_y():
    line = PlotHints(y=AxisHints(label="Bt", unit="nT"))
    spec = PlotHints(
        display_type="spectrogram",
        y2=AxisHints(label="Energy", unit="eV", scale="log"),
        z=AxisHints(label="flux", scale="log"),
    )
    combined = combine_hints([line, spec])
    assert combined.y.label == "Bt [nT]"
    assert combined.y2.label == "Energy"
    assert combined.z.label == "flux"
    assert combined.display_type == "spectrogram"


def test_combine_first_non_empty_y2_wins():
    h1 = PlotHints(y2=AxisHints(label="E1", unit="eV"))
    h2 = PlotHints(y2=AxisHints(label="E2", unit="keV"))
    assert combine_hints([h1, h2]).y2.label == "E1"
