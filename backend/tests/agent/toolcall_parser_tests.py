"""Tests for the text-based tool-call protocol parser."""

from app.agent.toolcall_parser import (
    has_tool_calls,
    parse_tool_calls,
    strip_tool_blocks,
)

_BLOCK = '```tool\n{"tool": "validate_location", "arguments": {"address": "Denver, CO"}}\n```'


def test_parses_single_tool_block():
    calls = parse_tool_calls(f"Let me look that up.\n{_BLOCK}")
    assert len(calls) == 1
    assert calls[0].name == "validate_location"
    assert calls[0].arguments == {"address": "Denver, CO"}


def test_parses_multiple_independent_blocks():
    text = (
        '```tool\n{"tool": "validate_location", "arguments": {"address": "A"}}\n```\n'
        '```tool\n{"tool": "validate_location", "arguments": {"address": "B"}}\n```'
    )
    calls = parse_tool_calls(text)
    assert [c.arguments["address"] for c in calls] == ["A", "B"]


def test_parses_json_on_same_line_as_tag():
    """The model sometimes puts the JSON on the same line as the ```tool tag
    (no newline). This must still parse and strip — otherwise the raw block
    leaks into the user-facing reply."""
    text = '```tool {"tool": "validate_location", "arguments": {"address": "SLO"}} ```'
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "validate_location"
    assert "```" not in strip_tool_blocks(text)


def test_parses_spaced_language_tag():
    """A space between the fence and the tag (``` tool) must still match."""
    text = '``` tool\n{"tool": "validate_location", "arguments": {"address": "SLO"}}\n```'
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "validate_location"
    assert "```" not in strip_tool_blocks(text)


def test_parses_crlf_line_endings():
    """CRLF (\\r\\n) line endings must not defeat the block match."""
    text = (
        "Prose.\r\n```tool\r\n"
        '{"tool": "validate_location", "arguments": {"address": "SLO"}}\r\n```\r\n'
    )
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "validate_location"
    assert "```" not in strip_tool_blocks(text)


def test_no_block_returns_empty():
    assert parse_tool_calls("Just a normal reply, no tools here.") == []
    assert parse_tool_calls("") == []


def test_malformed_json_is_skipped_not_raised():
    text = "```tool\n{not valid json}\n```"
    assert parse_tool_calls(text) == []


def test_block_without_tool_name_is_skipped():
    text = '```tool\n{"arguments": {"x": 1}}\n```'
    assert parse_tool_calls(text) == []


def test_accepts_name_alias():
    text = '```tool\n{"name": "recall_facts", "arguments": {}}\n```'
    calls = parse_tool_calls(text)
    assert calls[0].name == "recall_facts"


def test_missing_arguments_defaults_to_empty_dict():
    text = '```tool\n{"tool": "recall_facts"}\n```'
    calls = parse_tool_calls(text)
    assert calls[0].arguments == {}


def test_strip_tool_blocks_leaves_prose():
    text = f"Here's what I found.\n{_BLOCK}\nAnything else?"
    stripped = strip_tool_blocks(text)
    assert "```tool" not in stripped
    assert "Here's what I found." in stripped
    assert "Anything else?" in stripped


def test_has_tool_calls():
    assert has_tool_calls(_BLOCK) is True
    assert has_tool_calls("no tools") is False
    assert has_tool_calls("") is False
