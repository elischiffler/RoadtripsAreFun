"""Run inside the real API image on Mentro's isolated pilot network.

This injects only disposable Auth into the existing provider seam, never into
the API's authentication boundary. No database or external service is touched.
"""

import argparse
import json
import time

from app.agent.providers import MentroGatewayProvider, ProviderError
from app.agent.schemas import LLMMessage
from app.agent.toolcall_parser import parse_tool_calls

parser = argparse.ArgumentParser()
parser.add_argument("--expect-down", action="store_true")
args = parser.parse_args()


class FixtureAuth:
    def configured(self):
        return True

    def get_token(self):
        return "local-fixture-token"


provider = MentroGatewayProvider(
    gateway_url="http://mentro-server:3001", auth=FixtureAuth()
)
start = time.monotonic()
try:
    response = provider.complete(
        [LLMMessage(role="user", content="[fixture:text-tool]")], tools=[]
    )
except ProviderError:
    elapsed = time.monotonic() - start
    if not args.expect_down or elapsed > 15:
        raise
    print(json.dumps({"status": "expected_dependency_error", "seconds": elapsed}))
else:
    assert not args.expect_down, "Dependency unexpectedly reachable"
    calls = parse_tool_calls(response.content)
    assert len(calls) == 1
    assert calls[0].name == "validate_location"
    assert calls[0].arguments == {"address": "Denver, CO"}
    assert response.usage.promptTokens == 4
    print(
        json.dumps(
            {
                "status": "pass",
                "tool": calls[0].name,
                "seconds": time.monotonic() - start,
            }
        )
    )
