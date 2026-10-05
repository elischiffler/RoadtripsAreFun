# Release consolidation — October 5, 2026

The single release branch is `codex/production-release`, targeting `main`.
It combines the integrated feature/UI tip `b0662ad` with final live preset fix
`85b207c`. Every pre-cleanup local and remote branch tip is an ancestor of the
release branch. The source-code integration was checked at `1bb0da8`.

The original record-trip branch (`a6acdeb`) and complete-trip branch (`495c61a`)
are historical variants superseded by `c919494` and `1e2fb29` plus later validated
changes. Their histories are preserved with ancestry-only merges, retaining the
current extraction, location confirmation, occupancy and dated persistence behavior.
All other old branch tips were already contained in the integrated feature tip.

## Included behavior

- Sole CP-SAT planner, provider-verified candidates, profile score explanations,
  local scheduling, explicit room occupancy and dated hotel offers.
- Validated chat trip collection, confirmed endpoints, optional car choice,
  bounded questions, progress feedback and saved route/itinerary recovery.
- Session renewal, authenticated owner-only Algorithm Lab, nine live presets,
  persistent evaluation history, saved map/itinerary popup and numbered map pins.
- Docker/Windows development workflows, PostgreSQL recovery checks, operations
  runbooks and existing CI coverage thresholds.

## Verification and release boundaries

Combined checks passed at integration source `1bb0da8`:

- Node 24.12.0: npm ci, formatting, lint, 288 tests with 89.95% line coverage,
  and the production build. Existing large-bundle warning remains.
- Python 3.12.14: pinned requirements/Ruff install, formatting/lint and 677
  tests with 86.83% coverage (63% minimum retained). Test-process CORS settings
  included the documented localhost/127.0.0.1 development origins.
- Rebuilt guarded Docker preview: both container smoke tests passed.
- Isolated backend test image: 677 tests passed with 86.83% coverage, without
  network access or production credentials. Five development-launcher checks passed.
- Disposable PostgreSQL: CRUD, ownership, saved results, connection recovery,
  restart/recreation, backup/restore and populated-target refusal passed.
  Recovery volumes `roadtrips-crud-05f104ccd8_source-data` and
  `roadtrips-crud-05f104ccd8_restore-data` and backups remain preserved.

The nine live preset runs and their actual fulfillment
and hotel costs are recorded in [live validation](algorithm-live-preset-validation.md).
Those live runs predate this consolidation; their code changes are preserved.

This cleanup does not merge `main`, deploy the application, change hosted credentials,
weaken TLS or change branch protection. Public runtime parity, intended production
migration target/schema compatibility, live owner/non-owner Cognito acceptance and
release/rollback operations remain separate gates in the existing
[senior demo runbook](senior-demo-runbook.md) and
[container runbook](container-runbook.md). The additive Algorithm Lab table and
saved-result column migrations must exist on the approved deployment target.
A passing disposable database test does not establish the production schema.

The GitHub main branch-protection API reported "Branch not protected" during
this audit; the `Main Restrictions` ruleset exists with enforcement disabled.
Repository settings were not changed by cleanup; CI workflow
configuration alone must not be described as enforced merge protection.

## Cleanup audit

A verified pre-cleanup Git bundle and exact ref/PR inventory are saved outside the
checkout at `/Users/elischiffler/.codex/backups/roadtrips-2026-10-05/`.
The backup preserves all original commits and branch identities. Obsolete remote
branches are deleted only after ancestry verification and publication of the
single release PR. Closed/merged PRs remain available as GitHub history.
Local worktrees remain on their original commits with detached HEADs; files and
recovery volumes are retained. `main` remains the default branch.

| Original remote branch | Preserved tip |
| --- | --- |
| `codex/agent-token-reduction` | `5ecb9f9a59fcb7f181b48ceec5ad5b67f0419c4b` |
| `codex/algorithm-live-only` | `d021ff0485cc676372116e1e9a18fa52dc416df1` |
| `codex/ambiguous-location-confirmation` | `620df3cb366acee01b38f8b15b8388f1a4a48144` |
| `codex/canonical-trip-confirmations` | `9d2d0061f8fcd0179ef409416fb7f0246445f339` |
| `codex/chat-confirm-spacing` | `85f9590d111efb758b0d5c3ed8d395c934eddf15` |
| `codex/chat-creation-arrival-timing` | `7993ac94e0c3ce8ef5a6a526d12fd523cfb5a5bd` |
| `codex/chat-minimal-style` | `c90cd789a85fd9716bb6576fc9da81c4f6262862` |
| `codex/chat-question-lines` | `869979782cf33b252a7b52b3b5a3d6e97d12d7c0` |
| `codex/complete-trip` | `495c61aeb8d69840efafead41d98f2002456987d` |
| `codex/conditional-room-questions` | `5f49704d052cac813ff93487b92b63b36bda9b8f` |
| `codex/confirm-locations-together` | `6a815c79cd2c576227e8106e1183c98ca31f1766` |
| `codex/cp-sat-selection-schedule` | `bfeb3686a81cdc9fa38a47720da94a0f12b9aa6c` |
| `codex/cp-sat-solver` | `b0662ad6644371d4ca6a6886290b477764c51a76` |
| `codex/dated-route-serialization` | `fab38ea0179b497657bbabf849b7aedae46c1505` |
| `codex/flexible-hotel-evenings` | `079dc4186171f19762eaa6e0853302538575bb32` |
| `codex/google-hotel-prices` | `648ff419c8492dfa7680965cef2f9425ce9849ef` |
| `codex/hotel-evenings-integration` | `a64074377d0a47192f7286a5259a77314974fde7` |
| `codex/hotel-verification-fix` | `ec9ecb02988d2ed2cfc7549b8625d620a06b08e9` |
| `codex/inline-location-confirmation` | `2eae35351fae9b049b7526e41361a0b60595c1dd` |
| `codex/lab-live-presets-results` | `85b207ca4eaa8448fd46aa2ac1be140d34e8b2da` |
| `codex/lab-trip-evaluation` | `c1164d24a24a09fa3ad295a39aa9dd0d1376832b` |
| `codex/location-proposals` | `da1b56e127437cb074c4410b442d87dc02689ffd` |
| `codex/persona-ai-candidates` | `3ec2eaf4aefb54ef72d604d1b8a49dc29674d7fe` |
| `codex/record-trip-details` | `a6acdeb5245adc327d23f1e10a2e393b5b7306e3` |
| `codex/refresh-roadtrips-context` | `cd03486dc39cfee8012cce5745ed5d7107430e8a` |
| `codex/senior-demo-plan` | `ca04cea2d2fdf7656e84205a1825ca0dd1513a77` |
| `codex/session-refresh` | `f9f1c31d83311c2bc9921788b23ffdaad9859d0b` |
| `codex/transparent-chat-icons` | `53fd0bf9d03f31103b909818ee646fb19ce5b825` |
| `codex/trip-detail-lists` | `6247a1ebddf55ad7693475b179f9f3bd71474188` |
| `codex/trip-travelers` | `200a326a72ff949d01e9b67a8895382305aa01cd` |
| `codex/trip-validation-recovery` | `74c55d93e11579455f859c5233bd3bc74026a4f1` |
| `codex/windows-make-run` | `e6d5033e1fc10cacd430ad74a531c240451704d6` |
| `main` | `92ac3af4155afc99704dc6072e6f25e57a4dc488` |
