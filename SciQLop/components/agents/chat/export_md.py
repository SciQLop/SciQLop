"""Serialize a chat transcript (list of ChatMessage) to Markdown.

Pure rendering of the in-memory message/block model, so a saved .md mirrors the
in-app transcript: role headings, assistant text as-is, thinking as a blockquote,
images as links, and (when present) tool activity as a collapsible ``<details>``
block that renders nicely on GitHub and other Markdown viewers.
"""
from __future__ import annotations

from typing import Any, List

from .view import (
    ChatMessage,
    ImageBlock,
    TextBlock,
    ThinkingBlock,
    ToolActivityBlock,
)
from .render_model import input_one_line

_ROLE = {"user": "You", "assistant": "Claude", "error": "Error"}


def _block_md(block: Any) -> List[str]:
    if isinstance(block, ThinkingBlock):
        text = (block.text or "").strip()
        if not text:
            return []
        return ["> " + line for line in text.splitlines()]
    if isinstance(block, TextBlock):
        return [(block.text or "").rstrip()]
    if isinstance(block, ImageBlock):
        return [f"![image]({block.path})"]
    if isinstance(block, ToolActivityBlock):
        line = f"- 🔧 `{block.tool_name}`"
        preview = input_one_line(block.tool_input, cap=120)
        if preview:
            line += f" · {preview}"
        out = [line]
        if block.result:
            out.append(f"  - ↳ {block.result.strip()[:200]}")
        return out
    return []


def transcript_to_markdown(messages: List[ChatMessage], title: str = "SciQLop chat") -> str:
    lines: List[str] = [f"# {title}", ""]
    for msg in messages:
        role = _ROLE.get(getattr(msg, "role", ""), getattr(msg, "role", "?"))
        lines.append(f"## {role}")
        lines.append("")
        for block in getattr(msg, "blocks", []) or []:
            rendered = _block_md(block)
            if rendered:
                lines.extend(rendered)
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"
