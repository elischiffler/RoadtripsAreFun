"""Conversational chat agent package.

A tool-using LLM assistant layered on top of the existing trip-planning
workflow. See ``docs/chat-agent-design.md`` for the frozen contracts. This
package is Stream A (endpoint + providers + loop): everything is built against
injected interfaces (providers, memory, tools) so the loop is testable with
fakes — no network, no DB.
"""
