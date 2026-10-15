# Route evaluation v1

`scenarios.json` is the deterministic 30-cell controlled input matrix. It is not
an attraction catalog or a result dataset. See `docs/route-evaluation.md` from
repository root for the fixture contracts, capture gates and CLI.

Corridor evidence folders have not been populated: `short-1d`, `medium-2d`,
`long-3d`, `coast-5d`. Tight budget shares `medium-2d`. Real selection-100 runs
require 100 distinct usable imported places per corridor and captured evidence.
Missing folders produce explicit blocked result rows.

Synthetic unit graphs are generated only by `evaluation_tests.py` into temporary
test directories. They never populate primary real-data fixtures or reports.
