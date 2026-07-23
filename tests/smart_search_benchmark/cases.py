"""Seed corpus of (query, expected path-prefix) benchmark cases for smart
search ranking quality. Grows organically: add a case here whenever a live
query surfaces a bad result -- see docs/superpowers/specs/
2026-07-22-smart-search-benchmark-corpus-design.md."""
from pydantic import BaseModel

DEFAULT_TOP_N = 10


class BenchmarkCase(BaseModel):
    query: str
    expected_prefixes: list[str]
    top_n: int | None = None


CASES: list[BenchmarkCase] = [
    BenchmarkCase(
        query="MMS spacecraft 1 magnetic field",
        expected_prefixes=["root speasy cda MMS MMS1 FGM", "root speasy cda MMS MMS1 SCM"],
    ),
    BenchmarkCase(
        query="MMS1 spacecraft magnetic field",
        expected_prefixes=["root speasy cda MMS MMS1 FGM", "root speasy cda MMS MMS1 SCM"],
    ),
    BenchmarkCase(
        query="MMS1 Search Coil",
        expected_prefixes=["root speasy cda MMS MMS1 SCM"],
    ),
    BenchmarkCase(
        query="MMS1 trajectory",
        expected_prefixes=["root speasy cda MMS MMS1 MEC"],
    ),
    BenchmarkCase(
        query="MMS1 ephemeris",
        expected_prefixes=["root speasy cda MMS MMS1 MEC"],
    ),
    BenchmarkCase(
        query="MMS1 electrons",
        expected_prefixes=["root speasy cda MMS MMS1 DES"],
    ),
    BenchmarkCase(
        query="ACE trajectory",
        expected_prefixes=["root speasy amda Parameters ACE Ephemeris"],
    ),
    BenchmarkCase(
        # Real bug report (2026-07-22): "MMS1 ion"/"MMS1 ion flux" surface
        # only FEEPS/HPCA respectively -- FPI DIS, MMS's primary ion
        # instrument, is missing from both, even though the plural "MMS1
        # ions" correctly finds it (via the AMDA-source duplicate, whose
        # descriptive path segment happens to say "ions"). Same class of
        # gap as the Search Coil/electrons cases: FPI DIS's own field/path
        # names use the acronym "DIS", never the literal word "ion(s)".
        query="MMS1 ion",
        expected_prefixes=[
            "root speasy cda MMS MMS1 DIS",
            "root speasy amda Parameters MMS MMS1 FPI fast mode DIS",
            "root speasy amda Parameters MMS MMS1 FPI burst mode DIS",
        ],
    ),
    BenchmarkCase(
        query="MMS1 ion flux",
        expected_prefixes=[
            "root speasy cda MMS MMS1 DIS",
            "root speasy amda Parameters MMS MMS1 FPI fast mode DIS",
            "root speasy amda Parameters MMS MMS1 FPI burst mode DIS",
        ],
    ),
]
