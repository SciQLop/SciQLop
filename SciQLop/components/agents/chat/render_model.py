"""Turn a chat transcript into a JSON-serialisable model for the web
transcript renderer (`web_view.py`). Also home to the tool-call preview
helpers shared with the native `TranscriptView` (`view.py` imports them back
lazily, see `activity_group_html`), so both renderers show identical previews.
"""
from __future__ import annotations

import base64
import json as _json
from typing import Dict, List, Optional, Set

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

from .view import ChatMessage, ImageBlock, TextBlock, ThinkingBlock, ToolActivityBlock

_IMAGE_MAX_WIDTH_PX = 720
_RESULT_PREVIEW_CAP = 200


def input_one_line(tool_input: dict, cap: int = 80) -> str:
    """A compact single-line preview of a tool call's arguments."""
    if not tool_input:
        return ""
    parts = []
    for k, v in tool_input.items():
        sval = v if isinstance(v, str) else _json.dumps(v, default=str)
        sval = " ".join(str(sval).split())
        parts.append(f"{k}={sval}")
    s = ", ".join(parts)
    return s if len(s) <= cap else s[: cap - 1] + "…"


def result_preview(result: str, cap: int = _RESULT_PREVIEW_CAP) -> str:
    """A truncated single-block preview of a tool call's result."""
    res = result.strip()
    return res if len(res) <= cap else res[: cap - 1] + "…"


def _image_data_url(path: str) -> Optional[str]:
    image = QImage(path)
    if image.isNull():
        return None
    if image.width() > _IMAGE_MAX_WIDTH_PX:
        image = image.scaledToWidth(
            _IMAGE_MAX_WIDTH_PX, Qt.TransformationMode.SmoothTransformation)
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.data().data()).decode()


def _tool_step(block: ToolActivityBlock, verbosity: int) -> dict:
    input_preview = input_one_line(block.tool_input) if verbosity >= 2 else ""
    result = result_preview(block.result) if verbosity >= 3 and block.result else ""
    return {
        "name": block.tool_name,
        "input": input_preview or None,
        "result": result or None,
    }


def _tools_part(run: List[ToolActivityBlock], verbosity: int,
                expanded: Set[str], running: bool) -> dict:
    group_id = run[0].id
    return {
        "type": "tools",
        "id": group_id,
        "expanded": group_id in expanded,
        "running": running,
        "steps": [_tool_step(block, verbosity) for block in run],
    }


def _message_parts(message: ChatMessage, verbosity: int, expanded: Set[str]) -> List[dict]:
    parts: List[dict] = []
    blocks = message.blocks
    running = not message.done
    i = 0
    while i < len(blocks):
        block = blocks[i]
        if isinstance(block, ToolActivityBlock):
            run = []
            while i < len(blocks) and isinstance(blocks[i], ToolActivityBlock):
                run.append(blocks[i])
                i += 1
            parts.append(_tools_part(run, verbosity, expanded, running))
            continue
        if isinstance(block, TextBlock):
            if block.text:
                parts.append({"type": "text", "markdown": block.text})
        elif isinstance(block, ThinkingBlock):
            if block.text:
                parts.append({"type": "thinking", "text": block.text})
        elif isinstance(block, ImageBlock):
            data_url = _image_data_url(block.path)
            if data_url is None:
                parts.append({"type": "text", "markdown": "*[missing image]*"})
            else:
                parts.append({"type": "image", "data_url": data_url})
        i += 1
    return parts


def transcript_model(messages: List[ChatMessage], *, verbosity: int,
                     expanded: Set[str], role_labels: Dict[str, str]) -> List[dict]:
    return [
        {
            "role": message.role,
            "label": role_labels.get(message.role, message.role),
            "done": message.done,
            "parts": _message_parts(message, verbosity, expanded),
        }
        for message in messages
    ]
