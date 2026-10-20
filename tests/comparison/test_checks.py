from SciQLop.components.comparison.backend.checks import compatible, is_remote
from SciQLop.core.plot_hints import AxisHints, PlotHints


def test_compatible_reports_units_and_components():
    nT = PlotHints(y=AxisHints(unit="nT"), component_labels=["Bx", "By", "Bz"])
    assert compatible(nT, PlotHints(y=AxisHints(unit="mV")), False) == "different units: nT vs mV"
    assert compatible(nT, PlotHints(y=AxisHints(unit="nT"), component_labels=["Bn", "Be", "Bz"]), False) == \
        "different components: Bx/By/Bz vs Bn/Be/Bz"
    assert compatible(nT, PlotHints(), False) is None


def test_compatible_reads_z_unit_for_colormaps():
    a = PlotHints(y=AxisHints(unit="eV"), z=AxisHints(unit="counts"))
    b = PlotHints(y=AxisHints(unit="keV"), z=AxisHints(unit="flux"))
    assert compatible(a, b, True) == "different units: counts vs flux"
    assert compatible(a, b.model_copy(update={"z": AxisHints(unit="counts")}), True) is None


def test_compatible_allows_unknown_hints():
    assert compatible(None, PlotHints(y=AxisHints(unit="nT")), False) is None
    assert compatible(PlotHints(), PlotHints(), False) is None


def test_local_product_is_not_remote():
    assert is_remote("nowhere//to//be//found") is False
