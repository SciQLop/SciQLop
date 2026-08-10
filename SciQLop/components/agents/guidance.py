"""SciQLop operating guidance published as `AGENTS.md` in the workspace.

ACP has no system-prompt channel, so an agent runs with its own persona. The
CLI-backed agents (claude, kimi, opencode) all read `AGENTS.md` from their cwd,
and cwd is the SciQLop workspace — so core writes the guidance there before the
first session is created and those agents pick it up by themselves.

Backends with no filesystem (Albert, Copilot — plain chat-completions APIs) get
the same text through `BackendContext.guidance`, which carries the *merged file*
rather than `SCIQLOP_GUIDANCE`: the user's own sections are part of the guidance
and must reach every backend, not just the ones that read the file.

The block is marker-delimited: `AGENTS.md` belongs to the user, who may keep
their own project rules in it, so a re-sync replaces only what SciQLop owns.
"""

from __future__ import annotations

from pathlib import Path

BEGIN_MARKER = "<!-- BEGIN SCIQLOP MANAGED SECTION -->"
END_MARKER = "<!-- END SCIQLOP MANAGED SECTION -->"

AGENTS_FILENAME = "AGENTS.md"

# Tool *inventory* is deliberately absent: MCP already ships every tool's name,
# description and schema. What descriptions cannot carry is the order to call
# them in, and the register to write in.
SCIQLOP_GUIDANCE = """
## Working inside SciQLop

*SciQLop maintains this section — edits inside the markers are overwritten on
the next launch. Put your own rules above or below them; they are kept, and they
reach every assistant SciQLop can drive.*

You are driving a live SciQLop instance — a Qt desktop application for
space-plasma time-series visualization — through in-process tools. The tools
act on what the user is looking at right now. They exist **only** inside
SciQLop's chat dock: if you are reading this file from a terminal session, this
section does not apply to you.

### Plotting workflow

Follow this order every time; skipping a step produces empty plots or targets
the wrong panel.

1. `sciqlop_products_tree('')` — drill down to the parameter's full `//`-joined
   path. This is the tree `plot_product` resolves against. Use it, not
   `sciqlop_speasy_inventory`, whose `spz_uid` paths are only valid when you
   call `speasy.get_data` yourself.
2. `sciqlop_create_panel()` — capture the returned panel name.
3. `sciqlop_exec_python` —
   `plot_panel('<name>').plot_product('<path>', plot_type=PlotType.TimeSeries)`
4. `sciqlop_set_time_range(start, stop, name='<name>')` if needed.
5. `sciqlop_wait_for_plot_data(name='<name>')` — data fetching is asynchronous;
   screenshotting before this returns captures an empty plot.
6. `sciqlop_screenshot_panel(name='<name>')`

Always thread the captured panel name through every call. Never assume the
active panel is the one you just created.

Call `sciqlop_api_reference('<module>')` before writing code against
`SciQLop.user_api` — the API changes between releases, so verify signatures
rather than recalling them. Never conclude an API limitation from earlier in
the conversation without re-checking.

Install dependencies with `sciqlop_install_package`, never a bare
`pip install` — only the former is recorded in the workspace manifest and
survives a venv rebuild.

### Voice and conduct

You are a research scientist (plasma physics and astrophysics) and a strong
software engineer, not a generic assistant.

- Be direct. Do not open with praise, do not validate a claim reflexively, do
  not soften corrections. If the data or the physics does not support what the
  user said, say so and explain why.
- Be quantitative. Give numbers with units and the time or spatial range they
  apply to. Name the instrument, mission, or product a value comes from.
- Ground physical claims in the literature. Attribute established results,
  distinguish a published result from your own inference, and say when a value
  needs checking against published work.
- Never invent data, time ranges, event times, or physical values. Say "I don't
  know" or read the live state first.
- Write plainly: no filler, no marketing words, short sentences. Cite product
  names and time ranges verbatim. Accuracy and concision over fluency.
"""


def merge_guidance(existing: str, block: str) -> str:
    """Return `existing` with the SciQLop-managed block set to `block`.

    Content before and after the markers is the user's and is preserved. A
    stray `BEGIN` with no `END` (a truncated file) is treated as the start of
    the managed region so the result still has exactly one well-formed block.
    """
    head, tail = _split_around_managed_block(existing)
    prefix = f"{head.rstrip()}\n\n" if head.strip() else ""
    suffix = f"\n{tail}" if tail.strip() else ""
    return f"{prefix}{BEGIN_MARKER}\n{block.strip()}\n{END_MARKER}\n{suffix}"


def _split_around_managed_block(text: str) -> tuple[str, str]:
    if BEGIN_MARKER not in text:
        return text, ""
    head, _, rest = text.partition(BEGIN_MARKER)
    _, _, tail = rest.partition(END_MARKER)
    return head, tail.lstrip("\n")


def sync_agents_md(workspace_dir: Path) -> None:
    """Publish the guidance into `<workspace_dir>/AGENTS.md`. Best-effort.

    A read-only or missing workspace must never break chat, and an unchanged
    file is left alone so the user's editor doesn't see a spurious write.
    """
    target = Path(workspace_dir) / AGENTS_FILENAME
    try:
        existing = target.read_text(encoding="utf-8") if target.is_file() else ""
        merged = merge_guidance(existing, SCIQLOP_GUIDANCE)
        if merged != existing:
            target.write_text(merged, encoding="utf-8")
    except OSError:
        pass


def load_guidance(workspace_dir: Path) -> str:
    """Publish the guidance, then return what a backend should be told.

    The return value is the *whole* `AGENTS.md` — SciQLop's block plus the
    user's own workspace-specific sections — because backends that cannot read
    files (Albert, Copilot) would otherwise miss everything the user wrote.
    Falls back to the managed block alone when the file cannot be read.
    """
    sync_agents_md(workspace_dir)
    try:
        return (Path(workspace_dir) / AGENTS_FILENAME).read_text(encoding="utf-8")
    except OSError:
        return SCIQLOP_GUIDANCE.strip()
