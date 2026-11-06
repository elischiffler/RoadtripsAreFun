# Documentation

Start with the [current repository context](../.steering/overview.md) and
[active change map](../.steering/current-work.md). The algorithm analysis and
refactor documents retain historical designs; their old defaults are not the
current interactive routing policy. Current contracts live in
[hotel prices](hotel-prices.md), [owner settings](owner-routing-settings.md) and
[chat retirement and compatibility](journeygenie-removal.md).

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

> Diagrams are written in [Mermaid](https://mermaid.js.org/) and render natively
> on GitHub. No build step is needed to view them.

Independent catalog expansion: [103 reviewed additional arrivals and import handoff](catalog-expansion-103.md) (October 15, 2026; no activation or deployment).

Next catalog increment: [12 reviewed nature arrivals, exclusions and source handoff](catalog-expansion-nature-12.md) (115 proposed additions; hypothetical total 197).
