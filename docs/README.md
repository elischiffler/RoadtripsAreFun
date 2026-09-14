# Documentation

Technical documentation for MyRoadtrip.

| Doc | Description |
|---|---|
| [Route-Finding Algorithm](./route-finding.md) | How the backend turns a start/end pair into a multi-day trip with attractions and hotels. Two-phase design, the `_add_stops` scheduler, TripAdvisor attraction discovery, Google Hotels scraping, and data models — with Mermaid diagrams. |
| [Algorithm Analysis](./algorithm-analysis.md) | Analytical companion: problem formalization (orienteering / TSP-with-profits), the objective function, why the current algorithm is a greedy single-pass heuristic, and three candidate designs (classical optimization, pure AI, hybrid) with logic-flow diagrams and a comparison table. |
| [Chat Agent Design](./chat-agent-design.md) | Design spec for the conversational chat agent: the request/response, memory (facts + conversation), tool-calling, and multi-provider LLM fallback (Groq → Cerebras → Claude) contracts, plus the agent loop and the parallelization plan. |

> Diagrams are written in [Mermaid](https://mermaid.js.org/) and render natively
> on GitHub. No build step is needed to view them.
