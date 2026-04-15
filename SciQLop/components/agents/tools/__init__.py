"""SciQLop tool surface exposed to LLM agents.

`build_sciqlop_tools(main_window)` returns the canonical list of tools
(read-only + write-gated) in a dict format that any agent backend can map
to its own SDK's tool shape. Tool handlers run on the Qt main thread via
`SciQLop.user_api.threading.on_main_thread`; callers only need to await
the result.
"""
from ._builder import build_sciqlop_tools

__all__ = ["build_sciqlop_tools"]
