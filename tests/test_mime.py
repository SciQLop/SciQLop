import pytest

from SciQLop.core.mime import encode, decode


def test_can_encode_and_decode():
    assert decode(encode(["a", "b"])) == ["a", "b"]


def test_time_range_mime_codec_is_registered(qapp):
    """TIME_RANGE_MIME_TYPE was declared and accepted by every plot panel's
    TimeRangeDnDCallback, but had no producer and no registered decoder
    anywhere -- decode_mime(mime_data) always returned None for it, so
    dropping anything tagged with this MIME type was a silent no-op
    (2026-09-06 review, part of the catalog event drag-to-plot fix)."""
    from SciQLop.core.mime import encode_mime, decode_mime
    from SciQLop.core.mime.types import TIME_RANGE_MIME_TYPE
    from SciQLop.core.time_range import TimeRange

    tr = TimeRange(1000.0, 2000.0)
    md = encode_mime(tr)
    assert md.hasFormat(TIME_RANGE_MIME_TYPE)

    decoded = decode_mime(md)
    assert decoded.start() == 1000.0
    assert decoded.stop() == 2000.0


def test_time_range_encode_rejects_non_finite_values(qapp):
    """A newly-shared, generic codec (any future drag source can produce
    this MIME type) must not silently emit non-standard JSON tokens
    (NaN/Infinity) that a non-Python consumer couldn't even parse."""
    import math
    from SciQLop.core.mime import encode_mime
    from SciQLop.core.time_range import TimeRange

    with pytest.raises(ValueError):
        encode_mime(TimeRange(math.nan, 2000.0))
    with pytest.raises(ValueError):
        encode_mime(TimeRange(1000.0, math.inf))


def test_time_range_decode_rejects_malformed_payload(qapp):
    """Decoding is the untrusted-input side (any drag source can produce
    this MIME type): malformed/non-finite payloads must return None, like
    decode_event_list does for garbage, not raise out of a drop callback."""
    import json
    from PySide6.QtCore import QMimeData
    from SciQLop.core.mime import decode_mime
    from SciQLop.core.mime.types import TIME_RANGE_MIME_TYPE

    def _mime_with(raw: bytes) -> QMimeData:
        md = QMimeData()
        md.setData(TIME_RANGE_MIME_TYPE, raw)
        return md

    assert decode_mime(_mime_with(b"not json")) is None
    assert decode_mime(_mime_with(json.dumps({"start": 1.0}).encode())) is None
    assert decode_mime(_mime_with(json.dumps({"start": "a", "stop": 2.0}).encode())) is None
    assert decode_mime(_mime_with(json.dumps({"start": float("nan"), "stop": 2.0}).encode())) is None
    assert decode_mime(_mime_with(b"")) is None


def test_time_range_dnd_callback_ignores_undecodable_drop(qapp):
    """opencode review: the callback called plot.time_axis().set_range(None)
    unconditionally on a decode failure -- a malformed/foreign payload
    tagged with TIME_RANGE_MIME_TYPE must be a no-op, not a call into the
    plotting layer with None."""
    from unittest.mock import MagicMock
    from PySide6.QtCore import QMimeData
    from SciQLop.components.plotting.ui.time_sync_panel import TimeRangeDnDCallback
    from SciQLop.core.mime.types import TIME_RANGE_MIME_TYPE

    callback = TimeRangeDnDCallback(None)
    plot = MagicMock()
    bad_mime = QMimeData()
    bad_mime.setData(TIME_RANGE_MIME_TYPE, b"not json")

    callback.call(plot, bad_mime)

    plot.time_axis().set_range.assert_not_called()
