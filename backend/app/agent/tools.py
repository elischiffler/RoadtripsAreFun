"""Contract 3 — Tool interface (agent loop <-> existing capabilities), §5.

Stream A provides only the interface the loop depends on: the tool primitive
models, a :class:`ToolContext`, and the :class:`ToolDispatcher` Protocol. The
real dispatcher that wraps existing app capabilities (routing / itinerary /
location / car / memory) is a separate stream (Stream A-tools); tests inject a
fake dispatcher.

The primitives :class:`ToolSpec`, :class:`ToolCall`, and :class:`ToolResult`
physically live in :mod:`app.agent.schemas` (they are also referenced by the
provider message models, and keeping them in one low-level module avoids an
import cycle). They are re-exported here so the doc's ``tools.py`` surface is
preserved — import them from either module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

# Re-export the shared primitives so callers can import them from tools.py
# (per the design doc §5) or from schemas.py (where they physically live).
from app.agent.schemas import ToolCall, ToolResult, ToolSpec

if TYPE_CHECKING:  # avoid importing the memory module at runtime just for typing
    from app.agent.memory import MemoryStore

__all__ = [
    "ToolSpec",
    "ToolCall",
    "ToolResult",
    "ToolContext",
    "ToolDispatcher",
    "ArtifactStore",
]


class ArtifactStore:
    """A per-turn store for heavy objects the LLM must NOT carry in its context.

    Tools that produce large payloads (a full Mapbox route, a planned ``Route``)
    stash the real object here and hand the model a short **handle** string
    (e.g. ``"initial_route_1"``). A downstream tool that needs the object takes
    the handle back and resolves it. This keeps multi-kilobyte geometry out of
    the message history (which otherwise blows the gateway's request-size limit),
    while the frontend still receives the full payload via ``action.payload``.

    Lifetime is a single ``run_turn`` — a fresh store per turn, discarded after.
    """

    def __init__(self) -> None:
        self._items: dict[str, Any] = {}
        self._counters: dict[str, int] = {}

    def put(self, kind: str, obj: Any) -> str:
        """Store ``obj`` under a new handle namespaced by ``kind``; return the handle."""
        self._counters[kind] = self._counters.get(kind, 0) + 1
        handle = f"{kind}_{self._counters[kind]}"
        self._items[handle] = obj
        return handle

    def get(self, handle: str) -> Any:
        """Resolve a handle to its stored object.

        Raises:
            KeyError: if the handle is unknown (surfaced by dispatch as a
                readable tool error so the model can recover).
        """
        if handle not in self._items:
            raise KeyError(
                f"Unknown artifact handle {handle!r}. "
                f"Known handles: {sorted(self._items) or 'none'}."
            )
        return self._items[handle]

    def has(self, handle: str) -> bool:
        return handle in self._items


@dataclass
class ToolContext:
    """Scope + injected dependencies a tool needs to read/write correctly.

    Carries the resolved ``user_id`` and ``chat_id`` so tools act on the right
    scope, the injected ``memory`` store, and a per-turn :class:`ArtifactStore`
    so tools can pass heavy objects to each other by handle without routing them
    through the LLM's context.
    """

    user_id: str
    chat_id: str
    memory: MemoryStore | None = None
    artifacts: ArtifactStore = field(default_factory=ArtifactStore)


@runtime_checkable
class ToolDispatcher(Protocol):
    """Maps tool name + arguments to a callable and returns a serializable result.

    Tool failures are captured as ``ToolResult(ok=False, error=...)`` — never
    raised — so the agent loop can feed the error back to the model.
    """

    def specs(self) -> list[ToolSpec]:
        """The tools advertised to the model."""
        ...

    async def dispatch(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
        """Execute one tool call within ``ctx`` and return its result.

        ``dispatch`` is async because the real tools wrap inherently I/O-bound
        capabilities (Mapbox / TripAdvisor / planner / car data), several of
        which are already ``async``. The agent loop (``run_turn``) awaits it.
        """
        ...
