from PySide6.QtCore import QMimeData, QByteArray, QDataStream, QIODevice
from typing import Any, Callable, Dict, List

_MIME_ENCODERS_: Dict[type, Callable[[Any], QMimeData] or Dict[type, Callable[[Any], QMimeData]]] = {list: {}}
_MIME_DECODERS_: Dict[str, Callable[[QMimeData], Any]] = {"": lambda _: None}


def register_mime(obj_type: type, mime_type: str, encoder: Callable[[Any], QMimeData],
                  decoder: Callable[[QMimeData], Any],
                  nested_type: type = None):
    if obj_type is list:
        _MIME_ENCODERS_[obj_type][nested_type] = encoder
    else:
        _MIME_ENCODERS_[obj_type] = encoder
    _MIME_DECODERS_[mime_type] = decoder


def encode(data: Any) -> QByteArray:
    ba = QByteArray()
    ds = QDataStream(ba, QIODevice.WriteOnly)
    ds << data
    return ba


def decode(data: QByteArray) -> Any:
    ds = QDataStream(data, QIODevice.ReadOnly)
    decoded = ds.readQVariant()
    return decoded


def encode_mime(object_to_encode: Any) -> QMimeData:
    if type(object_to_encode) is list:
        if len(object_to_encode):
            return _MIME_ENCODERS_[type(object_to_encode)][type(object_to_encode[0])](object_to_encode)
    else:
        return _MIME_ENCODERS_[type(object_to_encode)](object_to_encode)


def decode_mime(mime_data: QMimeData, preferred_formats: List[str] = None) -> Any:
    if preferred_formats is not None:
        for f in preferred_formats:
            if mime_data.hasFormat(f):
                return _MIME_DECODERS_[f](mime_data)
    for f in mime_data.formats():
        if f in _MIME_DECODERS_:
            return _MIME_DECODERS_[f](mime_data)
    return None

def _register_product_list_decoder():
    from .types import PRODUCT_LIST_MIME_TYPE
    from  SciQLopPlots import ProductsModel
    _MIME_DECODERS_[PRODUCT_LIST_MIME_TYPE] = ProductsModel.decode_mime_data

_register_product_list_decoder()


def _register_time_range_codec():
    """TIME_RANGE_MIME_TYPE (declared in types.py, accepted by
    TimeRangeDnDCallback on every plot panel) had no producer and no
    registered decoder anywhere -- dropping anything tagged with it was a
    guaranteed no-op. Registered here, matching _register_product_list_decoder,
    so any future drag source can just encode_mime(a TimeRange)."""
    import json
    from .types import TIME_RANGE_MIME_TYPE
    from SciQLop.core.time_range import TimeRange

    def _encode(tr) -> QMimeData:
        md = QMimeData()
        md.setData(TIME_RANGE_MIME_TYPE,
                  json.dumps({"start": tr.start(), "stop": tr.stop()}).encode("utf-8"))
        return md

    def _decode(mime_data: QMimeData):
        raw = bytes(mime_data.data(TIME_RANGE_MIME_TYPE))
        if not raw:
            return None
        payload = json.loads(raw.decode("utf-8"))
        return TimeRange(payload["start"], payload["stop"])

    register_mime(TimeRange, TIME_RANGE_MIME_TYPE, _encode, _decode)

_register_time_range_codec()