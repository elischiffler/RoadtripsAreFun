# Container migration evidence

Pre-PR snapshot, 2026-09-24. Existing PR20/branch `feat/self-hosted-postgres` is
reused; baseline `af1cb97ef907d4588c655838a245e11ce2afc57d` includes the existing
TLS change. Final committed image IDs and current CI belong in the PR handoff
and consolidated run report. This snapshot is not a full acceptance pass.

Host Node24.16, Docker29.5.3/Compose5.1.4; images use Node24.21/Python3.12.14/nginx
by digest. Deadlines and exact commands are in [runbook](container-runbook.md).
All data/provider checks below use fixtures/mocks; no actual Cognito, Neon,
Mapbox, routing proxy or inference service was invoked.

| Gate | Status                                | Procedure and observed result                                                                                                                                                                                                                                                                                                                  |
| ---- | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S1   | PASS locally; final identity pending  | npm ci/frontend production build and both Docker builds pass. requirements pins include formerly floating botocore/coverage. Image builds install committed dependencies.                                                                                                                                                                      |
| S2   | FAIL                                  | Frontend format passes; frontend coverage suite/build pass but existing ESLint errors/warnings remain. Backend247 pytest tests pass with76.91% coverage (required63) inside --network none. Ruff0.16.7 reports252 existing errors outside touched files and20 existing files needing formatting. Changed Python files pass scoped Ruff checks. |
| S3   | BLOCKED overall                       | Process/static health pass, both services stop in1.85s and start healthy in11.45s. Database readiness is503 as expected; actual DB recovery cannot run without reviewed schema.                                                                                                                                                                |
| S4   | PASS local runtime                    | Exec uid10001 API/101web; read-only paths; no runtime test source/pytest; explicit loopback binding, tmpfs, capability/PID/resource/log limits. Idle API64.67MiB/0.13%CPU/5PIDs; web4.80MiB/0%/3PIDs.                                                                                                                                          |
| S5   | BLOCKED full journey                  | Two real-container HTTP tests pass: health/readiness/CORS including denied origin; static deep route/cache/404/local browser URLs. Home/login render desktop1440x900/mobile390x844 and route reloads; console errors/warnings empty. No authenticated route/map journey.                                                                       |
| S6   | PASS diagnostic boundary              | Local-config negative tests reject hosted/missing destinations and provider config. Business routes return503 before reaching hardcoded external providers. Actual backend suite runs with networking disabled. Image excludes dotenv; no production secrets.                                                                                  |
| S7   | BLOCKED                               | Current PR CI pending; new jobs intentionally expose baseline lint/format failures. All PR/main changes trigger validation without production secrets. Remote branch protection is not claimed.                                                                                                                                                |
| S8   | PASS partial preview                  | Start/stop/recovery commands reproduce diagnostic preview. No guessed database/volume is created. Complete persistence/backup operations await authoritative schema.                                                                                                                                                                           |
| R1   | BLOCKED                               | Unit route/agent fixtures pass, but real API/browser itinerary/map/chat journey needs authoritative disposable DB and controlled providers.                                                                                                                                                                                                    |
| R2   | BLOCKED                               | README/chat-agent DDL is incomplete evidence, not a reviewed schema. No database recreation/persistence exercise is claimed.                                                                                                                                                                                                                   |
| R3   | BLOCKED                               | Actual Mentro provider contract integration is pending in the run report; full application recovery still needs the database.                                                                                                                                                                                                                  |
| R4   | FAIL baseline; actual Cognito BLOCKED | Existing get_user_id_from_token decodes with verify_signature=False and accepts arbitrary token strings. In the real image, a disposable HS256 token signed with an untrusted key returned fixture-second-user. No production token/data used. Actual isolated Cognito users are unavailable.                                                  |
| R5   | BLOCKED                               | Backup/restore/API verification requires reviewed schema and disposable data. Reuse hosting-ops scripts when available; no production export/restore performed.                                                                                                                                                                                |
| R6   | BLOCKED full DB path                  | TLS/config/reconnect unit regressions pass. Default hosted TLS requirement preserved, local disable explicit. Actual database loss/recovery and TLS destination checks await DB.                                                                                                                                                               |
| R7   | PASS suites; external BLOCKED         | Backend247pass/76.91%; frontend coverage/buildpass. Real map/provider integration unavailable; lint/format failures separately keep S2 open.                                                                                                                                                                                                   |

## Required follow-up scope

Keep this PR draft. Obtain a reviewed complete schema and isolated Cognito/provider
resources, then complete persistence/recovery/journeys. Separately repair backend
JWT verification (trusted issuer/JWKS, audience/token-use/expiry, reject invalid
tokens) and add negative/two-user authorization regression tests. This is an
existing security boundary defect; containers and CORS cannot correct it.

A separate quality cleanup should address existing Ruff/ESLint findings without
lowering thresholds. CORS is now explicit, retaining the known hosted frontend;
additional approved origins require CORS_ORIGINS. No hosting settings changed.
The combined15-minute workload remains blocked pending usable local journeys;
these idle/smoke measurements do not establish production capacity.

## Real Mentro provider contract follow-up

The checked-in `tests/mentro_container_probe.py` ran inside the actual Roadtrips
runtime image on Mentro's isolated pilot network. It consumed streamed content
and parsed the expected `validate_location` text-tool with `Denver, CO` arguments
and expected usage. Initial response 0.19 seconds. Stopping Mentro produced the
expected bounded ProviderError in 0.037 seconds; restarting restored the same
probe in 0.239 seconds, within the 60-second recovery deadline. Other preview
health endpoints remained responsive. This closes the provider-contract portion
of R3; full trip/database-dependent recovery remains BLOCKED, and this is not the
combined C3 workload. Live upstream inference was replaced only by Mentro's
controlled fixture; no real provider call or database mutation occurred.
