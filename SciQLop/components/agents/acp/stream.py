"""Translate ACP session updates into SciQLop chat StreamBlocks.

Chunks are already incremental deltas; they forward as incomplete blocks,
closed when the other kind interrupts or the turn ends. ToolCallStart yields
the activity block; ToolCallProgress with content yields a result-only
activity block the dock merges by tool_call_id, plus ImageBlocks for inline
screenshots.

Note: chunks are deltas on the wire for both kimi and opencode (verified
2026-08-10 against `opencode acp` 1.18.15 — the accumulation the old
opencode-agent-sdk exposed was its own `_text_buffer`, not the protocol). An
agent that ever streams *accumulated snapshots* needs a diffing translator —
subclass or wrap this one rather than piling a mode flag in here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Tuple

from ..backend import StreamBlock
from ..chat import (
    ImageBlock,
    TextBlock,
    ThinkingBlock,
    ToolActivityBlock,
    write_b64_image,
)

try:
    from acp.schema import (
        AgentMessageChunk,
        AgentThoughtChunk,
        ToolCallProgress,
        ToolCallStart,
    )
    _ACP_AVAILABLE = True
except Exception:  # pragma: no cover
    _ACP_AVAILABLE = False

    class AgentMessageChunk:  # type: ignore[no-redef]
        pass

    class AgentThoughtChunk:  # type: ignore[no-redef]
        pass

    class ToolCallProgress:  # type: ignore[no-redef]
        pass

    class ToolCallStart:  # type: ignore[no-redef]
        pass


class AcpStreamTranslator:
    """Feed it session updates; it yields the blocks to append to the chat."""

    def __init__(self, tempdir: Path):
        self._tempdir = tempdir
        self._open: Optional[type] = None  # TextBlock | ThinkingBlock | None

    def feed(self, update) -> List[StreamBlock]:
        if isinstance(update, AgentMessageChunk):
            return [self._switch(TextBlock),
                    TextBlock(text=update.content.text, complete=False)]
        if isinstance(update, AgentThoughtChunk):
            return [self._switch(ThinkingBlock),
                    ThinkingBlock(text=update.content.text, complete=False)]
        if isinstance(update, ToolCallStart):
            return [self._close(),
                    ToolActivityBlock(
                        tool_name=str(update.title or "").split("__")[-1],
                        tool_input=raw_input_dict(update.raw_input),
                        tool_use_id=update.tool_call_id or "",
                    )]
        if isinstance(update, ToolCallProgress):
            blocks: List[StreamBlock] = []
            text, images = tool_output(update)
            for data, mime in images:
                path = write_b64_image(data, mime, self._tempdir, prefix="tool")
                if path:
                    blocks.append(ImageBlock(path=path))
            if text:
                blocks.append(ToolActivityBlock(
                    tool_use_id=update.tool_call_id or "", result=text))
            return blocks
        return []

    def flush(self) -> List[StreamBlock]:
        return [self._close()]

    def _switch(self, kind: type) -> Optional[StreamBlock]:
        closing = None
        if self._open is not None and self._open is not kind:
            closing = self._close()
        self._open = kind
        return closing

    def _close(self) -> Optional[StreamBlock]:
        if self._open is not None:
            cls = self._open
            self._open = None
            return cls(text="", complete=True)
        return None


def raw_input_dict(raw_input: Any) -> dict:
    return raw_input if isinstance(raw_input, dict) else {}


def tool_output(update) -> Tuple[str, List[Tuple[str, str]]]:
    """Extract (text, [(b64 data, mime)]) from a ToolCallProgress update."""
    texts: List[str] = []
    images: List[Tuple[str, str]] = []
    for content in update.content or []:
        inner = getattr(content, "content", None)
        items = inner if isinstance(inner, list) else [inner]
        for item in items:
            if item is None:
                continue
            text = getattr(item, "text", None)
            if text is not None:
                texts.append(text)
                continue
            data = getattr(item, "data", None)
            if data is not None:
                images.append((data, getattr(item, "mime_type", None) or "image/png"))
    raw = update.raw_output
    if not texts and isinstance(raw, str):
        texts.append(raw)
    return "\n".join(t for t in texts if t), images
