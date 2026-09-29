# Agent prompt size and trip completion

Run the fixed offline comparison from `backend/`:

```sh
python -m tests.agent.token_benchmark
```

The script compares the prompt at baseline commit `ff370b5` with the current
prompt. It replays the same ten saved messages, bounded conversation summary,
validated trip profile, and scripted provider responses for four scenarios.
It counts every provider request in a turn. The prompt-token column is a
**lexical token proxy** (words and punctuation across all requests), since the
script does not call Mentro or its tokenizer. It is useful for a repeatable
relative comparison, not a provider billing estimate.

| Scenario | Before prompt proxy | After prompt proxy | Model calls before → after | Scripted trip completion before → after |
| --- | ---: | ---: | ---: | --- |
| Collecting details | 2,008 | 465 | 1 → 1 | Not yet applicable |
| Correcting stops | 4,255 | 1,061 | 2 → 2 | Not yet applicable |
| Completing a trip | 8,785 | 2,401 | 4 → 4 | Pass → pass |
| Revising a trip | 8,804 | 2,456 | 4 → 4 | Pass → pass |
| **Total** | **23,852** | **6,383** | **11 → 11** | **2/2 → 2/2** |

The proxy fell by 73.2%. The scripted completion cases verify that the
route and itinerary actions still reach the frontend while the model receives
only handles and short tool results. They do not establish that a real model
will choose the right tools, nor do they exercise real providers. A live
before/after comparison requires the same fixed conversations against an
authorized provider environment and should record actual `usage.promptTokens`,
`modelCalls`, and successful itinerary delivery. The response now sums
available provider usage across all calls in each turn; `modelCalls` counts
agent-level provider requests. Gateway-internal retries and failed fallback
providers may make upstream request counts higher when no usage is returned.

The production prompt keeps six recent messages (up to 400 characters each)
and includes at most 600 characters of rolling summary once the recent window
is full. Trip data comes from the validated profile; UI hints select the
revision stage only when the profile is complete.
