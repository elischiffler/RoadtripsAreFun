# Documentation

Start with the [current repository context](../.steering/overview.md) and
[active change map](../.steering/current-work.md). The algorithm analysis and
refactor documents retain historical designs; their old defaults are not the
current interactive routing policy. Current contracts also live in
[trip detail lists](agent-trip-detail-lists.md),
[location confirmations](agent-location-confirmations.md),
[process status](agent-progress.md), [hotel prices](hotel-prices.md) and
[owner settings](owner-routing-settings.md).

Technical documentation for MyRoadtrip.

For current product direction, start with [Product vision](product-vision.md),
[Algorithm Lab implementation contract](senior-demo-plan.md), and
[CP-SAT code walkthrough](cp-sat-explained.md). The Lab is implemented on the senior-demo task branch. The walkthrough describes
feature `53fd0bf` plus this refactor; public acceptance remains pending. See the
[public/MacBook runbook](senior-demo-runbook.md) and
[validation evidence](senior-demo-validation.md).

| Doc | Description |
|---|---|
| [Route-Finding Algorithm](./route-finding.md) | Current CP-SAT notes plus historical greedy scheduling/discovery and model diagrams. |
| [Algorithm Analysis](./algorithm-analysis.md) | Historical objective and greedy analysis with candidate designs; current selection is owned by the CP-SAT planner. |
| [Chat Agent Design](./chat-agent-design.md) | Agent design rationale and earlier contract examples; consult the current architecture map and source schemas for extraction, memory, completion and frontend behavior. |

> Diagrams are written in [Mermaid](https://mermaid.js.org/) and render natively
> on GitHub. No build step is needed to view them.
