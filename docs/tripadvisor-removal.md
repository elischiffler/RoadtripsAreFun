# Tripadvisor integration removal audit

October 15, 2026. The cleanup is based on deployed main
`6fa4077e6bad36399247ef2891be720abe7f5237` (PR #40). It does not change the
active catalog generation, saved trips, authentication or deployment settings.

## Executable discovery

All three discovery entry points already read `app.catalog.repository.nearby`:

| Entry point | Catalog behavior |
| --- | --- |
| `LivePlaceProvider.attractions_near` | Bounded daytime records; database failure becomes a safe catalog error. |
| `LiveEveningProvider.nearby` | Bounded records in supported evening categories; opening hours remain unknown. |
| `attractions.find_stop` | Legacy planner contract backed by catalog records; empty coverage returns 404, database failure 503. |

There is no executable Tripadvisor HTTP client, details lookup, pacer, import,
discovery fallback or provider credential loader in the application. The legacy
planner adapter's compatibility `rank` is deterministic catalog order, not a
popularity claim. Routing and evening driving checks still use Mapbox; hotel
prices, geocoding and AI ratings remain independent dependencies.

## Removed leftovers

- The editor's `.kiro/settings/mcp.json` connection to Tripadvisor's documentation
  MCP server. It was the only configured server in that file.
- The unused Tripadvisor credential attribute name in provider error redaction.
  Routing configuration already stopped loading that credential in PR #40;
  generic credential/URL redaction and active provider secret redaction remain.
- The retired provider counter from newly compiled run metrics. Catalog lookups
  still use the existing `external_calls.catalog` compatibility field, which
  counts database lookups rather than external discovery API calls.
- Provider-specific identities in current discovery test fixtures, obsolete
  active pacing instructions and outdated evening-provider descriptions.

There is no Tripadvisor-specific Python or JavaScript dependency to remove.
Shared HTTP libraries remain necessary for routing, hotels, authentication and
other active providers. Tracked environment examples, Compose files and CI
workflows contain no Tripadvisor credential configuration.

## Deliberately retained references

`RunHistory.jsx` renders a saved `external_calls.tripadvisor` value only when an
older record contains it. Its label explicitly identifies the historical Terra
API measurement; it does not reinterpret it as a catalog query count. Historical
saved place IDs, links and provenance remain readable without network refresh.
The frontend's old-source regression ensures historical stops do not acquire
invented catalog attribution.

Dated validation records, historical architecture/research diagrams, migration
rights assessments and the attribution page retain accurate descriptions of
their original sources. Negative transport regressions also name the retired
provider so accidental reintroduction is detected. These references are not
active integrations. Current discovery guidance points to the catalog instead.

## Verification scope

The discovery regression blocks both HTTP libraries and exercises populated,
empty and failed catalog responses across all three adapters. New metrics omit
the retired provider; frontend regressions cover both new catalog measurements
and preserved historical measurements. Required repository checks are recorded
in the cleanup PR. These are local/CI source checks, not a deployed traffic
trace or proof of a new production release.

Local validation: Ruff format/lint passed; backend **960 passed, 88.06% coverage**
with the unchanged 63% floor, including the explicitly configured disposable
PostgreSQL catalog tests. Frontend format/lint/build passed; **315 tests passed,
90.23% line coverage** with unchanged thresholds. The focused backend audit suite
passed all 104 cases.

No production data is deleted and no external credentials are inspected,
revoked or removed by this cleanup. A separate review and coordinated deployment
are required to publish it.
