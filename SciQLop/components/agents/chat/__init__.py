"""Chat UI primitives: typed message/block model and Qt widgets.

`ChatMessage`, `TextBlock`, `ImageBlock` are the data model shared across
backends. `TranscriptView` renders them with coalesced markdown updates;
`ChatInput` handles image paste into a dock-owned tempdir.
"""
from ._images import write_b64_image
from .view import (
    ChatInput,
    ChatMessage,
    ImageBlock,
    TextBlock,
    TranscriptView,
)

__all__ = [
    "ChatInput",
    "ChatMessage",
    "ImageBlock",
    "TextBlock",
    "TranscriptView",
    "write_b64_image",
]
