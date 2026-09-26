from SciQLop.components.workspaces.backend.notebook_stamp import (
    NotebookStamp,
    build_stamp,
    environment_gap,
    read_stamp,
    stamp_notebook,
)

INSTALLED = {"scipy": "1.14.1", "xarray": "2024.1.0", "sciqlop-radio": "0.3.0", "spok": "0.1"}


def installed_version(name: str) -> str | None:
    return INSTALLED.get(name)


def test_build_stamp_pins_named_requirements_to_installed_versions():
    stamp = build_stamp("0.13.0", ["scipy>=1.11", "xarray[io]"], installed_version)

    assert stamp == NotebookStamp(version="0.13.0",
                                  dependencies=["scipy==1.14.1", "xarray[io]==2024.1.0"])


def test_build_stamp_keeps_markers():
    stamp = build_stamp("0.13.0", ["scipy; sys_platform == 'linux'"], installed_version)

    assert stamp.dependencies == ['scipy==1.14.1; sys_platform == "linux"']


def test_build_stamp_keeps_url_and_not_installed_requirements_verbatim():
    specs = ["spok @ https://example.org/spok.zip",
             "https://example.org/other.zip",
             "notinstalled>=2"]

    assert build_stamp("0.13.0", specs, installed_version).dependencies == specs


def test_build_stamp_drops_local_requirements():
    specs = ["/home/me/plugin", "./wheels/x.whl", "file:///tmp/x.whl", "-e ../mine",
             "C:\\plugins\\mine", "mine @ file:///home/me/mine", "scipy"]

    assert build_stamp("0.13.0", specs, installed_version).dependencies == ["scipy==1.14.1"]


def test_build_stamp_drops_sciqlop_itself():
    assert build_stamp("0.13.0", ["sciqlop[all]==0.12"], installed_version).dependencies == []


def test_stamp_round_trips_through_notebook_metadata():
    notebook = {"cells": [], "metadata": {"kernelspec": {"name": "python3"}}}
    stamp = NotebookStamp(version="0.13.0", dependencies=["scipy==1.14.1"])

    stamped = stamp_notebook(notebook, stamp)

    assert stamped["metadata"]["kernelspec"] == {"name": "python3"}
    assert read_stamp(stamped) == stamp
    assert "sciqlop" not in notebook["metadata"]


def test_read_stamp_ignores_unstamped_and_malformed_notebooks():
    assert read_stamp({"cells": []}) is None
    assert read_stamp({"metadata": {}}) is None
    assert read_stamp({"metadata": {"sciqlop": "0.13"}}) is None
    assert read_stamp({"metadata": {"sciqlop": {"version": 13, "dependencies": "scipy"}}}) is None


def gap(stamp, running="0.13.0", current=()):
    return environment_gap(stamp, running, installed_version, list(current))


def test_no_gap_when_everything_is_installed():
    stamp = NotebookStamp(version="0.13.0", dependencies=["scipy==1.14.1", "xarray[io]>=2024"])

    assert gap(stamp) is None


def test_gap_lists_missing_and_mismatched_dependencies():
    stamp = NotebookStamp(version="0.13.0",
                          dependencies=["scipy==1.15.0", "notinstalled==1.0", "xarray==2024.1.0"])

    assert gap(stamp).missing == ["scipy==1.15.0", "notinstalled==1.0"]


def test_newer_installed_package_satisfies_an_exact_pin():
    stamp = NotebookStamp(version="0.13.0", dependencies=["scipy==1.10.0", "xarray[io]==2023.1"])

    assert gap(stamp) is None


def test_wildcard_pin_keeps_specifier_matching():
    assert gap(NotebookStamp(version="0.13.0", dependencies=["scipy==1.14.*"])) is None
    assert gap(NotebookStamp(version="0.13.0", dependencies=["scipy==1.13.*"])).missing == ["scipy==1.13.*"]


def test_bare_url_dependency_is_satisfied_only_when_the_workspace_requires_it():
    url = "https://example.org/other.zip"
    stamp = NotebookStamp(version="0.13.0", dependencies=[url])

    assert gap(stamp).missing == [url]
    assert gap(stamp, current=[url]) is None


def test_named_url_dependency_is_satisfied_when_installed():
    stamp = NotebookStamp(version="0.13.0", dependencies=["spok @ https://example.org/spok.zip"])

    assert gap(stamp) is None


def test_gap_when_notebook_needs_a_newer_sciqlop():
    stamp = NotebookStamp(version="0.14.0", dependencies=[])

    found = gap(stamp, running="0.13.0")

    assert found.stamp.version == "0.14.0"
    assert found.needs_newer_sciqlop
    assert found.missing == []


def test_older_notebook_on_newer_sciqlop_is_not_a_gap():
    assert gap(NotebookStamp(version="0.12.0", dependencies=[]), running="0.13.0") is None


def test_unparseable_versions_are_not_a_gap():
    assert gap(NotebookStamp(version="main", dependencies=[]), running="0.13.0") is None
    assert gap(NotebookStamp(version="0.14.0", dependencies=[]), running="") is None
