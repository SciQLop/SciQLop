import cocat_rs
import pytest

from SciQLop.plugins.sciqlop_cocat.transfer import FORMATS, NeedsValueRange, export_catalogue, format_for_filter, import_file


@pytest.fixture
def projects(tmp_path):
    made = [cocat_rs.Project.open(tmp_path / name, name) for name in ("src", "dst")]
    yield made
    for project in made:
        project.close()


@pytest.mark.parametrize("name", [f.name for f in FORMATS])
def test_a_catalogue_goes_out_and_back_in(projects, tmp_path, name):
    source, destination = projects
    shocks = source.create_catalogue(name="shocks", author="a")
    event = source.create_event(start="2020-01-01T00:00:00Z", stop="2020-01-01T01:00:00Z", author="a")
    shocks.add_events([event])
    fmt = next(f for f in FORMATS if f.name == name)
    path = tmp_path / f"out{fmt.suffix}"
    export_catalogue(fmt, source, shocks, path, value_range=(1.0, 10.0) if name == "TFCat" else None)
    import_file(fmt, destination, path)
    [imported] = destination.catalogues()
    assert len(imported.events) == 1


def test_tfcat_asks_for_a_band_when_events_have_no_shape(projects, tmp_path):
    source, _ = projects
    shocks = source.create_catalogue(name="shocks", author="a")
    shocks.add_events([source.create_event(start="2020-01-01T00:00:00Z", stop="2020-01-01T01:00:00Z",
                                           author="a")])
    tfcat = next(f for f in FORMATS if f.name == "TFCat")
    with pytest.raises(NeedsValueRange):
        export_catalogue(tfcat, source, shocks, tmp_path / "out.json")


def test_the_chosen_filter_names_the_format():
    for fmt in FORMATS:
        assert format_for_filter(fmt.filter) is fmt
    assert format_for_filter("") is None


def test_a_band_is_two_increasing_numbers():
    from SciQLop.plugins.sciqlop_cocat.questions import parse_value_range
    assert parse_value_range("10, 2000") == (10.0, 2000.0)
    assert parse_value_range("10;20") == (10.0, 20.0)
    assert parse_value_range("20, 10") is None
    assert parse_value_range("ten") is None
