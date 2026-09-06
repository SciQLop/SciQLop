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
