"""MIME types are contributions to sciqlop.mime_types; register_mime/encode_mime/decode_mime keep working."""
from dataclasses import dataclass

import pytest
from PySide6.QtCore import QMimeData

from SciQLop.core.extensions import owned_by
from SciQLop.core.mime import MIME_TYPES, MimeType, decode_mime, encode_mime, register_mime
from SciQLop.core.mime.types import (CATALOG_LIST_MIME_TYPE, EVENT_LIST_MIME_TYPE, PRODUCT_LIST_MIME_TYPE,
                                     TIME_RANGE_MIME_TYPE)


@dataclass(frozen=True)
class _Thing:
    label: str


_THING_MIME = "application/x.mime-ep-test.thing"


@pytest.fixture
def withdraw(qapp):
    yield
    MIME_TYPES.remove_owner("mt_demo")


def test_core_mime_types_are_owned_by_sciqlop(qapp):
    import SciQLop.components.catalogs.backend.catalog_mime  # noqa: F401
    import SciQLop.components.catalogs.backend.event_mime  # noqa: F401
    for mime in (TIME_RANGE_MIME_TYPE, PRODUCT_LIST_MIME_TYPE, CATALOG_LIST_MIME_TYPE, EVENT_LIST_MIME_TYPE):
        assert MIME_TYPES.owner_of(mime) == "sciqlop", mime


def test_a_plugin_mime_type_round_trips(withdraw):
    def encode(thing):
        md = QMimeData()
        md.setData(_THING_MIME, thing.label.encode())
        return md

    with owned_by("mt_demo"):
        MIME_TYPES.contribute(MimeType(_THING_MIME, lambda md: _Thing(bytes(md.data(_THING_MIME)).decode()),
                                       encode, obj_type=_Thing))
    assert decode_mime(encode_mime(_Thing("vdf"))) == _Thing("vdf")
    assert MIME_TYPES.owner_of(_THING_MIME) == "mt_demo"


def test_register_mime_replaces_and_takes_an_owner(withdraw):
    register_mime(_Thing, _THING_MIME, lambda t: QMimeData(), lambda md: "first", owner="mt_demo")
    register_mime(_Thing, _THING_MIME, lambda t: QMimeData(), lambda md: "second", owner="mt_demo")
    md = QMimeData()
    md.setData(_THING_MIME, b"x")
    assert decode_mime(md) == "second"


def test_unknown_formats_decode_to_none(qapp):
    md = QMimeData()
    md.setData("application/x.nobody", b"x")
    assert decode_mime(md) is None
    assert decode_mime(md, preferred_formats=["application/x.nobody"]) is None


def test_empty_list_encodes_to_none(qapp):
    assert encode_mime([]) is None
