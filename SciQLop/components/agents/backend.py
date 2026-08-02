"""Agent backend protocol — contract a chat-capable plugin implements."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    List,
    Optional,
    Protocol,
    Tuple,
    runtime_checkable,
)

from .chat import ChatMessage, ImageBlock, TextBlock, ThinkingBlock, ToolActivityBlock

StreamBlock = TextBlock | ThinkingBlock | ImageBlock | ToolActivityBlock
ConfirmCallback = Callable[[str, dict], Awaitable[bool]]
# questions: list of {question, header, options:[{label, description}], multiSelect}
# returns: {question_text: chosen_label | [chosen_labels]}
AskQuestionCallback = Callable[[list], Awaitable[dict]]


@dataclass
class BackendContext:
    main_window: Any
    tools: List[dict]
    tempdir: Path
    confirm_cb: ConfirmCallback
    allow_writes: bool = False
    ask_question_cb: Optional[AskQuestionCallback] = None


@dataclass
class SessionEntry:
    id: str
    label: str
    mtime: float


@dataclass(frozen=True)
class TokenCounts:
    """Token usage for a session. All fields optional — backends differ."""
    input: Optional[int] = None
    output: Optional[int] = None
    cache_read: Optional[int] = None
    cache_write: Optional[int] = None
    reasoning: Optional[int] = None

    @property
    def total(self) -> Optional[int]:
        # cache_read/cache_write are excluded on purpose: providers disagree on
        # whether cached tokens are already inside input_tokens, so summing them
        # would double-count on some backends.
        known = [v for v in (self.input, self.output) if v is not None]
        return sum(known) if known else None


@dataclass(frozen=True)
class Cost:
    """Session cost. `unit` is "USD" for real currency, or a backend-specific
    unit such as "credits" (Copilot bills in nano-AIU, not currency)."""
    amount: float
    unit: str = "USD"


@dataclass(frozen=True)
class Quota:
    """One allowance window — a Claude rate-limit window, Copilot premium
    requests, an Albert budget.

    `percent_remaining` is the canonical figure because Copilot reports it
    natively; displays that want consumption use `percent_used`.
    """
    label: str
    percent_remaining: Optional[float] = None
    remaining: Optional[float] = None
    entitlement: Optional[float] = None
    unlimited: bool = False
    resets_at: Optional[float] = None      # unix epoch seconds

    @property
    def percent_used(self) -> Optional[float]:
        if self.percent_remaining is None:
            return None
        return 100.0 - self.percent_remaining


@dataclass(frozen=True)
class CarbonFootprint:
    """Environmental impact of a request. Albert (OpenGateLLM) only."""
    kwh: Optional[float] = None
    kg_co2eq: Optional[float] = None


@dataclass(frozen=True)
class ContextCategory:
    """One row of a context-window breakdown (system prompt, MCP tools, …)."""
    name: str
    tokens: int


@dataclass(frozen=True)
class UsageSnapshot:
    """What a backend knows about the live session, as of now.

    Every field is optional and independently rendered: a backend that reports
    only tokens still produces a useful strip.
    """
    model: Optional[str] = None
    tokens: Optional[TokenCounts] = None
    cost: Optional[Cost] = None
    context_tokens: Optional[int] = None
    context_max: Optional[int] = None
    context_categories: Tuple[ContextCategory, ...] = ()
    # a tuple, not one entry: Claude reports a 5-hour AND a weekly window, and
    # Copilot reports chat/completions/premium-interactions separately.
    quotas: Tuple[Quota, ...] = ()
    carbon: Optional[CarbonFootprint] = None
    num_turns: Optional[int] = None
    duration_api_ms: Optional[int] = None
    session_id: Optional[str] = None

    @property
    def context_percent(self) -> Optional[float]:
        if not self.context_max or self.context_tokens is None:
            return None
        return 100.0 * self.context_tokens / self.context_max


@runtime_checkable
class UsageReportingBackend(Protocol):
    """OPTIONAL companion to `AgentBackend` — implement any subset.

    Never fold these into `AgentBackend`: that protocol describes the *required*
    contract, and backends without usage reporting are still perfectly valid.
    The dock probes each member with `getattr`.
    """

    async def usage_snapshot(self) -> Optional[UsageSnapshot]:
        """Current session usage. May do I/O. Returns None when unavailable."""
        ...

    def effort_values(self) -> Tuple[str, ...]:
        """Effort levels accepted for the CURRENTLY selected model.

        Empty tuple means the backend cannot vary effort. Lives here rather than
        in core because the valid set is a join of two things only the backend
        knows: what its SDK accepts on the wire, and what the model supports.
        """
        ...

    async def set_effort(self, effort: Optional[str]) -> None:
        """Select an effort level. None restores the backend default."""
        ...


@runtime_checkable
class AgentBackend(Protocol):
    display_name: str
    model_choices: List[Tuple[str, Optional[str]]]
    supports_sessions: bool

    def ask(
        self, prompt: str, image_paths: Optional[List[str]] = None
    ) -> AsyncIterator[StreamBlock]:
        ...

    async def reset(self) -> None:
        ...

    async def cancel(self) -> None:
        ...

    async def resume(self, session_id: str) -> None:
        ...

    async def set_model(self, model: Optional[str]) -> None:
        ...

    def set_allow_writes(self, allow: bool) -> None:
        ...

    async def list_slash_commands(self) -> List[str]:
        ...

    def list_sessions(self) -> List[SessionEntry]:
        ...

    def load_session(self, session_id: str, image_tempdir: Path) -> List[ChatMessage]:
        ...
