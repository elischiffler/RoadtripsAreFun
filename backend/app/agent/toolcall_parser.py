"""Text-based tool-call protocol parser.

The Mentro gateway is a plain chat-completion passthrough with **no native
function-calling** — ``LLMResponse.tool_calls`` is always empty. To let the model
still invoke tools, we use a text protocol: the model emits tool requests as
fenced ```tool blocks containing JSON, and this module extracts them from the
reply text.

Protocol (documented to the model in ``prompt.py``):

    ```tool
    {"tool": "validate_location", "arguments": {"address": "Denver, CO"}}
    ```

- Zero or more blocks may appear in one reply.
- Anything outside the blocks is the assistant's natural-language content (shown
  to the user or used as the final reply once no tool blocks remain).
- Malformed JSON inside a block is skipped (and reported) rather than raising —
  a flaky model shouldn't crash the turn.

This module is intentionally the *only* place that knows the wire format, so the
agent loop stays format-agnostic and the protocol can evolve in one file.
"""

from __future__ import annotations

import json
import logging
import re

from app.agent.schemas import ToolCall

logger = logging.getLogger(__name__)

# Matches a fenced ```tool ... ``` block, tolerant of the ways models actually
# emit it:
#   - an optional space between the fence and the tag (``` tool)
#   - the JSON on the SAME line as the tag OR on the next line
#   - CRLF or LF line endings
# The tag is followed by ``\s*`` (any whitespace, incl. a newline) rather than a
# mandatory ``\n``, so a same-line block still parses. Body is captured
# non-greedily and DOTALL so it may span lines without merging adjacent blocks.
_TOOL_BLOCK = re.compile(r"```[ \t]*tool[ \t]*\r?\n?(.*?)```", re.DOTALL | re.IGNORECASE)


def parse_tool_calls(text: str) -> list[ToolCall]:
    """Extract tool calls from a model reply.

    Args:
        text: The assistant's raw content.

    Returns:
        A list of :class:`ToolCall` (possibly empty). Blocks whose JSON is
        malformed, or that lack a string ``tool`` name, are skipped with a
        warning — never raised.
    """
    if not text:
        return []
    calls: list[ToolCall] = []
    for match in _TOOL_BLOCK.finditer(text):
        body = match.group(1).strip()
        if not body:
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            logger.warning("tool-call parse: skipping malformed JSON block: %s", exc)
            continue
        name = payload.get("tool") or payload.get("name")
        if not isinstance(name, str) or not name:
            logger.warning("tool-call parse: block missing a string 'tool' name: %r", payload)
            continue
        arguments = payload.get("arguments")
        if not isinstance(arguments, dict):
            arguments = {}
        calls.append(ToolCall(name=name, arguments=arguments))
    return calls


def strip_tool_blocks(text: str) -> str:
    """Remove ```tool blocks from ``text``, returning the prose that remains.

    Used to derive the user-facing message from a reply that also contained tool
    calls (so the raw JSON is never shown to the traveler).
    """
    if not text:
        return ""
    return _TOOL_BLOCK.sub("", text).strip()


def has_tool_calls(text: str) -> bool:
    """True if ``text`` contains at least one ```tool block."""
    return bool(text) and _TOOL_BLOCK.search(text) is not None
