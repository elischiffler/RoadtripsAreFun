# Algorithm Lab validation

October 4, 2026 (America/Los_Angeles), on `codex/senior-demo-plan`, based on
shared feature `53fd0bf`. These results cover the owner `/algorithm` screen,
profile crossmatching, solver refactor and direct-run API. They do not establish
public deployment or real-provider acceptance.

| Check | Result | Evidence |
| --- | --- | --- |
| Backend Ruff formatting and lint | PASS | Python 3.12.10, Ruff 0.16.7; unchanged repository checks |
| Backend full suite and coverage | PASS | Final Linux Python 3.12.14 container: 652 tests, 86.28%; required floor remains 63% |
| Frontend install, formatting and lint | PASS | Node 24.16.0, npm 11.13.0; committed lockfile unchanged |
| Frontend full suite and coverage | PASS | 25 files, 207 tests; lines/statements 86.93%, branches 85.42%, functions 75.50% |
| Frontend production build | PASS | Local and Docker build; existing large-bundle warning remains |
| Final Docker build and container smoke | PASS | `docker compose -p roadtrips-senior-demo up --build --detach --wait --wait-timeout 60`; `node --test tests/container-smoke.test.mjs`: 2 tests |
| Disposable PostgreSQL integration | PASS | `node tests/postgres/run.mjs`: CRUD, owner isolation, API recreation, database loss/readiness, backup, restore and refusal to overwrite populated storage |
| Documentation diagrams | PASS | `npm run validate` from `docs/diagrams`: 11 Mermaid diagrams |
| Browser: owner replay | PASS, fixture | Normal login UI against isolated locally signed test tokens; real scoring and CP-SAT with frozen synthetic candidates |
| Browser: non-owner denial | PASS, fixture | Owner-access-required screen; backend auth/claim cases also covered by tests |
| Browser: presentation layout | PASS, fixture | `/algorithm`, global header absent; help click/Escape, score disclosures, results focus and comparison |
| Real Cognito sessions and live providers | BLOCKED | No real owner/non-owner provider-backed rehearsal completed |
| Public release parity | BLOCKED | Public API still advertised greedy/ortools with greedy default during read-only check |
| Production schema, recovery and deployment | NOT APPLICABLE to local acceptance | No schema or deployment changes made; release needs independently verified recovery/runtime evidence |

## Reproducible browser experiment

The browser used the actual frontend and Lab router on loopback, with an
isolated test authentication endpoint and ephemeral signing key. This does not
test the deployed Cognito configuration. No production auth bypass was added.
Live mode was deliberately unavailable in that fixture.

For `teaching-v1`, the nature preset selected scenic museum and local gardens
with objective 3,380,003. The culture preset selected historic market and scenic
museum with objective 4,290,005. Both reported `OPTIMAL`. The historic-market
culture match was .63 + .16 + .02 = .81. `empty-v1` reported `NOT_RUN` and zero
selected candidates. Replay returned no fabricated road map or hotel itinerary.

Automated coverage includes owner token/subject checks, invalid inputs,
request-local diagnostics, no replay provider/database calls, real CP-SAT
selection, final rerouting failures, partial itinerary failure, stale requests,
malformed diagnostic rendering, and map remounting between runs.

## Local environment notes

Docker Desktop was initially stopped. After starting it, a concurrent preview
and PostgreSQL run exhausted the existing Docker network pool. Removing only
the task's preview containers/networks allowed a clean PostgreSQL rerun; no
unrelated projects or volumes were pruned. The successful disposable project
was `roadtrips-crud-ce9c35338b`; its source/restore volumes and ignored 7,235-byte
dump were retained. These contain fixture data, not production data.

The frontend lockfile install reports 40 audit findings. No dependency upgrade
or threshold reduction is included here. The build's roughly 2.10 MB JavaScript
bundle (613 KB gzip) is a concrete follow-up for a separate route-lazy-loading
PR, with navigation/build checks; it is not expanded into this presentation task.

See the [public/MacBook runbook](senior-demo-runbook.md) for the release and
rehearsal gates, and the [walkthrough](cp-sat-explained.md) for what the measured
solver status actually proves. Final remote checks belong to the PR's final
head, not the historical baseline listed above.

## Pie editor follow-up

The `/algorithm` trip-interest form now uses a drag-and-drop percentage pie.
After integrating the shared session-refresh work through `f9f1c31`, the final
frontend checks pass: locked install, formatting, lint, production build and
267 tests across 30 files (88.68% lines/statements, 86.30% branches, 80.93%
functions). The clean install required stopping this task's Vite process to
release its Windows esbuild file lock; the local preview was restarted.
The existing bundle-size warning remains. No backend or database code changed.

Eight interaction tests cover drop/cancellation, capped allocations, preserving
other topics, edge dragging, the circular seam, keyboard edits/removal, decimal entry, touch
and disabled controls. Browser checks on the local authenticated fixture verify
actual pointer edge resizing, dragging scenery onto the circle, the 100% cap,
full-circle guidance and a successful CP-SAT replay with edited weights.
This remains fixture evidence, not a live-provider/public release claim.

The chart exposes unallocated space. Positive allocations below 100% are still
normalized by the existing backend; an empty mix disables Run. Numeric controls
and keyboard-accessible handles provide alternatives to dragging. The final
PR head's CI covers integration; earlier backend/database results above retain
their original scope.
