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
