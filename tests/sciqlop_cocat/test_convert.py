import json
from datetime import datetime, timezone

import numpy as np
import pytest

from SciQLop.plugins.sciqlop_cocat.convert import (
    decode_subpath,
    encode_subpath,
    event_rows,
    schema_specs,
    rows_of,
    split_typed_meta,
)


def test_subpath_roundtrip():
    assert decode_subpath(encode_subpath(["a", "b"])) == ["a", "b"]
    assert decode_subpath(None) == [] and decode_subpath("") == []
    assert decode_subpath("/a//b/") == ["a", "b"]
    assert decode_subpath(["a", "", "b"]) == ["a", "b"]


def test_schema_specs_skips_garbage_and_foreign_keys():
    from SciQLop.core.knobs import IntKnob, spec_to_dict
    spec = IntKnob(name="rating", min=1, max=5, default=2)
    specs = schema_specs({
        "sciqlop_schema__rating": json.dumps(spec_to_dict(spec)),
        "sciqlop_schema__bad": "{not json",
        "other": 1,
    })
    assert list(specs) == ["rating"]
    assert spec_to_dict(specs["rating"]) == spec_to_dict(spec)


def _arrays(uuids, starts, stops):
    return {"uuid": uuids, "start": np.array(starts, "datetime64[us]"),
            "stop": np.array(stops, "datetime64[us]")}


def test_event_rows_from_arrays_are_utc_aware():
    [row] = event_rows(_arrays(["u1"], ["2020-01-01T00:00:00"], ["2020-01-01T01:00:00"]),
                       [{"note": "x"}])
    assert row.uuid == "u1"
    assert row.start == datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert row.stop == datetime(2020, 1, 1, 1, tzinfo=timezone.utc)
    assert row.meta == {"note": "x"}


def test_event_rows_empty_catalogue():
    assert event_rows(_arrays([], [], []), []) == []


def test_event_rows_rejects_misaligned_attributes():
    with pytest.raises(ValueError):
        event_rows(_arrays(["u1"], ["2020-01-01"], ["2020-01-02"]), [])


def test_split_typed_meta():
    assert split_typed_meta({"tags": ["a"], "rating": 3, "note": "n"}) == (
        {"tags": ["a"], "confidence": 0.3}, {"note": "n"})


def test_derived_rows_get_a_stable_id_and_are_marked():
    import numpy as np
    arrays = {"uuid": ["e1", None], "sources": [[], ["e1", "e2"]], "attributes": [{}, {}],
              "start": np.array(["2020-01-01T00", "2020-01-01T01"], dtype="datetime64[us]"),
              "stop": np.array(["2020-01-01T01", "2020-01-01T02"], dtype="datetime64[us]")}
    real, derived = rows_of(arrays)
    assert (real.uuid, real.derived) == ("e1", False)
    assert derived.derived and derived.uuid == rows_of(arrays)[1].uuid and "e1" in derived.uuid
