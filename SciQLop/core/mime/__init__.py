from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from PySide6.QtCore import QByteArray, QDataStream, QIODevice, QMimeData

from SciQLop.core.extensions import ExtensionPoint, declare


@dataclass(frozen=True)
class MimeType:
    id: str
    decoder: Callable[[QMimeData], Any]
    encoder: Optional[Callable[[Any], QMimeData]] = None
    obj_type: Optional[type] = None
    nested_type: Optional[type] = None


MIME_TYPES = declare(ExtensionPoint("sciqlop.mime_types", MimeType, what="MIME type",
                                    doc="Drag-and-drop payloads: how each MIME type is encoded and decoded."))


def register_mime(obj_type: type, mime_type: str, encoder: Callable[[Any], QMimeData],
                  decoder: Callable[[QMimeData], Any], nested_type: type = None, owner: str = None):
    MIME_TYPES.contribute(MimeType(mime_type, decoder, encoder, obj_type, nested_type), owner=owner, replace=True)


def encode(data: Any) -> QByteArray:
    ba = QByteArray()
    ds = QDataStream(ba, QIODevice.WriteOnly)
    ds << data
    return ba


def decode(data: QByteArray) -> Any:
    ds = QDataStream(data, QIODevice.ReadOnly)
    decoded = ds.readQVariant()
    return decoded


def _encoder_key(obj) -> tuple:
    return (list, type(obj[0])) if type(obj) is list else (type(obj), None)


def encode_mime(object_to_encode: Any) -> QMimeData:
    if type(object_to_encode) is list and not object_to_encode:
        return None
    key = _encoder_key(object_to_encode)
    found = next((m for m in MIME_TYPES.list() if m.encoder and (m.obj_type, m.nested_type) == key), None)
    if found is None:
        raise KeyError(f"no MIME type encodes {key[0].__name__}")
    return found.encoder(object_to_encode)


def decode_mime(mime_data: QMimeData, preferred_formats: List[str] = None) -> Any:
    for f in [*(preferred_formats or []), *mime_data.formats()]:
        if f in MIME_TYPES and mime_data.hasFormat(f):
            return MIME_TYPES.get(f).decoder(mime_data)
    return None


def _register_product_list_decoder():
    from .types import PRODUCT_LIST_MIME_TYPE
    from SciQLopPlots import ProductsModel
    MIME_TYPES.contribute(MimeType(PRODUCT_LIST_MIME_TYPE, ProductsModel.decode_mime_data), owner="sciqlop")


_register_product_list_decoder()


def tree_product_path(raw: str) -> str:
    """A products-tree MIME path (``root//a//b``) as a product path (``a//b``).

    Keeps ``//`` separators so ``to_product_path`` can split unambiguously even when a product's display
    name contains ``/`` (AMDA's ``"final / prelim"`` is why single-slash paths were dropped).
    """
    return raw[len("root//"):] if raw.startswith("root//") else raw


def _register_time_range_codec():
    """TIME_RANGE_MIME_TYPE (declared in types.py, accepted by
    TimeRangeDnDCallback on every plot panel) had no producer and no
    registered decoder anywhere -- dropping anything tagged with it was a
    guaranteed no-op. Registered here, matching _register_product_list_decoder,
    so any future drag source can just encode_mime(a TimeRange)."""
    import json
    import math
    from .types import TIME_RANGE_MIME_TYPE
    from SciQLop.core.time_range import TimeRange

    def _encode(tr) -> QMimeData:
        # allow_nan=False: this codec is a generic, shared registration --
        # any future drag source can produce this MIME type, and NaN/
        # Infinity are non-standard JSON tokens a non-Python consumer
        # couldn't even parse.
        md = QMimeData()
        md.setData(TIME_RANGE_MIME_TYPE,
                  json.dumps({"start": tr.start(), "stop": tr.stop()}, allow_nan=False).encode("utf-8"))
        return md

    def _decode(mime_data: QMimeData):
        # Decoding is the untrusted-input side: a malformed or foreign
        # payload tagged with this MIME type must return None (matching
        # decode_event_list's contract), not raise out of a drop callback.
        raw = bytes(mime_data.data(TIME_RANGE_MIME_TYPE))
        if not raw:
            return None
        try:
            payload = json.loads(raw.decode("utf-8"))
            start, stop = payload["start"], payload["stop"]
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError):
            return None
        if not isinstance(start, (int, float)) or not isinstance(stop, (int, float)):
            return None
        if not (math.isfinite(start) and math.isfinite(stop)):
            return None
        return TimeRange(start, stop)

    register_mime(TimeRange, TIME_RANGE_MIME_TYPE, _encode, _decode, owner="sciqlop")

_register_time_range_codec()